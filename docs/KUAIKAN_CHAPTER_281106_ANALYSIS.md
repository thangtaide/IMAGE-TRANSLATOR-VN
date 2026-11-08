# Kuaikan chapter 281106 — phân tích và sửa adapter, 07/11/2026

## Cập nhật DEFAULT_ALLOW_PUBLIC của chủ ứng dụng — 07/11/2026

Policy mới cho phép PUBLIC an toàn theo **USER_POLICY_DEFAULT_ALLOW**, không
thay bằng chứng quyền nội dung UNKNOWN và không ghi OFFICIAL_PERMISSION.
Downloader đã nối cache/LocalComicJob/pipeline gốc. Live2 ảnh đầu281106:
2 GET200/689114 byte/JPEG1280×1000/decode-cache PASS; OCR/MT/output2 ảnh sample
thật PASS, GUI QThread/pause/resume PASS. Không tải cả116, không build EXE.
**Pytest/unittest207 PASS,10 SKIPPED**. Lịch sử Stage A dưới giữ nguyên;
quyết định strict lúc đó không còn là chính sách vận hành mặc định sau chỉ dẫn
mới. Xem **[báo cáo đầy đủ](KUAIKAN_IMAGE_DOWNLOAD_VALIDATION.md)** và evidence
`logs/kuaikan-default-allow-20261107T101940Z/` để biết phạm vi USER_POLICY/test.

## IMAGE DOWNLOAD VALIDATION — 07/11/2026

Giai đoạn A đã kiểm tra điều khoản chính thức/đúng tài liệu nhúng và cấu trúc CDN.
Gate **case C: DOWNLOAD_UNKNOWN**, Stage B **BLOCKED_BY_POLICY** vì chưa có grant
phù hợp cho third-party auto download/cache/OCR/MT/export cá nhân. Không gán hạn
chế cộng đồng/VIP/AI training thành cấm toàn bộ inference chương free.
Xem **[KUAIKAN_IMAGE_DOWNLOAD_VALIDATION.md](KUAIKAN_IMAGE_DOWNLOAD_VALIDATION.md)**
để biết nguồn, phạm vi điều khoản, quyết định và giới hạn.

Metadata thật vẫn **LIVE_HTTP_PASS / IMAGE_DISCOVERY_PASS**: chương281106 PUBLIC,
free/unlocked/noVIP/noPay,116 URL manifest tn1.kkmh.com có sign/t. Không HEAD/GET
CDN,0 ảnh/0 byte, không biết TTL hoặc bitmap. Không tạo downloader, không nối
ảnh web vào cache/OCR/MT, không build EXE. Production source giữ nguyên.

Thêm8 policy tests; **pytest/unittest180 PASS,10 SKIPPED,0 FAIL**. GUI Windows
Qt ảnh đơn/folder/OCR/Argos/cache/output, local E2E và smoke thật PASS; không
coi đó là Kuaikan URL-to-translation E2E. 102 file bảo vệ giữ hash,5 model
integrity PASS,4 EXE/config/DOM/BAT/native guard bảo toàn. Evidence:
`logs/kuaikan-download-policy-20261107T095823Z/`. Bước tiếp là grant đủ phạm vi,
không phải dò chữ ký hoặc yêu cầu DOM mới. Lịch sử live/parser dưới đây giữ nguyên.

## LIVE HTTP RUNTIME VALIDATION — phiên có mạng, 07/11/2026 từ 09:33 UTC

**LIVE_HTTP_PASS và IMAGE_DISCOVERY_PASS trên hai URL mẫu qua cửa sổ chính /
QThread / fetch_public_html thật.** Transport giữ nguyên. Đã sửa tối thiểu parser
để dùng public Nuxt state có sẵn trong HTTP HTML ban đầu khi DOM chưa render đủ.
Không tải ảnh, không bật downloader, không thay OCR/MT và không build EXE.

### Quyền thực thi và HTTP response thực

Phiên mới Windows build26200 / Python `.venv` **3.10.9 x64**, cấu hình thực thi
`danger-full-access`, mạng enabled. `CODEX_SANDBOX_NETWORK_DISABLED` không có;
HTTP_PROXY/HTTPS_PROXY/ALL_PROXY không có; `getproxies()` không có proxy áp dụng.
Không sửa biến mạng, proxy hệ thống, firewall hoặc ACL. Dùng đúng stdlib transport
`fetch_public_html` với TLS verify/DNS public-IP pin/header hiện có, không cookie,
token, User-Agent thay thế hoặc endpoint khác.

| Kết quả lượt GUI xác minh cuối | Topic 6677 | Chapter 281106 |
| --- | --- | --- |
| Status thật | 200 | 200 |
| Content-Type / encoding | text/html; charset=utf-8 / UTF-8 | text/html; charset=utf-8 / UTF-8 |
| Response byte | 291725 | 144594 |
| URL cuối | https://www.kuaikanmanhua.com/web/topic/6677/ | https://www.kuaikanmanhua.com/webs/comic-next/281106 |
| Redirect | Không | Không |
| Nuxt state trong response | Có: topic_info.comics | Có: comic_info.comic_images |
| GET / TCP connect | 1 / 1 | 1 / 1 |
| Parser và GUI | LIVE_HTTP_PASS | LIVE_HTTP_PASS |

Quan sát status/headers bằng stdlib profiling tại **HTTPResponse thật**, không
mock transport. Diagnostic worker subclass chỉ bật profile rồi gọi nguyên
ComicSourceWorker.run. Adapter mới cho từng URL, không preload DOM. Response
được parse trong bộ nhớ không sửa thủ công. Tham chiếu DOM được đọc bằng adapter
riêng sau đó. Không lưu raw response/cookie/chữ ký; ảnh trong JSON đã che query.

Trong cả lượt có **8 GET page** (4 topic + 4 reader): probe ban đầu, kiểm tra
public state, GUI QA đầu và GUI QA xác minh lại. Chỉ hai URL đã chỉ định; không
crawl chương khác/endpoint/ảnh. Tất cả response quan sát đều200; không có
401/403/429 hoặc cơ chế né hạn chế. Không cần thử live thêm sau khi đạt.

### Bằng chứng lỗi và sửa production tối thiểu

Probe đầu: topic trả200 và metadata đúng nhưng **chapter parser FAIL
StructureChanged** vì HTML ban đầu không có `.title-item`. State có đủ26 record.
Reader trả200, DOM có2 img-box/4 img nội dung (2 trùng), parser cũ chỉ trả2 URL;
manifest công khai trong cùng response có116 URL. Đây là khác biệt SSR/rendered
DOM, không phải lỗi kết nối hoặc quyền đọc.

Đã sửa **hai file production**:

- `sources/kuaikan_dom.py`: khi topic chưa có mục DOM, đọc đúng
  `topic_info.comics` đã kiểm chứng, kiểm tra topic ID với URL, giữ thứ tự mảng,
  lấy ID/title/cờ đọc thực tế và canonical route. Captured DOM vẫn ưu tiên thứ
  tự mục DOM và ánh xạ title duy nhất như cũ. Không sort/suy ID theo số chương.
