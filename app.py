"""
AMOU Messenger Bot - webhook server for Facebook Messenger Platform.
- Verifies webhook, receives messages/postbacks
- Keyword intents (price, booking, hours, address, services, promo, human handoff)
- Optional AI fallback via any OpenAI-compatible API
- Replies in Vietnamese / English / Korean based on user message

Env vars:
  MESSENGER_VERIFY_TOKEN  token you invent, pasted into Meta webhook config
  MESSENGER_PAGE_TOKEN    Page Access Token from developers.facebook.com
  OPENAI_API_KEY          (optional) enables AI answers for free-form questions
  OPENAI_BASE_URL         (optional) default https://api.openai.com/v1
  AI_MODEL                (optional) default gpt-4o-mini
  PORT                    (optional) default 5000
"""

import json
import logging
import os
import re

import requests
from flask import Flask, jsonify, request

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("amou-bot")

VERIFY_TOKEN = os.environ.get("MESSENGER_VERIFY_TOKEN", "")
PAGE_TOKEN = os.environ.get("MESSENGER_PAGE_TOKEN", "")
AI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
AI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
AI_MODEL = os.environ.get("AI_MODEL", "gpt-4o-mini")
# Direct Anthropic (Claude) API - takes priority over OPENAI_API_KEY when set
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
# HTTP timeout (seconds) for AI calls - free providers can be slow, raise if needed
AI_TIMEOUT = int(os.environ.get("AI_TIMEOUT", "25"))
GRAPH = "https://graph.facebook.com/v21.0"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "knowledge.json"), encoding="utf-8") as f:
    KB = json.load(f)

app = Flask(__name__)

# ---------------------------------------------------------------- language ---
KO_RE = re.compile(r"[\uac00-\ud7a3]")
VI_DIACRITICS_RE = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
    re.IGNORECASE,
)
# common Vietnamese words typed without diacritics
VI_WORDS = {
    "chao", "xin", "ban", "minh", "gia", "bao", "nhieu", "dat", "lich",
    "gio", "mo", "cua", "dong", "dia", "chi", "dau", "dich", "vu", "lam",
    "mong", "kham", "khuyen", "mai", "uu", "dai", "giam", "nhan", "vien",
    "nguoi", "tu", "van", "giup", "gi", "khong", "duoc", "co", "muon",
    "hen", "hom", "nay", "mai", "tuan", "tiem", "nail", "dep",
}


def detect_lang(text: str) -> str:
    """vi | en | ko — default Vietnamese (shop's main audience)."""
    t = (text or "").strip()
    if KO_RE.search(t):
        return "ko"
    if VI_DIACRITICS_RE.search(t):
        return "vi"
    words = set(re.findall(r"[a-z]+", t.lower()))
    if words & VI_WORDS:
        return "vi"
    ascii_letters = re.findall(r"[a-zA-Z]", t)
    if ascii_letters and len(ascii_letters) / max(len(t), 1) > 0.6:
        return "en"
    return "vi"


def T(lang: str, key: str, **kw) -> str:
    tpl = KB["replies"].get(lang, {}).get(key) or KB["replies"]["vi"][key]
    kw.setdefault("shop", KB["shop"]["name"])
    return tpl.format(**kw)

# ---------------------------------------------------------------- intents ----
INTENTS = {
    "greeting": ["hello", "hi", "chào", "chao", "xin chào", "alo", "안녕", "여보세요", "hey"],
    "price": ["giá", "gia", "bao nhiêu", "nhiêu", "nhieu", "price", "prices", "cost",
            "how much", "giá cả", "가격", "얼마"],
    "booking": ["đặt lịch", "dat lich", "đặt", "book", "booking", "appointment", "reserve",
                "reservation", "예약"],
    "hours": ["giờ", "gio", "mở cửa", "đóng cửa", "hour", "hours", "open", "thời gian",
              "시간", "영업", "영업시간"],
    "address": ["địa chỉ", "dia chi", "ở đâu", "address", "location", "where", "주소", "위치"],
    "services": ["dịch vụ", "dich vu", "service", "services", "làm gì", "có gì", "menu",
                 "서비스", "메뉴"],
    "promo": ["khuyến mãi", "khuyen mai", "ưu đãi", "giảm giá", "promo", "discount", "offer", "할인", "이벤트"],
    "human": ["nhân viên", "nhan vien", "người thật", "người", "tư vấn", "gọi", "staff",
              "human", "real person", "직원", "상담", "사람"],
}


