# Website Adapter AI Guide — Image Translator VN

## Stage 2 — cache recovery và OCR override, 08/11/2026

Không thay adapter, downloader hay API retry để sửa OCR/MT. Pipeline chung
`core/pipeline.py` áp dụng `core/ocr_overrides.py` sau đọc OCR cache, trước MT;
profile `overrides/ocr_regions.json` cần hash+text+polygon chính xác và evidence/
version/enabled. Không hardcode chapter/page trong core. Chỉ ảnh có rule active
thêm fingerprint revision; pipeline job ID và118 checkpoint cũ giữ nguyên.
Cache OCR gốc không sửa. Sai hash/polygon giữ fallback/diagnostic, không fuzzy
match vùng khác. Không còn chữ cần MT có thể xuất nguyên byte nguồn như hoàn
tất bình thường, metadata `no_text_to_translate` phân biệt fallback do lỗi.

Stage2 thật đã dùng `LocalComicJob(retry_only=True)` qua GUI/QThread, không HTTP/
CDN, chỉ0074/0111. Chương274872:120 output,119 hoàn tất,1 fallback needs_retry111.
Guard ngày không nới vì raw target sai; numeric v2 chỉ siết thêm dấu số theo
test, signed cache v4 / unsigned legacy v3, không đổi pipeline identity để
không làm mất resume. Không sửa receipt118 trang hoặc dữ liệu job khác.
Xem báo cáo Stage2 và USER_GUIDE để đánh giá override trước khi thêm domain.

## Stage 1 — diagnostic, fallback và retry cache, 08/11/2026

Adapter tiếp tục đưa `ImageCollection` vào `sources/service.py` / ProcessingManager;
không tự OCR/dịch hoặc gắn quyền tải từ việc tìm URL. Lỗi pipeline có
`output_status`: TRANSLATED_SUCCESS / FALLBACK_ORIGINAL / FAILED_NO_OUTPUT;
PARTIAL_TRANSLATION được dành riêng, chưa bật xuất từng phần. Đủ file còn
fallback là `completed_with_warnings`, không phải translation success.

`core/diagnostics.py` ghi record giới hạn tại `logs/diagnostics/<job>/`, raw target
chỉ cho lỗi mới nếu Options.diagnostic_text bật. Không ghi signed CDN URL/cookie.
Lỗi tải trước pipeline dùng transfer job ID riêng, trường ảnh chưa biết để null.
`ui/review_dialog.py` cung cấp danh sách trang cần xem lại/log trong cả GUI nguồn
và tab thư mục. `ui/comic_sources.py` giữ chế độ retry riêng.

`LocalComicJob(retry_only=True)` đọc manifest/hash của ChapterCache, bỏ qua acquisition,
không gọi adapter/HTTP/CDN. Chỉ gửi các trang lỗi/fallback/thiếu output vào
ProcessingManager.run(only=...). Ánh xạ manifest theo đường dẫn ảnh, không theo
chỉ số trong tập retry (trang 111 vẫn là trang 111 khi retry hai trang). Giữ
job recipe hiện tại; diagnostic_text không tham gia identity. Không sửa OCR/MT
cache gốc để chữa lỗi, không đánh dấu fallback thành `done`.

