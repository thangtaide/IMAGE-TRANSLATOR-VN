# Stage3D.1 — Gemini API preflight & compact GUI

08/11/2026. **STAGE_3D1_WITH_WARNINGS**: triển khai và nghiệm thu local/mock/Qt
offscreen; không nghiệm thu Gemini API thật hoặc DPI qua Windows desktop thật.

## 1. Kết luận điều tra trước khi sửa

Đã báo nguyên nhân trong commentary trước thay đổi production source. Repo lúc
bắt đầu sạch, branch `main`, HEAD mới
`7ee5962069ca3b8c44713e3073c2e1355bb92819`. Stage3C.1/3D đã được người dùng
commit; không dùng baseline uncommitted của báo cáo cũ.

**Nguyên nhân được chứng minh:** `gemini_api_free_tier_confirmed=false` trong
config/settings.json và options của source/chapter journal. Diagnostic runtime:

- Job `e26eec3c8595a4a98a5ec74a7c18757773483d01d8f82ba33727c63be5f85d1a`.
- Chương276880, trang1, provider Gemini API/model cấu hình gemini-2.5-flash.
- Lúc10:28:55.299491UTC (17:28:55 UTC+7), code FREE_TIER_UNCONFIRMED,
  checkpoint_state paused_provider.
- Chapter journal009a25fafa3d41ffbca714fcda004f50:109trang pending/0done,
  35trang ocr_ready,0region receipt đã validated. Không kết luận cả35trang đều
  chạy inference mới vì có thể dùng OCR cache.
- Source journal815ef1649faf4f689fd0c6dd245f2e6a cũng paused_provider/free=false.

Đường đi cũ:

`GeminiAPIProvider.translate_batch → if not free_tier_confirmed → fail →
ProviderSuspended(FREE_TIER_UNCONFIRMED) → ProcessingManager.run catch →
diagnostic/checkpoint + provider_paused → LocalComicJob pipeline event →
ComicSourceWorker.event → ComicSourcesPanel.handle_event → thông báo pause chung`.

Code chặn này nằm trước `self.requests += 1` và `client.post`. Vì vậy **lần gọi
gây lỗi dừng trước HTTP**. Không gọi đó là Gemini đã dịch thất bại, quota hết,
key hỏng hoặc model bị từ chối. Job đã có download/OCR cache; không được viết
"chưa xử lý gì". Không có HTTP counter lịch sử toàn diện để kết luận mọi job/
mọi lần chạy đều0request. Không kiểm tra trực tiếp bộ nhớ worker/GUI đang mở;
persisted state khớp thông báo nhưng không chứng minh screenshot là state sống
hay state cũ tại thời điểm chụp.

Ô xác nhận cũ đã có trong SettingsDialog và accept/save_options/load_options;
không tìm thấy lỗi lưu bool của thao tác đã xác nhận. Bằng chứng hiện tại là
flag **chưa được xác nhận**, không phải app đã nhận true rồi làm mất nó. Một lỗi
khác xác minh bằng QA: `MainWindow.restore_previous` dùng toàn bộ Options cũ,
có thể lấy false/provider cũ từ journal ghi đè lựa chọn mới. Sửa được trường
hợp này nhưng không khẳng định nó đã xảy ra trong lần chạy276880.

## 2. Preflight và phân loại trạng thái

`core/provider_preflight.py:check_configuration` là hàm cục bộ, không tạo HTTP
client/AGY process hoặc xác minh tài khoản. Các nút Start/begin/restore source
kiểm tra trước khi khởi chạy worker, lưu cấu hình job, OCR hoặc download mới.
Phân tích URL vẫn được phép khi thiếu thiết lập dịch; không tự tải/dịch.

| Trạng thái | Ý nghĩa / nơi tạo |
|---|---|
| API_KEY_MISSING | Không có GEMINI_API_KEY; local check hoặc provider trước HTTP. Không dùng AUTH_REQUIRED để gọi đó là lỗi server. |
| FREE_TIER_UNCONFIRMED | Có key presence nhưng bool xác nhận false; không tự tích hoặc kiểm tra billing. |
| READY_UNVERIFIED | Đủ điều kiện cấu hình cục bộ. Không chứng minh key, model, quota hay Free tier thực tế. |
| CONFIGURATION_BLOCKED | UI chưa khởi chạy lượt mới vì preflight thiếu; không ghi state mới vào journal. |
| AUTH_REQUIRED / ACCESS_DENIED | Remote401/403; giữ riêng với missing key. |
| MODEL_UNAVAILABLE | Remote404; không tự đổi model. |
| RATE_LIMITED / QUOTA_EXCEEDED | Giữ phân loại429 cũ và bằng chứng QuotaFailure/PerDay; không suy reset/quota. |
| NETWORK_ERROR / TIMEOUT / INVALID_RESPONSE | Giữ lỗi transport/protocol; không tự retry/switch. |
| PAUSED_BY_USER | UI nhận thao tác Pause chủ động; không phải báo lỗi provider. |
| PAUSED_PROVIDER | Worker đã dừng do provider; giữ code và pending. |

