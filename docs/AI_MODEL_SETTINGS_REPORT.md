# Nghiệm thu lựa chọn model AI — 11/11/2026

PROJECT_ROOT thực tế: workspace chứa `main.py`, `ImageTranslatorVN.spec` và
`AGENTS.md`, tại `D:/WebLocal/IMAGE-TRANSLATOR-VN-main` trong phiên này. Code
dùng `core.paths.ROOT`, không chứa đường dẫn project của máy này.

**Kết luận: phần Settings/config/GUI/EXE PASS; CHƯA ĐẠT toàn bộ model vì
GPT-OSS không vượt qua hợp đồng giao thức đang giữ nguyên.** Không tuyên bố
GPT-OSS dịch được chỉ vì CLI có model hoặc terminal báo SUCCESS.

## Catalog và cách sử dụng

AGY CLI thực tế **1.5.5**. [Danh sách ID/effort và hướng dẫn](AI_MODEL_SETTINGS.md).
Model mặc định cài mới: **Gemini 3.8 Flash Low**. Medium/High hợp lệ trong
config cũ được bảo toàn; config không hợp lệ phải chọn rõ trước khi Lưu.

Vào **Cài đặt → AI dịch thuật (AGY)**, chọn model và effort rồi **Lưu**.
**Hủy** không ghi config. Gemini có Low/Medium/High; Claude/GPT hiển thị
“Theo mặc định của model”, không truyền effort chưa xác minh. Giao diện chính
chỉ hiển thị một dòng thông tin, không thêm combobox hoặc nút Cài đặt thứ hai.

Batch và Whole Chapter nhận đúng model/effort từ settings. Mỗi invocation
truyền model tường minh. Gemini truyền effort cùng mức trong ID. CLI init
xác nhận model; không cung cấp số đo effort nội bộ. Profile CLI tương tác
hiện lưu Medium, nhưng lượt Low thật vẫn init đúng Low. Không sửa profile đó.

Model/effort gắn với run trong options/journal. Resume pin cấu hình cũ, không
theo Settings mới hoặc xử lý lại trang hoàn tất. Trường effort là provider
field, không đổi recipe OCR/render; identity Gemini cũ được giữ tương thích.
Không fallback sang model khác khi provider/quota/giao thức lỗi.

## Kiểm thử tự động và GUI

| Kiểm tra | Kết quả | Evidence |
| --- | --- | --- |
| Regression AGY/parser/Batch/Whole/cache/resume/API/online trust | 211 PASS, 0 FAIL, 0 SKIP | `logs/ai-model-settings-regression.xml` |
| Model Settings + ToonCN Bridge/connection | 40 PASS, 0 FAIL, 0 SKIP | `logs/ai-model-settings-final-smoke-node.xml` |
| Source GUI DPI 100/125/150% | PASS | `source-gui-100/`, `source-gui-125/`, `source-gui-150/` |
| Source GUI cuối + lưu/mở lại process mới | PASS | `source-final-gui/`, `source-reopen/` |
| EXE GUI DPI 100/125/150% | PASS, exit 0 | `exe-gui-100/`, `exe-gui-125/`, `exe-gui-150/` |
| EXE đóng/mở lại và kiểm tra Settings | PASS, exit 0 | `exe-reopen/` |
| Full regression toàn repository | SKIP, ngoài phạm vi cần chạy | Không gọi các kiểm tra trên là full suite |

Hai bộ pytest có chín test trùng nhau, không cộng thành 251 test độc lập.
Chín test model bao gồm sáu biến thể Batch/Whole, Save/Cancel/persistence,
unknown/conflicting selection, diagnostic, resume Batch giữ ảnh hoàn tất và
Whole giữ model cũ trước recipe check. GUI driver kiểm tra cả argv Batch/Whole
cho sáu biến thể từ chính settings đã lưu, không gọi dịch trong GUI tests.

Lượt smoke đầu: 37 PASS/3 FAIL do `node` không nằm trong PATH của host Python.
Đã tìm thấy Node cài sẵn, thêm PATH chỉ cho process test rồi chạy lại toàn bộ
hai bộ: 40 PASS. Node `v26.13.0`, npm `11.20.0`. Không cài dependency hoặc sửa
Chrome Bridge. Giữ log thất bại đầu để đối chiếu, không đổi thành SKIP/PASS giả.

