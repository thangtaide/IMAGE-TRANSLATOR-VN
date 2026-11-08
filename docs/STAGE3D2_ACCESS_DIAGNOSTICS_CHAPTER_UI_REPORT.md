# Stage3D.2 — ACCESS_DENIED và compact chapter workflow

08/11/2026. **STAGE_3D2_WITH_WARNINGS**.
Triển khai/kiểm thử local/mock và Qt offscreen; không gọi API thật, không thay
quyền Google để ép thành công. Nguyên nhân quyền phía Google vẫn chưa chứng minh.

## 1. Baseline và điều tra trước sửa

Root D:/TransTool, branch main, HEAD mới
`2226723b98880f9a811daa93ecf78dc2e514f790`. Repo sạch, không staged/untracked/
unmerged trước sửa. Không dùng trạng thái HEAD cũ của Stage3D.1. Đọc AGENTS,
PROJECT_STATUS, Stage3D/3D.1/3C/3C.1 và provider/pipeline/multipage/diagnostics/
resume/source worker/service/UI; không thay thế ứng dụng hoặc nghiên cứu lại DOM.

Đã thông báo kết quả điều tra trong commentary trước sửa source:

- Diagnostic mới lúc11:50:21.654689UTC (18:50:21 UTC+7), job
  `e26eec3c8595a4a98a5ec74a7c18757773483d01d8f82ba33727c63be5f85d1a`,
  chapter276880, page1, Gemini API, ProviderSuspended, ACCESS_DENIED,
  checkpoint paused_provider.
- Config hiện tại mode AI Gemini API, model2.5Flash, Free confirmation=true.
- Source journal0647956228e84692a5cf296ce7626366 và chapter journal
  2723a36ba2494c92b23038341624de3e mới11:50 cũng true; chapter109pending/0done.
- Hai journal cũ10:28/Free=false còn nguyên nhưng **không phải** hai record mới.
  Cùng pipeline job ID là bình thường vì bool xác nhận không đổi recipe dịch.
- Error message cũ là static message có403. Không có http_status, attempt ID,
  response_received, reason Google hoặc raw response được persist trong record.

**Kết luận bằng chứng:** source đang commit chỉ ánh xạ403 sang ACCESS_DENIED
trong `GeminiAPIProvider.translate_batch`, sau `client.post`, đọc response và
lấy status. Code+runtime cung cấp **suy luận mạnh về nhánh403**. Nhưng không có
metadata HTTP độc lập trong log lịch sử; không gắn nhãn HTTP_403_CONFIRMED cho
lượt đó hoặc khẳng định response đã được kiểm chứng trực tiếp từ Google.

Nhãn điều tra: **ACCESS_DENIED_ROOT_CAUSE_UNPROVEN**, **REQUEST_SENT_NOT_PROVEN**
theo nghĩa chưa có bằng chứng độc lập request tới Google/response của Google.
Không có nghĩa source chưa gọi HTTP: đường code bình thường của mã lỗi này nằm
sau HTTP. Không biến code inference thành dữ liệu response đã capture.

## 2. Đường đi và các giả thuyết

`GUI collect_options → local preflight → ComicSourceWorker/ProcessingWorker →
LocalComicJob/ProcessingManager → TranslationService._gemini_api → MultiPageAGY
(API branch) → GeminiAPIProvider.translate_batch → HTTP mapping → ProviderSuspended
→ pipeline diagnostic/checkpoint/provider_paused → worker signal → ProviderNotice`.

| Giả thuyết | Code và runtime | Kết luận |
|---|---|---|
| HTTP403 | Chỉ mapping403 tạo ACCESS_DENIED trong luồng chuẩn; runtime có mã/message403 nhưng không status field | Inferred, chưa xác nhận độc lập HTTP/server reason |
| Local preflight phát ACCESS_DENIED | Luồng chuẩn preflight trả key missing/free/config/budget riêng | Không có bằng chứng; không phải nhánh local bình thường |
| Chỉ là journal cũ Free=false | Record mới11:50 và hai journal mới đều true | Loại trừ giả thuyết chỉ hiển thị lỗi Free cũ cho sự kiện này |
| GUI banner cũ | Banner cũ có thể tồn tại trong bộ nhớ; không inspect process GUI người dùng | Không chứng minh; không giải thích riêng được record ACCESS_DENIED mới |
| Resume dùng provider/consent cũ | Record mới Gemini API + journal mới true; merge PROVIDER_FIELDS hiện có | Không có bằng chứng lỗi này trong lượt đã ghi |
| Lỗi source bị gộp | ACCESS_DENIED thuộc ProviderSuspended/Gemini/TRANSLATION; source AccessRestricted dùng source_error/image_source_error | Không thấy gộp ở lượt này |
| Timeout/network→403 | Catch requests.Timeout/RequestException có code TIMEOUT/NETWORK_ERROR riêng | Không có mapping nhầm trong source |
|429→403 |429 RATE_LIMITED/QUOTA_EXCEEDED riêng, không chuyển403 | Không có bằng chứng quota/rate gây ACCESS_DENIED |
| Key thuộc project khác | Key chỉ đọc từ environment process; không có project identity của key trong log | Unknown; không in/so key/prefix hoặc gọi account API |
| Model/project/region/API-key restriction | Không có structured reason lịch sử | Unknown; không tự thay model/key/billing |