- Reader dùng `comic_info.comic_images` khi khớp chapter ID/title, các URL/domain
  hợp lệ và thứ tự img hiện có nhất quán với manifest. Giữ thứ tự manifest,
  chọn URL `url1280` hoặc `url` **đã có sẵn**, không tự tạo tài nguyên. Metadata
  mâu thuẫn thì giữ kết quả DOM/cảnh báo, không ghép tùy ý. Loại record sai/trùng,
  ghi rõ partial. Locked/restricted vẫn dừng trước discovery.
- Kết quả thêm `discovery_source`, `dom_unique_valid_urls`,
  `manifest_valid_urls`, identity/consistency/rejected counts. `source_attribute`
  có thể là `comic_info.comic_images.url1280`; dimension vẫn là metadata, không
  bitmap đã giải mã. Không đoán height khi biến thể scale chưa có height tương ứng.
- `sources/kuaikan.py`: cập nhật mô tả/support_status cho public HTTP parser;
  không thay transport, API worker, GUI hoặc quyết định tải.

Transport `sources/metadata_http.py`, literal decoder `kuaikan_state.py`,
core/providers/native guard, cache/service/registry/UI không sửa. Không thêm
dependency. Backup trước sửa: `backups/kuaikan-ssr-20261107T093330Z/`.

### So sánh với hai captured DOM

| Dữ liệu | HTTP ban đầu thật | DOM người dùng sau render |
| --- | --- | --- |
| Topic metadata | ID6677/title/count26/main23 | Khớp |
| Mục chapter trong DOM | 0 | 26 |
| Public topic_info.comics | 26 ID/title thật | 26 |
| ChapterInfo sau sửa | 26, gồm23 main/3 phụ | 26, gồm23 main/3 phụ |
| Thứ tự ID/chapter URL | Khớp toàn bộ capture | Tham chiếu |
| Chương15 | ID281106, 第15话 查出死因 | Khớp |
| Reader img toàn trang / nội dung | 12 / 4 | 130 / 122 |
| img-box / URL duy nhất từ thẻ img | 2 / 2 | 116 / 116 |
| data-src / lazy attribute | 0 / 0 (có noinit2) | 116 / 116 |
| Public comic_images manifest | 116 | 116 |
| URL ảnh sau sửa | **116 từ manifest response thật**, DOM xác nhận2 | 116 từ DOM |
| Thứ tự URL path | Khớp cả116 path capture | Tham chiếu |

Các con số là quan sát của hai mẫu, không hardcode trong runtime. Chữ ký query
không dùng làm điều kiện so sánh, không tạo/sửa/làm mới chữ ký. Prev/next vẫn là
281105/282537 theo href thật. `image_list_complete=None`: manifest116/116 không
chứng minh bitmap truy cập được hoặc toàn nội dung server. Chưa tải/giải mã ảnh.

### GUI, test và các lần QA thất bại được giữ lại

MainWindow tab URL được bấm bằng QtTest, chạy QThread và HTTP thật. Topic nhận
metadata/26 mục, chọn được và không tự chọn; direct chapter dùng adapter mới,
nhận116 URL, không cần mở topic trước. Heartbeat main loop97/84 trong hai tác
vụ; không treo. Nút tải luôn tắt, quyết định **DOWNLOAD_UNKNOWN**. Không tự phân
tích các chương đã chọn hoặc tải tài nguyên khi chỉ phân tích topic.

- Probe trước sửa giữ tại `logs/kuaikan-http-20261107T093330Z/live-response-analysis.json`.
  Topic có metadata nhưng error StructureChanged; field `parser=NOT_TESTED` là
  default chẩn đoán ở lượt lỗi, không phủ nhận parser đã được gọi và FAIL.
- GUI QA đầu `gui-live.json` có FAIL do **script QA** đọc `.analysis` từ list
  qua Qt Signal(dict), nơi DiscoveryList bị chuyển thành list thường. App đã
  tới IMAGE_LIST_READY. Sửa phép đo QA: đối chiếu list GUI với parser trên chính
  response cache, rồi đọc analysis từ parser; không thay app hoặc giả dữ liệu.
- Lượt xác minh cuối **`logs/kuaikan-http-20261107T093330Z/gui-live-verified.json`**:
  LIVE_HTTP_PASS cả2 URL,2 page GET,0 image GET, nguồn discovery/provenance rõ.
  Có ảnh chụp `topic-live-tab.png`, `chapter-live-tab.png` trong cùng thư mục.

**Pytest:172 PASS,10 SKIPPED,0 FAIL. Unittest:182 ca,172 PASS,10 SKIPPED,
0 lỗi/fail.** Thêm10 test `tests/test_kuaikan_ssr.py` cho state fallback, order,
partial, identity/locked, invalid URL, conflict và dimension. 14 mocked HTTP cũ
vẫn PASS; **MOCKED_HTTP_PASS không dùng thay LIVE_HTTP_PASS**. Hai full DOM gốc
trong regression vẫn PASS và giữ hash. 3 test live opt-in trong full suite vẫn
skip để không gửi thêm request; lý do skip cũ nhắc sandbox không mô tả môi
trường phiên mới. Live được nghiệm thu riêng bởi diagnostic thực ở trên.

Fixture mới: `kuaikan_topic_http_state_sanitized.html`,
`kuaikan_reader_http_state_sanitized.html`, `kuaikan_http_state_provenance.json`
trong tests/fixtures. Public state lấy từ response thật, đã whitelist/reserialize,
query chữ ký dummy; **DOM skeleton viết tay theo hình dạng đã thấy**, không
gọi fixture này là nguyên bản HTTP HTML hoặc DOM capture. Hash response gốc nằm
trong provenance; không lưu nguyên state người dùng/comment.

Bằng chứng regression tại `logs/kuaikan-http-20261107T093330Z/pytest.xml`,
`pytest.log`, `unittest/test-results.json`. Windows Qt local single/folder,
pause/resume, cache/output, 2 vùng OCR/2 bản dịch thật nhánh single PASS:
`output/source-tabs-validation/20261107T094212Z-56fc12/report.json`.
E2E Offline thật trên ảnh Trung tổng hợp PASS:
`output/e2e-validation/20261107T094302Z-a9a665/report.json`.
GUI smoke Windows Qt PASS: `logs/gui-smoke-20261107T094258Z-179c56/report.json`.
Không tuyên bố chất lượng MT hoặc nghiệm thu desktop thủ công từ smoke tự động.

Bảo toàn: `logs/kuaikan-http-20261107T093330Z/preservation.json`: ngoài2 file
production có chủ đích, **99 file trước nhiệm vụ giữ hash**, gồm config/DOM,
core/providers/native guard/BAT/spec/requirements và4 EXE. 5 model integrity PASS,
receipt không đổi. Không cài package, sửa .venv, xóa nguồn/cache/output hoặc build.

