# AMOU Messenger Bot 🤖

Bot tự động trả lời tin nhắn Facebook Page của AMOU NAIL STUDIO —
không cần AI key vẫn chạy được (trả lời theo kịch bản từ khóa),
có AI key thì trả lời được cả câu hỏi tự do.

## Bot làm được gì

- Tự chào + hiện menu nút bấm khi khách nhắn tin
- Nhận diện ý định: **bảng giá, đặt lịch, giờ mở cửa, địa chỉ, dịch vụ, khuyến mãi**
- Tự nhận diện ngôn ngữ **Việt / Anh / Hàn** theo tin nhắn của khách
- Khách gõ "gặp nhân viên" → bot báo đã ghi nhận, bạn vào Page xử lý tay
- (Tùy chọn) Gắn AI để trả lời câu hỏi tự do dựa trên thông tin tiệm

## Chuẩn bị trước khi chạy

1. **Facebook Page** của tiệm (tài khoản phải là Admin của Page).
2. Tài khoản tại [developers.facebook.com](https://developers.facebook.com) (dùng nick Facebook cá nhân).

## Bước 1 — Deploy bot lên mạng (miễn phí, ~10 phút)

Dùng Render (gói free đủ chạy):

1. Đẩy thư mục `messenger-bot` này lên một repo GitHub riêng.
2. Vào [render.com](https://render.com) → New → Web Service → chọn repo.
3. Cài đặt:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
4. Thêm Environment Variables (sẽ điền token ở bước sau, cứ tạo key trước):
   - `MESSENGER_VERIFY_TOKEN` = tự đặt một chuỗi bí mật, ví dụ `amou-xyz-2026` (nhớ chuỗi này)
   - `MESSENGER_PAGE_TOKEN` = để trống, điền sau
5. Deploy → bạn được URL dạng `https://amou-bot.onrender.com`.
   Webhook của bạn là: `https://amou-bot.onrender.com/webhook`

> Lưu ý: gói free của Render sẽ "ngủ" khi không có ai nhắn ~15 phút,
> tin nhắn đầu tiên sau đó có thể chậm ~30 giây. Muốn luôn thức thì nâng gói trả phí (~7 USD/tháng)
> hoặc dùng Railway/VPS.

## Bước 2 — Tạo Facebook App & nối webhook (~15 phút)

1. Vào [developers.facebook.com/apps](https://developers.facebook.com/apps) → **Create App** → chọn loại **Business**.
2. Trong dashboard app → **Add Product** → thêm **Messenger**.
3. Mục **Messenger → Settings**:
   - **Webhooks** → Add Callback URL:
     - Callback URL: `https://amou-bot.onrender.com/webhook` (URL của bạn ở bước 1)
     - Verify Token: chuỗi bạn đặt ở `MESSENGER_VERIFY_TOKEN`
     - Nhấn **Verify and Save** (nếu báo lỗi, kiểm tra bot đã deploy xong và biến môi trường đúng)
   - **Webhooks** → Add Subscriptions → chọn Page của tiệm, tick 2 field:
     - `messages`
     - `messaging_postbacks`
4. Mục **Access Tokens** → Generate Token cho Page → **copy Page Access Token**,
   dán vào biến môi trường `MESSENGER_PAGE_TOKEN` trên Render → Redeploy.

## Bước 3 — Test

1. Mở Facebook Page → nhắn tin vào Page bằng một nick **khác** (nick admin vẫn được khi app ở chế độ dev).
2. Thử: `chào`, `giá`, `đặt lịch`, `giờ mở cửa`, `địa chỉ`, `price`, `예약`, `gặp nhân viên`.
3. Kiểm tra log trên Render nếu có lỗi.

## Bước 4 — Cho bot chạy public (App Review)

Khi app còn ở **Development Mode**, chỉ admin/tester của app mới nhắn được với bot.
Để mọi khách hàng đều dùng được:

1. App Dashboard → chuyển sang **Live Mode** cần duyệt quyền.
2. Vào **App Review → Permissions and Features** → xin quyền:
   - `pages_messaging`
3. Meta sẽ yêu cầu mô tả + video demo bot hoạt động. Chuẩn bị:
   - Video quay màn hình: nhắn tin vào Page, bot tự trả lời
   - Mô tả: "Chatbot tự động trả lời FAQ (giá, giờ mở cửa, đặt lịch) cho tiệm nail"
4. Thường duyệt trong 1–5 ngày.

## (Tùy chọn) Bật AI trả lời tự do

Khi khách hỏi câu không khớp từ khóa nào, bot sẽ nhờ AI trả lời dựa trên
thông tin trong `knowledge.json`. Có 2 cách — **điền 1 trong 2 là đủ**,
nếu điền cả 2 thì Claude được ưu tiên:

**Cách A — Claude (Anthropic)**
1. Tạo API key tại [console.anthropic.com](https://console.anthropic.com)
   (tài khoản mới thường được tặng credit dùng thử).
2. Thêm biến môi trường:
   - `ANTHROPIC_API_KEY` = key của bạn
   - `ANTHROPIC_MODEL` = `claude-haiku-4-5-20251001` (bản Haiku rẻ nhất,
     đủ dùng cho trả lời FAQ; kiểm tra tên model mới nhất trong console)

**Cách B — OpenAI hoặc API tương thích (OpenRouter, Groq...)**
1. Thêm biến môi trường:
   - `OPENAI_API_KEY` = key của bạn
   - `OPENAI_BASE_URL` = `https://api.openai.com/v1`
     (dùng Claude qua OpenRouter mà không đổi code: để base URL
     `https://openrouter.ai/api/v1` và `AI_MODEL` là `anthropic/claude-haiku-4-5`)
   - `AI_MODEL` = `gpt-4o-mini`

**Cách C — Miễn phí hoàn toàn, không cần key (Pollinations)**
1. Chỉ cần thêm 2 biến môi trường, không cần API key gì cả:
   - `OPENAI_BASE_URL` = `https://text.pollinations.ai/openai`
   - `AI_MODEL` = `openai`
2. Lưu ý: đây là dịch vụ miễn phí dùng chung nên thỉnh thoảng chậm
   hoặc bị giới hạn lượt gọi lúc cao điểm. Nếu AI không trả lời kịp,
   bot tự động gửi menu nút bấm cho khách chọn thay vì im lặng.
   (Có thể tăng `AI_TIMEOUT`, mặc định 25 giây.)

**Token tính thế nào?**
- Token do nhà cung cấp AI tính (Anthropic/OpenAI/...), trừ vào tài khoản
  gắn với API key — không liên quan đến Meta/Facebook.
- Mỗi tin nhắn AI tốn ~400–600 token (cả hỏi + đáp). Ví dụ Claude Haiku
  (~$1/1 triệu token input, $5/1 triệu output): **1.000 tin nhắn ≈ $1–3**.
- AI **chỉ chạy với câu hỏi lạ** — 90% câu hỏi thường gặp đã được template
  trả lời miễn phí, nên chi phí thực tế còn thấp hơn nhiều.

## Trí nhớ hội thoại

Bot nhớ ~6 lượt trao đổi gần nhất của từng khách (trong 24h) nên hiểu được
câu nối tiếp kiểu "vậy cái đó giá sao?", "đặt lịch đó luôn đi".
- Lưu trong RAM của server → deploy/restart lại là quên hết (chấp nhận được
  cho trí nhớ ngắn hạn).
- Chạy đúng với 1 worker của gunicorn (mặc định). Không tăng `--workers`
  nếu chưa có nơi lưu chung (Redis/DB).
- Chỉnh bằng `HISTORY_TURNS` và `HISTORY_TTL_HOURS`.

## Tùy chỉnh nội dung

Mọi chữ bot nói nằm trong **`knowledge.json`** — sửa file này, push lên GitHub,
Render tự deploy lại:

- `shop.address`, `shop.hours`: địa chỉ, giờ mở cửa (3 ngôn ngữ)
- `services`: thêm `"price": "250k"` vào từng dịch vụ để hiện giá
- `promo`: nội dung khuyến mãi hiện tại
- `replies`: toàn bộ câu trả lời mẫu

## Lưu ý chính sách của Meta

- Bot chỉ được nhắn **trong 24h** kể từ tin nhắn cuối của khách (cửa sổ 24h).
  Không dùng bot để spam quảng cáo — Page có thể bị hạn chế.
- Khi khách bấm "Gặp nhân viên", bot chỉ ghi log — bạn cần vào
  [business.facebook.com](https://business.facebook.com) → Hộp thư để trả lời tay.
  (Nâng cấp: có thể nối thêm thông báo Telegram/email khi có yêu cầu gặp nhân viên.)

## Chạy thử trên máy (không bắt buộc)

```bash
cd messenger-bot
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export MESSENGER_VERIFY_TOKEN=test123
python app.py
# Mở http://localhost:5000/health để kiểm tra
```