Người dùng cung cấp Free tier và RPM5/TPM250.000/RPD20 trên AI Studio: đây là
thông tin do người dùng quan sát ở thời điểm đó, không hardcode hoặc xác minh
bằng tài khoản trong Stage này. Quota/model xuất hiện không chứng minh quyền
generateContent. Không có bằng chứng để yêu cầu bật billing hoặc tạo key mới.

## 3. Diagnostic mới

Module providers/gemini_diagnostics.py, observer ở GeminiAPIProvider; metadata
gắn vào exception, bổ sung batch ID ở MultiPageAGY/API branch và job/chapter/
pending/checkpoint tại ProcessingManager. Không đổi journal schema/DB migration.

| request_state | Bằng chứng |
|---|---|
| NOT_ATTEMPTED | Lượt hiện tại chưa vào client.post |
| ATTEMPT_STARTED | Vừa bắt đầu client.post, không chứng minh đã tới Google |
| RESPONSE_RECEIVED | client.post trả response object/header; giữ status ngay trước đọc body |
| UNKNOWN | Thiếu metadata, bool unknown là null, không được xem là false/not attempted |

Nhóm `gemini_api_request` gồm timestamp, provider/model, internal UUID attempt,
SHA256 batch/job ID, chapter ID số, preflight state, attempt/response state,
HTTP status, category/code, enum reason, Retry-After bounded, pending page count
của worker hiện tại, checkpoint và cache state RETAINED. Cache state nói giữ
receipt cũ, không thay cho hash/integrity verification của ResumeStore.

Reason chỉ nhận enum trong allowlist từ error.status hoặc ErrorInfo.reason,
không lưu message, metadata, request body hay toàn JSON. Enum fixture là manual
contract cases, không phải capture API thật; UNSPECIFIED là chưa biết. Không
được coi việc nhận PERMISSION_DENIED là đã biết nguyên nhân account cụ thể.

Chỉ model2.5Flash hiện được allowlist. Không thêm model/endpoint/key mới. Capture
status ngay khi nhận headers giúp phân biệt timeout đọc body với chưa có response.
Không sửa mapping trạng thái HTTP, retry0, API budget64, TLS/redirect policy,
prompt/payload/generation settings hoặc response translation parser.

Hai lớp lọc: observer `clean` chỉ enum/kiểu/bounds, và DiagnosticLog lọc lần nữa,
chỉ giữ top-level metadata cho record API. Không raw stdout/body/header/key/
Authorization/cookie/token/OCR/target/prompt/đường dẫn cá nhân/unknown nested
objects. Control characters/unknown reasons không được echo. Record tối đa theo
DiagnosticLog4MB/1.000records cũ; group metadata khoảng1KB. Không telemetry.
Không rewrite/xóa log cũ để bổ sung dữ liệu chưa từng capture.

## 4. Thông báo lỗi

- RESPONSE_RECEIVED+403 mới được đặt tiêu đề **Gemini API từ chối quyền truy cập
  (HTTP403)**; không tự nói key sai hoặc phải trả phí. Origin journal không được
  dùng metadata cũ để nói có request mới.
- ACCESS_DENIED không có metadata: **Gemini API chưa thể tiếp tục**, chưa xác
  định trước/sau request, xem Chi tiết. NOT_ATTEMPTED/ATTEMPT_STARTED có câu đúng
  phạm vi; không gộp attempt với delivery tới Google.
- Restore/record paused cũ có nhãn **Công việc có lỗi đã lưu**, không tự chạy.
- Source hạn chế có **Nguồn truyện từ chối truy cập / SOURCE_ACCESS_DENIED**,
  không Gemini/quota. Không vượt source access gate.
- Free chưa xác nhận giữ nút mở Settings và metadata preflight Stage3D.1.
- AGY Unexpected tool use giữ Guard AGY/bộ kiểm tra an toàn, không quota hoặc
  tool invocation đã được chứng minh. Guard/observer AGY giữ nguyên byte.