### Trạng thái sử dụng và bước tiếp

- **LIVE_HTTP_PASS / IMAGE_DISCOVERY_PASS:** source Python hiện tại nhận hai URL,
  tự thu thập page/state và trả danh sách thực qua GUI. Không phải gửi DOM lại.
- **CAPTURED_DOM_PARSER_PASS / MOCKED_HTTP_PASS / OFFLINE_REGRESSION_PASS:** giữ.
- **DOWNLOAD_UNKNOWN / NOT IMPLEMENTED:** chưa có quyền tải được xác minh hoặc
  downloader Kuaikan; không tải ảnh, không chạy OCR/MT từ ảnh web trong task.
- **EXE NOT_TESTED trong nhiệm vụ:** không build mới;4 EXE cũ không chứa sửa SSR.

Có thể dùng source để phân tích URL ngay. Để URL → ảnh → dịch hằng ngày, bước
riêng tiếp theo là xác minh điều kiện tải và thiết kế downloader khi được phép;
hiện dùng ảnh đã lưu hợp lệ qua tab cục bộ. Không cần browser automation để lấy
dữ liệu hai URL này. Các truyện/chương khác chưa live-test; không gán toàn website
SUPPORTED đầy đủ từ một topic/chapter. Lịch sử ENVIRONMENT_BLOCKED bên dưới là
phiên trước, được giữ để đối chiếu.

---

## LIVE HTTP RUNTIME VALIDATION — 07/11/2026, 09:05 UTC

**Kết quả: ENVIRONMENT_BLOCKED trước DNS/TCP, chưa nhận HTTP response.**
Không có bằng chứng website từ chối ứng dụng; không sửa transport/parser để
vượt giới hạn. Lịch sử kiểm chứng hai DOM thật phía dưới được giữ nguyên.

### Môi trường, transport và hai lần thử thực tế

- Tiến trình Windows chạy trong **Codex managed sandbox**, không phải phiên host
  không giới hạn; `platform=Windows-10-10.0.26200-SP0`, Python **3.10.9 x64**,
  interpreter `D:\TransTool\.venv\Scripts\python.exe`.
- Transport thật: `sources/metadata_http.py:fetch_public_html`, dùng stdlib
  `http.client.HTTPSConnection` qua `_PinnedHTTPS`, TLS certificate verification,
  DNS public-IP validation/pinning, GET không cookie/auth. Connect timeout 10s,
  giới hạn đọc 30s/2MB, redirect cùng allowlist, không retry 401/403/429.
- `CODEX_SANDBOX_NETWORK_DISABLED=1`; HTTP_PROXY, HTTPS_PROXY, ALL_PROXY đều trỏ
  loopback port **9**. `getproxies()` cũng có http/https/all. Không in/lưu cấu
  hình đăng nhập proxy hoặc NO_PROXY đầy đủ; không sửa bất kỳ biến/cấu hình nào.
- Đã gọi **chính fetch_public_html hiện có** một lần cho mỗi URL, không mock,
  không preload DOM. Audit hook đếm DNS/connect/http-send. Guard từ chối ngay ở
  đầu hàm vì sandbox/proxy; không thử direct socket, DNS hoặc TLS khác để né guard.

| Quan sát | Topic `/web/topic/6677/` | Chapter `/webs/comic-next/281106` |
| --- | --- | --- |
| Phân loại | ENVIRONMENT_BLOCKED | ENVIRONMENT_BLOCKED |
| DNS / socket.connect / HTTP send | 0 / 0 / 0 | 0 / 0 / 0 |
| Response HTTP thật | Không nhận được | Không nhận được |
| HTTP status | null, không xác minh | null, không xác minh |
| Content-Type / encoding / byte / final redirect URL | null, chưa có response | null, chưa có response |
| HTML / Nuxt state / cấu trúc reader | NOT_TESTED | NOT_TESTED |
| Parser trên HTTP response thật | NOT_TESTED | NOT_TESTED |
| Discovery chương / ảnh live | NOT_TESTED | NOT_TESTED |
| Số byte ảnh tải | 0 | 0 |

Lỗi thực tế là `NetworkUnavailable`, category `network`:

> Mạng bị giới hạn hoặc có proxy: bộ đọc metadata trực tiếp chưa hỗ trợ proxy.
> Không bỏ qua cấu hình mạng.

Không suy diễn thành HTTP 403, CAPTCHA, website khóa chương hoặc lỗi parser.
HTTPS/DNS tới Kuaikan **chưa thể kiểm chứng trong phiên này**, không kết luận
server mất mạng. Không xin tắt proxy/firewall hoặc tự sửa ACL/chính sách mạng.
Không lặp lại request bằng User-Agent/proxy/endpoint khác.

Bằng chứng được làm sạch: `logs/kuaikan-http-20261107T090510Z/environment.json`
và `runtime-probe.json`. Hai URL được phép là toàn bộ phạm vi thử. GUI regression
còn kiểm tra lại một lần lỗi guard với topic; không có HTTP request gửi ra mạng.

### Parser, captured DOM và nguyên nhân không sửa production source

Không có response nên **không thể so sánh HTML HTTP với DOM sau render**, Nuxt,
path/thứ tự ảnh hoặc chữ ký mới. Không ghép DOM mẫu vào live result. Các con số
26/23/116 vẫn chỉ là captured DOM, không trở thành số chương/ảnh live.

Chưa có bằng chứng cần sửa parser hoặc transport. Giới hạn transport đã biết:
reader DNS-pinned chỉ hỗ trợ kết nối trực tiếp, từ chối môi trường có proxy.
Nếu môi trường đích bắt buộc proxy hợp lệ, cần đánh giá hỗ trợ proxy riêng với
chính sách SSRF/TLS tương ứng; không tự bỏ proxy trong ứng dụng. Không nghiên cứu
lại domain hoặc thêm browser automation/framework HTTP/downloader trong lượt này.

**Không sửa file production nào**, gồm metadata_http/kuaikan/dom/state, GUI,
registry/service, core/providers/native guard. Tạo đúng một file test:
`tests/test_kuaikan_http_runtime.py` (14 ca). Cập nhật ba tài liệu: báo cáo này,
`WEBSITE_ADAPTER_AI_GUIDE.md`, `PROJECT_STATUS.md`. Không thêm dependency.

### Kiểm chứng worker/GUI và kiểm thử HTTP giả lập

`MOCKED_HTTP_PASS`: thay DNS và HTTPS connection ở ranh giới test, vẫn gọi
fetch_public_html → KuaikanAdapter → parser thật; không gọi load_document.
Payload là **sanitized capture excerpt**, không phải HTTP capture mới.

- HTTP 200 UTF-8 → metadata/chapter mapping; reuse response, không request lại.
- Redirect hợp lệ cùng host, validate/pin mỗi hop; timeout và DNS failure giữ
  network category/cause, đóng connection khi đã mở, không retry.
