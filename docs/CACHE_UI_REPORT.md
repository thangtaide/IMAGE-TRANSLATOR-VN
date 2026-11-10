# Cache, dịch lại từ đầu và giao diện xử lý

## Điều tra trước triển khai — 10/11/2026

Root được xác minh từ workspace/module và Git; đường dẫn dưới đây tương đối
PROJECT_ROOT. Baseline Git và inventory read-only lưu trong lượt riêng
`output/cache-ui-acceptance-*/baseline.json`, `cache-before.json`.

1. `TranslationCache` mặc định dùng `core.paths.CACHE/state.sqlite3`; có thể
   được truyền database khác. Source lấy ROOT từ module; EXE lấy từ cấu trúc
   project/dist/build/exe. Hiện không dùng AppData cho database pipeline.
   SQLite dùng WAL; không được xóa/move WAL/SHM khi ứng dụng đang mở.
2. OCR key gồm SHA256 ảnh, identity engine/model, ngôn ngữ, confidence,
   tile size, reading direction. Cache nằm trong bảng cache, kind=ocr.
3. Translation key gồm source text, source/target language, provider identity
   (mode/model), glossary, context, revision numeric/glossary. Không phải mọi
   provider key đều có image hash hoặc rendering revision. AGY Batch thêm
   item IDs chứa job/page/image hash và context; không có nonce riêng cho lần
   bấm bắt đầu. Cùng input/config có thể dùng lại bản dịch hợp lệ.
4. Job/fingerprint gồm options, OCR/service identity, image hash và
   readable-outline-layout-v4. Output JPEG ở thư mục người dùng; DB lưu
   output-hash, metadata và items receipts, không chứa bitmap inpaint riêng.
5. ResumeStore cạnh database: `<db-stem>-resume-v1/*.json`, lưu OCR-ready,
   region translation receipts, source/output hash và recipe. Không chỉ có
   thư mục cache mặc định: database độc lập sinh journal cạnh DB đó.
6. Whole có workspace `output/stage3g-*/`: qa.sqlite3, OCR JSON, manifest,
   validated-translations, journal và rendered. latest_workspace theo nguồn
   sẽ mở lượt cũ; nút Whole tạo lượt mới hiện có đã dùng workspace riêng.
7. ToonCN/website có ChapterCache `cache/online_comics`, manifest/ảnh tải,
   Bridge snapshots và source service checkpoint; Whole có thể đọc ảnh cache
   nguồn đã xác minh. Source service còn có `cache/online_comics/pipeline.sqlite3`,
   journal cạnh DB, staging `output/online_comics_work`; các lượt mới sẵn có
   dùng `_fresh` và `output/stage3j-batch-*`. Bridge có
   `cache/tooncn_browser/inbox`, `runtime-v2`; Chrome profile/session nằm ngoài
   phạm vi dọn. Không coi ảnh tải/Bridge/auth là cache OCR để dọn.
   `cache/agy/request-*` là work directory transport, không phải cache dịch
   mà pipeline đọc thay request. Models/config/credentials không phải cache dọn.
8. Build chỉ đóng gói code/dependencies/assets, không đổi runtime DB/journals.
   Do đó EXE mới vẫn đọc dữ liệu cũ. Checkbox skip_success không tham gia
   cache key; hiện còn bị GUI khóa checked và các nhánh checkpoint/page_done
   bỏ qua ảnh vô điều kiện. Bỏ tick không có nghĩa OCR/translation cache miss.

**Root cause:** thiếu ranh giới run cho thao tác dịch lại, cùng với skip guard
không tôn trọng tùy chọn. Không thể khắc phục đúng bằng đổi tên nút hoặc xóa
toàn bộ database. Triển khai namespace DB riêng theo run, giữ checkpoint cũ;
quản lý cache chỉ dọn các loại xác định được ownership, có backup/transaction.