- Banner mặc định title/code/hướng xử lý ngắn/Chi tiết/×; message+nhật ký chỉ mở
  khi chủ động. × không resume. Tab khác không lặp banner folder; không reset
  provider vì chỉ đổi layout. Không lặp cùng code vào banner và status dài.

## 5. Luồng chương trực tiếp

`URL + Phân tích link → metadata ngắn → Chọn tất cả/Bỏ chọn/Phân tích chương đã
chọn → bảng4cột → banner gọn nếu có → tải/dịch/progress → tùy chọn phụ`.

Nút Phân tích chương luôn trên bảng trong tab URL, không nằm trong cache/menu/
advanced. Chưa chọn/busy/chưa có adapter/đã chọn>10 đều disabled với tooltip.
Giới hạn1–10 là giới hạn worker đã có, không siết thêm access gate; một test cũ
chọn26 được cập nhật để kiểm tra disabled+tooltip và chọn lại1chương thì enabled,
thay vì kỳ vọng enabled rồi bị worker từ chối sau khi chạy.

Phân tích chương giữ metadata/image discovery ở ComicSourceWorker('images'),
không download/render/translate, không chọn thêm hoặc đổi thứ tự/provider.
Public/UNKNOWN có thể chọn để phân tích; locked/restricted không được chọn như
trước. Enter trong URL chỉ dispatch URL discovery khi chủ động và không busy.
Tải và dịch mới tạo process job; không tự tải từ IMAGE_LIST_READY.

Bảng ngay dưới thanh chọn, chiếm vùng stretch chính; cột0/1/2/5 hiển thị,3/4/6
vẫn có data/tooltip/nâng cao. Không overlay. Output/cache/technical nằm dưới
phần chính, có disclosure. Nút dịch dưới bảng; khi nhỏ/highDPI dùng scroll để
truy cập. Resume chỉ enable descriptor checkpoint chương hiện tại; full source/
receipt/hash validation vẫn chạy trong worker khi người dùng bấm, không hash
toàn bộ ảnh ở main GUI thread. Không đổi ResumeStore semantics.

## 6. Test và layout QA

Baseline427PASS/10SKIPPED mỗi runner.27test mới trong
tests/test_access_diagnostics_chapter_ui.py. Fixture HTTP/source/bitmap/OCR mới
đều là giả lập thủ công. Pipeline fixture vẫn dùng renderer/cache/journal thật
trên QA riêng; không gọi đó là Gemini API E2E thật.

- New+focused suite:74PASS trước ca bổ sung NOT_ATTEMPTED; full cuối gồm cả ca mới.
- **Pytest454PASS/10SKIPPED/0FAIL**,65,99giây.
- **Unittest454PASS/10SKIPPED/0FAIL**,64,16giây,464ca tổng.
- Windows Qt offscreen/QThread/GUI4provider, capturedDOM/cache/checkpoint,
  numeric/glossary, OCR Trung+Argos Offline và E2E thật trong full suite PASS.
-10SKIPPED: model chưa có và live opt-in không chạy; không gọi skip là PASS hoặc
  suy môi trường đang chặn mạng từ chuỗi skip cũ.
- First new fixture test so sánh toàn ChapterInfo sau discovery thất bại vì
  image_count cập nhật hợp lệ; sửa assertion so selection ID/order, không che
  regression. Không bỏ test hoặc sửa numeric guard để đạt PASS.
- LIVE Gemini/AGY/MyMemory/source/CDN: **NOT_TESTED**,0request trong Stage3D.2.
  Billing/key project/model eligibility thực tế không xác minh.
- Không build EXE, không cài dependency/model hoặc chạy production retry.

Layout QA9process riêng,3resolutions1366×768/1600×900/1920×1080 ×Qt scale1/1,25/
1,5; devicePixelRatio thật khớp từng cấu hình. Mỗi case kiểm tra nút chính và
phân tích chương visible/reachable/minimum hints, selection, analysis-before-
table, controls-after-table, bannerheight.9/9PASS, banner69logical px (khoảng104
physical px ở150%). Ở1366×768/150% vẫn có thể cần cuộn tới nút dịch; không hứa
mọi thành phần cùng xuất hiện trên viewport. Chưa test Windows monitor scaling
thủ công/multi-monitor hoặc EXE. Không dùng screenshots làm bằng chứng API thật.

Ảnh dùng26chương/585ảnh **fixture**, không live website:

- [Luồng1366×768/100%](../logs/stage3d2-20261108T120529Z/layout-1366x768-scale1/workflow.png).
- [Luồng1366×768/150%](../logs/stage3d2-20261108T120529Z/layout-1366x768-scale1.5/workflow.png).
- [Thanh nút150% sau cuộn](../logs/stage3d2-20261108T120529Z/layout-1366x768-scale1.5/controls.png).