Provider vẫn kiểm tra lại key/xác nhận ngay trước HTTP để bảo vệ trường hợp cấu
hình hoặc môi trường đổi sau preflight GUI. Chỉ đổi nhãn missing key và thêm
phase/request_sent/scope; không thay model identity, payload, HTTP parser, quota
policy, numeric/glossary, budget hoặc cache namespace.

Mã hiện tại để truy vết: providers/gemini_api.py `fail/translate_batch`,
core/pipeline.py `ProcessingManager.run`, ui/main_window.py `check_provider_setup/
start/handle_event/show_settings/restore_previous`, ui/comic_sources.py
`check_provider_setup/begin/restore_cached_job/handle_event`, ui/provider_notice.py
`ProviderNotice.show_error`. Bản source trước sửa có trong evidence/before để
đối chiếu thứ tự guard/HTTP cũ mà không sửa lịch sử Git.

## 3. Thông báo và log an toàn

- Tiêu đề dễ hiểu, code, nguyên nhân xác minh, phạm vi đã/chưa xảy ra, hướng dẫn,
  nút Mở Cài đặt Gemini API, × và Chi tiết/Nhật ký mở rộng.
- `local_preflight/request_sent=false` nói **thao tác mới chưa khởi chạy/gửi OCR**.
  `provider_preflight/current_batch` chỉ nói batch hiện tại chặn trước HTTP.
  Không có metadata thì dùng câu trung lập, không kết luận request chưa gửi.
- UI không echo detail/raw payload/model reasoning/đường dẫn hoặc unknown code
  tùy ý. Allowlist code/provider, thời gian do app tạo, số trang kiểu int nếu có.
  Log trong widget giới hạn50block; không mở file log production mới.
- Preflight diagnostic ở backend bỏ OCR source/raw target/numeric tokens trước
  ghi log. Event phase/request_sent/scope và image_index đi qua worker/source
  wrapper tới UI; không ghi key, prompt hoặc response body.
- `INVALID_RESPONSE: Unexpected tool use` được gọi là **guard AGY từ chối**,
  không phải quota hay bằng chứng tool invocation thật. Observer/guard AGY giữ
  nguyên; không suy loại metadata/invocation nếu thiếu capture.
- job_finished paused không ghi đè code bằng câu pause chung. Sửa thiết lập/
  chọn phương thức hợp lệ sẽ ẩn cảnh báo cấu hình cũ, giữ lịch sử/pending; không
  tự resume. × cũng không tự resume hoặc chuyển provider.

## 4. Giao diện gọn

- Thanh chung: OCR, phương thức, model/provider/trạng thái cục bộ và Cài đặt.
  Provider phụ và Auto Fallback consent chuyển vào Cài đặt; giữ widgets trạng
  thái ẩn để tương thích, sync sau khi chấp nhận Settings. Không đổi mặc định
  Offline, lựa chọn đã lưu hoặc tự bật consent. Legacy Auto Fallback vẫn có để
  không phá cấu hình cũ; bốn phương thức chính giữ nguyên.
- Phần Gemini API nằm đầu Settings, link AI Studio cố định mở theo click chủ
  động, checkbox không tự tích; gọi từ cảnh báo focus đúng phần này. Phần form
  dài cuộn riêng, nút OK/Cancel vẫn truy cập được ở chiều cao nhỏ.
- URL/Phân tích cùng hàng; metadata ngắn vẫn có tổng URL ảnh; tooltip giữ thông
  tin đầy đủ. Thư mục xuất và tùy chọn cache là disclosure chỉ đổi visibility,
  không dùng group unchecked làm disabled các chức năng con.