- Proxy/sandbox guard dừng trước DNS; test patch cấu hình chỉ trong unit-test
  scope, không bỏ giới hạn của lần probe thật hoặc thay môi trường toàn máy.
- 401/403 → access; 429 → usage_limit; không đọc body hoặc retry. Non-HTML bị
  từ chối trước đọc. Thiếu state/thay cấu trúc → analysis, không phải access.
- URL chương đi thẳng reader, chỉ 1 request page; excerpt có **3 URL ảnh**, không
  dùng 116 làm số live. Không fetch topic hoặc ảnh, download vẫn UNKNOWN.
- **3 ca GUI thật với simulated HTTP**: bấm nút URL → registry → QThread →
  transport → parser → panel; topic 26 mục chọn được/không tự chọn, reader 3 URL;
  thiếu state giữ metadata và nút retry. Main-thread heartbeat tiếp tục trong khi
  worker đợi response; không preload DOM, không tự crawl chương hoặc tải ảnh.

Đây là GUI/worker PASS với mocked transport, **chưa phải GUI live URL PASS**.
Luồng xử lý guard thật còn được kiểm chứng bởi Windows Qt validation bên dưới.

### Kết quả regression và bằng chứng mới

| Nhãn | Kết quả |
| --- | --- |
| CAPTURED_DOM_PARSER_PASS | Hai full DOM gốc chạy lại trong cả pytest/unittest: topic 26/23/3, chapter15=281106, reader116 URLs; file không đổi |
| MOCKED_HTTP_PASS | 14 ca mới: 11 transport/adapter, 3 GUI/QThread; không mock OCR/MT để báo live |
| LIVE_HTTP_PASS / LIVE_HTTP_FAIL | Không gán: chưa có response website; kết quả là ENVIRONMENT_BLOCKED |
| IMAGE_DISCOVERY_PASS | Chỉ captured DOM và mock response; live image discovery NOT_TESTED |
| DOWNLOAD_UNKNOWN | Giữ nguyên, downloader Kuaikan NOT IMPLEMENTED, 0 ảnh tải |
| OFFLINE_REGRESSION_PASS | GUI single/folder + OCR/Argos + cache/output, E2E và GUI smoke thật PASS |
| EXE TEST | NOT_TESTED; không build/chạy EXE trong nhiệm vụ, giữ 4 bản EXE cũ |

**Pytest: 162 PASS, 10 SKIPPED, 0 FAIL. Unittest: 172 ca,
162 PASS, 10 SKIPPED, 0 lỗi/fail.** Baseline 148/10 được giữ; thêm 14 ca HTTP/Qt.
10 skip vẫn là các model OCR/MT ngôn ngữ chưa cài, M2M100 chưa có model,
Online và 3 Kuaikan live opt-in. Không ép skip thành PASS. Cảnh báo pkg_resources/
Qt offscreen hiện có không được xử lý bằng thay phiên bản dependency.

- Pytest: `logs/kuaikan-http-20261107T090510Z/pytest.xml`, `pytest.log`.
- Unittest: `logs/kuaikan-http-20261107T090510Z/unittest/test-results.json`.
- Windows Qt ba tab, ảnh đơn/folder, pause/resume, responsive GUI và lỗi mạng
  tách quyền: `output/source-tabs-validation/20261107T090853Z-d91fb8/report.json`.
  PASS; 2 vùng OCR/2 bản dịch thật nhánh single, folder xuất ảnh, config/nguồn
  nguyên vẹn, socket attempts rỗng. Guard metadata thất bại được hiển thị đúng.
- E2E: `output/e2e-validation/20261107T090904Z-15b74d/report.json`: PASS kỹ thuật
  trên ảnh Trung tổng hợp, OCR/Argos/mask/inpaint/render/export/model reuse thật.
  Không phải ảnh lấy từ Kuaikan; chất lượng câu dịch vẫn có hạn chế đã ghi nhận
  (câu chào mừng có thể dịch thành “Không có gì.”), không thay model trong task.
- GUI smoke Windows Qt: `logs/gui-smoke-20261107T090900Z-90e537/report.json`:
  PASS glyph/modes/picker Qt/model manager/preview/event loop; physical desktop
  nghiệm thu thủ công và native Windows picker chưa được xác minh.
- `logs/kuaikan-http-20261107T090510Z/preservation.json`: **100 file đã chụp hash**
  (source/test cũ, BAT/spec, config, DOM, model receipt, 4 EXE) đều không đổi;
  5 model integrity PASS. Không xóa cache/output/ảnh nguồn hoặc sửa .venv.

### Việc còn lại để sử dụng URL hằng ngày

1. Chạy lại hai GET bằng transport/adapter hiện tại trong **phiên được cấp mạng
   hợp lệ**, giữ nguyên proxy/firewall/chính sách của máy. Không cần cung cấp DOM
   lại, không thay bằng browser automation. Phiên hiện tại vẫn bị sandbox chặn.
2. Khi có response, ghi status/type/charset/bytes/final URL thực, không lưu
   cookie/token/chữ ký; parse response nguyên bản trong bộ nhớ và đối chiếu
   cấu trúc/state/title-ID/path/order với capture, không ghép dữ liệu cũ.
3. Nếu response đủ dữ liệu thì giữ parser; nếu chỉ có state đủ dùng thì chỉ sửa
   phần cần thiết theo response thật, giữ captured tests. Nếu thiếu dữ liệu,
   mô tả vùng thiếu rồi mới đề xuất acquisition khác cho người dùng quyết định.
4. Kiểm thử URL qua GUI/QThread thật với HTTP, không tự phân tích tất cả chương.
   Parser/HTTP PASS không cấp quyền tải; downloader và OCR ảnh web vẫn ngoài task.

---

## Kết quả mới nhất — hai DOM thật do người dùng cung cấp

Phần dưới là kết quả lượt DOM trước khi thử runtime; xem mục LIVE HTTP RUNTIME
VALIDATION phía trên để biết trạng thái HTTP và tổng số test mới nhất.

**Parser offline PASS trên cả hai bản DOM gốc.** Topic trả 26 mục có ID/URL
được ánh xạ, gồm 23 chương chính và 3 nội dung phụ. Reader trả 116 URL ảnh nội
dung duy nhất. Không tải ảnh, không thử HTTP Kuaikan, không build/chạy EXE trong
nhiệm vụ này. Không coi kết quả này là URL → ảnh → dịch đã hoàn thành.

### 1. Kiểm tra đầu vào và bảo toàn

Đã kiểm tra trước khi sửa code, cả hai file tồn tại, đọc UTF-8 (chấp nhận BOM),
HTML/DOM chứa đúng các vùng cần nghiên cứu. Không tự tạo thay file người dùng.