def _kw_pattern(kw: str):
    # match whole word/phrase, not inside another word
    # (so "hi" doesn't match inside "nhiêu")
    return re.compile(r"(?<!\w)" + re.escape(kw) + r"(?!\w)")


_INTENT_RES = {
    intent: [_kw_pattern(k) for k in kws]
    for intent, kws in INTENTS.items()
}


def match_intent(text: str):
    t = text.lower()
    for intent, patterns in _INTENT_RES.items():
        if any(p.search(t) for p in patterns):
            return intent
    return None

# ---------------------------------------------------------------- send api ---
MENU = [
    {"id": "MENU_PRICE", "vi": "💅 Bảng giá", "en": "💅 Price list", "ko": "💅 가격표"},
    {"id": "MENU_BOOKING", "vi": "📅 Đặt lịch", "en": "📅 Book now", "ko": "📅 예약하기"},
    {"id": "MENU_HOURS", "vi": "🕘 Giờ mở cửa", "en": "🕘 Opening hours", "ko": "🕘 영업시간"},
    {"id": "MENU_HUMAN", "vi": "👩 Gặp nhân viên", "en": "👩 Talk to staff", "ko": "👩 직원 연결"},
]


def quick_replies(lang: str):
    return [
        {"content_type": "text", "title": m[lang], "payload": m["id"]}
        for m in MENU
    ]


def api_post(path: str, payload: dict):
    if not PAGE_TOKEN:
        log.error("MESSENGER_PAGE_TOKEN is not set - cannot send message")
        return None
    try:
        r = requests.post(
            f"{GRAPH}{path}",
            params={"access_token": PAGE_TOKEN},
            json=payload,
            timeout=15,
        )
        if r.status_code != 200:
            log.error("Send API error %s: %s", r.status_code, r.text[:500])
        return r.json()
    except Exception as e:  # noqa: BLE001
        log.error("Send API exception: %s", e)
        return None


def send_typing(psid: str):
    api_post("/me/messages", {
        "recipient": {"id": psid},
        "sender_action": "typing_on",
    })


def send_text(psid: str, text: str, with_menu: bool = False, lang: str = "vi"):
    payload = {"recipient": {"id": psid}, "message": {"text": text[:1900]}}
    if with_menu:
        payload["message"]["quick_replies"] = quick_replies(lang)
    api_post("/me/messages", payload)

# ---------------------------------------------------------------- handlers ---
def service_list(lang: str) -> str:
    lines = []
    for s in KB["services"]:
        name = s["name"].get(lang) or s["name"]["vi"]
        price = s.get("price")
        lines.append(f"• {name}" + (f" — {price}" if price else ""))
    return "\n".join(lines)


def handle_intent(psid: str, intent: str, lang: str):
    shop = KB["shop"]
    if intent == "greeting":
        send_text(psid, T(lang, "welcome", shop=shop["name"]), with_menu=True, lang=lang)
    elif intent == "price":
        send_text(psid, T(lang, "price", services=service_list(lang),
                          booking=KB["booking_url"][lang]),
                  with_menu=True, lang=lang)
    elif intent == "booking":
        send_text(psid, T(lang, "booking", booking=KB["booking_url"][lang]),
                  with_menu=True, lang=lang)
    elif intent == "hours":
        send_text(psid, T(lang, "hours", hours=shop["hours"][lang]),
                  with_menu=True, lang=lang)
    elif intent == "address":
        send_text(psid, T(lang, "address", address=shop["address"][lang]),
                  with_menu=True, lang=lang)
    elif intent == "services":
        send_text(psid, T(lang, "services", services=service_list(lang)),
                  with_menu=True, lang=lang)
    elif intent == "promo":
        send_text(psid, T(lang, "promo", promo=KB["promo"][lang],
                          booking=KB["booking_url"][lang]),
                  with_menu=True, lang=lang)
    elif intent == "human":
        # Handoff: tell the customer staff were notified, log for the owner.
        log.warning("HUMAN HANDOFF requested by psid=%s (lang=%s)", psid, lang)
        send_text(psid, T(lang, "human"), with_menu=False)


def ai_provider() -> str:
    """Which AI backend answers free-form questions: 'anthropic' | 'openai' | 'off'."""
    if ANTHROPIC_API_KEY:
        return "anthropic"
    if AI_API_KEY:
        return "openai"
    return "off"