**Menu:** QSS hiện chỉ định màu chữ QWidget và màu nút, thiếu QMenu/QMenuBar
và palette popup đầy đủ. Popup Windows có thể dùng nền hệ thống sáng trong
khi kế thừa chữ/disabled xám của dark theme. QComboBox item view thiếu một số
text/disabled/selection states. Cần áp dụng palette và QSS popup thống nhất.

## Kết quả triển khai và nghiệm thu

**ĐẠT trên máy hiện tại.** Root thực tế là `IMAGE-TRANSLATOR-VN-main` trong
workspace. Evidence nhiệm vụ: `output/cache-ui-acceptance-20261110T140037Z/`,
gọi là RUN. Git branch `main`, HEAD `f82a6db7513245af41f6c23b694d473f51d2f6fc`;
giữ 26 đường dẫn sửa/untracked có sẵn. Không thực hiện thao tác Git ghi dữ liệu.

### Cơ chế run và sử dụng

`core/run_cache.py` tạo UUID 32 ký tự, DB rỗng riêng ở
`<thư mục DB thực>/<db-stem>-runs/<run_id>/state.sqlite3`, journal cạnh DB và
`run.json`. Không copy OCR, target, DB hoặc receipt cũ vào run mới. Worker
dùng DB đó xuyên suốt OCR/TranslationService/pipeline/resume. Cache của chính
run được ghi để tiếp tục khi bị dừng. `active.json` chỉ tìm namespace đã lưu
khi nguồn/đích khớp, không tự chạy. Khôi phục giữ pending_cache_path/run_id
của checkpoint, không quay về DB chung; run đã xong không che job chung còn dở.

**Bắt đầu dịch:** dùng cache hợp lệ. Checkbox bật thì skip receipt/hash đúng;
tắt thì render_repeat_id bền trong journal tạo job/receipt/output riêng, giữ
output cũ. OCR/dịch vẫn có thể dùng cache nếu key khớp; đây chưa phải buộc
OCR/dịch mới. Explicit resume giữ các trang done của chính journal.

**Dịch lại từ đầu:** nút trực tiếp → dialog đếm ảnh trong nền, hiển thị
mode/model/nguồn/đích/UUID/bypass → Hủy hoặc Xác nhận. Chưa xác nhận không
tạo run/gọi AGY. DB mới không có cache/checkpoint cũ, bất kể checkbox. Đích
`run-<thời gian>-<ID>` riêng, từ chối đích đã tồn tại; các lần sau ngang cấp.
Loại vùng output cũ khỏi input nếu nó nằm trong nguồn. Whole dùng
`output/stage3g-restart-<run_id>` và vẫn cần xác nhận manifest riêng trước AGY.
Không đổi nhánh nguồn/Chrome Bridge. [Hướng dẫn thao tác](CACHE_UI_GUIDE.md).

### Mở/dọn cache an toàn và giao diện

Mở cache dùng DB đang hoạt động; Whole mở workspace chứa qa.sqlite3. Không
giả định AppData hoặc ổ đĩa cố định; thiếu thư mục thì báo, không tự tạo.
Cache manager QThread hiển thị đường dẫn, dung lượng, job/run, loại và ngày
cập nhật. Có giới hạn thời gian, khoảng 50.000 file và 500 run; thống kê chưa
đủ được ghi là tối thiểu. task_pending chờ cả queued result đến GUI, không
coi QThread đã dừng là bảng đã cập nhật xong.

Chỉ dọn **OCR/translation rows của run riêng đã done**. Kiểm UUID/path và từ
chối symlink/junction/hardlink; cross-process lease chặn worker đang chạy;
SQLite backup và copy journal trước BEGIN IMMEDIATE/parameterized DELETE.
Backup lỗi/quá 15 giây/lock bận thì không dọn; lỗi DELETE rollback. Đóng kết
nối cả khi có exception. Backup ở `cache-backups/<run>/<timestamp>` cạnh DB
chung, có nút backup riêng và xác nhận trước dọn.

