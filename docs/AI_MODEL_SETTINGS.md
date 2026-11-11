# Chọn model AI trong Cài đặt

Mở **Cài đặt → AI dịch thuật (AGY)**, chọn **Model AI** và **Mức suy luận**, rồi
bấm **Lưu**. **Hủy** giữ nguyên lựa chọn cũ. Màn hình dịch chỉ có dòng trạng
thái AI; không có bộ chọn model/effort thứ hai.

Danh sách cố định được xác minh bằng `agy models` và `agy --help` của CLI
**1.5.5** đang cài. Đây là tên của catalog AGY, không phải khẳng định tên model
trực tiếp trong API của từng hãng.

| Hiển thị | Model ID truyền cho AGY | Effort |
| --- | --- | --- |
| Gemini 3.8 Flash | `gemini-3.8-flash-low` | `--effort low` |
| Gemini 3.8 Flash | `gemini-3.8-flash-medium` | `--effort medium` |
| Gemini 3.8 Flash | `gemini-3.8-flash-high` | `--effort high` |
| Claude Sonnet | `claude-sonnet-4-6` | Theo mặc định của model |
| Claude Opus | `claude-opus-4-6-thinking` | Theo mặc định của model |
| GPT-OSS | `gpt-oss-120b-medium` | Theo mặc định của model, ID là 120B Medium |

Gemini có effort ngay trong ID; ứng dụng truyền thêm cờ effort cùng giá trị,
không gửi hai mức khác nhau. CLI chỉ công bố tập effort chung, chưa công bố
ma trận hỗ trợ riêng từng model. Vì vậy Claude/GPT không có tùy chọn ép effort
chưa được xác minh: combobox hiển thị mặc định và bị vô hiệu hóa.

CLI init xác nhận model ID, không xác nhận chỉ số suy luận riêng. Bằng chứng
effort hiện có là argv thực tế và biến thể trong catalog; không có số liệu
token, tiết kiệm quota hay kiểm chứng mức suy luận nội bộ của nhà cung cấp.

## Cấu hình và công việc đang chạy

- Lựa chọn lưu bằng `agy_model` và `agy_effort` trong settings hiện có. Không
  đổi vị trí config/cache. Cài mới mặc định Gemini Flash Low.
- Config cũ có ID Gemini hợp lệ và thiếu trường effort được suy ra theo ID:
  Medium vẫn là Medium, High vẫn là High. Không âm thầm đổi sang Low.
- Config không hợp lệ hiện cảnh báo; phải chọn rõ một lựa chọn hợp lệ mới Lưu.
- Cả Batch và Whole Chapter truyền model rõ ràng trên từng invocation,
  không dựa vào model đã chọn trong CLI tương tác.
- Run mới chụp model/effort vào options/journal. Tiếp tục run dùng cấu hình đã
  lưu của run, kể cả Cài đặt đã thay đổi. Lựa chọn mới áp dụng cho run mới.
- **Bắt đầu dịch** luôn tạo journal mới theo Cài đặt hiện tại, kể cả khi đang
  có checkpoint còn dở và ô Bỏ qua ảnh đã xử lý vẫn bật. Cache hợp lệ vẫn dùng
  được. **Tiếp tục/Thử lại ảnh lỗi** mới gắn với checkpoint cũ. Model của lượt
  cũ không được ghi ngược vào lựa chọn đã Lưu trong Cài đặt.
- Không tự đổi model khi quota, xác thực, provider hoặc giao thức lỗi.
- Effort là trường provider, không đổi recipe OCR/render. Model ID đã phân
  biệt mọi effort tường minh đang hỗ trợ; không di chuyển hoặc xóa cache cũ.

## Kiểm thử và giới hạn

Evidence đợt này: `output/ai-model-settings-20261111T162337Z/`.
Driver nội bộ: `scripts/validate_ai_model_settings.py`; config và SQLite của
QA riêng dưới output, không sửa config người dùng. Tối đa bốn invocation dịch
thật trong đợt này; ledger ở `agy-budget.json`, chi phí thực tế **UNKNOWN**.

Gemini Low và Sonnet đã dịch một ảnh OCR thật và render thành công. GPT-OSS
nhận đúng model nhưng trả terminal SUCCESS hai lượt, response khác cấu trúc
JSON yêu cầu dù structured_output có một bản dịch. Guard hiện có từ chối
`INVALID_RESPONSE / AGENT_TURNS`; không sửa guard/validator nội dung chỉ để
biến lượt đó thành PASS. Bản tóm tắt đã khử nội dung nằm tại
`live-gpt/safe-protocol.json`; stdout gốc chỉ giải mã trong RAM, không lưu bản rõ.

Đây là giới hạn nghiệm thu thực tế của GPT-OSS với hợp đồng giao thức hiện tại,
không phải lỗi lưu lựa chọn model. Không retry tự động hoặc fallback Gemini.
[Báo cáo nghiệm thu](AI_MODEL_SETTINGS_REPORT.md): đã build và chạy EXE thật,
GUI DPI 100/125/150%, lưu/mở lại và Opus Whole Chapter PASS. Gemini Low/Sonnet
source Batch PASS. Đã dùng đủ 4/4 invocation; GPT-OSS vẫn FAIL, nên chưa đạt
toàn bộ model. Bộ test liên quan 211 PASS và smoke 40 PASS (trùng chín test).

Không thay OCR, mask, inpainting, renderer, validation nội dung dịch hoặc
Chrome Bridge. Không thay token/tài khoản/AGY profile toàn cục.

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT**
