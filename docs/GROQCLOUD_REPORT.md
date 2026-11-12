# GroqCloud: tích hợp cơ bản và nghiệm thu EXE — 12/11/2026

**ĐẠT phạm vi tích hợp cơ bản:** chọn nguồn/model trong Settings, kết nối
Groq thật, dịch một ảnh thật qua OCR/parser/render và chạy EXE mới. Không
benchmark hoặc so sánh model.

PROJECT_ROOT xác định từ workspace: `D:/WebLocal/IMAGE-TRANSLATOR-VN-main`
trong phiên này. Code dùng ROOT/module, không hardcode đường dẫn project.

## Cấu hình

Vào **Cài đặt → AI dịch thuật → GroqCloud**, chọn Qwen 3.8 27B (mặc định),
GPT-OSS 120B hoặc GPT-OSS 20B, **Lưu**. Mode dịch chính dùng **AI — Batch**
hoặc **AI — Toàn chương**. Chỉ có một nguồn/model selector trong Settings.

ID đúng ba lựa chọn: `qwen/qwen3.8-27b`, `openai/gpt-oss-120b`,
`openai/gpt-oss-20b`. Chỉ Qwen được gọi live; hai GPT-OSS kiểm bằng fixture,
không tuyên bố đã gọi thật cả ba. AGY model/effort cũ được bảo toàn khi chọn
Groq; không thêm effort cho Groq hoặc tự đổi model/provider khi lỗi.

Đọc GROQ_API_KEY từ process environment, fallback đúng biến User Windows
nếu process cũ chưa nạp lại môi trường. Máy này có biến User, không có trong
process ban đầu. Không thay biến, token/tài khoản/security; không lưu key vào
config, DB, log, test output hoặc EXE. Không thêm Credential Manager hoặc SDK.

