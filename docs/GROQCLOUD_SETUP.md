# GroqCloud API trong Image Translator VN

Mở **Cài đặt → AI dịch thuật → Nguồn dịch: GroqCloud**. Chọn model, bấm
**Lưu**, rồi chọn **AI — Batch** hoặc **AI — Toàn chương** ở phương thức dịch.
Không thêm bộ chọn provider/model thứ hai trên màn hình chính.

| Tên hiển thị | Model ID |
| --- | --- |
| Qwen 3.8 27B (mặc định của Groq) | `qwen/qwen3.8-27b` |
| GPT-OSS 120B | `openai/gpt-oss-120b` |
| GPT-OSS 20B | `openai/gpt-oss-20b` |

Chỉ hỗ trợ ba ID này. Không tự đổi model khi thiếu quyền, quota hoặc model
không tồn tại. Không thêm effort cho Groq. Lựa chọn và effort AGY cũ được giữ
khi chuyển qua lại nguồn dịch. Cài đặt cũ thiếu trường mới tiếp tục dùng AGY.

## API key và kết nối

Đọc **GROQ_API_KEY** từ môi trường process; trên Windows, nếu process cũ chưa
nạp biến mới thì đọc đúng biến User `Environment/GROQ_API_KEY` bằng winreg.
Không đọc toàn bộ danh sách credential. Không sửa biến môi trường, không lưu
key trong options/config/DB/journal/log/EXE, không thêm trường nhập key.

Có thể đặt biến User bằng công cụ Environment Variables của Windows rồi mở
lại ứng dụng. Người dùng tự nhập giá trị, không dán key vào báo cáo/chat.
Trạng thái “đã có” chỉ là có key, chưa chứng minh API hoạt động.

**Kiểm tra kết nối** gửi một đoạn chào ngắn, chạy trên QThread, không treo GUI
và có thể tiêu thụ hạn mức. Hủy Settings không đổi config; nút kiểm tra chỉ
gửi khi được bấm, không chạy lúc mở ứng dụng hoặc Lưu. Khi đang kiểm tra,
chờ worker kết thúc trước khi Lưu/Hủy/đóng dialog. Nút này cũng tôn trọng
Retry-After trước khi cho gửi lần nữa.

Transport dùng `requests` đã có, không thêm SDK/dependency. Endpoint cố định
`https://api.groq.com/openai/v1/chat/completions`, HTTPS verify bật, không theo
redirect, Authorization chỉ trong header. Không gửi ảnh, tools hoặc nội dung
chương dư thừa: chỉ những OCR regions cần dịch. [API chính thức](https://console.groq.com/docs/openai).

Ba model dùng `response_format=json_schema`, `strict=true` theo
[Structured Outputs của Groq](https://console.groq.com/docs/structured-outputs).
Parser vẫn kiểm model, finish_reason, JSON duplicate keys, đủ/đúng ID, không
trùng ID, không có tool calls hoặc nội dung bị cắt. Giữ nguyên chính sách
validation nội dung online đang có; không sửa validator hoặc thuật toán ảnh.

## Batch, Whole Chapter và resume

Tận dụng TranslationService/MultiPage và vòng đời manifest/receipt Whole
Chapter hiện có. Mode nội bộ AI giữ mã cũ để tương thích journal; provider
thực tế nằm ở `ai_provider`, model ở `groq_model`, identity cache khác AGY và
khác từng model Groq. Field mới không đổi recipe OCR/render hoặc key cache
cũ khi vẫn dùng AGY/Offline/API cũ.

Batch Groq giới hạn 1.000 ký tự nguồn/16 vùng mỗi batch trong planner sẵn có.
Trần output token theo kích thước OCR: tối thiểu 512, tối đa 4.096; không
claim đây là số token thực tế hoặc bảo đảm không gặp quota.

Whole Chapter gửi một request cho toàn bộ vùng cần dịch sau xác nhận riêng.
Giới hạn cục bộ 2.000 vùng và 12.000 ký tự nguồn, không cắt hoặc chia ngầm.
Chương quá giới hạn phải chọn Batch hoặc nguồn nhỏ hơn. Hạn mức tài khoản
Groq có thể thấp hơn giới hạn cục bộ; nếu API từ chối thì dừng, không fallback.

Checkpoint gắn provider/model với run. Tiếp tục giữ lựa chọn cũ, không đọc
model mới từ Settings để dịch lại trang đã hoàn thành. Với Whole, lỗi HTTP
cần người dùng Tiếp tục và xác nhận lại trước request mới; không tự replay.

## Lỗi và dữ liệu

401: AUTH_REQUIRED; 403: ACCESS_DENIED; 400: INVALID_REQUEST hoặc
MODEL_UNAVAILABLE nếu có machine code model cụ thể; 404: MODEL_UNAVAILABLE;
429: RATE_LIMITED; 500/503: PROVIDER_UNAVAILABLE; timeout/network/JSON sai có
mã riêng. Không đưa raw error body/header/key vào GUI hoặc log.

429 giữ checkpoint, không tự retry. Retry-After (giây hoặc HTTP date) được
đọc và lưu mốc chờ theo run; resume trước mốc chờ dừng trước HTTP. Không suy
đoán hết quota ngày chỉ từ một HTTP 429. Timeout hoặc network failure không
xác minh được tính phí: UNKNOWN. Không có dashboard, provider switch hoặc
vòng retry mới.

Giữ nguyên OCR/mask/inpainting/renderer/layout, source ảnh và output đã xong.
AGY CLI, Gemini API và ToonCN không đổi thuật toán hoặc quyền đăng nhập.

Kết quả kiểm thử/build ở [báo cáo](GROQCLOUD_REPORT.md).

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT**