def build_system_prompt(lang: str) -> str:
    shop = KB["shop"]
    addr = shop["address"].get(lang) or shop["address"]["en"]
    hours = shop["hours"].get(lang) or shop["hours"]["en"]
    booking = KB["booking_url"].get(lang) or KB["booking_url"]["en"]
    return (
        f"You are the friendly receptionist of {shop['name']}, a Korean-style nail studio. "
        f"Address: {addr}. Hours: {hours}. "
        f"Services: {', '.join(s['name']['en'] for s in KB['services'])}. "
        f"Booking: {booking}. Current promo: {KB['promo']['en']}. "
        f"Answer in {'Vietnamese' if lang == 'vi' else 'English' if lang == 'en' else 'Korean'}. "
        "Keep replies short (under 80 words), warm, no emojis overload. "
        "If asked about prices not listed, say prices are confirmed in-store and share the booking link. "
        "If the customer wants a human, say staff will be notified shortly."
    )


def claude_reply(user_text: str, lang: str) -> str | None:
    """Free-form answer via Anthropic's Messages API."""
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={"model": ANTHROPIC_MODEL, "max_tokens": 300,
                  "system": build_system_prompt(lang),
                  "messages": [{"role": "user", "content": user_text}]},
            timeout=AI_TIMEOUT,
        )
        r.raise_for_status()
        blocks = r.json().get("content", [])
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        return text.strip() or None
    except Exception as e:  # noqa: BLE001
        log.error("Claude error: %s", e)
        return None


def openai_reply(user_text: str, lang: str) -> str | None:
    """Free-form answer via any OpenAI-compatible chat completions API."""
    try:
        r = requests.post(
            f"{AI_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {AI_API_KEY}"},
            json={"model": AI_MODEL, "temperature": 0.4, "max_tokens": 300,
                  "messages": [{"role": "system", "content": build_system_prompt(lang)},
                               {"role": "user", "content": user_text}]},
            timeout=AI_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:  # noqa: BLE001
        log.error("OpenAI-compatible AI error: %s", e)
        return None


def ai_reply(user_text: str, lang: str) -> str | None:
    """Free-form answer grounded in the shop knowledge base."""
    provider = ai_provider()
    if provider == "anthropic":
        return claude_reply(user_text, lang)
    if provider == "openai":
        return openai_reply(user_text, lang)
    return None


def handle_message(psid: str, text: str):
    lang = detect_lang(text)
    intent = match_intent(text)
    send_typing(psid)
    if intent:
        handle_intent(psid, intent, lang)
        return
    answer = ai_reply(text, lang)
    if answer:
        send_text(psid, answer, with_menu=True, lang=lang)
    else:
        send_text(psid, T(lang, "fallback"), with_menu=True, lang=lang)


def handle_postback(psid: str, payload: str, lang_hint: str = "vi"):
    mapping = {"MENU_PRICE": "price", "MENU_BOOKING": "booking",
               "MENU_HOURS": "hours", "MENU_HUMAN": "human"}
    intent = mapping.get(payload)
    if intent:
        handle_intent(psid, intent, lang_hint)

# ---------------------------------------------------------------- webhook ----
@app.get("/webhook")
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN and VERIFY_TOKEN:
        log.info("Webhook verified")
        return challenge, 200
    log.warning("Webhook verification failed")
    return "Forbidden", 403


@app.post("/webhook")
def incoming():
    data = request.get_json(force=True, silent=True) or {}
    if data.get("object") != "page":
        return "not a page event", 404
    for entry in data.get("entry", []):
        for ev in entry.get("messaging", []):
            psid = str(ev.get("sender", {}).get("id", ""))
            if not psid or ev.get("sender", {}).get("id") == ev.get("recipient", {}).get("id"):
                continue
            msg = ev.get("message", {})
            postback = ev.get("postback")
            if postback and postback.get("payload"):
                handle_postback(psid, postback["payload"])
            elif msg.get("text") and not msg.get("is_echo"):
                handle_message(psid, msg["text"])
    return "OK", 200


@app.get("/health")
def health():
    return jsonify(ok=True, page_token_set=bool(PAGE_TOKEN),
                   ai_provider=ai_provider())


if __name__ == "__main__":
    if not VERIFY_TOKEN:
        log.warning("MESSENGER_VERIFY_TOKEN not set - webhook verification will fail")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