## 7. Bảo toàn

Snapshot2.444file trước sửa tại logs/stage3d2-20261108T120529Z/protected-before.json.
Kiểm tra sau test2.444/2.444SHA256 không đổi: cache/source/output/manifest/journal/
DB/WAL/log cũ/model/config/BAT/spec/4EXE. Không thay flagFree=true trong config,
không resume276880/276337 hoặc retryfallback106/111, không downloadproduction.

Byte checks: ResumeStore/source resume/service/options/OCR/overrides/nativeguard/
AGY/AGYdiagnostics/Argos/MyMemory/.gitignore/AGENTS giữ nguyên; core translation
numeric/glossary/cache logic, API response parser và provider identity giữ nguyên.
Multipage chỉ thêm metadata API exception, không đổi packing/context/region IDs/
namespace/recipe/limits. Không migration DB/journal hoặc thay provider/default.

Evidence runtime: logs/stage3d2-20261108T120529Z/, pointer latest-stage3d2.json;
git-before, protected-before, before/, investigation-before (allowlist),
preservation, pytest/unittest XML/JSON/txt và layout-summary/results/PNGs.
Không đưa log/ảnh QA vào Git.

## 8. Git & Fork Handoff

Root/branch/HEAD như mục1, baseline sạch. File Stage3D.1 đã commit, không bị hiểu
nhầm là thay đổi tồn đọng. .gitignore không cần sửa; runtime cache/output/log/
model/DB/EXE/key env/config cá nhân tiếp tục được ignore; source/test/docs mới
hiện trong Fork, check-ignore không che các file mới. Git diff --check **PASS**;
status cuối12tracked modified/3untracked, staged0, không unmerged. Không phát
hiện literal credential hoặc binary/runtime mới trong file review. git-final.json
lưu status/stat/ignore/secret scan; model/config template và spec vẫn được track.
Không stage để đo hoặc xóa dữ liệu để làm sạch status.

File nên review/commit:

- Source mới providers/gemini_diagnostics.py; source sửa providers/gemini_api.py,
  core/diagnostics.py, core/pipeline.py, core/multipage.py, ui/provider_notice.py,
  ui/main_window.py, ui/comic_sources.py.
- Test mới tests/test_access_diagnostics_chapter_ui.py; sửa
  tests/test_kuaikan_http_runtime.py cho UI limit1–10 đã tồn tại ở worker.
- PROJECT_STATUS.md, README.md, docs/USER_GUIDE.md, docs/TROUBLESHOOTING.md và
  docs/STAGE3D2_ACCESS_DIAGNOSTICS_CHAPTER_UI_REPORT.md.

Không commit2.444runtime/resources, .venv, modelweights, cache/DB/log/output,
PNGs QA, credential/config cá nhân hoặc4EXE. Không tự untrack/delete dữ liệu.
Review source/test/docs từng file trong Fork → tự stage → xem staged diff →
tự commit. Gợi ý `fix(ui): clarify Gemini access errors and improve chapter workflow`.
**NO_COMMIT / NO_PUSH / NO_TAG / NO_DESTRUCTIVE_GIT**.

## 9. Trả lời A–G và việc còn lại

**A.** ACCESS_DENIED trong luồng chuẩn đến từ mapping403 của Gemini provider;
runtime có mã đó, chưa đủ metadata độc lập để xác minh sâu hơn nguyên nhân quyền.
**B.** Có suy luận code về HTTP response, chưa có bằng chứng độc lập request
đã tới Google/Google trả response lịch sử. Không tự nâng nhãn confirmed.
**C.** Free tier đã được người dùng xác nhận không đồng nghĩa generateContent
được cấp; chưa xác định restriction nào áp dụng, không tự sửa key/billing/model.
**D–E.** Có nút phân tích trực tiếp trên bảng; không cần mở cache/advanced.
**F.** Hash2.444/2.444giữ nguyên, production không được tiếp tục hoặc sửa.
**G.** Cần metadata response đã lọc từ lỗi đã có, hoặc một lượt QA nhỏ mới được
duyệt riêng, để xác minh thêm. Không bắt buộc tạo key mới/bật billing. Có thể
đề xuất1generateContent2.5Flash với văn bản tổng hợp ngắn/1request/0retry/không
ảnh hoặc production, QA DB riêng; **chưa được duyệt và chưa thực hiện** trong
Stage này. Không gửi lại OCRproduction để lấy reason. Không tự chuyển Stage4.