GUI được mở thật bằng PySide6 trên Windows. Save/Cancel được bấm qua QtTest,
popup được mở và chụp ảnh thật, kiểm palette tối/chữ sáng, kích thước nút và
model label. Đã xem trực quan ảnh Settings và popup EXE 150%; không cắt chữ.
Đây là DPI mô phỏng qua `QT_SCALE_FACTOR`, không phải ba màn hình vật lý khác nhau.

## AGY thật: 4/4 lượt CLI, không tự retry

Mỗi lượt dùng một ảnh fixture `你好`, OCR Paddle thật, output/SQLite riêng;
không gửi chương truyện người dùng. Có thể phát sinh chi phí/hạn mức;
số tiền, billable status và số request upstream bên trong CLI **UNKNOWN**.
GPT trả hai turns; ledger đếm invocation ứng dụng gọi CLI, không khẳng định
một invocation luôn tương ứng một lượt suy luận upstream.

| # | Mục đích / nhánh | Model ID | Effort gửi | Giây CLI | Kết quả |
| --- | --- | --- | --- | --- | --- |
| 1 | Source Batch | `gemini-3.8-flash-low` | low | 7,938 | PASS, 1/1 OCR/dịch/render |
| 2 | Source Batch | `claude-sonnet-4-6` | không ép | 8,453 | PASS, 1/1 OCR/dịch/render |
| 3 | Source Batch | `gpt-oss-120b-medium` | không ép | 48,609 | FAIL: INVALID_RESPONSE / AGENT_TURNS |
| 4 | EXE Whole Chapter | `claude-opus-4-6-thinking` | không ép | 9,062 | PASS, 1/1 OCR/dịch/render |

Cả bốn init đều xác nhận đúng model ID truyền. Không có quota error trong
bốn lượt này. Không có live test Medium/High riêng: argv và GUI đã kiểm tra,
không tuyên bố AGY live PASS cho hai effort đó. Không còn ngân sách gọi thêm.

GPT-OSS: exit 0, terminal SUCCESS, `num_turns=2`, có structured_output một
bản dịch, nhưng response không phải JSON object theo hợp đồng hiện có và CLI
đã có lượt user_input/agent_response bổ sung. Parser giữ nguyên giới hạn
single-turn nên từ chối. Không phải lỗi combobox, model ID hoặc effort không
được truyền. Không nới parser/validation hoặc đổi model để báo thành công.
Attempt thử nghiệm: `6b2909440c0b4e6c9ebff5624c35b588`. Chỉ giải mã cục bộ
trong RAM; tóm tắt không có nội dung thô ở `live-gpt/safe-protocol.json`.

## EXE và ảnh bằng chứng

Đã chạy **build.bat**, `pip check` và PyInstaller thành công:

`dist/ImageTranslatorVN-20261111T165120860976Z/ImageTranslatorVN-20261111T165120860976Z.exe`

Giữ nguyên cả thư mục **_internal** bên cạnh EXE. Model OCR vẫn ở
`models/ocr` của project theo cách đóng gói hiện có. Không thay hệ thống build.
Log: `logs/build-ImageTranslatorVN-20261111T165120860976Z.log`.
SHA-256 EXE: `c67bae04f9fd36cd3c15e78d829c132a91431af3eb579bec917ca54ddb9d04b3`.

EXE đã được khởi chạy nhiều process thật: MainWindow/Settings, Save/Cancel,
đóng/mở lại, DPI ba mức, popup tối, argv của provider đóng gói và Whole Chapter
AGY thật. Không chỉ dựa vào dòng PyInstaller build success.

Thư mục evidence gốc: `output/ai-model-settings-20261111T162337Z/`.

- Trước: `settings-before-top.png`, `settings-before-model.png`, chụp lại
  dialog từ source baseline đã lưu trước sửa, không giả là EXE cũ đang chạy.
- Sau: `exe-gui-150/settings.png`, `model-popup.png`, `effort-popup.png`,
  `main.png`; cùng bộ ở `exe-gui-100/` và `exe-gui-125/`.