Không xóa DB/WAL/SHM, jobs/items, output-hash/metadata, journal, ảnh, output,
models, config hoặc credentials. Run còn dở bị chặn. DB chung, Whole/ToonCN/
Bridge và render receipts chỉ xem/được bảo vệ vì chưa có ownership dọn an
toàn. Không rmtree, không VACUUM hoặc tự xóa backup; file SQLite chưa chắc
nhỏ đi ngay sau dọn rows.

Tab có sáu khu vực nguồn/đích, tùy chọn, thao tác, công cụ, tiến trình và bảng.
Header hai cột ở cửa sổ rộng, xếp dọc khi hẹp; controls tối đa ba nút/hàng,
có scroll và tooltip. Nút skip đã bật cho người dùng thay đổi. Giữ retry,
review/log, khôi phục và model manager cũ. Theme cấp QApplication dùng
QPalette/Fusion/QSS cho menu, menubar, combo, hover/selected/disabled. Đã tái
hiện menu trắng thật và xem popup tối sau sửa, không chỉ kiểm palette bằng test.

### Bằng chứng pipeline thật

Cổng QA `main.py --cache-ui-check` chạy source/frozen code thật. Wrappers chỉ
đếm/ghi metadata, gọi nguyên phương thức; không cung cấp OCR/target/response
giả. Source Offline dùng bitmap chữ Trung hợp lệ, Paddle và Argos/CT2 thật;
AGY dùng ảnh truyện 0003 nguồn thật từ dữ liệu nghiệm thu đã có, không đoán
đường dẫn và không xử lý chương 134 ảnh.

| Bước | OCR mới | Dịch mới | Inpaint/render | Skip |
| --- | --- | --- | --- | --- |
| Source Offline thường ban đầu | 1 | 1 | 1/1 | 0 |
| Source thường dùng cache | 0 | 0 | 0/0 | 1 |
| Source Dịch lại từ đầu | 1 | 1 | 1/1 | 0 |
| EXE AGY thường ban đầu | 1 | 1 invocation thật | 1/1 | 0 |
| EXE AGY thường dùng cache | 0 | 0 invocation | 0/0 | 1 |
| EXE AGY Dịch lại từ đầu | 1 | 1 invocation thật | 1/1 | 0 |
| EXE release Offline thường/cache/fresh | 1/0/1 | 1/0/1 | 1/0/1 mỗi bước | 0/1/0 |

DB/output lượt thường không đổi sau fresh; mọi cache read của fresh thuộc DB
mới. Cleanup GUI qua xác nhận có backup, giữ DB/output cũ. Source và EXE
release hủy sau OCR thật bằng JobControl.cancel, mở lại widget với options
snapshot QA rồi khôi phục đúng namespace: OCR trên resume=0 (cache riêng hit),
dịch thật=1, render=1, done. Không sửa user config để giả lập mở lại. Test hai
ảnh riêng kiểm tra giữ trang done khi hủy giữa chừng.

Evidence cuối: `RUN/source-release-pipeline3/report.json`,
`RUN/exe-handoff-offline/report.json`, `resume-after-reopen.png`.
Cùng fixture/options, PNG source/EXE **giống hệt byte**: `RUN/equivalence.json`.
Source đọc snapshot cache AGY của EXE với skip=1, OCR/render/request=0 tại
`RUN/source-agy-cache/report.json`; đây là cache reuse, không inference AGY mới.

### AGY thật: 3 request, gồm 2 ban đầu và 1 được cấp thêm

| Lần | Mục đích | Ảnh | UTC bắt đầu | Transport | Kết quả | Còn |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | EXE thường, tạo cache thật | 0003, 1 ảnh | 14:40:26 | 24,297s | exit 0, done, không fallback | 1 |
| 2 | Nút fresh, DB/OCR/request mới | 0003, 1 ảnh | 14:40:58 | 22,344s | exit 0, done, không fallback | 0 |
| 3 | Xác minh production release sau khi người dùng cho thêm lượt | 0002–0004, 3 ảnh | 15:14:32 | 30,766s | exit 0, 3 done/0 lỗi/0 fallback; gate GUI cũ kiểm sớm FAIL, đã recheck | 0 |