Output dịch giữ nguyên; fallback truyện dùng thư mục `original/` trong cùng run.
Retry thành công tạo bản dịch riêng, giữ fallback cũ. Không cleanup chương còn
fallback. Không đổi provider/model hoặc cấu hình rồi hứa sẽ skip được output
của recipe cũ. Unit tests nằm ở `tests/test_error_fallback.py`; dữ liệu thật của
chương 274872 chưa được retry trong Stage 1. Chi tiết người dùng:
[USER_GUIDE.md](USER_GUIDE.md), [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Policy hiện hành — DEFAULT_ALLOW_PUBLIC của chủ ứng dụng, 07/11/2026

**Ưu tiên phần này cho vận hành hiện tại.** Chủ ứng dụng đã chọn
`download_policy="default_allow_public"`. Đây là **USER_POLICY_DEFAULT_ALLOW**,
không phải OFFICIAL_PERMISSION. Kết luận Stage A về quyền chính thức UNKNOWN
vẫn giữ nguyên. Các quy tắc gate chỉ cho tải sau grant ở phần lịch sử dưới đây
mô tả `verified_only`, không còn là mặc định sau chỉ dẫn mới của chủ ứng dụng.
Không sửa lịch sử thành website đã cấp phép; không dùng policy mới để vượt hạn
chế đã xác minh và áp dụng được hoặc chặn truy cập kỹ thuật.

### Các module và bốn lớp dữ liệu thật

- `sources/states.py`: ContentPermission UNKNOWN/ALLOWED/RESTRICTED;
  ContentPermissionEvidence(status,source_url,verified,applies_to_download,reason).
  DownloadDecision giữ content_permission/permission_source, policy, access_status,
  basis và state cuối. `allowed` là bridge tương thích adapters cũ, không tự
  tạo evidence. Kuaikan dùng ALLOWED_BY_USER_POLICY hoặc ALLOWED_BY_VERIFIED_PERMISSION,
  BLOCKED/UNKNOWN; không đổi content permission chỉ vì HTTP200/manifest.
- `sources/download_policy.py`: loader config đơn giản và pure decide_download.
  PUBLIC/free + ảnh safe + không applicable restriction/barrier có thể cho tải
  theo owner policy dù content permission UNKNOWN. Verified applicable restriction
  luôn BLOCKED. Thiếu URL discovery thì UNKNOWN; URL unsafe thì BLOCKED.
- `sources/kuaikan_dom.py`: AccessStatus vẫn là lớp truy cập; VIP/paywall/login/
  CAPTCHA/DRM flags được normalize thành RESTRICTED, không đổi evidence quyền.
- `sources/kuaikan.py`: giữ discovery results trong bộ nhớ, URL safety và technical
  barrier; permission_evidence theo chapter ID. download_decision thuần/không HTTP
  trên UI thread. download_chapter kiểm tra lại rồi gọi IO, không tự gọi từ analyze.
- `sources/kuaikan_download.py`: tải tuần tự có TLS/DNS public pin, host allowlist,
  redirect/timeout/quota/MIME/magic/Pillow verify+decode/hash/atomic/checkpoint.
  Trả ImageCollection files đã xác minh; signature nguyên bản, không lưu raw
  signed URL, không cookie/Referer/UA rotation/proxy bypass.
- `sources/service.py`/`cache.py`: LocalComicJob kiểm tra decision.allowed trong
  worker, nhận progress, tải vào incoming được cấp, ChapterCache.stage nhận
  download_decision để lưu provenance `adapter_download_by_user_policy` cùng
  permission UNKNOWN. Vẫn một ProcessingManager/OCR/MT theo batch.
- `ui/comic_sources.py`: sau images_ready cập nhật decision; chọn chương mới có
  thể bật Tải và dịch. Cập nhật download progress byte/trang, pause/resume/cancel
  qua JobControl. Khi CDN restriction xảy ra, đổi decision/BLOCKED và dừng.

Ví dụ gọi pure policy và scoped restriction (dữ liệu minh họa, không grant thật):

```python
from sources.download_policy import decide_download
from sources.states import ContentPermission, ContentPermissionEvidence

# chapter comes from verified public page/state; images_safe from URL discovery.
decision = decide_download(chapter, "default_allow_public", images_safe=True)
# allowed by owner policy can coexist with content_permission UNKNOWN.

# Only set this from actually verified, applicable source evidence:
adapter.permission_evidence[chapter.chapter_id] = ContentPermissionEvidence(
    status=ContentPermission.RESTRICTED,
    source_url=verified_source_url,
    verified=True,
    applies_to_download=True,
    reason=verified_restriction_reason,
)
```

Không lấy ví dụ/test fixture làm evidence website thật. Không tự gán verified
cho một URL điều khoản hoặc mặc định grant theo private use. Nếu nghiên cứu
domain mới phát hiện hạn chế áp dụng, tích hợp evidence scoped tương ứng trước
khi cho download; owner default không xóa hạn chế đó. Quyền UNKNOWN và không có
hạn chế áp dụng đã xác minh thì cho phép theo cấu hình chủ ứng dụng, không bắt
xin lại quyền mỗi chương hoặc tự áp verified_only trái với lựa chọn hiện tại.

### Cấu hình và workflow hằng ngày

Config `core.paths.CONFIG/download_policy.json`: một key download_policy, default
`default_allow_public` kể cả file vắng. Giá trị `verified_only` giữ được workflow
strict; malformed/unsupported config fail closed về verified_only. Mở lại app sau
khi đổi cấu hình. Không sửa settings cũ, không thêm hệ thống tài khoản/quản trị.

Tab URL → phân tích → chọn chương → phân tích ảnh nếu cần → **Tải và dịch**.
Direct chapter tự discovery nhưng không tự chọn/tải. Topic chỉ lấy danh sách,
không tự crawl/tải116 ảnh. Có thể phân tích/chọn batch theo giới hạn hiện có.
Tải chỉ do hành động chủ động, không do paste URL hoặc checkbox đơn lẻ.

IO defaults:200 ảnh/chương,32MB/ảnh,512MB/chương,2GB cache,2 attempts tối đa
cho lỗi transient,30s deadline mỗi attempt, connect/read tối đa10s và tối đa3
redirect hop. Vượt giới hạn báo lỗi, không cắt chương âm thầm. 401/403/429,
HTML/CAPTCHA/DRM/unsafe redirect dừng; không tìm header/Referer/UA khác. Cancel
tại checkpoint, socket đang chờ có thể cần đợi timeout. Giữ cache/part/receipt
cho resume; không tự xóa nguồn/unfinished jobs.

Download receipt chứa SHA path/URL, file/hash/bitmap metadata, selection/sample
và decision snapshot; không raw query. Cache hit phải verify lại. Không dùng
file hỏng, unowned file hoặc manifest bị đổi làm lý do ghi đè. `limit=` chỉ dùng
chọn mẫu QA có ghi rõ discovered/requested/sample; production bình thường dùng
toàn bộ chương được chọn trong cap, không hardcode mẫu chapter/116 ảnh.

### Acceptance mới và giới hạn đã kiểm chứng

- **LIVE_IMAGE_DOWNLOAD_PASS**:2 ảnh thật281106,2 GET200,689114 byte, JPEG1280×1000,
  magic/decode/hash/cache PASS. Không401/403/429 thật, không tải lại khi cache hit.
- **KUAIKAN_URL_TO_TRANSLATION_E2E_PASS — mẫu2 ảnh theo user policy**, không phải
  official permission hoặc full116: OCR/Argos2 vùng/2 bản dịch/export2 ảnh thật.
  GUI QThread/LocalComicJob sample pause/resume/responsive PASS, dùng verified
  image cache; không mock OCR/MT. Backup/evidence và lỗi diagnostic giữ nguyên tại
  `logs/kuaikan-default-allow-20261107T101940Z/`, báo cáo download mô tả đầy đủ.
- Pytest/unittest **207 PASS/10 SKIPPED**,27 test mới. Historical strict tests chạy
  với verified_only; default tests kiểm tra ALLOWED_BY_USER_POLICY cùng UNKNOWN
  permission. Không xóa lịch sử hoặc sửa output OCR/MT để tạo PASS.
- Local single/folder/Offline/cache/output/Windows Qt smoke PASS. Chưa kiểm thử
  full116/multi-chapter/live socket cancel/TTL hoặc chất lượng MT toàn truyện.
  Không build EXE,4 EXE cũ giữ nguyên và chưa chứa thay đổi. Source launcher
  run_source.bat dùng policy/downloader mới.

Khi thêm domain: giữ interface/registry/pipeline hiện có, dùng pure policy để
tách owner choice khỏi evidence. Downloader website mới vẫn cần verified public
access + URL safety, hạn chế áp dụng, tests và live sample riêng; không gán mọi
website SUPPORTED chỉ vì Kuaikan đã tải được2 ảnh.

## Lịch sử cổng quyền tải verified_only — Kuaikan, kiểm tra 07/11/2026

Đã hoàn thành Stage A image download validation. **Case C / DOWNLOAD_UNKNOWN**,
Stage B **BLOCKED_BY_POLICY** do chưa có grant phù hợp cho tải CDN/cache/OCR/MT/
export cá nhân bằng ứng dụng ngoài. Đây không phải lỗi HTTP hoặc kết luận mọi
cách đọc cá nhân đều bị cấm. Metadata/discovery live vẫn PASS;0 request ảnh,
không downloader mới hoặc Kuaikan URL-to-translation E2E. Không sửa production.
Chi tiết nguồn/phạm vi/bằng chứng: **[KUAIKAN_IMAGE_DOWNLOAD_VALIDATION.md](KUAIKAN_IMAGE_DOWNLOAD_VALIDATION.md)**.
Regression mới **180 PASS/10 SKIPPED**, thêm8 policy tests; local Offline/GUI PASS.

### Giai đoạn nghiên cứu policy một lần, không hỏi lại mỗi chương

1. Đọc đúng tài liệu chính thức của domain, ngày kiểm tra/phạm vi/version. Trang
   agreement có thể chứa nhiều tài liệu; Kuaikan `/webs/agreement` có serviceData,
   policyData và upload terms khác nhau trong public state. Không dùng search
   snippet hoặc thỏa thuận tác giả upload làm license cho app đọc/tải bên ngoài.
2. Phân loại **OFFICIAL_PERMISSION, OFFICIAL_RESTRICTION, TECHNICAL_OBSERVATION,
   INSUFFICIENT_EVIDENCE**. Tách quyền xem, lưu trong app chính thức, tải tự động,
   xử lý cá nhân và xuất/phân phối. Chỉ theo đúng phạm vi nguồn đã xác minh.
3. Điều khoản cộng đồng/VIP/AI training không tự áp cho mọi chương free hoặc mọi
   OCR/MT inference. Quyền ghi storage trong privacy policy không tự thành quyền
   tải CDN ngoài app. Personal/noncommercial là phạm vi sử dụng, không thay grant.
4. Trước gate chỉ phân tích URL trong bộ nhớ: scheme/host/path/query/duplicates/
   metadata/order/variants. Không HEAD/GET CDN, dò/gia hạn/chỉnh chữ ký hoặc log
   query thật. Hình dạng sign/t không chứng minh TTL, quyền hoặc khả năng truy cập.
5. Gate ALLOWED chỉ sau bằng chứng có hiệu lực đủ phạm vi; RESTRICTED nếu hạn
   chế áp dụng được xác minh; chưa rõ/mâu thuẫn thì UNKNOWN. UNKNOWN vẫn giữ
   metadata/discovery/nhập ảnh hợp lệ, chỉ dừng phần tải. Không biến grant một nội
   dung thành quyền toàn site/VIP hoặc cho phép tải hàng loạt mặc định.
6. Nếu UNKNOWN/RESTRICTED thì dừng Stage B, ghi BLOCKED_BY_POLICY/NOT_TESTED cho
   download/bitmap/cache ảnh web/E2E tương ứng. Không tạo ảnh giả để đạt E2E, không
   viết downloader hoặc HTTP mock rồi gọi live download PASS. Nhiệm vụ Stage A
   vẫn có thể hoàn thành đúng phạm vi với một quyết định chưa cho phép tải.
7. Chỉ khi đủ điều kiện mới thử lượng ảnh nhỏ theo giới hạn người dùng; tiếp tục
   mọi kiểm tra TLS/DNS/redirect/size/MIME/magic/decode/hash/atomic/cache/cancel/
   retry hữu hạn và dừng401/403/429. Dùng bridge ImageCollection/ChapterCache/
   LocalComicJob/ProcessingManager hiện có; không nhân bản OCR/MT.

Không thêm hệ thống tài khoản/quản trị/quyền phức tạp hoặc checkbox tự khai để
lách gate cho ứng dụng cá nhân. Không hỏi quyền lặp lại khi đã có nguồn xác minh
còn áp dụng; đánh giá lại khi điều khoản/quyền/phạm vi thay đổi. Không liên hệ
Kuaikan/chủ quyền bằng tool khi chưa được người dùng yêu cầu gửi liên hệ.

### Test và nhãn của download gate

`tests/test_kuaikan_download_policy.py` kiểm tra PUBLIC/HTTP200/image discovery/
policy URL/legacy flag không tự ALLOWED, missing source vẫn UNKNOWN và locked/
restricted vẫn RESTRICTED. Positive grant của generic fixture adapter chỉ test
wiring UI/pipeline, không là giấy phép Kuaikan. Grant thật chưa có thì ghi rõ
positive Kuaikan case NOT_TESTED; không tạo fixture quyền giả để báo đã xác minh.

Giữ riêng LIVE_HTTP_PASS, IMAGE_DISCOVERY_PASS, DOWNLOAD_POLICY_VERIFIED,
DOWNLOAD_ALLOWED/RESTRICTED/UNKNOWN, LIVE_IMAGE_DOWNLOAD_PASS,
MOCKED_DOWNLOADER_PASS, LOCAL_OFFLINE_E2E_PASS,
KUAIKAN_URL_TO_TRANSLATION_E2E_PASS, BLOCKED_BY_POLICY và NOT_TESTED.
URL parser PASS hoặc local Offline E2E PASS không thay download/Kuaikan E2E PASS.

Hiện Kuaikan vẫn dùng download_decision hiện có: chương281106 PUBLIC nhưng
DOWNLOAD_UNKNOWN, download_chapter còn là stub. Bước tiếp cần nguồn/chấp thuận
đủ phạm vi tải/lưu/xử lý dự kiến và điều kiện nền tảng; không cần DOM mới hoặc
cookie/token. Trong lúc chờ, dùng ảnh đã lưu hợp lệ qua tab cục bộ.

## Cập nhật live Kuaikan — 07/11/2026 từ 09:33 UTC

**LIVE_HTTP_PASS / IMAGE_DISCOVERY_PASS** qua MainWindow tab URL, QThread và
`fetch_public_html` thật cho topic6677/chapter281106. Phiên mới có mạng và không
proxy; không bỏ guard hoặc thay transport. Kết quả ENVIRONMENT_BLOCKED09:05 UTC
ở các mục lịch sử không còn là trạng thái của phiên có mạng này.

Khác biệt đã có bằng chứng: initial HTTP HTML topic không có `.title-item`,
nhưng `topic_info.comics` có26 ID/title; reader có2 img-box/2 URL DOM duy nhất,
nhưng `comic_info.comic_images` có116 URL. Không cần browser automation.

### Quy tắc dùng state khi initial HTML chưa render đủ

- `sources/kuaikan_dom.py:discover_chapters` ưu tiên mục DOM nếu có. Nếu không,
  dùng public `topic_info.comics` trong **chính HTTP response**, kiểm tra topic
  ID với URL. Giữ thứ tự mảng, không sort theo ID hoặc dựa số chương; phân loại
  main/phụ và reading status theo record. Báo `analysis.source='embedded_state'`
  và `order_source='topic_info.comics'`. Topic đã kiểm thử có26 mục/23 main/3 phụ;
  các số này không là hằng trong parser.
- Reader ưu tiên DOM đầy đủ như trước. Nếu DOM ít hơn manifest, chỉ dùng các
  URL literal trong `comic_info.comic_images` khi chapter ID/title khớp, URL/domain
  hợp lệ và các path/thứ tự DOM đã thấy nhất quán. Giữ thứ tự manifest; ưu tiên
  `url1280` rồi `url` nếu có hợp lệ, không biến đổi hoặc tạo URL/chữ ký.
- `DiscoveryList.analysis.discovery_source='embedded_manifest'` và
  `ChapterImage.source_attribute='comic_info.comic_images.url1280'` (hoặc url)
  phân biệt với thẻ img. Ghi `dom_unique_valid_urls`, `manifest_valid_urls`,
  `manifest_rejected_entries`, identity/consistency. Không gọi116 URL metadata
  là116 thẻ img SSR. Nếu path/order mâu thuẫn, giữ kết quả DOM và warning thay vì
  ghép tùy ý; thiếu/invalid/trùng record thì ghi partial, không đoán phần còn lại.
- Cờ locked/restricted vẫn chặn discovery. PUBLIC reading không cấp download.
  `image_list_complete=None`, dimensions là metadata chứ không bitmap được decode;
  không đoán height của biến thể scale chưa có thông tin tương ứng.
- Các captured DOM đầy đủ giữ behavior cũ:116 URL từ data-src/DOM. So sánh với
  live bằng ID, title, URL path và thứ tự; không đòi chữ ký query phải giống nhau.

### Dữ liệu mẫu và kiểm thử của sửa SSR

`tests/test_kuaikan_ssr.py` thêm10 ca: topic state/no DOM, order, partial/duplicate,
wrong identity, reader manifest với2/0 DOM URLs, invalid URL, DOM/state conflict,
locked và dimension. Fixture `*_http_state_sanitized.html` là **public state từ
HTTP thật đã whitelist/reserialize + DOM skeleton viết tay**, query signature
dummy; không phải raw HTTP HTML. `kuaikan_http_state_provenance.json` ghi hash
response và cách lọc. Không commit raw body/comments/account/signature.

Kết quả full pytest/unittest **172 PASS/10 SKIPPED**, gồm captured DOM và14
mocked HTTP cũ. Live được kiểm chứng riêng, không lấy fixture PASS thay thế:
`logs/kuaikan-http-20261107T093330Z/gui-live-verified.json`, cùng screenshot2 tab.
Diagnostic subclass chỉ profile HTTPResponse rồi gọi nguyên worker.run, không
mock network/parser/GUI. Một lượt QA trước FAIL do đo `.analysis` sau Qt đã
chuyển DiscoveryList thành list; evidence giữ tại gui-live.json và giải thích
trong báo cáo. App/GUI không sửa để né lỗi phép đo.

Hai production file sửa: `sources/kuaikan_dom.py`, `sources/kuaikan.py` (mô tả/
status). Literal decoder, transport, GUI, pipeline, models/native guard giữ nguyên.
Daily source hiện nhập URL và discovery tự động, không cần gửi lại DOM; không
tuyên bố đã hỗ trợ download hoặc website đầy đủ. DOWNLOAD_UNKNOWN, downloader
NOT IMPLEMENTED,0 ảnh tải, không build EXE. EXE cũ chưa chứa sửa này.

## LIVE HTTP ACQUISITION VALIDATION

Giai đoạn này thực hiện **sau khi parser PASS trên DOM mẫu**. Mục tiêu là
kiểm chứng thu thập dữ liệu từ URL trong môi trường chạy thật; không nghiên cứu
lại domain, không biến DOM upload thành thao tác đọc chương hằng ngày.

### Quy trình cho Codex

1. Đọc PROJECT_STATUS/báo cáo capture và source transport/adapter/worker đang dùng.
   Giữ selector/schema đã có bằng chứng; không bắt người dùng lấy lại hai DOM.
2. Kiểm tra interpreter, OS/sandbox, network-disabled flag, proxy đang áp dụng
   trước khi gọi. Chỉ lưu proxy có/không, loại, loopback/port và cờ credential;
   không ghi URL đăng nhập proxy hoặc toàn bộ biến môi trường.
3. Thử số GET nhỏ cho đúng URL topic/chapter được người dùng cung cấp bằng
   **transport hiện có**, không preload DOM trong adapter live. Không đổi User-Agent,
   endpoint, proxy hoặc xóa guard để thử đường khác. Đếm DNS/connect/HTTP send
   nếu cần phân biệt lỗi trước kết nối với response website.
4. Nếu sandbox/proxy từ chối trước kết nối, ghi **ENVIRONMENT_BLOCKED**, status
   null, dữ liệu response/parser live NOT_TESTED. Không kết luận HTTP403,
   CAPTCHA/paywall hoặc parser hỏng khi chưa có response. Dừng phần cần live;
   tiếp tục mocked HTTP và captured DOM/local regression. Chỉ chạy lại khi môi
   trường hợp lệ thay đổi, không retry cùng lỗi. Không tự thay chính sách mạng.
5. Khi nhận response thật, ghi status, Content-Type, charset/encoding, số byte,
   URL cuối và redirect được cho phép bằng diagnostic metadata đã lọc tại response
   boundary. `fetch_public_html` trả **str**, không trả response object; không
   gọi DOM preload/fixture là HTTP200. Không log raw headers/body/cookie/token/
   chữ ký. Có thể giữ SHA hoặc thống kê thay cho nội dung nhạy cảm.
6. Chạy parser trực tiếp trên HTML/state nhận được, không sửa HTML thủ công,
   không lấy ID/ảnh từ capture ghép vào response. So sánh cấu trúc và trường
   cần thiết với DOM mẫu: topic ID/title/count/items/mapping/order/main-extra;
   reader ID/title/topic/prev-next/img/lazy/manifest/path/order. Chữ ký query có
   thể thay đổi; đối chiếu URL path, không tạo/sửa/làm mới chữ ký.
7. Chỉ sửa tối thiểu khi có bằng chứng: response đủ và parser PASS thì không
   sửa; response đủ nhưng parser FAIL thì sửa parser; response thiếu DOM nhưng
   có public state đủ dùng thì đọc state đã xác minh, không thực thi JavaScript.
   Giữ captured DOM tests PASS, không hardcode số chương/ảnh hoặc ID mẫu.
8. Nếu HTML/state thực sự thiếu dữ liệu, ghi chính xác phần có/thiếu và lý do
   không thể giải quyết bằng parser thuần. Chỉ **đề xuất** acquisition khác sau
   bằng chứng đó; chờ người dùng quyết định, không tự thêm Playwright/Selenium.
   401/403/429/CAPTCHA/paywall thì dừng, không retry/né giới hạn.
9. Kiểm tra GUI URL tab → ComicSourceWorker QThread → adapter → transport →
   parser. Topic chỉ lấy danh sách; URL chương không cần topic trước. Không tự
   chọn/crawl mọi chương; giữ metadata khi bước sau lỗi, progress/heartbeat và
   cancel/timeout. Khi không có mạng, dùng **mock transport** để kiểm tra đường
   nối này, ghi rõ MOCKED_HTTP_PASS, không gọi GUI live URL PASS.
10. Chạy pytest/unittest, captured DOM, local single/folder/cache/output,
    OCR/MT Offline thật, GUI smoke/E2E phù hợp một lần. Không đổi models/native
    guard/dependencies. Cập nhật báo cáo/guide/status/registry và phân loại theo
    bằng chứng. Không build nếu nhiệm vụ không yêu cầu.

### API thật cho lượt live được cho phép

```python
from sources.kuaikan import KuaikanAdapter

topic_adapter = KuaikanAdapter()  # fresh instance: no preloaded captured DOM
comic = topic_adapter.get_comic_info(topic_url)
chapters = topic_adapter.get_chapters(comic)  # reuse the fetched page

reader_adapter = KuaikanAdapter()
reader_comic = reader_adapter.get_comic_info(chapter_url)
chapter = reader_adapter.get_chapters(reader_comic)[0]
images = reader_adapter.get_chapter_images(chapter)  # page reuse, no image GET
decision = reader_adapter.download_decision(chapter)  # still independent
```

Đường gọi: `sources/kuaikan.py:_html` →
`sources/metadata_http.py:fetch_public_html` → `_PinnedHTTPS` (stdlib http.client,
TLS verify + DNS public-IP pin). Transport chủ động từ chối sandbox flag/proxy;
không bỏ proxy để làm chạy được. Proxy bắt buộc ở môi trường đích cần thiết kế
hỗ trợ riêng khi được yêu cầu và có thông tin, không sửa mù trong lượt bị chặn.

`tests/test_kuaikan_discovery.py:KuaikanLiveTests` là opt-in live metadata/reader/
image discovery, không download; chỉ kích hoạt khi phiên thực thi có quyền mạng
hợp lệ. `tests/test_kuaikan_http_runtime.py` là **14 ca mocked HTTP**, giữ transport/
adapter/parser/Qt worker thật, thay DNS/connection bằng simulated response. Fixture
là sanitized excerpt, không phải response HTTP mới hoặc toàn bộ chương.

### Nhãn nghiệm thu độc lập

| Nhãn | Điều kiện được ghi |
| --- | --- |
| CAPTURED_DOM_PARSER_PASS | Parser chạy trên file DOM thật đã lưu; không nói HTTP runtime |
| MOCKED_HTTP_PASS | Test response mô phỏng, ghi rõ lớp được mock và payload nguồn |
| LIVE_HTTP_PASS | Có response thật từ URL được phép và parser chạy trực tiếp trên response đó |
| LIVE_HTTP_FAIL | Có bằng chứng lỗi kết nối/response/parser live cụ thể, tách website với môi trường |
| ENVIRONMENT_BLOCKED | Môi trường/guard từ chối; status null nếu không nhận response |
| IMAGE_DISCOVERY_PASS | Có URL ảnh đúng thứ tự; ghi rõ captured/mock/live, không đồng nghĩa đã tải |
| DOWNLOAD_UNKNOWN | Chưa xác minh điều kiện tải; HTTP200/public-readable/image URLs không chuyển ALLOWED |
| OFFLINE_REGRESSION_PASS | Inference OCR/MT và output pipeline hiện có chạy thật |
| NOT_TESTED | Phần chưa thực hiện; EXE chưa thử không được lấy source PASS thay thế |

**HTTP PASS không phải download PASS.** Kuaikan downloader vẫn UNKNOWN / NOT
IMPLEMENTED. Không dùng cờ giả hoặc đổi nguồn web thành LOCAL để lách quyết định
tải. Khi quyền tải chưa xác minh, giữ discovery phù hợp và tab nhập ảnh đã lưu hợp lệ.

Lịch sử lượt runtime **07/11/2026 09:05 UTC** (trước phiên có mạng ở đầu guide): hai lần gọi transport bị guard
sandbox/proxy từ chối trước DNS/TCP, **ENVIRONMENT_BLOCKED**; chưa có status,
HTML/Nuxt/chapters/images live. Không sửa production source. Captured parser vẫn
PASS; 14 mocked tests mới và regression **162 PASS/10 SKIPPED**. Báo cáo:
`docs/KUAIKAN_CHAPTER_281106_ANALYSIS.md`, evidence
`logs/kuaikan-http-20261107T090510Z/`. Không cần cung cấp lại DOM; bước tiếp là
phiên được cấp mạng để kiểm chứng cùng transport/adapter, không nghiên cứu lại site.

## Quy tắc ưu tiên — ứng dụng cá nhân và DOM mẫu (07/11/2026)

**Image Translator VN là ứng dụng cá nhân.** Ưu tiên giải pháp nhỏ, ổn định, dễ
bảo trì. Không thêm tài khoản, quản trị, onboarding hoặc hệ thống tự khám phá
website. Chỉ tự động hóa khi công việc lặp lại hoặc cần xử lý số lượng lớn.

- **Nghiên cứu một lần mỗi domain:** người dùng có thể mở F12, đọc HTML, lưu DOM
  sau render và cung cấp dữ liệu mẫu. AI dùng dữ liệu này viết adapter tổng quát.
  Không cần Playwright/Selenium chỉ để thay thao tác nghiên cứu một lần.
- **Sử dụng hằng ngày:** nhập URL thuộc domain đã tích hợp → ứng dụng tự thu thập
  dữ liệu bằng cơ chế đã xác minh → chọn chương → phát hiện URL ảnh → chỉ tải
  khi điều kiện cho phép → cache → pipeline Offline cũ → output. Không thiết kế
  luồng bắt người dùng cung cấp DOM lại cho mỗi chương.
- Parser chạy với DOM mẫu **không chứng minh** transport HTTP lấy được cùng dữ
  liệu khi dùng ứng dụng. Đây là hai khả năng phải kiểm thử và báo cáo riêng.

Phần cập nhật này và registry cuối tài liệu thay thế những nhận định lịch sử
"chưa có DOM thật"/"fixture-only" trong các mục cũ; không xóa hướng dẫn còn đúng.

### USER-PROVIDED DOM WORKFLOW

Đầu vào ưu tiên cho mỗi domain mới:

```text
SITE_NAME: <tên website>
SITE_DOMAIN: <hostname chính xác>
TOPIC_URL: <URL truyện thật>
TOPIC_DOM_FILE: <đường dẫn DOM danh sách chương>
CHAPTER_URL: <URL chương thật>
CHAPTER_DOM_FILE: <đường dẫn DOM trang đọc>
```

Hai DOM là dữ liệu nghiên cứu quan trọng. Phân tích file không bắt buộc truy cập
Internet. Khi nhiệm vụ chỉ cho phép offline, không thử live hoặc điều tra sandbox.

**Cách lấy DOM mẫu bằng Chrome/Edge:**

1. Mở trang truyện, đợi nội dung render xong.
2. Mở **F12 → Elements**, chọn phần tử `html` hoặc vùng danh sách chương.
3. Chọn **Copy → Copy outerHTML**, lưu file văn bản UTF-8 đuôi `.dom.html`.
4. Với trang đọc chương, cuộn vùng đọc để các ảnh lazy-loading xuất hiện rồi
   sao chép DOM vùng ảnh; giữ heading, breadcrumb và điều hướng nếu có.
5. Kiểm tra và loại thông tin riêng tư: dữ liệu tài khoản, lịch sử đọc, bình
   luận người dùng, cookie/token hoặc chữ ký URL. Không gửi thông tin đăng nhập.
   Nếu không chắc phần nào cần giữ, gửi vùng công khai tối thiểu; không gửi HAR.

| Dạng dữ liệu | Chứng minh được gì |
| --- | --- |
| View Page Source | Source ban đầu mà trình duyệt nhận, chưa phản ánh đầy đủ JS/lazy |
| HTML response | Byte/text của HTTP response; phải ghi cách thu thập và status riêng |
| DOM sau JavaScript render | Cây hiện tại trong Elements; có thể chứa state, lịch sử và dữ liệu người dùng |
| DOM vùng danh sách chương | Có thể đủ mục/title/link nhưng thiếu heading hoặc state ánh xạ ID |
| DOM vùng nội dung ảnh | Có thể đủ ảnh đã lazy-load; không tự chứng minh toàn bộ chương |

Không yêu cầu cookie, token, phiên đăng nhập hoặc bước vượt CAPTCHA/paywall.
Chữ ký CDN có sẵn trong DOM chỉ dùng phân tích trong bộ nhớ; báo cáo/fixture phải
che hoặc thay giá trị, không tạo/chỉnh chữ ký để thử tải.

**Quy trình AI khi nhận bộ DOM:**

1. Đọc AGENTS, PROJECT_STATUS, guide và adapter/test thật trước khi sửa.
2. Kiểm tra từng file tồn tại, kích thước, UTF-8/BOM, SHA-256; không sửa bản gốc.
3. Kiểm tra riêng tư bằng cấu trúc/thống kê, tránh in nguyên script/URL nhạy cảm.
4. Phân tích topic DOM: scope, từng item, tiêu đề, ID/href hoặc ánh xạ ID thật,
   thứ tự, khóa, main/extra, số công bố so với số thực có trong DOM.
5. Phân tích reader DOM: URL/ID/title, topic, prev/next, vùng ảnh và lazy attrs.
6. Ghi bằng chứng cho selector/schema/hostname; không đoán endpoint hoặc số trang.
7. Viết parser tổng quát domain, không gắn dữ liệu truyện mẫu vào logic.
8. Tạo fixture **đã làm sạch** từ capture, ghi nguồn SHA và thao tác rút gọn;
   fixture viết tay vẫn phải phân loại riêng. Không commit DOM nguyên bản riêng tư.
9. Viết unit test cho success, partial, malformed, sai ID, duplicate, locked,
   invalid URL, lazy/placeholder/UI; không sửa test để che lỗi.
10. Chạy captured DOM test trên cả hai bản gốc, kiểm tra hash trước/sau.
11. Tích hợp parser với adapter/registry hiện có; transport HTTP là công đoạn riêng.
12. Kiểm tra worker/GUI giữ metadata khi bước chương hoặc ảnh lỗi.
13. Chạy regression ảnh đơn/folder/cache/OCR/MT/xuất ảnh, không thay pipeline.
14. Cập nhật registry, guide, PROJECT_STATUS và báo cáo bằng chứng.
15. Ghi live HTTP/download/EXE NOT TESTED nếu chưa chạy; chỉ ghi BLOCKED khi đã
    thực sự thử đúng phạm vi và có bằng chứng bị chặn. Không build nếu chưa yêu cầu.

### Khi DOM chưa đủ

- **Topic không có href:** tìm ID/title trong dữ liệu công khai nhúng đã quan sát.
  Chỉ ánh xạ khi ID thật khớp tiêu đề duy nhất. Không dùng số học, vị trí mảng
  hoặc ID mẫu để tạo chương. Nếu thiếu, yêu cầu đúng vùng danh sách hoặc đoạn
  dữ liệu công khai chứa ánh xạ ID/title; không bắt lấy lại toàn bộ trang.
- **Reader chưa có URL ảnh:** kiểm tra `src`, các `data-*`, `srcset`, `picture`
  thực xuất hiện và placeholder. Nêu rõ thiếu vùng nào/thuộc tính nào; có thể
  cần DOM vùng ảnh sau cuộn. Không suy số ảnh còn lại hoặc đổi hostname bằng đoán.
- **Parser lỗi một bước:** giữ metadata/kết quả từng phần, trả warning/count và
  StructureChanged có ý nghĩa. Không biến lỗi cấu trúc thành lỗi quyền truy cập.
- **Parser tốt nhưng URL runtime chưa hoạt động:** báo đúng khoảng trống thu
  thập HTML/DOM; không biến DOM upload thủ công thành yêu cầu sử dụng hằng ngày.
  Không mở rộng sang browser automation nếu nhiệm vụ không yêu cầu.

Quy ước dữ liệu mẫu tương lai: `website_samples/<domain>/topic-example.dom.html`
và `chapter-example.dom.html` dưới workspace. Chỉ là quy ước, không hệ thống quản
lý mới. Không di chuyển hai DOM Kuaikan đang ở `output/kuaikan-capture/`.

### Kuaikan: cấu trúc đã xác minh bằng DOM thật

- `sources/kuaikan_dom.py`: `.TopicEpisode` → `.title-item`, giữ thứ tự DOM.
  Capture không có href trong các mục này. Ánh xạ title duy nhất với ID trong
  `data[0].res.data.topic_info.comics`; tạo canonical URL theo route reader đã
  xác minh, ghi `ChapterInfo.url_source='embedded_id+verified_route'`.
- `sources/kuaikan_state.py`: decoder dữ liệu Nuxt IIFE bị giới hạn grammar,
  alias/literal/assignment hằng và sparse `Array(N)` nhỏ đã quan sát; **không
  eval/exec JavaScript**, không chạy onclick/script trang, không gọi endpoint.
  Chỉ trả `topic_info/comic_info`, không serialize toàn state người dùng.
- Reader: `.step-comic`, liên kết topic/prev/next thật và
  `.comicDetails .imgList .img-box`. `img alt` khớp tên chương; ưu tiên `data-src`,
  khử trùng theo path trong vùng này. Manifest `comic_info.comic_images` dùng
  đối chiếu/dimensions; sau kiểm chứng live SSR, còn dùng discovery khi DOM chưa
  đủ theo identity/order/domain checks ở đầu guide. Chỉ URL có thật trong state,
  không suy hoặc tạo trang/URL mới.
- Capture topic: 26 mục/26 ánh xạ/23 main/3 extra, href literal 0. Capture reader:
  130 img toàn trang, 122 img nội dung, 116 URL duy nhất, 6 phần tử trùng, khớp
  116 mục manifest. Không coi đây là số cố định của website.
- `AccessStatus.PUBLIC` (`public_readable`) chỉ phản ánh các cờ đọc của snapshot;
  **DownloadDecision vẫn UNKNOWN**. Không biến ảnh xem được thành quyền tải.
- URL HTTPS tn1.kkmh.com có cặp `sign`/`t` đúng dạng đã quan sát được giữ trong
  bộ nhớ để discovery; CLI che mọi query value và lưu hash thay thế. Không lưu
  các chữ ký nguyên bản vào fixture, báo cáo, config hoặc log.
- `DiscoveryList.analysis` ghi số quan sát, scope và provenance. Ảnh có thể có
  `dimensions_source='embedded_metadata'`, chưa phải kích thước giải mã bitmap.
  Khớp manifest của snapshot không đủ khẳng định toàn chương từ server;
  `image_list_complete=None`.

Ví dụ gọi **API thực**, hoàn toàn offline khi preload hai file:

```python
from pathlib import Path
from sources.kuaikan import KuaikanAdapter

adapter = KuaikanAdapter()
adapter.load_document(topic_url, Path(topic_dom_file).read_text(encoding='utf-8-sig'))
comic = adapter.get_comic_info(topic_url)
chapters = adapter.get_chapters(comic)
adapter.load_document(chapter_url, Path(chapter_dom_file).read_text(encoding='utf-8-sig'))
reader_comic = adapter.get_comic_info(chapter_url)
chapter = adapter.get_chapters(reader_comic)[0]
images = adapter.get_chapter_images(chapter)  # URLs discovered, no downloads
decision = adapter.download_decision(chapter)  # independent of image discovery
```

Khi thêm domain: tạo `sources/<site>.py`, parser và `tests/test_<site>.py`, đăng
ký `ADAPTERS` ở `sources/registry.py`. Interface thật ở contracts và ví dụ Kuaikan
là điểm tham chiếu; không sao chép selector website này sang website khác.
GUI `ui/comic_sources.py` gọi cùng API qua ComicSourceWorker trong tab URL;
thông thường không cần sửa GUI. Lỗi metadata/chapters/images có phase riêng.
Downloader tương lai chỉ nối vào `LocalComicJob(adapter=...)` sau khi quyết định
ALLOWED và implementation/download test thật đạt; dùng ImageCollection →
ChapterCache → ProcessingManager hiện có. Khi không được phép, giữ metadata,
chapter/image discovery phù hợp và hướng dẫn nhập ảnh đã lưu hợp lệ qua tab cục bộ.

### Checklist hai giai đoạn

**Nghiên cứu một lần cho domain:**

- [ ] Có URL topic/chapter và hai DOM đọc được, rõ phạm vi/nguồn/encoding.
- [ ] Đã kiểm tra riêng tư; bản gốc bảo toàn, fixture làm sạch có provenance.
- [ ] Selector, mapping chương, URL ảnh/lazy/order có bằng chứng.
- [ ] Parser PASS trên DOM thật; unit fixture success/error/partial PASS.

**Sử dụng lặp lại trong ứng dụng:**

- [ ] Thu thập HTML/DOM từ URL trong runtime thật đã được kiểm chứng.
- [ ] Metadata/danh sách chương/URL ảnh thật và thứ tự đúng, có cảnh báo partial.
- [ ] Điều kiện đọc và tải đánh giá riêng; downloader chỉ chạy khi được phép.
- [ ] Download/cache/cancel/resume/retry có kiểm thử thật nếu được phép.
- [ ] OCR/MT Offline và output đúng, ảnh nguồn không đổi, GUI không treo.
- [ ] Regression local single/folder và adapter cũ PASS.
- [ ] EXE kiểm thử thật nếu được yêu cầu build; chưa thử thì NOT TESTED.

Báo cáo riêng: MANUAL FIXTURE TEST; SANITIZED CAPTURE EXCERPT TEST;
CAPTURED REAL DOM TEST; LIVE HTTP TEST; IMAGE DOWNLOAD TEST;
OFFLINE OCR/MT REGRESSION; EXE TEST. Một nhóm PASS không thay nhóm khác.

### ADD WEBSITE ADAPTER FROM USER-PROVIDED DOM

```text
Workspace: <đường dẫn dự án Image Translator VN>
Website name / SITE_NAME: <tên website>
Domain / SITE_DOMAIN: <hostname>
Topic URL / TOPIC_URL: <URL truyện thật>
Topic DOM path / TOPIC_DOM_FILE: <file UTF-8>
Chapter URL / CHAPTER_URL: <URL chương thật>
Chapter DOM path / CHAPTER_DOM_FILE: <file UTF-8>

Đọc AGENTS.md, PROJECT_STATUS.md và docs/WEBSITE_ADAPTER_AI_GUIDE.md.
Đây là ứng dụng cá nhân. Nghiên cứu domain một lần từ DOM tôi cung cấp;
tự động hóa các bước sử dụng lặp lại qua adapter hiện có.
Kiểm tra hai file thật trước khi sửa. Phân tích topic và reader, kiểm tra riêng
tư, chapter ID/title/order/mapping/lazy/image URL từ dữ liệu thực có.
Viết parser domain tổng quát, fixture làm sạch và captured DOM test.
Không hardcode truyện/chương/URL ảnh mẫu hoặc bịa endpoint/dữ liệu thiếu.
Không tự nghiên cứu bằng browser automation. Không yêu cầu tôi nộp DOM mỗi lần
dịch chương. Tách parser khỏi HTTP acquisition; chưa thử live thì NOT TESTED.
Không nhầm DOM test với live HTTP/download test; không bật downloader khi chưa
xác minh điều kiện tải. Không vượt paywall/DRM/login/CAPTCHA.
Giữ source/model/.venv/EXE/BAT/spec/config/dữ liệu cũ và native import guard;
không tạo lại OCR, dịch Offline hoặc GUI. Dùng ImageCollection/ChapterCache/
ProcessingManager hiện có khi có ảnh hợp lệ.
Chạy regression phù hợp, cập nhật guide/registry/status/báo cáo thật.
Nếu thiếu dữ liệu, chỉ yêu cầu vùng DOM cụ thể còn thiếu. Không build trừ khi
tôi yêu cầu riêng. Báo rõ mức nghiên cứu đã đạt và khoảng trống runtime còn lại.
```

## Cập nhật ưu tiên — nhận URL chương và image discovery, 07/11/2026

Đọc cùng `docs/KUAIKAN_CHAPTER_281106_ANALYSIS.md`. URL chương do người dùng xác
minh `/webs/comic-next/281106` giúp sửa router chỉ nhận topic trước đây. Adapter
giờ nhận **topic hoặc chapter ID bất kỳ hợp lệ**, không gắn một chapter ID vào logic.
Parser mới là fallback HTML/DOM tiêu chuẩn, **chưa nghiệm thu DOM Kuaikan live**.

### Kiến trúc và API mới

- `sources/kuaikan_dom.py`: normalize phân loại topic/chapter; Document/ReaderPage;
  discover_chapters, parse_reader, discover_images. Không gọi mạng, không execute JS.
- `KuaikanAdapter.url_kind`, `chapter_id_from_url`, `load_document`,
  `parse_reader_html`, `parse_chapters_html` là các API thật để debug với captured DOM.
- `get_comic_info(chapter_url)` không yêu cầu lấy topic. ComicInfo.source_url là URL
  đầu vào; source_kind=chapter, topic_url và comic_id chỉ có khi reader có link cha
  hợp lệ. Không rõ thì null, không giả ID truyện từ chapter ID.
- `get_chapters` với source_kind chapter trả đúng chương của URL đã nhập, kèm cảnh
  báo không đại diện toàn truyện. Với topic, chỉ lấy a/href thực ở mục chương.
- `DiscoveryList` kế thừa list để giữ interface cũ, bổ sung warnings/complete.
  ChapterInfo.content_kind: main/supplementary/unknown; chapter_number lấy từ nhãn;
  order_index là thứ tự DOM/collection, không phải chapter ID hoặc suy thứ tự phát hành.
- `get_chapter_images` chỉ fetch HTML chương công khai qua transport cũ; tuyệt đối
  không fetch img. Kết quả ChapterImage status=discovered, local_path=None.
- Worker URL chương có thể tự chạy discovery sau metadata; topic chỉ phân tích
  ảnh các chương đã chọn qua nút Phân tích ảnh chương. Giới hạn 10 chương/lượt,
  tuần tự; gặp 401/403/429 dừng, không né giới hạn.

### DOM JavaScript, lazy loading và debug bằng URL chương

Khi topic cho 0 link, **đi vào một URL chương thật trước** để kiểm tra reader/title/
topic association/prev/next/img. Không suy URL bằng số học từ ID mẫu. So sánh initial
HTML với DOM sau render/scroll bằng trình duyệt thông thường với nội dung được phép.
Nếu công cụ không đọc được, yêu cầu file DOM đã lưu thay vì tự sáng tác selector/API.
Không giả HTTP 200/403 chỉ từ lỗi fetch của công cụ.

Không execute script/hydration/onclick tùy ý để lấy dữ liệu. JSON nhúng chỉ xử lý
khi xác minh được schema công khai và test capture; chưa biết thì báo thiếu dữ liệu.
DOM do người dùng cung cấp ưu tiên vùng công khai đã loại tài khoản/token, lưu ở
output/ (không Git); không lấy cookie/HAR hoặc điều khiển đăng nhập/CAPTCHA.

Image parser phải phân biệt img UI/avatar/ad/placeholder với page. Fallback hiện
so tên accessible với tiêu đề chương và hostname được cung cấp, loại khu vực UI
semantic, URL giả/nội bộ/data URI và query nhạy cảm. Đọc data-srcset/data-src/
data-original/data-lazy-src/srcset/src, giữ DOM order, khử trùng, chọn biến thể
srcset hợp lệ. Đây là quy tắc bảo thủ, không được coi là cấu trúc Kuaikan đã live PASS.
Nếu site dùng picture/CSS background/JS khác cần kiểm chứng và bổ sung theo DOM thật.

`width/height` HTML không chứng minh kích thước bitmap; ChapterImage.dimensions_source
ghi html_attributes, còn natural dimensions/decoded dimensions cần dữ liệu thật.
Hai img có thể chỉ là viewport/chunk/preview; image_list_complete=None cho đến khi
có cơ sở đầy đủ. Không nói tổng chương có 2 ảnh chỉ vì thấy 2 phần tử.

### IMAGE_LIST_READY khác DOWNLOAD_READY

Source panel giữ metadata_state/chapter_state khi image parser lỗi; thêm
image_states theo chapter ID và IMAGE_LIST_READY/ERROR. Hiển thị số URL đã phát
hiện, cảnh báo chưa đủ chương; không chuyển DownloadDecision.UNKNOWN thành ALLOWED.
Parser URL ảnh không phải downloader. Có URL ảnh thật vẫn phải kiểm tra điều kiện
tải trước khi gọi ImageCollection → ChapterCache → ProcessingManager như phần sau.
Chưa có comic ID thật thì service không tạo cache web bằng ID giả.

### Kiểm thử / công cụ file

- tests/test_kuaikan_discovery.py: URL/ID/title/href/order/main-extra/lock/lazy/
  URL safety và worker state. Hai fixture *_manual.html viết tay, không là capture.
- Live metadata, live chapter, live image list là ba test opt-in riêng
  (`ITVN_KUAIKAN_LIVE=1`, chỉ khi môi trường cho phép HTTP). Không download ảnh.
- `scripts/analyze_kuaikan_html.py --url <url> --html <file> --input-kind rendered_dom`
  phân tích file offline, lưu JSON trong output/kuaikan-html-analysis, không lấy ảnh.
  File parser PASS không phải live PASS; manual_fixture có nhãn rõ.

Checklist bổ sung: nhận hai loại URL; không yêu cầu topic list cho URL chương;
chapter ID lấy từ href/input thật; parent ID unknown để null; link 15 từ topic
capture được kiểm chứng; giữ partial list/warnings; phân loại main/extra; kiểm tra
lazy/source attributes/placeholder/URL; image list chưa bật tải; ghi rõ count scope;
metadata giữ khi lỗi; regression single/folder/Offline; không ghi đè build cũ.

Registry cập nhật: router và parser topic/chapter/image PASS trên DOM thật đã lưu;
live HTTP chưa thử trong lượt DOM. Downloader UNKNOWN / NOT IMPLEMENTED.
Không đánh dấu website đầy đủ SUPPORTED hoặc EXE mới PASS từ parser test.

## Cập nhật GUI và trạng thái — 07/11/2026, lượt cải tiến tab

**Đọc phần này trước các phần kiến trúc cũ bên dưới.** MainWindow hiện có ba tab
nhúng **Ảnh đơn / Thư mục ảnh / Link truyện online**, không mở dialog nguồn lớn.
`ComicSourcesDialog` chỉ là compatibility host cho script/QA cũ. Các hướng dẫn
HTTP/cache/pipeline/quyền truy cập bên dưới vẫn áp dụng; cập nhật cụ thể như sau.

### GUI hiện tại

- `ui/main_window.py`: QScrollArea → cấu hình OCR/dịch chung → QTabWidget.
  Tab thư mục giữ ProcessingWorker, bảng/progress/preview/checkpoint cũ.
- `ui/comic_sources.py`: `ComicSourcesPanel(QWidget)` nhúng riêng cho ảnh đơn và
  URL. Mỗi panel giữ nguồn/output/trạng thái riêng. `fixed_kind=0/2` ẩn combo cũ.
  `options_factory` lấy cấu hình font/OCR/provider hiện tại trước khi xử lý.
- `busyChanged` khóa tab bar và cấu hình chung khi có worker; cancel của tác vụ
  hiện tại vẫn hoạt động. Root closeEvent chờ hủy an toàn mọi worker.
- Phân tích, retry danh sách chương và xử lý ảnh chạy trong ComicSourceWorker.
  `retry_chapters` dùng ComicInfo đã lấy, không xóa metadata. Đổi URL mới mới xóa
  dữ liệu truyện cũ, tránh hiển thị nhầm truyện.
- Ảnh đơn tự chọn file vừa nhập để có thể bắt đầu; chương URL không tự chọn.
  Chương UNKNOWN được chọn để đọc/kiểm tra; chương LOCKED/RESTRICTED không chọn.
- Cấu hình folder cũ giữ nguyên; panel lưu riêng `single_source.json` và
  `url_source.json`. `MainWindow(persist_settings=False)` dùng cho QA, không ghi
  đường dẫn tạm vào cấu hình thật. Không dùng False trong launcher người dùng.

### Các trạng thái độc lập

Định nghĩa thật tại `sources/states.py`:

| Nhóm | Trạng thái và ý nghĩa |
| --- | --- |
| AnalysisState | IDLE, URL_INVALID, ANALYZING, METADATA_READY/METADATA_ERROR, CHAPTER_LIST_READY/CHAPTER_LIST_ERROR, CONNECTION_ERROR, ACCESS_ERROR, USAGE_LIMIT, TECHNICAL_ERROR |
| metadata_state | Giữ METADATA_READY khi bước chương thất bại |
| chapter_state | Tiến trình/lỗi lấy danh sách chương riêng, không làm mất metadata |
| ChapterInfo.access_status | UNKNOWN/PUBLIC/ALLOWED/LOCKED/RESTRICTED/LOCAL; PUBLIC chỉ nói trạng thái đọc snapshot; `chapter_access()` trả CHAPTER_ACCESS_* |
| DownloadDecision | DOWNLOAD_UNKNOWN/ALLOWED/RESTRICTED/FAILED, reason, evidence_url tùy chọn |
| ProcessingState | IDLE, READY_TO_TRANSLATE, TRANSLATING, COMPLETED, CANCELLED, FAILED |

`download_enabled` là thuộc tính thông tin cũ, **không** dùng khóa URL hoặc làm
cơ sở bật tải. Registry không khóa phân tích dựa vào quyền tải. Worker gửi lỗi có
`phase` (url/metadata/chapters/process) và `category` riêng: url, website, analysis,
network, access, usage_limit, download_policy, cache hoặc lỗi kỹ thuật.
HTTP 401/403 là access; HTTP 429 là usage_limit và dừng không retry. Thiếu parser
không phải thiếu quyền; metadata lỗi không phải chương bị khóa.

### Quyết định tải và kết nối pipeline

Adapter triển khai `download_decision(chapter)` như một phép đánh giá thuần, nhanh,
không HTTP trên UI thread. Trả UNKNOWN khi chưa đủ bằng chứng; RESTRICTED khi có
hạn chế xác định; chỉ ALLOWED khi có cơ sở truy cập **và sử dụng/tải** được kiểm
chứng. Lưu lý do/tham chiếu phù hợp, không hỏi xác nhận lặp lại thay cho xác minh.
Trang công khai/HTTP 200 không tự chứng minh quyền tải. Không hardcode theo ID truyện.

Nút Tải và dịch chỉ bật khi có danh sách chương thành công, có chương chọn,
mọi quyết định tương ứng ALLOWED và adapter thực sự override download_chapter.
UNKNOWN chỉ chặn thao tác tải, không chặn nhập URL/phân tích/chọn chương/retry.

`LocalComicJob` hiện nhận thêm `adapter=` cho nguồn website, giữ nguyên site_id và
provenance. Worker kiểm tra lại policy mỗi chương trước khi gọi downloader.
`download_chapter(chapter, cache_dir, control)` phải trả **ImageCollection** ảnh đã
xác minh, nằm dưới đúng cache_dir được cấp (`_incoming/<site>/<comic>/<chapter>`).
Service từ chối collection sai vùng, giữ provenance `verified_adapter_download`,
đưa qua ChapterCache rồi gọi đúng ProcessingManager gốc. Không đổi nguồn web thành
LOCAL để lách điều kiện; không tạo OCR/MT thứ hai. Hiện chưa có downloader Kuaikan.

Downloader của website mới vẫn phải đáp ứng HTTPS/allowlist/DNS/redirect, MIME/
magic/decode, quota, timeout, retry có giới hạn, 401/403/429 dừng, manifest/resume và
không xóa nguồn như hướng dẫn phía dưới. Method stub hoặc cờ ALLOWED không thay
cho việc triển khai và live test thật.

### Kuaikan hiện tại và kiểm thử

- `get_comic_info` đọc HTML công khai và giữ HTML cuối trong bộ nhớ; get_chapters
  dùng lại HTML đó hoặc fetch công khai khi retry. Không bịa endpoint.
- HTML thiếu mục chương → lỗi cấu trúc; có mục nhưng chưa xác minh ID/link → lỗi
  parser cụ thể. Metadata giữ nguyên. Link ảnh chưa được xác minh → StructureChanged.
- DownloadDecision hiện UNKNOWN trừ chương khóa rõ ràng; không khẳng định website
  cấm mọi cách đọc cá nhân. Dùng tab thư mục cho ảnh đã lưu hợp lệ.
- Lượt DOM hiện tại không thử mạng; runtime HTTP NOT TESTED. Kết quả quan sát
  browser trước đây không thay live HTTP runtime PASS. Chưa xác minh cách tải
  động/phân trang live; capture topic hiện có đủ 26 mục theo số công bố.

Thêm `tests/test_source_tabs.py` (fixture/mock được ghi nhãn) và
`scripts/validate_source_tabs.py` (MainWindow/QThread/OCR/MT thật). Entry point/EXE:
`--validate-source-tabs`. Test quyền UNKNOWN vẫn phân tích/chọn được, ALLOWED bật
đúng nút dù cờ cũ False, metadata giữ khi lỗi chương, các nhóm lỗi riêng, worker
kiểm tra lại policy, provenance web giữ đúng, config không bị QA ghi đè.

Checklist bổ sung: ba tab độc lập; ẩn thành phần không liên quan; cuộn cửa sổ nhỏ;
file/folder Offline cũ PASS; URL lỗi có thể retry; không mất metadata; không gộp
parser/network với access; không tự chọn chương; kiểm tra nút theo từng chương;
không có kết nối mạng từ OCR/MT; giữ config/model/BAT/EXE cũ; test chính EXE tên mới.

Registry hiện tại: Kuaikan metadata/chapter/image parser CAPTURED_DOM_VERIFIED,
runtime HTTP NOT TESTED trong lượt DOM, download policy UNKNOWN, downloader
NOT IMPLEMENTED; không ghi SUPPORTED đầy đủ.

Ngày: 07/11/2026. Đọc `AGENTS.md` và phần mới nhất `PROJECT_STATUS.md` trước khi sửa.
Tài liệu mô tả source hiện có, kể cả phần chưa được phép/chưa kiểm chứng.
**Không coi sự tồn tại của adapter là website đã được hỗ trợ đầy đủ.**

## 1. Kiến trúc thực tế

Luồng đã triển khai:

```text
MainWindow → QTabWidget → ComicSourcesPanel (ảnh đơn / URL), folder UI cũ
  Ảnh đơn / thư mục ảnh hoặc thư mục các chương
    → ComicSourceWorker(local) → discover_local → ComicInfo + ChapterInfo[]
    → người dùng chọn chương (không tự chọn)
    → ComicSourceWorker(process) → LocalComicJob
    → ImageCollection → ChapterCache → ImageCollection(cache)
    → ProcessingManager.run(only=paths) [pipeline gốc]
    → PaddleOCR → Offline provider → inpainting → TextRenderer → staging
    → kiểm tra ảnh + xuất nguyên tử vào thư mục người dùng chọn

  URL → ComicSourceWorker(url) → registry.resolve_adapter
    → public metadata HTML → ComicInfo → get_chapters
    → get_chapter_images (discovery độc lập) → DownloadDecision
    → chỉ tải khi ALLOWED và có downloader thật; UNKNOWN không chặn phân tích
```

| File | Vai trò |
| --- | --- |
| `sources/contracts.py` | Data model, WebsiteAdapter ABC, nhóm lỗi |
| `sources/registry.py` | ADAPTERS tuple và resolve_adapter theo hostname chính xác |
| `sources/kuaikan.py` | URL topic/chapter, adapter parser và policy độc lập |
| `sources/kuaikan_dom.py`, `sources/kuaikan_state.py` | DOM chapter/image và decoder literal Nuxt có giới hạn, không JS execution |
| `sources/security.py` | HTTPS/domain/DNS, chống địa chỉ nội bộ, tên Windows, containment |
| `sources/metadata_http.py` | HTML công khai tối đa 2 MB, TLS/DNS pin, redirect cùng allowlist, không cookie |
| `sources/collection.py` | ImageCollection, natural sort, discover_local, bridge Options/only |
| `sources/cache.py` | Kiểm tra giải mã ảnh, hash, quota, copy cục bộ, manifest, dọn cache có điều kiện |
| `sources/service.py` | LocalComicJob dùng pipeline gốc và publish_image không ghi đè |
| `ui/comic_sources.py` | Panel nhúng ảnh đơn/URL, bảng chương, QThread, progress, điều khiển, retry |
| `ui/main_window.py` | Ba tab nguồn; luồng thư mục cũ được giữ |
| `core/pipeline.py` | ProcessingManager, TranslationService, JobControl dùng chung |
| `core/runtime.py`, `ui/__init__.py` | Native import guard: CT2/Torch trước Paddle/Qt |
| `core/paths.py` | ROOT/CACHE/CONFIG khi chạy source/EXE |
| `tests/test_comic_sources.py` | Unit/CV/IO/Qt; HTML và HTTP mock được ghi rõ |
| `scripts/validate_comic_sources.py` | GUI/QThread/ảnh truyện cục bộ/OCR/dịch thật, không tải web |
| `scripts/qa_common.py` | Fingerprint bao gồm sources/*.py, giữ gate GUI/E2E cũ |
| `run_source.bat` | Launcher source mới; không thay BAT/EXE cũ |

Không có downloader ảnh HTTP được kích hoạt. Không có backend trình duyệt/login.
Luồng ảnh đơn/thư mục/chương dùng chung pipeline gốc, không nhân bản OCR/MT.

### Interface và kiểu dữ liệu

Đọc định nghĩa thật trong `sources/contracts.py`:

```python
class WebsiteAdapter(ABC):
    site_id: str
    hosts: tuple[str, ...]
    download_enabled = False
    def can_handle(self, url: str) -> bool: ...
    def normalize_url(self, url: str) -> str: ...
    def get_comic_info(self, url: str, control=None) -> ComicInfo: ...
    def get_chapters(self, comic: ComicInfo, control=None) -> list[ChapterInfo]: ...
    def get_chapter_images(self, chapter: ChapterInfo, control=None) -> list[ChapterImage]: ...
    def download_chapter(self, chapter: ChapterInfo, cache_dir: Path, control=None): ...
```

Đây là chữ ký interface thật, không phải triển khai downloader mẫu. Base
`download_chapter` báo thiếu implementation bằng SourceError; không có hành vi tải ẩn.

- `ComicInfo`: site_id, comic_id, source_url, title/author/chapter_count/status và
  main_chapter_count tùy chọn. `chapter_count` là số công bố nếu chỉ biết metadata;
  `len(chapters)` mới là số chương thực lấy được.
- `ChapterInfo`: chapter_id, chapter_title, chapter_number (không phải ID),
  chapter_url, access_status, order_index; local_source và image_count tùy chọn.
- `ChapterImage`: image_index, source_url/local_path, content_type, width/height,
  download_status. Không biết thì `None`, không bịa số/trạng thái.
- `AccessStatus`: UNKNOWN/PUBLIC/LOCKED/RESTRICTED/LOCAL/ALLOWED. PUBLIC chỉ là
  đọc công khai theo snapshot; DownloadDecision vẫn riêng. ALLOWED cần bằng chứng
  quyền tải, không đồng nghĩa HTTP 200 hoặc chương không hiện khóa.
- Lỗi: InvalidURL, UnsupportedWebsite, StructureChanged, AccessRestricted,
  NetworkUnavailable, CacheError; tất cả có `category` để UI giải thích.

### Cache, output và điều khiển

- Dùng `core.paths.CACHE/online_comics/<site>/<comic>/chapter_<id>/manifest.json`.
  Hiện chỉ namespace `local` có ảnh: đó là bản sao người dùng cung cấp.
- Cache mỗi ảnh: index, file, source, magic/format xác định bởi Pillow,
  width/height, content_type, bytes, SHA256; sau dịch có output/output_sha256,
  pipeline_job_id và cảnh báo. File dở `.part` không bị tự xóa.
- 32 MB/ảnh, 65 triệu pixel, tổng cache mặc định 2 GB; kiểm tra dung lượng trống.
- Resume kiểm tra hash thực tế, không chỉ sự tồn tại. Nguồn/cache bị đổi → báo lỗi,
  không ghi đè. Giữ nguyên cache nếu chưa xong/cancel/error.
- Bỏ chọn giữ cache chỉ xóa các bản sao đã xác minh sau khi mọi output thành công.
  Không xóa nguồn, manifest, output hoặc staging.
- Pipeline gốc vẫn xuất staging tại `ROOT/output/online_comics_work/...`; publisher
  mới sao chép ảnh đã xác minh sang thư mục chọn. Không nới validator của pipeline cũ.
  Staging có namespace theo database checkpoint để các profile/test riêng không
  va chạm output mà database của mình không có receipt.
- Output: `<safe title>__<comic id>/<order>_<safe chapter>__<id>/run_<job id>/0001.ext`.
  Khác recipe/model/cấu hình có run ID khác; output đã đổi thủ công không bị ghi đè.
- Mỗi batch một PaddleOCREngine và TranslationService, tái sử dụng qua các chương.
  `LocalComicJob` cưỡng chế Offline, `allow_online_fallback=False`.
- `JobControl.checkpoint()` dùng chung cho scan/copy/inference/publish;
  pause/resume/cancel từ GUI. Không dùng QThread.terminate hoặc worker cho từng câu.
- UI lưu lựa chọn ảnh/output/giữ cache tại `CONFIG/online_comics.json` riêng,
  không lưu cookie/token/URL chứa tài khoản.

## 2. Quy trình phân tích website mới

Nếu có bộ USER-PROVIDED DOM, ưu tiên quy trình offline ở đầu tài liệu. Những
bước truy cập mạng dưới đây chỉ thực hiện khi phạm vi nhiệm vụ cho phép; không
bắt buộc live để nghiên cứu parser từ file, không cần tự động hóa trình duyệt.

1. Nhận URL mẫu, domain; audit source/status/tests trước khi sửa.
2. Mở URL thật bằng công cụ được phép; ghi URL/ngày/cách quan sát, không đoán endpoint.
3. Đọc điều khoản/quyền tải, robots và giới hạn kỹ thuật. Phân biệt đọc công khai,
   lấy metadata, tải ảnh và tái phân phối. Không suy ra quyền tải từ HTTP 200.
4. Nếu chưa có bằng chứng/cách tải hợp lệ, đặt DOWNLOAD_UNKNOWN (RESTRICTED khi có hạn chế xác định); vẫn làm phần
   metadata công khai phù hợp và đường nhập ảnh do người dùng cung cấp.
5. Xác minh đường URL và ID truyện. Lưu metadata tối thiểu, không lưu bình luận cá nhân.
6. Xác minh raw HTML/JSON thực được cung cấp công khai; có pagination/lazy loading?
   Không đặt endpoint nội bộ phỏng đoán hoặc thực thi JS tùy ý từ trang.
7. Xác minh từng ID/link/tên/thứ tự chương, chương phụ/thông báo và trạng thái khóa.
   Số chương công bố không thay cho danh sách đã phân tích.
8. Với chương được phép tải: xác minh trang đọc, thứ tự ảnh, host CDN thật, định dạng,
   Referer công khai nếu cần; không lấy cookie/token bí mật.
9. Ghi trường hợp thiếu dữ liệu, giới hạn, 401/403/429/CAPTCHA/paywall; dừng phần bị chặn.
10. Thiết kế adapter nhỏ theo interface, fixture có nhãn nguồn/giấy phép.
11. Unit test và live test tách biệt; fixture tự tạo không phải capture HTML website.
12. Kết nối worker/UI, chạy regression luồng cũ, cập nhật registry/tài liệu/báo cáo.

## 3. Thêm adapter vào source

Tạo `sources/<site>.py` kế thừa WebsiteAdapter. Dùng `https_url(url, self.hosts)` và
full path validation trong normalize_url. Không regex gắn một comic ID. Chỉ chấp
nhận hostname chính xác đã xác minh. Lỗi URL phải là InvalidURL để can_handle hoạt động.

Đăng ký instance ở `sources/registry.py` trong `ADAPTERS`. Chỉ thêm host được kiểm
chứng; không wildcard toàn Internet. Khi hỗ trợ bare/mobile/CDN cần kiểm tra riêng.

`sources/kuaikan.py` là ví dụ thật về normalize_url, parse_topic_html và cách chặn
phần chưa xác minh. **Không sao chép selector h3 sang website mới khi chưa quan sát.**

Ví dụ sử dụng bridge thật hiện có, không tạo engine OCR khác:

```python
from sources.collection import ImageCollection
from core.pipeline import ProcessingManager

collection = ImageCollection.discover(local_chapter_directory)
options, selected_paths = collection.request(existing_options)
summary = ProcessingManager(options, cache, control, emit).run(only=selected_paths)
```

Để có cache/chương/publisher đầy đủ, dùng `LocalComicJob`: LOCAL dùng đường dẫn ảnh
người dùng; website cần `adapter=` và các quyết định tải ALLOWED như phần cập nhật.
Giữ provenance website, không đổi site_id thành local để lách gate và không nhân
bản pipeline. Test local phải còn PASS sau thay đổi này.

### Điều kiện bổ sung downloader trong tương lai

Downloader chưa tồn tại ở bản này. Chỉ viết sau khi quyền và cấu trúc thật được xác minh:

- Chỉ HTTPS + allowlist đã quan sát cho trang/CDN; kiểm tra DNS/IP mọi redirect,
  chặn localhost/private/link-local/địa chỉ đặc biệt, ngăn DNS rebinding.
- Tôn trọng proxy/chính sách mạng; không bỏ proxy hệ thống khi bị lỗi. Metadata
  transport hiện từ chối môi trường có proxy và sandbox chặn mạng.
- Giới hạn timeout, số kết nối, tốc độ, số lần retry/backoff; không retry 401/403/429
  hoặc CAPTCHA. Không tự đổi domain/proxy/User-Agent nhằm né cơ chế bảo vệ.
- MIME và magic bytes và giải mã thật, không lưu HTML lỗi thành ảnh; byte/pixel/quota
  và đĩa trống; stream có checkpoint; file tạm rồi publish nguyên tử.
- Bằng chứng quyền tải, verified image list, hash/manifest/resume; không tải lại ảnh
  hợp lệ; URL hết hạn chỉ refresh bằng đường công khai đã được cho phép.
- Không lưu URL có chữ ký/token bí mật vào log/config; không thêm auth/cookie scraper.
- Không cleanup job chưa xong; không xóa dữ liệu người dùng.

Không bật một cờ download_enabled đơn lẻ để tuyên bố đã tích hợp tải ảnh.

## 4. Kiểm thử và những việc không được làm

Tạo `tests/test_<site>.py` với fixture phân biệt thủ công/capture. Chạy:

```bat
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\run_tests.py --evidence-dir logs\new-site-unit-<stamp>
.venv\Scripts\python.exe scripts\validate_comic_sources.py
.venv\Scripts\python.exe scripts\smoke_gui.py
.venv\Scripts\python.exe scripts\validate_e2e.py
```

Live URL test chỉ opt-in khi được phép, ghi số chương/ảnh/download/OCR/MT/export
thực; ít nhất 2 topic khác nếu truy cập được. Không thay live bằng HTTP mock.
Kiểm thử một ảnh cục bộ, folder, batch, pause/resume/cancel/retry/cache, model loading,
font/output và đường dẫn Unicode. Test thực không khẳng định chất lượng dịch đạt.

Không tạo lại dự án/OCR/MT/GUI/.venv; không xóa source/model/backup/EXE/evidence;
không nâng dependency/DLL/PATH để phục vụ scraper; không phá native import guard;
không bịa endpoint/chapter/ảnh; không hardcode truyện; không vượt paywall/DRM/login/
CAPTCHA; không xóa/sửa ảnh nguồn; không chỉnh output test để báo PASS.

Chỉ build khi các gate hiện có đạt, giữ BAT/spec/EXE cũ; build tên mới, kiểm tra
chính EXE với Offline và nguồn mới. Source PASS không phải EXE PASS.

## 5. Checklist nghiệm thu adapter mới

- [ ] Quyền truy cập và tải tự động được xác minh; nếu chưa, công bố gate bị khóa.
- [ ] URL/host/normalize hợp lệ; SSRF/redirect/private DNS bị từ chối.
- [ ] Metadata đúng, không bịa trường chưa biết.
- [ ] Danh sách/ID/link/thứ tự/quyền chương đúng; không nhầm số công bố.
- [ ] Image list/thứ tự/host/quyền tải đúng.
- [ ] Download thật hợp lệ; MIME/magic/decode/quota/timeout/rate limit hoạt động.
- [ ] Cache/manifest/cancel/resume/tamper/cleanup hoạt động.
- [ ] OCR và Offline translation thật dùng pipeline hiện có.
- [ ] Output đúng thứ tự/kích thước/Unicode, ảnh gốc còn nguyên, không ghi đè.
- [ ] GUI không treo, lựa chọn không tự đánh dấu, lỗi rõ theo công đoạn.
- [ ] Pause/resume/cancel/retry và local single/folder regression PASS.
- [ ] Các adapter cũ còn PASS.
- [ ] EXE PASS thực tế nếu build; nếu chưa ghi NOT TESTED.
- [ ] Báo cáo phân biệt PASS thật / mock / FAIL / SKIPPED / BLOCKED / NOT TESTED.

## 6. Registry website

| Website | Adapter | Metadata | Chapters | Download | URL → Offline → Output |
| --- | --- | --- | --- | --- | --- |
| kuaikanmanhua.com (www only) | sources/kuaikan.py | LIVE_HTTP_PASS + CAPTURED_DOM_PARSER_PASS | 26 items/23 main/3 phụ;116 manifest URLs,2 DOM URLs in SSR | Owner DEFAULT_ALLOW_PUBLIC → ALLOWED_BY_USER_POLICY; content permission UNKNOWN; restrictions win | LIVE_IMAGE_DOWNLOAD_PASS + URL-to-translation sample2 images PASS; full116 NOT_TESTED; no EXE build |

Ảnh người dùng cung cấp: luồng riêng `local`, không phải website được hỗ trợ.
Xem `ONLINE_COMIC_TEST_REPORT.md` để biết kết quả đã chạy của luồng này.

## HOW TO ADD A NEW COMIC WEBSITE

Prompt mẫu, thay ba dòng URL/domain:

```text
Tiếp tục Image Translator VN trong workspace hiện tại, không tạo lại dự án.
Đọc AGENTS.md, PROJECT_STATUS.md và docs/WEBSITE_ADAPTER_AI_GUIDE.md trước.
Website URL: <https://website.example/>
Domain: <website.example>
URL truyện mẫu: <https://website.example/comic/example>
URL chương mẫu (nếu có): <URL chương thật để debug reader trước khi topic list hoạt động>

Audit kiến trúc, phân tích website thật và điều khoản/quyền tải trước khi viết code.
Tích hợp adapter riêng qua interface/registry, dùng chung GUI worker, cache và
ProcessingManager; bảo toàn Offline/native import guard/model/EXE cũ.
Không bịa endpoint hoặc vượt cơ chế kiểm soát truy cập. Nếu tải chưa được phép,
khóa downloader, tiếp tục metadata phù hợp và nhập ảnh người dùng cung cấp.
Chạy unit + live hợp lệ + local regression; không gọi mock là live PASS.
Cập nhật registry, guide, PROJECT_STATUS và báo cáo số chương/ảnh thực tế.
Chỉ build tên mới khi gate đạt; kiểm thử EXE nếu build, giữ bản cũ.
```