| File dưới `output/kuaikan-capture/` | Byte | SHA-256 |
| --- | ---: | --- |
| `topic-6677.dom.html` | 222544 | `e8398c93d97cdf6c1c42d5ae8b93f6d4c44188002d93f91b14c0551dfefdb1ea` |
| `chapter-281106.dom.html` | 210366 | `09982e856c071cf76fae8045346272aa2099d7c8ea5dacba67fdfdf1e21aae05` |

DOM nguyên bản có dữ liệu bình luận/người dùng công khai, avatar/nickname/ID,
điều khiển tiếp tục đọc và URL CDN có chữ ký. Chúng không phải bộ fixture sạch
để commit. Không phát hiện mẫu cookie/bearer/password rõ qua kiểm tra cấu trúc;
điều này không phải bảo đảm file không chứa mọi dạng dữ liệu riêng tư. Không
đưa nguyên script hoặc giá trị chữ ký vào báo cáo. Hai file giữ nguyên trong
output bị loại khỏi Git; fixture mới chỉ giữ vùng cần thiết và dữ liệu công khai
đã lọc, chữ ký thay bằng số 0. Không di chuyển hoặc sửa DOM gốc.

Backup source/tài liệu trước sửa: `backups/captured-dom-20261107T080651Z/`.
Kiểm chứng sau kiểm thử: `logs/captured-dom-20261107/preservation.json`:
hai DOM/config hash không đổi; 24 file bảo vệ core/providers/BAT/spec/requirements/
EXE khớp hash; 5 model kiểm tra integrity PASS, receipt không đổi. Không cài
package, sửa .venv, native guard, GUI, pipeline hay ảnh nguồn.

### 2. Topic DOM — cấu trúc và kết quả

- URL: `https://www.kuaikanmanhua.com/web/topic/6677/`.
- Vùng thực tế: `.TopicEpisode .topic-episode .episode-title .title-item`,
  mỗi mục có `span.text`. Có **26 mục**, nhưng **0 href chương literal** trong
  các mục và không có chapter ID attribute trực tiếp để đọc.
- Inline `window.__NUXT__` có dữ liệu công khai tại
  `data[0].res.data.topic_info`: `id`, `title`, `comics_count`,
  `comic_body_count`, `comics`. Mỗi comic có ID/tiêu đề và cờ đọc.
- Decoder literal có giới hạn đọc alias/IIFE/assignment hằng từ cấu trúc đã quan
  sát, không thực thi JavaScript hoặc gọi API. Ghép tiêu đề DOM với **tiêu đề
  duy nhất** trong `comics`, không ghép theo vị trí mảng. Mảng comic trong reader
  có thứ tự khác topic, nên thứ tự đầu ra luôn dựa trên các mục DOM topic.
- Đầu ra: **26 ID/tiêu đề ánh xạ được; 26 canonical URL; 0 mục thiếu URL**.
  URL được dựng theo route reader đã xác minh và **ID thực trong chính DOM**,
  provenance `embedded_id+verified_route`; không tuyên bố tìm được 26 thẻ a.
- Website công bố **26 nội dung / 23正文**; DOM có 26; parser trả 26; phân loại
  được **23 main / 3 supplementary / 0 unknown**. Các mục phụ là `预告`,
  `连更福利~`, `下期预告X开奖公告`. Không bỏ mục phụ khỏi thứ tự.
- **Chương 15**: DOM title `第15话 查出死因` ánh xạ ID **281106** trong state;
  canonical URL `https://www.kuaikanmanhua.com/webs/comic-next/281106`;
  order_index **17** (mục thứ 18). Không chèn ID từ thông tin tham chiếu.
- Các record snapshot có cờ free/unlocked/no-VIP/no-pay rõ: PUBLIC
  (`public_readable`), chỉ nói quyền đọc theo snapshot. DownloadDecision UNKNOWN.
- Không thấy control phân trang/tải thêm trong vùng danh sách đã lưu; 26/26 khớp
  số công bố. Đây là đầy đủ **đối với snapshot này**, không xác nhận cách phân
  trang/tải động của HTTP runtime hoặc mọi truyện khác.

### 3. Chapter DOM — cấu trúc, ảnh và phạm vi xác minh

- URL chương trực tiếp nhận độc lập với danh sách topic. ID từ URL được đối
  chiếu `comic_info.id`; title `.step-comic` khớp `comic_info.title`.
- Breadcrumb topic là `/web/topic/6677`; tên truyện `权妃之帝医风华`.
- Prev href thật: `/webs/comic-next/281105`. Next href thật:
  `/webs/comic-next/282537` (mục phụ), **không suy chương kế bằng ID + 1**.
- Vùng nội dung thực: `.comicDetails .imgList .img-box`.

| Quan sát trên DOM đã lưu | Số lượng |
| --- | ---: |
| Tất cả thẻ img trên trang | 130 |
| img trong vùng nội dung có alt khớp tên chương | 122 |
| img-box | 116 |
| URL nội dung HTTPS hợp lệ về cú pháp/hostname sau khử trùng | 116 |
| Phần tử img trùng (fallback ẩn `display:none`) | 6 |
| Mục `comic_info.comic_images` | 116 |
| URL DOM có path khớp manifest | 116 |
| Ảnh tải/giải mã/OCR/dịch/xuất từ Kuaikan trong nhiệm vụ | 0 |

URL nội dung thực có trong DOM, hostname **tn1.kkmh.com**, có `sign` và `t`.
Parser giữ URL nguyên bản trong bộ nhớ, chỉ chấp nhận dạng chữ ký đã quan sát
để discovery; không tạo chữ ký, xác thực hoặc tải ảnh. Report JSON che mọi query
value và ghi SHA-256 URL; không đưa URL còn chữ ký nguyên bản vào tài liệu.

Lazy attributes quan sát: `data-src` **116**, `lazy="loaded"` **116**,
`noinit="true"` **116**. `src` có trên 122 img nội dung, gồm 6 fallback trùng.
Không thấy `data-original`, `data-lazy-src`, `srcset`, `data-srcset`, `picture`
hoặc `source` trong capture. Các dạng khác vẫn có manual regression riêng.
Không có width/height attributes trên img nội dung; kích thước đầu ra parser lấy
từ metadata và ghi `dimensions_source='embedded_metadata'`, chưa phải decoded
bitmap dimensions. Không có placeholder được đưa vào danh sách 116 URL.
Ảnh UI/avatar/khuyến nghị ngoài scope và ảnh không khớp alt bị loại.

**116/116 khớp manifest của snapshot**, không tự chứng minh toàn bộ chương từ
server, ảnh có truy cập được hay cache trình duyệt tải thành công. Vì vậy
`image_list_complete=None`. Không suy số trang thiếu; không gọi 2 ảnh đã quan sát
trước đây là toàn chương. Không cần bổ sung DOM để kiểm chứng parser snapshot
hiện tại; nếu cần chứng minh bitmap dimensions phải kiểm tra ảnh hợp lệ riêng.

### 4. Nguyên nhân và sửa đúng thành phần