Transport `requests` sẵn có, endpoint chính thức và structured JSON theo
[Groq OpenAI compatibility](https://console.groq.com/docs/openai) và
[Groq Structured Outputs](https://console.groq.com/docs/structured-outputs).
[Hướng dẫn và giới hạn](GROQCLOUD_SETUP.md).

## Test và request thật

Evidence: `output/groq-setup-20261111T224304Z/`.

| Kiểm tra | Kết quả |
| --- | --- |
| Regression AGY, Gemini API, Groq, Settings, Batch/Whole, cache/resume | 200 PASS / 0 FAIL / 0 SKIP |
| Bộ Groq cuối, thêm kiểm tra nút Start nhận cấu hình đã lưu | 14 PASS, có 13 case trùng regression |
| Hợp testcase cuối | **201 PASS / 0 FAIL / 0 SKIP**, không phải full repository suite |
| Source GUI Save/Cancel, ba model, popup tối | PASS |
| Source pipeline OCR thật + HTTP fixture | PASS, không phải Groq live |
| EXE GUI Save/Cancel, đóng/mở lại | PASS, exit 0 |
| EXE GUI DPI 100% / 150% | PASS, dùng QT_SCALE_FACTOR |
| EXE OCR → Groq live → parser → xóa chữ/render/export (bản build đầu) | **PASS, 1/1 ảnh** |
| EXE cuối sau sửa nhãn tiến trình: OCR thật + HTTP fixture | PASS, 1/1 ảnh, không gọi API thêm |
| Whole Chapter live | SKIP, giữ ngân sách ba request; đã test HTTP fixture |

Logs: `logs/groq-basic.xml`, `logs/groq-regression.xml`,
`logs/groq-final-unit.xml`, `logs/groq-final-gui-route.xml`.
Sau sửa nhãn Batch, bộ Groq/Gemini/Settings chạy lại **56 PASS**, không có
case mới ngoài hợp 201 testcase đã nêu (`logs/groq-progress-label.xml`).

Ledger `api-budget.json` ghi **3/3 request Groq thật**, **0 AGY thật**:

1. `source-connect`: Qwen, HTTP **429**, RATE_LIMITED. Không coi là kết nối
   thành công hoặc suy đoán quota ngày. Request ban đầu có trần output 8.192.
2. Sau test cục bộ và điều chỉnh trần output theo lượng OCR (512 cho câu thử),
   `source-connect-small`: Qwen, HTTP **200**, JSON hợp lệ, trả “Xin chào”.
3. `exe-live-image`: Qwen, HTTP **200**, PaddleOCR thật đọc “你好”, Groq thật
   trả “Xin chào”, render và export thành công, ảnh nguồn nguyên hash.

Không tự retry ở transport hoặc tự đổi model; lượt hai là phép kiểm chứng
riêng sau sửa giới hạn request, không phải replay vô hạn. Chưa đủ bằng chứng
để khẳng định duy nhất trần output gây 429 đầu tiên. Chi phí/billable status
của từng lượt **UNKNOWN**; không có dữ liệu billing để kết luận miễn phí.
Không gọi thêm sau khi đủ ba lượt.

Các test phủ 401/403/400/404/429/500/503, timeout/network, response JSON sai/
trùng/mất ID/tool call/finish bị cắt, Retry-After chặn HTTP khi resume sớm,
cache tách model, AGY không bị gọi khi dùng Groq, model/provider được pin khi
resume, giữ output hoàn tất và Whole dùng receipt dịch cũ không gọi lại.
Policy validation nội dung online hiện có được giữ nguyên; không làm đánh giá
ngữ nghĩa chuyên sâu hoặc tuyên bố chất lượng dịch toàn chương.

## EXE và ảnh kiểm tra

Đã chạy **build.bat**, pip check và PyInstaller thành công:

`dist/ImageTranslatorVN-20261111T230840399194Z/ImageTranslatorVN-20261111T230840399194Z.exe`

Giữ toàn bộ thư mục `_internal` cạnh EXE. Dùng models OCR hiện có dưới project,
không đóng gói truyện/cache/config riêng. Không thêm dependency.
Log: `logs/build-ImageTranslatorVN-20261111T230840399194Z.log`.
SHA-256 EXE: `f60dd5e3314888a46a86a375c6e901b26787b3d00cc6cdea3a8752906ba228fb`.

Đã mở EXE thật, vào Settings chọn Groq/Lưu, đóng/mở lại và xác nhận
provider/model còn đúng. GUI chỉ hiển thị trạng thái ngắn. Reports/screenshots
bản cuối: `final-exe-gui/`, `final-exe-reopen/`, `final-exe-gui-150/`.

Pipeline live từ EXE đã chạy trên bản `ImageTranslatorVN-20261111T225927612490Z`.
Sau đó phát hiện dòng tiến trình Batch vẫn ghi Gemini API do dùng chung planner;
đã sửa event/nhãn thành GroqCloud ở màn hình thư mục và nguồn ảnh, build lại.
Không có request live thứ tư: bản cuối kiểm OCR/render thật với HTTP fixture
(`final-exe-image-fixture/`). Bytecode đóng gói của `providers.groq_api`,
`core.pipeline`, `core.ocr`, `core.imaging` giống hệt bản đã chạy live, có
đối chiếu tại `packaged-code-comparison.json`. Không gọi fixture là API live
của bản build cuối; thay đổi cuối chỉ là nhãn tiến trình, đã test 56 case và EXE.

Ảnh live đã xem trực quan, chữ Việt đọc rõ và không chồng:

`output/groq-setup-20261111T224304Z/exe-live-image/export/neutral.vi-9a100ec0.png`

Đây là fixture trung tính nhỏ, không phải ảnh truyện cá nhân hoặc benchmark.

## File thay đổi

- Mới: `providers/groq_api.py`, `tests/test_groq_api.py`,
  `scripts/validate_groq.py`, `docs/GROQCLOUD_SETUP.md`, báo cáo này.
- Settings/UI: `core/types.py`, `config/settings.example.json`,
  `ui/settings_dialog.py`, `ui/main_window.py`, `ui/provider_notice.py`,
  `ui/whole_chapter.py`, `ui/comic_sources.py` (nhãn tiến trình).
- Tích hợp/snapshot: `core/pipeline.py`, `core/multipage.py`,
  `core/provider_preflight.py`, `core/resume.py`, `core/whole_chapter.py`,
  `providers/agy_models.py`.
- QA entry và tài liệu: `main.py`, `README.md`, `PROJECT_STATUS.md`.

Hash `core/ocr.py`, `core/imaging.py`, `providers/agy.py`,
`providers/gemini_api.py`, `sources/tooncn_bridge.py` giữ nguyên. Không đổi
mask/inpaint/renderer/layout/xóa chữ hoặc Chrome Bridge. Config người dùng,
SQLite, checkpoint và EXE baseline nguyên hash; không xóa dữ liệu cũ.

Hạn chế: chỉ Qwen có live evidence, Whole live chưa chạy; giới hạn request và
quota của API vẫn có thể khiến chương lớn dừng rõ ràng. Không có auto fallback,
quota dashboard hoặc cam kết không bao giờ gặp 429.

## Git & Fork Handoff

Branch `main`, HEAD baseline `0ccbd979af7e05bd46fe56cb8e1ad2c3db2c84f0`.
Working tree/index/unmerged sạch ở đầu lượt; không thay lịch sử/branch/index.
Kiểm tra cuối và danh sách file ở `git-review.json`, bảo toàn dữ liệu và test
ở `acceptance-summary.json` trong evidence. Không đổi `.gitignore`.

Cuối lượt: **16 modified + 5 untracked**, index/unmerged trống, HEAD không đổi.
`git diff --check` PASS, chỉ cảnh báo CRLF/LF. Runtime mẫu được ignore đúng,
source/test/docs/config mẫu không bị che; không có runtime đã track hoặc file
sửa/mới >2 MiB. Scan literal key trong file thay đổi/evidence/EXE không thấy
key; scan bundle không thấy settings.json/state.sqlite3/DPAPI/journal riêng tư.
Các kiểm tra này không thay thế review thủ công trước khi chia sẻ source.

Chỉ review source/test/docs/config mẫu trong Fork. Không commit logs/output,
cache/DB, model, settings riêng, token/key hoặc dist/build/EXE. Message gợi ý
nếu người dùng tự review/commit: `feat(groq): add official OCR translation API`.

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT**