- Mở lại: `exe-reopen/reopened-settings.png`, `reopened.png`.
- Gemini: `live-gemini/export/0001.vi-7469f0aa.png`.
- Sonnet: `live-sonnet/export/0001.vi-f2422f33.png`.
- Opus EXE: `output/stage3g-model-qa-ai-model-settings-20261111T162337Z-exe-live-opus-whole/rendered/0001.vi-bf06a8c5.png`.

Đã xem ba ảnh render: “Xin chào”, không còn glyph Trung trên fixture, không
chồng/cắt nội dung. Đây là fixture nhỏ xác minh model/pipeline, không phải
nghiệm thu lại chất lượng toàn bộ chương ảnh phức tạp.

## File thay đổi riêng nhiệm vụ

- Catalog/config: `providers/agy_models.py` (mới), `core/types.py`,
  `config/settings.example.json` (thêm lựa chọn mặc định, bỏ output máy cũ).
- Invocation/diagnostic: `providers/agy.py`, `providers/agy_diagnostics.py`,
  `core/agy_error_evidence.py`.
- Snapshot/resume: `core/pipeline.py`, `core/resume.py`, `core/whole_chapter.py`,
  `sources/resume.py`.
- GUI: `ui/settings_dialog.py`, `ui/main_window.py`, `ui/provider_notice.py`,
  `ui/whole_chapter.py`, `ui/comic_sources.py`.
- QA: `main.py` (entry QA nội bộ), `scripts/validate_ai_model_settings.py`
  (mới), `tests/test_ai_model_settings.py` (mới), `tests/test_agy.py`,
  `tests/fixtures/agy_models_1_5_5.txt` (mới, đã khử dữ liệu nhạy cảm).
- Tài liệu: `README.md`, `PROJECT_STATUS.md`, `docs/AI_MODEL_SETTINGS.md`,
  báo cáo này.

Không sửa `core/ocr.py`, `core/imaging.py`, `ui/theme.py`,
`sources/tooncn_bridge.py`, `providers/gemini_api.py`: hash so baseline giữ
nguyên. Phần content validation online/offline có sẵn giữ nguyên; thay đổi
pipeline chỉ liên quan snapshot model/effort, trạng thái và metadata.

Config người dùng nguyên SHA-256 so baseline. EXE cũ tại thời điểm baseline
nguyên hash. Không xóa/migrate SQLite, journal, output; toàn bộ QA dùng DB và
thư mục riêng. Scan bundle không thấy settings.json/state.sqlite3/DPAPI/
chapter-journal/errors.jsonl riêng tư. Không thay account/token/profile.

## Git & Fork Handoff

Branch `main`, HEAD `00213e305b280d99b52946b9e12159d21ee49982`.
Baseline 24 status entries (16 modified + 8 untracked), index/unmerged trống.
Giữ các thay đổi có sẵn; không nhận chúng là sửa mới của nhiệm vụ. Baseline
và diff theo hash nằm trong evidence; kết quả kiểm tra cuối ở `git-review.json`.
Không sửa `.gitignore`. Source/test/docs/config mẫu cần review; không commit
config riêng, logs, output ảnh, cache/DB, models hoặc dist/build/EXE.

Status cuối: **24 modified + 14 untracked** (gồm baseline cũ), index/unmerged
vẫn trống, HEAD không đổi. `git diff --check` PASS; chỉ có cảnh báo chuyển
CRLF/LF theo Git. Runtime mẫu cache/log/output/dist/venv được ignore đúng;
source/test/docs/spec/BAT/config mẫu không bị che. Không có runtime đã track,
file mới/sửa lớn hơn 2 MiB hoặc khớp các mẫu credential đã rà. Scan regex không
thay thế review thủ công. Message đề xuất nếu người dùng tự review/commit sau:
`feat(settings): select fixed AGY models and pin run effort`.

Hạn chế chặn nghiệm thu toàn bộ: GPT-OSS cần xử lý tương thích giao thức trong
phạm vi riêng và kiểm thử live mới; không thay guard ngoài yêu cầu hiện tại,
không gọi quá bốn lượt được cấp. Không có blocker đối với chọn/lưu model và
pipeline đã PASS của Gemini Low, Sonnet, Opus.

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT**