Hai chạy CLI trước sửa trên bản gốc đều FAIL: topic 0 chương; reader 1 chương,
0 ảnh. Evidence giữ nguyên:
`output/kuaikan-html-analysis/20261107T080553Z-305133/report.json` và
`output/kuaikan-html-analysis/20261107T080553Z-8464de/report.json`.

Nguyên nhân: parser topic chỉ nhận a/href, trong khi capture dùng div/title +
ánh xạ ID trong Nuxt; image URL filter loại toàn bộ query `sign`. Không phải
bằng chứng lỗi mạng hoặc thiếu quyền đọc.

Source đã sửa:

- `sources/kuaikan_dom.py`: scope/title-ID mapping thật, DOM order/main-extra,
  partial/warnings, reader/manifest đối chiếu, lazy và signed URL discovery.
- `sources/kuaikan.py`: nối parser/state, metadata giữ khi state không đọc được,
  support_status phản ánh capture; HTTP transport không đổi.
- `sources/contracts.py`: PUBLIC reading status, chapter url_source và
  DiscoveryList.analysis; trường mới có default để giữ API cũ.
- `sources/states.py`: ánh xạ PUBLIC sang trạng thái đọc, không cấp quyền tải.
- **Mới** `sources/kuaikan_state.py`: bounded literal/alias reader, từ chối câu
  lệnh/call/operator không hỗ trợ, prototype keys và dữ liệu vượt giới hạn.
- `scripts/analyze_kuaikan_html.py`: thống kê/provenance, phân loại test và che
  query URL ảnh khi ghi báo cáo. Audit hook chặn socket.connect.

Test/data mới: `tests/test_kuaikan_captured_dom.py`,
`tests/fixtures/kuaikan_topic_captured_excerpt.html`,
`tests/fixtures/kuaikan_reader_captured_excerpt.html`,
`tests/fixtures/kuaikan_captured_excerpt_provenance.json`.
Excerpt topic giữ 26 mục; reader chỉ giữ 3 img-box (đầu, thứ hai, cuối), không
giả là toàn chương. State được lọc/reserialize, chữ ký dummy; 2 test riêng chạy
trên **toàn bộ DOM nguyên bản**, không thay bằng excerpt hoặc fixture viết tay.

Không sửa core/providers/UI/metadata_http/service/registry, không tạo OCR/MT mới.
Docs cập nhật: báo cáo này, WEBSITE_ADAPTER_AI_GUIDE và PROJECT_STATUS.

### 5. Kết quả kiểm thử theo lớp

| Nhóm bắt buộc | Kết quả trong nhiệm vụ này |
| --- | --- |
| MANUAL FIXTURE TEST | PASS các ca cũ về URL/href/lazy/srcset/locked/worker; dữ liệu viết tay, không live |
| SANITIZED CAPTURE EXCERPT / DATA READER | PASS 12 ca mới; literal grammar, title mapping, partial/ambiguity, provenance, privacy, access, metadata preservation |
| CAPTURED REAL DOM TEST | PASS 2 ca mới trên hai bản gốc và 2 CLI rendered_dom; topic 26, reader 116 URLs |
| LIVE HTTP TEST | NOT TESTED, ngoài phạm vi; không thử Kuaikan hoặc giải quyết mạng trong nhiệm vụ này |
| IMAGE DOWNLOAD TEST | NOT TESTED, 0 tải; DownloadDecision UNKNOWN; downloader chưa triển khai |
| OFFLINE OCR/MT REGRESSION | PASS thật, suy luận model hiện có; GUI single/folder và E2E, không mock OCR/MT |
| EXE TEST | NOT TESTED, không build/chạy EXE mới; bản cũ bảo toàn hash |

**Pytest: 148 PASS, 10 SKIPPED, 0 FAIL. Unittest: 158 ca, 148 PASS,
10 SKIPPED, 0 lỗi/fail.** Baseline 134/10 giữ nguyên, thêm 14 ca PASS gồm 2
full-captured DOM. Cảnh báo pkg_resources/setuptools và Qt offscreen cũ không
được xử lý bằng nâng dependency. Không ép các test bị skip thành PASS.

10 skip: 3 OCR thiếu model Anh/Hàn/phồn thể; 2 MT Hàn/phồn thể; M2M100 chưa có
model; Online thật opt-in; 3 live Kuaikan opt-in. Thông báo skip mạng cũ không
chứng minh nhiệm vụ hiện tại đã thử mạng hay đang BLOCKED.

Bằng chứng mới:

- Topic CLI: `output/kuaikan-html-analysis/20261107T082007Z-14ec3b/report.json`.
- Chapter CLI: `output/kuaikan-html-analysis/20261107T082007Z-f9cb99/report.json`.
  Cả hai `PASS_FILE_PARSER`, `network_attempts=0`, `downloaded_images=0`,
  `source_unchanged=true`; URL query đã che.
- Pytest: `logs/captured-dom-20261107/pytest.xml` và `pytest.log`.
- Unittest: `logs/captured-dom-20261107/unittest/test-results.json`.
- MainWindow ba tab, ảnh truyện người dùng, QThread, pause/resume, folder,
  cache và output: `output/source-tabs-validation/20261107T082102Z-5fe8fe/report.json`.
  PASS, Windows Qt plugin, 2 vùng OCR/2 bản dịch thật trong nhánh ảnh đơn;
  folder cũng xuất ảnh, GUI responsive, config/nguồn không đổi, không socket.
  Nhánh URL mạng không chạy trong validation này.
- E2E Offline: `output/e2e-validation/20261107T082304Z-feff54/report.json`.
  PASS OCR → Argos → mask → inpaint → render → export → reuse, ảnh fixture Trung
  tổng hợp, không hardcode OCR/bản dịch. Không phải ảnh tải từ Kuaikan.
- GUI smoke: `logs/gui-smoke-20261107T082304Z-ec6a3a/report.json`: PASS Windows
  Qt plugin, font glyph/picker Qt/preview/model manager/event loop. Physical
  desktop rendering và native Windows picker chưa được người dùng nghiệm thu.

### 6. Runtime, downloader và dữ liệu còn thiếu

`load_document` kiểm thử khả năng **phân tích** đã có. `_html` vẫn dùng transport
HTTP hiện tại; nhiệm vụ không chứng minh transport lấy được markup/state tương
ứng từ URL. Chưa nghiệm thu daily URL → chương → ảnh → dịch. Không phát triển
browser automation, không yêu cầu nộp DOM mỗi lần đọc chương.

`get_chapter_images` là discovery; DOWNLOAD_UNKNOWN không chuyển ALLOWED chỉ vì
116 URL hoặc cờ PUBLIC. Downloader Kuaikan vẫn chưa triển khai/bật. Khi tải chưa
có cơ sở hợp lệ, dùng ảnh người dùng đã lưu hợp lệ qua tab ảnh đơn/thư mục.