Model cấu hình `gemini-3.8-flash-medium`. `RUN/agy-budget.json` giữ thời gian,
phạm vi, status, byte counts và remaining; không raw stdout/key/token. Probe
help/version là local, không generation. Không retry. Ledger ghi riêng
additional_authorization, limit từ 2 lên 3 và dừng ở used=3.

Hai request đầu trên candidate `ImageTranslatorVN-20261110T143711755463Z`,
evidence `RUN/exe-pipeline/report.json`. Request 3 trên bản
`ImageTranslatorVN-20261110T145628366097Z`, `RUN/exe-batch/report.json`:
pipeline state=done, completed=3, failed/fallback=0, audit đủ nội dung/ID và
không collision. Báo cáo tổng gốc **FAIL** vì GUI gate đọc nút trước queued
QThread.finished; không sửa evidence này thành PASS.

Sửa riêng QA chờ GUI idle và thêm replay cache thật. Bản bàn giao
`ImageTranslatorVN-20261110T152147487436Z` kiểm `RUN/exe-handoff-cached-agy`:
3 skip, 0 OCR/render/request mới, Start bật/Cancel tắt, **PASS**. Offline
fresh/cancel/reopen/resume trên bản này cũng PASS. Không cần request thứ 4.
Đã so sánh bytecode trong hai gói PyInstaller: **60 module core/ui/providers/
sources và main giống nhau**, chỉ QA đổi ở đóng gói cuối; xem build-handoff.json.
JPEG AGY đã xem 1280×720, Việt đọc được và không chồng nét Trung cũ.

### Test PASS/FAIL/SKIP

- Full release: **607 PASS, 0 FAIL, 12 SKIP**, 478,62 giây;
  `logs/cache-ui-regression-release.xml` và `.log`. Production code giữ nguyên;
  lần đóng gói sau chỉ sửa QA, đã kiểm source/frozen cache replay và idle.
- Cache/GUI contracts: **25 PASS**, `logs/cache-ui-release-ready.xml`.
  Bao gồm cache hit/miss, fresh, checkbox, cancel/resume, reopen route, scope
  run khác, backup lỗi, rollback, lock, pending protection, unsafe path/hardlink,
  conflict, Whole cache path, theme, inventory không chặn event loop.
- Mask/inpaint/layout/core/error: 104 PASS trước đó, 64 PASS sau bổ sung.
  Không cộng dồn testcase trùng vào số full run.
- Source/EXE Qt Windows **100%, 125%, 150% PASS**; không cắt nhãn nút chính
  ở cỡ thử 660×580. Dialog có scroll và nút xác nhận luôn nhìn được.
- Node v22.23.4/npm 10.9.9 portable đã có, PATH chỉ trong process test.
  ToonCN/Bridge JavaScript và Python host fixtures PASS; không sửa Bridge.

12 SKIP: thiếu OCR en/ml/zt, MT ko/zt, M2M100 tùy chọn; online chưa opt-in;
hai DOM thật Kuaikan thiếu; ba live Kuaikan tests chưa opt-in. Không báo các
model hoặc website live này PASS.

Giữ log FAIL cũ: backup exception giữ handle (sửa closing), assertion skip-off
cũ trái yêu cầu mới (đổi sang kiểm output mới và giữ output cũ), QA polling
native/GIL (đổi QEventLoop), inventory đọc trước queued result (task_pending),
route DB khi khôi phục (pending namespace + test reopen). Không sửa evidence
FAIL thành PASS. Process QA đầu bị dừng là process riêng, không AGY và không
xóa DB/journal/output của nó. Các run cuối đều PASS.

