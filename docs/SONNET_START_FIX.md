# Bắt đầu dịch giữ lựa chọn Sonnet — 12/11/2026

## Nguyên nhân đã tái hiện

Config thực tế lưu `claude-sonnet-4-6` đúng. Journal còn dở lưu
`gemini-3.8-flash-low`. Nút **Bắt đầu dịch** trước đây truyền tiếp `resume_id`
cũ khi ô Bỏ qua ảnh đã xử lý bật. Backend thực hiện đúng quy tắc pin model
vào run cũ, nên nhãn và invocation quay về Gemini dù người dùng muốn lượt mới.

Đây là lỗi phân biệt Start/Resume trong GUI, không phải CLI bỏ qua Sonnet hoặc
provider tự fallback. Ba test mới tái hiện trước sửa: **3 FAIL / 4 PASS**.

## Sửa đổi

- `MainWindow.start(..., resume=False)` mặc định không dùng journal cũ.
  Bắt đầu dịch tạo journal mới với model/effort mới nhất đã lưu, độc lập ô skip.
- Tiếp tục/Retry truyền `resume=True`; GUI đọc model của journal vào bản copy
  options cho worker trước preflight. Không đổi bản options của Settings.
- Khi lưu cấu hình, lưu lựa chọn cho lượt mới, không ghi model của run cũ
  ngược vào config. Trạng thái AI hiển thị model thực sự của worker.
- Nếu một run cache riêng thuộc model khác, Start tách khỏi namespace đó,
  dùng cache thông thường; giữ run.json/journal/output cũ nguyên vẹn.
- Không đổi OCR/mask/inpainting/renderer/parser/CLI/model catalog hoặc chính
  sách validation. Không tự fallback/retry/provider switch.

## Sử dụng

1. Mở Cài đặt, chọn **Claude Sonnet**, bấm **Lưu**.
2. Bấm **Bắt đầu dịch** để bắt đầu theo Sonnet. Cache hợp lệ vẫn được phép dùng;
   muốn OCR/dịch mới hoàn toàn thì dùng **Dịch lại từ đầu** có xác nhận.
3. Muốn tiếp công việc Gemini cũ, bấm **Tiếp tục**. Run đó tiếp tục Gemini,
   nhưng lựa chọn Sonnet cho lượt mới vẫn được giữ. Không tự đổi model giữa run.

## Bằng chứng

Evidence: `output/sonnet-start-fix-20261111T192349Z/`.

- `tests/test_model_settings_sync.py`: click Start với journal Gemini cũ phải
  queue Sonnet + resume_id=None; Continue queue Gemini + journal cũ nhưng
  config vẫn Sonnet; Start sau Continue trở lại Sonnet; run cache riêng nguyên
  hash. Test đi tiếp qua ProcessingManager/AGYProvider với transport fixture
  xác nhận argv `--model claude-sonnet-4-6`, không ép effort.
- Bộ model/Settings/GUI cache/run cache: **43 PASS**,
  `logs/sonnet-start-final.xml`.
- Regression multipage/resume/Whole Chapter: **74 PASS**,
  `logs/sonnet-start-resume-regression.xml`. Hợp hai bộ: **117 PASS / 0 FAIL /
  0 SKIP**, không phải full regression toàn repository.
- `source-gui/report.json`: Windows GUI thật, mở Settings/Lưu/click Start và
  Continue, model lần lượt Sonnet/Gemini, preference Sonnet, journal nguyên hash.
  Worker được mock rõ ràng, không gọi dịch thật.
- Driver `scripts/validate_ai_model_settings.py` kiểm tra cùng đường đi trên
  source và EXE, toàn bộ config/SQLite/journal/ảnh fixture nằm riêng trong output.

Không gọi AGY thật trong nhiệm vụ này. Test invocation là fixture transport,
không giả là một lượt dịch Sonnet mới. Không chạy lại chương truyện của người
dùng hoặc sửa nội dung ảnh.

## Build và EXE

Đã chạy `build.bat`, pip check và PyInstaller thành công, không thay hệ thống
build hoặc ghi đè EXE cũ. EXE mới:

`dist/ImageTranslatorVN-20261111T192625787431Z/ImageTranslatorVN-20261111T192625787431Z.exe`

Giữ nguyên `_internal` bên cạnh EXE; đóng bản cũ rồi mở bản mới.
SHA-256: `f49a26adbeafd6644ce8f17b11594e90c875541669169954f8932961683aacd6`.
Log: `logs/build-ImageTranslatorVN-20261111T192625787431Z.log`.

EXE được mở thật trên Windows, Save/Cancel và sáu biến thể model/effort đều
PASS; Start/Continue và mở lại PASS, exit 0. DPI 100% và 150% PASS; đây là
scale bằng QT_SCALE_FACTOR, không phải hai màn hình vật lý. GUI dùng worker
fixture có ghi rõ, không tuyên bố vừa chạy một lượt dịch live mới.

Reports: `exe-gui/`, `exe-gui-150/`, `exe-reopen/`. Ảnh sau khi click Start:
`exe-gui/start-sonnet.png`; ảnh Settings/popup trong cùng thư mục. Config riêng
của QA nằm dưới evidence; config Sonnet thật của người dùng không đổi hash.

## Git & Fork Handoff

PROJECT_ROOT từ workspace/module; root phiên này
`D:/WebLocal/IMAGE-TRANSLATOR-VN-main`, branch `main`.
Baseline 25 modified + 16 untracked, index/unmerged trống. Giữ thay đổi có sẵn;
không nhận các sửa renderer/AI settings trước đó là sửa riêng lượt này.
Baseline/hash tại `baseline.json`, kiểm tra cuối tại `git-review.json`.

Cuối lượt 25 modified + 17 untracked, index/unmerged trống, HEAD không đổi.
Config thật, database, checkpoint và EXE baseline nguyên hash. Diff check
PASS, chỉ có cảnh báo CRLF/LF. Không đổi ignore; source/test/docs hiển thị,
runtime mẫu được ignore đúng; không có runtime đã track, file mới/sửa >2 MiB
hoặc khớp mẫu credential đã rà. Regex scan không thay thế review thủ công.

File riêng nhiệm vụ: `ui/main_window.py`, `tests/test_model_settings_sync.py`,
`scripts/validate_ai_model_settings.py`, `docs/AI_MODEL_SETTINGS.md`, tài liệu
này, `README.md`, `PROJECT_STATUS.md`. Không sửa `.gitignore`.
Review source/test/docs trước khi tự stage trong Fork; không commit settings
riêng, logs/output/cache/DB/model/build/EXE. Message gợi ý:
`fix(ui): separate new translation starts from checkpoint resume`.

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT**