Hai DOM đã đủ cho mục tiêu parser hiện tại; **không cần người dùng cung cấp lại
DOM**. Bước runtime sau này cần một lượt HTTP được cho phép để kiểm chứng response
và so với cấu trúc này; downloader cần bằng chứng điều kiện sử dụng/tải và test
ảnh thật riêng. Chưa xác minh truyện/chương khác bằng live test; không tuyên bố
hỗ trợ toàn website hoàn chỉnh từ một cặp capture.

AI guide đã bổ sung ứng dụng cá nhân, nghiên cứu một lần/tác vụ lặp lại,
USER-PROVIDED DOM WORKFLOW, cách lấy DOM/sanitization, parser vs acquisition,
prompt ADD WEBSITE ADAPTER FROM USER-PROVIDED DOM, checklist hai giai đoạn và
registry CAPTURED_DOM_VERIFIED / LIVE_HTTP_UNVERIFIED / DOWNLOAD_UNKNOWN.

---

## Lịch sử trước khi nhận hai DOM — giữ để đối chiếu

Các nhận định thiếu DOM/BLOCKED/fixture-only và yêu cầu bổ sung file phía dưới
là lịch sử trước lượt kiểm chứng ở trên, không phải trạng thái mới nhất.

### Kết luận ở lượt trước

**Đã sửa nhận URL chương và triển khai fallback parser HTML/DOM có unit test.
Chưa nghiệm thu cấu trúc Kuaikan live. Không tải ảnh chương.**

Không coi hai phần tử ảnh là toàn chương. Không dùng fixture viết tay để tuyên bố
đã trích xuất được link/ảnh thật từ website. Chưa có HTML/DOM thật được người dùng
cung cấp trong workspace ở thời điểm báo cáo này.

## 1. Bằng chứng và giới hạn truy cập

| Hạng mục | Bằng chứng / trạng thái |
| --- | --- |
| URL topic | https://www.kuaikanmanhua.com/web/topic/6677/ |
| URL chương do người dùng xác minh | https://www.kuaikanmanhua.com/webs/comic-next/281106 |
| ID / tên do người dùng xác minh | 281106 / 第15话 查出死因 |
| Cấu trúc URL | Nhận `/webs/comic-next/<positive_id>` và topic, không gắn ID mẫu vào logic |
| Topic qua công cụ web | Quan sát lại tên 权妃之帝医风华, tác giả 有鱼互鱼, công bố 26 nội dung/23正文; không có chapter href trong dữ liệu trích xuất |
| Chương qua công cụ web | Công cụ báo không truy cập được; không trả HTTP status/HTML/DOM |
| HTTP trực tiếp Python của hai URL | BLOCKED trước kết nối bởi sandbox/proxy guard, không bypass |
| HTTP status 200/401/403/429 thực tế của chương | **Chưa xác minh**, không suy từ lỗi công cụ |
| DOM sau render / JSON nhúng / event handler / pagination live | **Chưa xác minh** |
| Link chương thật tự trích từ topic trong phiên | **0**; khác với 1 URL chương người dùng cung cấp |
| Link chương 15 từ topic live | **Chưa lấy được** |
| Phần tử ảnh nội dung tự xác minh live | **0**; người dùng báo đã quan sát 2 phần tử, chưa kiểm chứng lại được |
| URL ảnh thật đầy đủ | **Chưa có trong dữ liệu phiên này**; chỉ có hostname tn1.kkmh.com do người dùng cung cấp |
| Ảnh chương tải thật / OCR / dịch / xuất từ Kuaikan | **0 / 0 / 0 / 0** |
| Quyền tải tự động | DOWNLOAD_UNKNOWN; không có downloader Kuaikan được bật |

Runtime probe: `logs/chapter-281106-20261107/runtime-probe.json`.
`environment.json` ghi điều kiện mạng và giới hạn công cụ. Không coi đó là website
cấm đọc hoặc chương bị khóa. Không thử endpoint khác, giả đăng nhập, CAPTCHA,
cookie/token, proxy hoặc kỹ thuật né giới hạn.

## 2. Nguyên nhân adapter cũ luôn 0 chương / chưa có ảnh

1. normalize_url chỉ nhận topic, từ chối comic-next trước khi đọc trang.
2. get_chapters chỉ kiểm tra heading rồi luôn ném StructureChanged, không trích a/href.
3. get_chapter_images luôn ném StructureChanged, chưa có image discovery.

Đây là giới hạn implementation, ngoài giới hạn mạng; không phải bằng chứng thiếu
quyền cho mọi chương. Lỗi mạng vẫn độc lập với parser và điều kiện tải.

## 3. Thay đổi đã triển khai

- `sources/kuaikan.py`: chuẩn hóa cả topic/chapter, lấy chapter ID từ URL thực,
  cache tối đa hai HTML trong bộ nhớ, API load_document cho HTML/DOM người dùng.
  URL chương đi thẳng vào reader parser, trả một ChapterInfo, không cần topic list.
- `sources/kuaikan_dom.py` mới: parser thẻ HTML tiêu chuẩn, không CSS selector hoặc
  schema hydration phỏng đoán, không thực thi JS. Topic tìm a/href comic-next kèm
  tên chương trong vùng mục chương, dừng trước bình luận/recommendations. Khử trùng,
  giữ thứ tự DOM; không suy thứ tự phát hành từ ID. Phân loại main/supplementary
  bằng tiêu đề, giữ UNKNOWN access trừ dấu hạn chế rõ.
- Reader lấy heading/title/og:title; topic link chỉ khi có liên kết cha rõ/duy nhất;
  prev/next chỉ từ href có rel hoặc nhãn điều hướng tương ứng. Không tạo ID liền kề.
- Ảnh: chỉ img có accessible name khớp tiêu đề chương và URL HTTPS trên hostname
  tn1.kkmh.com đã được cung cấp; loại UI semantic/placeholder/data URI/URL nội bộ,
  domain giả và query chứa dấu hiệu credential. Đọc src/data-src/data-original/
  data-lazy-src/srcset/data-srcset; giữ thứ tự, chọn biến thể srcset và khử trùng.
- `ChapterImage.download_status='discovered'`, local_path=None, không gọi HTTP ảnh.
  Width/height nếu có là **HTML attributes**, không khẳng định kích thước bitmap.
  image_list_complete=None vì DOM hiện có có thể chưa bao gồm ảnh lazy khác.
- `sources/contracts.py`: DiscoveryList có warnings/complete; bổ sung source_kind,
  topic_url, content_kind và nguồn kích thước. Không biết comic ID thì null, không
  lấy chapter ID giả thành comic ID. `sources/service.py` từ chối tạo cache download
  nếu chưa xác minh comic ID; pipeline gốc không đổi.
- `ui/comic_sources.py`: chỉ nối worker/event, không thiết kế lại GUI. URL chương
  tự phân tích image URLs sau metadata. Topic có nút nhỏ **Phân tích ảnh chương**
  sau khi chọn, tối đa 10 chương/lượt, tuần tự có khoảng nghỉ. Không tự lấy mọi chương.
  Metadata/ChapterInfo giữ khi image parser lỗi. IMAGE_LIST_READY tách DOWNLOAD_UNKNOWN.