### Build và ảnh GUI

Build bằng build.bat/PyInstaller hiện có, pip check PASS, exit 0. Workpath theo
tên build để giữ intermediates cũ; giữ các candidate trước. Bản bàn giao:

`dist/ImageTranslatorVN-20261110T152147487436Z/ImageTranslatorVN-20261110T152147487436Z.exe`

20.012.162 byte; SHA256
`ea95d7dd806469e848ed32f4ca49522bc1971161965cd2786fd0c877d51a1577`.
Log `logs/build-ImageTranslatorVN-20261110T152147487436Z.log`.
`RUN/build-handoff.json`, `prebuild-handoff.json` xác minh fingerprint khớp.
Chính frozen EXE đã chạy GUI, mở cache thật, quản lý cache, fresh và resume
sau mở lại. Có qwindows.dll; Arial/Segoe UI Windows và models ngoài EXE, không
cài dependency/model nặng hoặc đưa cache/output/credentials vào bundle.

[GUI trước/sau](../output/cache-ui-acceptance-20261110T140037Z/gui-before-after.png) ·
[Menu trước/sau](../output/cache-ui-acceptance-20261110T140037Z/menu-before-after.png) ·
[Xác nhận ở 150%](../output/cache-ui-acceptance-20261110T140037Z/exe-handoff-gui-150/confirm.png) ·
[Quản lý cache](../output/cache-ui-acceptance-20261110T140037Z/exe-handoff-offline/cache-manager.png) ·
[Khôi phục sau mở lại](../output/cache-ui-acceptance-20261110T140037Z/exe-handoff-offline/resume-after-reopen.png) ·
[Cache AGY và nút GUI đã về idle](../output/cache-ui-acceptance-20261110T140037Z/exe-handoff-cached-agy/cached-agy-idle.png).

Đã xem grab Qt Windows thật, không tạo GUI bằng AI. Thao tác QTest/Qt events,
không tuyên bố màn hình vật lý/native picker hoặc portable trên máy sạch.
Giữ toàn bộ onedir và `_internal` dưới project/dist, models ở project/models.

### File, giới hạn và Git handoff

Code: core/run_cache.py, core/pipeline.py, ui/main_window.py, ui/workers.py,
ui/whole_chapter.py, ui/theme.py, ui/fresh_run.py, ui/cache_manager.py, main.py,
scripts/validate_cache_ui.py, scripts/acceptance_readability.py, build.bat.
Test: test_run_cache.py, test_cache_ui.py,
test_error_fallback.py. Docs: báo cáo/hướng dẫn cache, README, PROJECT_STATUS,
BUILD_REPORT, E2E_REPORT, EXPORT_AND_BUILD, TROUBLESHOOTING. Danh sách/tách
baseline đầy đủ và kiểm tra Git trong `RUN/handoff.json`.

Giới hạn có chủ đích: legacy/global/Whole/ToonCN/render receipts chưa hỗ trợ
dọn; inventory lớn có thể chỉ là tối thiểu; không cam kết mọi ảnh/site/máy
sạch. Request 3 chạy production code cuối, đóng gói cuối chỉ đổi QA và đã
kiểm cache AGY/idle cùng Offline fresh/resume. Giữ 5 EXE có sẵn trước nhiệm vụ,
mọi cache/output/candidate; không đổi credentials hoặc sources/Bridge.

.gitignore không đổi; runtime cache/output/logs/dist/venv được ignore, source/
test/docs không bị ignore. Không stage hoặc untrack. Kiểm diff --check, index,
unmerged, fingerprint, old EXE và secret/large-file scan lưu trong handoff.
Message chỉ đề xuất để người dùng tự review: `feat: isolate reruns and manage cache safely`.

Kết luận **ĐẠT tiêu chí nhiệm vụ trên máy hiện tại**, với giới hạn nêu trên.
NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT.