- Bảng mặc định0/1/2/5: Chọn/Thứ tự/Tên chương/Trạng thái. 3/4/6 vẫn giữ data,
  tooltip và panel chi tiết; bật nâng cao để xem. Không xóa hàng, đổi order hoặc
  checkbox selection. Cột tên/trạng thái stretch, scrollbar khi cần.
- Thanh thao tác chính nằm trước bảng, nút ít dùng ở Thêm. Giữ callbacks/pause/
  cancel/retry/restore cũ. Menu trạng thái enabled theo button/công việc thật.
- QScrollArea, stretch và kích thước theo availableGeometry; giữ màu dark,
  giảm title/spacing/tab padding, dùng Qt arrow icons cho disclosure. Cửa sổ nhỏ/
  scaling cao cần cuộn; không hứa toàn bộ nội dung luôn xuất hiện cùng lúc.

## 5. Resume và bảo toàn semantics

`restore_previous` chỉ khôi phục OCR/render/source/output cũ và merge các
PROVIDER_FIELDS từ lựa chọn hiện tại, giống source resume đã có. Không dùng
journal cũ âm thầm hủy xác nhận mới/provider được chọn. Không chạy khi khôi phục
cấu hình. Core ResumeStore/sources.resume, recipe, journal schema và verification
source/output/hash/receipt giữ nguyên byte; không migration dữ liệu.

QA riêng đã tái hiện:1output Offline hợp lệ → pending còn lại bị chặn API do
chưa xác nhận → xác nhận rõ →1request **HTTP fake** → hoàn tất pending, receipt/
hash output cũ giữ nguyên. Không coi đó là Gemini E2E thật hoặc tác vụproduction.

## 6. Test và ảnh layout

Baseline lịch sử Stage3D401PASS/10SKIPPED mỗi runner.26test mới trong
tests/test_preflight_compact_ui.py. tests/test_gemini_api.py cập nhật expected
API_KEY_MISSING và làm test default độc lập saved options (người dùng hiện đã
chọn API). Không ép GUI thực tế về Offline để test PASS, không sửa guard test.

- Preflight/notice/settings/receipt/layout: local, fake HTTP/OCR và Qt thật.
- Regression cuối: **pytest427PASS/10SKIPPED/0FAIL**,65,15giây;
  **unittest427PASS/10SKIPPED/0FAIL** (437ca). Xem pytest-accepted.xml/txt và
  unittest-accepted.json/txt. Qt Windows offscreen, numeric/glossary, OCR Trung,
  Argos Offline và E2E thực trong full suite PASS; không gọi mock là API E2E.
- Lượt toàn bộ trước rà privacy cuối: pytest/unittest427PASS/10SKIPPED/0FAIL.
- Lượt đầu full suite có4FAIL: một test cần số URL ảnh trong metadata và3test
  phát hiện button con bị groupbox unchecked vô hiệu hóa. Đã sửa production UI,
  không xóa/sửa các test đó. Compatibility tests chạy lại PASS; giữ XML lỗi cũ.
- Một test mới QA cleanup SQLite bị khóa do đóng DB sau TemporaryDirectory;
  đã sửa thứ tự cleanup fixture. Một expected action fixture nhầm analyze thay
  vì url đã sửa theo API thật. Những lỗi này không được báo là lỗi production.
-10SKIPPED tiếp tục là model thiếu/live opt-in không chạy; text skip cũ nói
  sandbox không phải bằng chứng quyền mạng hiện tại.

9case Qt offscreen, **mỗi case tiến trình riêng với QT_SCALE_FACTOR thật**:
1366×768/1600×900/1920×1080 ×1/1,25/1,5. Lưu devicePixelRatio thực, logicalsize,
minimum-size hints, scroll reachability của nút chính, Settings buttons và các
cột/selection. Không đổi scaling toàn Windows, chưa kiểm tra màn hình/VM/native
multi-monitor thật. Fixture26mục/871URL ảnh là dữ liệu giả lập gắn nhãn QA, không
phải discovery website trong Stage này. Không có API key thật trong ảnh.

Ảnh QA (runtime, không commit): `logs/stage3d1-20261108T103529Z/layout-*-accepted/`
có window.png, controls.png và settings.png. layout-summary-accepted.json và
layout-verification.json xác nhận9/9cases PASS với DPR1/1,25/1,5 đúng cấu hình.
Ví dụ [thanh thao tác1366×768/100%](../logs/stage3d1-20261108T103529Z/layout-1366x768-scale1-accepted/controls.png),
[Settings1366×768/150%](../logs/stage3d1-20261108T103529Z/layout-1366x768-scale1.5-accepted/settings.png).
Không dùng screenshot chứng minh Gemini API đã hoạt động thật.