- `sources/states.py`: IMAGE_LIST_READY/ERROR.
- `scripts/analyze_kuaikan_html.py` mới: đọc HTML/DOM cục bộ offline, báo rõ không
  phải live test. `tests/test_kuaikan_discovery.py` và hai fixture manual mới.

Không sửa GUI chính, core OCR/translation/inpainting/render, model, .venv, BAT,
spec hoặc EXE cũ. Không cài dependency. Backup:
`backups/chapter-adapter-20261107T051455Z` (86 file).

### Giới hạn của fallback parser

Chỉ xử lý những a/href và img có chứng cứ ngay trong HTML/DOM. Không đọc schema
JavaScript chưa được xác minh, không thực thi onclick, không tự gọi API phân trang.
DOM có thể không chứa link trước render. Image name hoặc hostname khác sẽ yêu cầu
kiểm chứng thêm, thay vì quét mọi img thành trang truyện. Những heuristic này chỉ
được unit-test trên fixture; **chưa phải selector đã được kiểm chứng trên Kuaikan**.

## 4. Phân biệt các lớp kiểm thử

| Kiểm tra | Trạng thái |
| --- | --- |
| Unit URL routing / ID / title / order / main-extra / lazy / SSRF / locked / errors | PASS fixture; không live |
| Qt worker direct chapter, IMAGE_LIST_READY và metadata giữ sau image error | PASS bằng HTML fixture và HTTP mock guard |
| HTML/DOM thật được lưu từ trình duyệt | BLOCKED: chưa nhận file |
| Live topic metadata | Chỉ quan sát qua công cụ web; Python HTTP BLOCKED |
| Live chapter metadata / DOM | BLOCKED |
| Live image list / kích thước bitmap | BLOCKED / NOT TESTED |
| Live download | NOT TESTED; DOWNLOAD_UNKNOWN và không triển khai downloader |
| Offline OCR/translation/local file-folder regression | PASS thật; evidence phía dưới |
| EXE mới | Chưa build; đợi xác minh DOM/site acceptance, giữ bản cũ |

Fixture `tests/fixtures/kuaikan_*_manual.html` viết tay có chú thích rõ. ID 900001,
900002 và `/__fixture__/...` là dữ liệu giả cho unit test, **không phải URL website
đã quan sát và không bao giờ được fetch**. CLI ghi input_kind=manual_fixture,
live_test=False và downloaded_images=0:

- Reader fixture: `output/kuaikan-html-analysis/20261107T052319Z-c09b9f/report.json`
  (1 chương/2 URL ảnh fixture; complete=None).
- Topic fixture: `output/kuaikan-html-analysis/20261107T052320Z-ea07fb/report.json`
  (3 link fixture trong tổng công bố 26; danh sách từng phần).

### Kết quả regression đã chạy

- Pytest sau các cập nhật cuối: **134 PASS, 10 SKIPPED**;
  `logs/chapter-281106-20261107/verified-pytest.xml` và `.log`.
- Unittest: **144 ca, 134 PASS, 10 SKIPPED**, 0 lỗi/fail;
  `logs/chapter-281106-20261107/acceptance-unittest/test-results.json`.
- 18 ca parser/worker fixture mới PASS, không phải website live PASS.
  3 test live topic/chapter/image-list SKIPPED vì runtime mạng/opt-in; 7 SKIPPED
  còn lại giữ nguyên các thiếu model/ngôn ngữ/Online opt-in cũ.
- GUI Qt Windows ảnh đơn/thư mục + OCR/MT thật: **PASS**, không mock,
  `output/source-tabs-validation/20261107T053330Z-7b5588/report.json`;
  source/config integrity và no-network của Offline được kiểm tra.
- E2E Offline chuẩn: **PASS**,
  `output/e2e-validation/20261107T053336Z-6977d3/report.json` (ảnh fixture tổng hợp,
  suy luận OCR/MT thật, không hardcode bản dịch).
- GUI smoke: **PASS**, `logs/gui-smoke-20261107T053343Z-323a1a/report.json`.
- Bảo toàn: `logs/chapter-281106-20261107/preservation.json`: core/providers,
  main.py, GUI chính, requirements, BAT/spec và mọi EXE cũ giữ hash;
  5 model verify PASS, receipt không đổi. Không cài dependency hoặc sửa .venv.

Phần chống query credential được kiểm tra cả token/signature/sig/auth_key; không
ghi URL có dấu hiệu bí mật ra report discovery. Không có full live/download PASS.
Fingerprint source cuối: `307fffaddfbe9248bde566feb65ff9409ed4ad68e2df7610ac4950780226821f`.

## 5. Dữ liệu cần thêm từ người dùng

Cần HTML/DOM của **cả hai trang**, ưu tiên phiên công khai chưa đăng nhập:

1. Topic 6677: vùng danh sách chương có a/href và các nhãn/chương phụ/khóa;
   phần heading/title và tổng số nội dung. Nếu có phân trang, ghi thao tác và URL
   công khai hiển thị, không cung cấp endpoint suy đoán.
2. Chapter 281106: heading/title, breadcrumb/topic link, prev/next, vùng img sau
   khi cuộn cho lazy loading hiển thị. Cần src/data-src/srcset/accessible name.
3. Nếu muốn xác minh kích thước thật: dữ liệu DOM currentSrc/naturalWidth/
   naturalHeight của những ảnh đang hiển thị; width/height attribute chưa đủ.

Có thể lưu dưới `output/kuaikan-capture/` (không đưa vào Git), ví dụ
`chapter-281106.dom.html` và `topic-6677.dom.html`, rồi gửi đường dẫn.
Không gửi cookie/token/HAR hoặc dữ liệu tài khoản; có thể chỉ sao chép DOM vùng
công khai cần thiết. Không cần và không yêu cầu tải file ảnh để làm bước parser.

Phân tích file sau khi có dữ liệu (không gửi mạng):

```bat
.venv\Scripts\python.exe scripts\analyze_kuaikan_html.py --url https://www.kuaikanmanhua.com/webs/comic-next/281106 --html output\kuaikan-capture\chapter-281106.dom.html --input-kind rendered_dom
.venv\Scripts\python.exe scripts\analyze_kuaikan_html.py --url https://www.kuaikanmanhua.com/web/topic/6677/ --html output\kuaikan-capture\topic-6677.dom.html --input-kind rendered_dom
```

Sau đó đối chiếu DOM thật, chỉnh selector theo chứng cứ, test link 15 lấy từ topic,
kiểm tra đầy đủ/lazy/count/order và thêm capture đã loại dữ liệu riêng vào test phù hợp.
Chỉ xem xét downloader khi điều kiện sử dụng/tải đã được xác minh riêng.