## 7. Production/evidence

Trước sửa lưu2.310SHA256 tại protected-before.json. Bao gồm runtime109ảnh/job
276880, toàn bộ tập bảo vệ cũ, DB/WAL/checkpoint/journal/diagnostic,120output
274872,113output276337, cache/model/config/BAT/spec và4EXE. Không sửa flag Free
trong config production; bool vẫnfalse. Không bật billing, liveAPI/AGY/MyMemory,
resume/retry57/106/111 hoặc tải ảnh/model. Không cài dependency/buildEXE.

Kiểm tra sau các test2.310/2.310hash không đổi, không mất file bảo vệ.
So byte xác nhận ResumeStore/multipage/AGY guards/native import/OCR/Offline/
MyMemory/translation numeric-glossary-cache logic/.gitignore/AGENTS không đổi.
Không đánh đồng normal pages với mọi trang đều có chữ đã dịch.

Evidence: `logs/stage3d1-20261108T103529Z/`, pointer logs/latest-stage3d1.json,
git-before.json, protected-before.json, before/, investigation.json,
runtime-state-before.json, preservation.json, testXML/JSON và ảnh Qt. Chỉ runtime
metadata allowlist trong investigation; không copy OCR/key/raw response vào report.

## 8. File thay đổi và Git & Fork Handoff

Root D:/TransTool, main, HEAD7ee5962…; baseline sạch/staged0/untracked0, khác
baseline Stage3D. Không hoàn nguyên hoặc ghi đè công việc chưa commit.

Nên review/commit:

- Source mới core/provider_preflight.py.
- Source sửa providers/gemini_api.py, core/pipeline.py (metadata/redaction),
  ui/main_window.py, ui/comic_sources.py, ui/settings_dialog.py, ui/provider_notice.py.
- Test mới tests/test_preflight_compact_ui.py; sửa tests/test_gemini_api.py.
- README.md, PROJECT_STATUS.md, docs/USER_GUIDE.md, docs/TROUBLESHOOTING.md,
  docs/STAGE3D1_API_PREFLIGHT_COMPACT_UI_REPORT.md.

Không commit logs/ảnh QA/cache/output/model/.venv/SQLite/EXE/config cá nhân/key.
.gitignore giữ nguyên; kiểm tra ignore runtime và visibility source/test/docs,
diff --check PASS. Status cuối11tracked modified/3untracked, staged0. Root và
branch/HEAD không đổi. Source/test/report mới không bị ignore; logs/cache/output/
config cá nhân/.env/dist bị ignore đúng. Không có runtimeDB/EXE/modelweights/secret
được track hoặc binary QA mới trong danh sách review. git-final.json lưu đầy đủ
status/stat/ignore và đường dẫn; chỉ kiểm tra chỉ đọc, không stage để đo diff.
Không tự untrack file; không staged/commit/tag/push/clean/reset/merge/rebase.

Mở Fork → Local Changes → review từng diff/fixture → tự stage source/test/docs
cần thiết → xem staged diff → tự commit nếu hài lòng. Commit gợi ý:
`fix(ui): clarify provider preflight and compact translation layout`.
**NO_COMMIT / NO_PUSH / NO_TAG / NO_DESTRUCTIVE_GIT**.

## 9. Thao tác tiếp theo

Người dùng tự kiểm tra project Free/không billing bằng link AI Studio rồi xác
nhận trong Cài đặt. Nếu phù hợp, chủ động Tiếp tục từ cache hoặc Thêm → Khôi
phục công việc đã lưu. Việc này không phải khuyến nghị thử API bằng chương
production để nghiệm thu Stage này. API thật/model eligibility/chất lượng/
latency/quota vẫn NOT_TESTED, cần duyệt QA nhỏ riêng theo Stage3D. Không nới
guard hoặc đổi model/paid tier để vượt lỗi. Không chuyển Stage4 hoặc build EXE.

Nếu ứng dụng đang mở từ trước hotfix, cần đóng an toàn và mở lại bản source để
nạp GUI mới. Không tự đóng tiến trình người dùng trong nhiệm vụ này. Khôi phục
từ journal không tự gửi OCR; vẫn phải bấm hành động tiếp tục rõ ràng sau thiết lập.
