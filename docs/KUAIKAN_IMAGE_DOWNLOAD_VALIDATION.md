# Kuaikan — image download validation

## DEFAULT_ALLOW_PUBLIC — chính sách vận hành mới của chủ ứng dụng, 07/11/2026

**Đã áp dụng DEFAULT_ALLOW_PUBLIC và triển khai downloader tối thiểu.**
Đây là lựa chọn của chủ Image Translator VN, **USER_POLICY_DEFAULT_ALLOW**,
không phải OFFICIAL_PERMISSION. Kết luận lịch sử Stage A phía dưới vẫn đúng:
chưa có bằng chứng cấp quyền tải chính thức cho phạm vi này. Không sửa nguồn
hoặc kết luận lịch sử thành “website đã cấp phép”.

### Bốn lớp dữ liệu và cấu hình

| Lớp | Giá trị chương281106 trong lần kiểm tra |
| --- | --- |
| Bằng chứng quyền nội dung | ContentPermission.UNKNOWN, permission_source=null |
| Cấu hình chủ ứng dụng | download_policy="default_allow_public" |
| Truy cập kỹ thuật | PUBLIC/free/unlocked/noVIP/noPay; URL ảnh đã kiểm tra |
| Quyết định ứng dụng | ALLOWED_BY_USER_POLICY, basis=USER_POLICY_DEFAULT_ALLOW |

`ContentPermissionEvidence` chứa status/source_url/verified/applies_to_download;
chỉ evidence đã xác minh, đúng phạm vi mới có thể thành ALLOWED hoặc RESTRICTED.
Thiếu permission vẫn UNKNOWN kể cả có200/manifest hoặc app cho tải. Link
`evidence_url` tới điều khoản chỉ là tham chiếu; `permission_source` vẫn null
trong trường hợp user policy, không gán nó thành giấy phép.

Config mới `config/download_policy.json` chỉ có:

```json
{"download_policy": "default_allow_public"}
```

Nếu không có file, code cũng mặc định giá trị này. Có thể đổi `verified_only`
rồi mở lại ứng dụng để dùng chính sách strict lịch sử. File sai/giá trị không
hợp lệ trở về verified_only. Không thay settings.json hoặc thêm UI quản lý quyền.

Quyết định mới: ALLOWED_BY_USER_POLICY, ALLOWED_BY_VERIFIED_PERMISSION, BLOCKED,
UNKNOWN. `DownloadDecision.allowed` nối tương thích với service/GUI và adapters
cũ dùng DOWNLOAD_ALLOWED; giá trị legacy không tự tạo bằng chứng quyền nội dung.

### Điều kiện cho phép và dừng

- Chỉ user policy cho **PUBLIC miễn phí**, không khóa/VIP/paywall/login/DRM/
  CAPTCHA, có danh sách URL HTTPS trên đúng allowlist và không có mâu thuẫn
  manifest/order hoặc record URL bị loại. Chưa phân tích ảnh thì UNKNOWN;
  URL/host không an toàn thì BLOCKED.
- Hạn chế tải đã xác minh và áp dụng được luôn thắng default allow. Evidence
  grant thật được đánh giá riêng. Chương UNKNOWN, LOCAL hoặc enum quyền cũ
  không bị coi là PUBLIC để tự mở tải.
- Dừng401/403/429, MIME HTML/trang chặn, redirect không an toàn, locked/DRM/
  CAPTCHA hoặc dữ liệu không xác minh được. Không retry access/usage restriction.
  Adapter ghi technical barrier để lần bấm lại không gửi tiếp request CDN vượt chặn.
- Không thay User-Agent/cookie/Referer/proxy, không tạo/gia hạn/sửa chữ ký.
  Signature chỉ được chuyển nguyên bản từ manifest sang request; receipt giữ
  hash thay query. Chưa xác minh TTL, không suy từ t.

### Luồng GUI hiện tại

Chạy source bằng `run_source.bat` → tab Link truyện online → nhập URL/phân tích
→ chọn chương → **Phân tích ảnh chương** nếu là topic → **Tải và dịch**.
URL chương trực tiếp tự discovery, vẫn không tự chọn chương hoặc tự tải.
Metadata/chapter/image discovery chỉ đọc HTML/state; sau chọn checkbox mới có
thể bật nút tải. Nút/tooltip hiển thị lý do user policy, không nói có giấy phép.
Worker kiểm tra lại quyết định trước IO. Không hỏi xác nhận quyền mỗi chương.

Nguồn web dùng lại `KuaikanAdapter → ImageCollection → ChapterCache →
LocalComicJob → ProcessingManager`. QThread, progress byte/trang, checkpoint,
pause/resume/cancel cũ được tái dùng; OCR/Paddle/Argos/render không nhân bản.
ChapterCache lưu snapshot quyết định, provenance **adapter_download_by_user_policy**,
content_permission UNKNOWN. Giới hạn mẫu QA được ghi rõ, không gọi là hoàn thành
toàn chương116 ảnh.

### Downloader đã triển khai và giới hạn

`sources/kuaikan_download.py` chỉ phục vụ Kuaikan, không framework nhiều website:

- TLS verify/DNS public-IP pin dùng cơ chế sẵn có; hostname chính xác
  tn1.kkmh.com, HTTPS443, validate mỗi redirect, tối đa3 hop.
- Tải tuần tự, tối đa200 ảnh/chương,32MB/ảnh,512MB thư mục tải/chương,2GB cache;
  không cắt chương vượt cap âm thầm. Connect/read timeout tối đa10s mỗi lần,
  deadline30s cho một attempt; tối đa2 attempts với backoff cho lỗi tạm thời.
- Content-Type allowlist, magic PNG/JPEG/WEBP/BMP, Pillow verify **và** decode,
  pixel/hash checks. MIME không phải ảnh dừng, không đổi header để thử lại.
- File UUID.part → kiểm tra bitmap → rename nguyên tử không ghi đè trên Windows
  → checkpoint download-manifest.json. Tên file do app tạo theo thứ tự, không
  dùng tên URL. Manifest/directory/path traversal/symlink/containment được kiểm tra.
- Cache hit kiểm tra bitmap/hash/path identity rồi mới bỏ qua GET. Query ký có
  thể khác nhưng không đổi hay làm mới; danh sách path phải khớp. Cache hỏng hoặc
  file chưa có receipt được giữ lại/báo lỗi, không ghi đè. Manifest giới hạn1MB.
- Pause/cancel tại checkpoint; request đang chờ socket có thể đợi tới timeout.
  Giữ file dở/receipt/job lỗi để resume, không tự dọn dữ liệu chưa hoàn tất.

### Live download và bitmap — 2 ảnh, trong giới hạn tối đa12

Đã thử **2 ảnh đầu** chương281106. **Chỉ2 GET ảnh thực**, không tải116 ảnh.
Metadata200, cả hai CDN response200; không có401/403/429. Không dùng cookie,
Referer, tài khoản, proxy khác hoặc User-Agent thay thế.

| Ảnh cache | MIME / format decode | Byte | Kích thước | SHA-256 |
| --- | --- | ---: | --- | --- |
| 0001.jpg | image/jpeg /JPEG | 403092 | 1280×1000 | bbc37f6560aa4e200aff6e39f58d51fa92f7e84f1f20f701ef27f36ae5cd5d23 |
| 0002.jpg | image/jpeg /JPEG | 286022 | 1280×1000 | d85abed93fe0cd71f31a6a62476b4e08ca5eed4b2dd865f19055acff12d849e4 |

Tổng **689114 byte**, MIME/magic/decode/hash/atomic/cache PASS:
**LIVE_IMAGE_DOWNLOAD_PASS (USER_POLICY_DEFAULT_ALLOW; content permission UNKNOWN)**.
Lượt kiểm tra cache, lần xác minh lại và GUI sample không gửi thêm GET ảnh.
Không ghi URL signed thật vào các báo cáo hoặc receipt.

Cache gốc:
`cache/kuaikan-user-policy-validation/kuaikan-default-allow-20261107T101940Z/incoming/`.
Download receipt ghi discovered_images116/requested_images2/sample=true và
sample_complete. Không dùng receipt này để khẳng định116 trang đã tải.

### E2E, GUI và bằng chứng QA thật

- **KUAIKAN_URL_TO_TRANSLATION_E2E_PASS, mẫu2 ảnh:** public URL → manifest →
  downloader thật → ChapterCache → ProcessingManager gốc → OCR/Argos Offline →
  inpainting/render/export. **2 vùng OCR/2 bản dịch thật**,2 output,0 lỗi;
  kích thước giữ1280×1000, ảnh tải/cache nguồn giữ hash. Không nhập tay OCR/MT.
- Output PNG và JSON OCR/MT tại
  `output/kuaikan-user-policy-validation/kuaikan-default-allow-20261107T101940Z-verified/`.
  Không coi số vùng hoặc bản dịch không rỗng là nghiệm thu chất lượng MT.
- **GUI Windows Qt sample PASS**: nút thật → QThread → LocalComicJob thật,
  cache→OCR/MT→xuất2 ảnh,307 heartbeat, pause/resume PASS. QA adapter chỉ giới
  hạn2 ảnh qua super.download_chapter; launch observer chỉ đặt cache/database
  QA riêng. Không mock network response/ảnh/OCR/MT. Hai ảnh đã tải được sao chép
  vào cache QA bằng hash verification; GUI không tải lại. Chính ứng dụng không
  bị giới hạn2 ảnh bởi QA, nhưng full116 ảnh chưa kiểm thử.
- GUI output:
  `output/kuaikan-user-policy-validation/kuaikan-default-allow-20261107T101940Z-gui/`.

Evidence dưới `logs/kuaikan-default-allow-20261107T101940Z/`:

- `live-sample.json`: chứng cứ download/bitmap/cache200 thật; lượt báo cáo đầu
  FAIL vì QA đọc sai thuộc tính TranslationCache.db thay vì connection.
- `live-sample-verified.json`: cache hit0 GET ảnh, fresh pipeline hoàn thành2
  ảnh/OCR2/MT2; FAIL phần cuối QA vì truyền str vào file_digest cần Path.
- Các lỗi QA giữ nguyên. Đã sửa accessor/type trong diagnostic, rồi kiểm tra
  độc lập DB checkpoint, Pillow outputs, nguồn/cache hashes:
  **`live-sample-audit.json` PASS**. Không sửa core hoặc đổi kết quả dữ liệu để
  vượt lỗi; GUI sample sau đó cũng hoàn thành đường orchestration thật.
- **`gui-sample.json` PASS**, screenshot `gui-sample.png`; policy/receipt
  chứng minh USER_POLICY và UNKNOWN cùng tồn tại. Không biến QA sample thành
  bằng chứng cấp phép hoặc full-chapter PASS.

### Regression cuối và thay đổi source

**Pytest207 PASS,10 SKIPPED,0 FAIL. Unittest217 ca,207 PASS,10 SKIPPED,
0 errors/failures.** Thêm27 ca:9 policy/config/access flags,17 mocked downloader,
1 GUI explicit selection. Mocked tests gồm success/decode/order/signature,
401/403/429 STOP, HTML/CAPTCHA, corruption/MIME, size/quota, redirect/host/DNS,
timeout/retry, proxy, cancel/resume/cache hit/tamper/path traversal/receipt bounds.
Không gọi mock là live download; 3 live opt-in trong suite skip để tránh GET thừa.

Test strict cũ được giữ dưới config verified_only; default-policy assertions
đổi thành ALLOWED_BY_USER_POLICY **và vẫn kiểm tra UNKNOWN permission** theo
yêu cầu mới. Lịch sử Stage A không sửa. Captured DOM vẫn26 mục/116 URL.
Không thay hoặc hardcode OCR/MT output để làm test PASS.

Production sửa: `sources/states.py`, `kuaikan.py`, `kuaikan_dom.py` (chặn flags
VIP/login/DRM/CAPTCHA), `cache.py`, `service.py`, `ui/comic_sources.py`.
Mới: `sources/download_policy.py`, `sources/kuaikan_download.py`,
`config/download_policy.json`, `tests/test_default_allow_policy.py`,
`tests/test_kuaikan_downloader.py`. Test cập nhật:
`test_kuaikan_download_policy.py`, `test_kuaikan_captured_dom.py`,
`test_kuaikan_ssr.py`, `test_kuaikan_http_runtime.py`.

- Full tests: `pytest-final.xml`, `unittest-final/test-results.json` trong evidence.
- Local single/folder + OCR/MT/cache/output/pause/resume thật PASS:
  `output/source-tabs-validation/20261107T103619Z-e47190/report.json`.
- Local Offline E2E tổng hợp PASS:
  `output/e2e-validation/20261107T103719Z-d089ec/report.json`.
- Windows Qt smoke PASS: `logs/gui-smoke-20261107T103716Z-2dc106/report.json`.
- Backup trước sửa: `backups/kuaikan-default-allow-20261107T101940Z/`.
  `preservation.json`:93 file bảo vệ giữ hash; core/providers/native guard/BAT/
  spec/settings/DOM/4 EXE không đổi,5 model integrity PASS. Chỉ thêm config policy
  mới, không cài package, đổi Python/.venv hoặc xóa dữ liệu/cache/output.

### NOT_TESTED và bước tiếp

Chưa kiểm thử tải/dịch toàn116 ảnh, nhiều chương hoặc truyện khác, khôi phục sau
crash giữa rename/receipt thực tế, pause/cancel giữa socket CDN thật, TTL của
sign/t, mọi định dạng ảnh nền phức tạp và chất lượng dịch truyện đầy đủ. Các lỗi
server/DRM/redirect/cancel đã mock-test, không giả có live403 để báo STOP PASS.

Không build hoặc kiểm thử EXE mới;4 EXE cũ chưa chứa downloader/policy này.
Dùng source để tiếp tục nghiệm thu chương lớn hơn theo lựa chọn chủ động của
người dùng. Giữ quyền nội dung UNKNOWN cho tới khi có bằng chứng thực; nếu xác
minh hạn chế áp dụng hoặc gặp chặn kỹ thuật thì BLOCKED, không đổi header/URL
để vượt qua. Cache chưa có tự động prune incoming; chạm quota sẽ báo lỗi và giữ
dữ liệu, không tự xóa để tiếp tục tải.

---

## Lịch sử Stage A — giữ nguyên kết luận và bằng chứng tại thời điểm kiểm tra

Ngày kiểm tra: **07/11/2026**. Workspace: `D:\TransTool`.
Evidence: `logs/kuaikan-download-policy-20261107T095823Z/`.

## 1. Kết luận và phạm vi

**Giai đoạn A hoàn thành. Cổng quyết định: Trường hợp C — DOWNLOAD_UNKNOWN.**
Không xác minh được nguồn cho phép đủ rõ cho công cụ bên ngoài tự tải ảnh chương
281106, lưu cache và xuất bản dịch cá nhân. **Giai đoạn B: BLOCKED_BY_POLICY** do
thiếu bằng chứng cho phép trong phạm vi dự kiến, không phải FAIL kỹ thuật CDN
hoặc kết luận pháp lý rằng mọi cách đọc/lưu cá nhân đều bị cấm.

Không gửi HEAD/GET ảnh, không thử chữ ký/CDN, không tạo downloader hoặc chạy
OCR/MT trên ảnh lấy từ Kuaikan. Không thay parser đang PASS hay pipeline Offline.
Metadata và image discovery vẫn dùng được; chế độ ảnh người dùng cung cấp giữ nguyên.

Phạm vi: `www.kuaikanmanhua.com`, topic6677, chapter281106 và phân tích cấu trúc
URL `tn1.kkmh.com`. Không crawl truyện khác, API hoặc tài nguyên ảnh. Các nguồn
chính sách liên quan được đọc bằng HTTP/công cụ web, không dùng tài khoản/cookie.

## 2. Nguồn chính thức đã kiểm tra và đánh giá bằng chứng

| Nguồn / phần thực tế | Bằng chứng ngắn và phạm vi | Phân loại |
| --- | --- | --- |
| [Thỏa thuận hiện được phục vụ](https://www.kuaikanmanhua.com/webs/agreement), serviceData4.1–4.2 | Quyền đọc/xem trực tuyến; không phải cấp quyền downloader ngoài | OFFICIAL_PERMISSION, chỉ đọc |
| Cùng nguồn,4.6.4 | Hạn chế tự động hóa/thu thập trong cộng đồng khi chưa có chấp thuận; giữ đúng phạm vi cộng đồng | OFFICIAL_RESTRICTION |
| Cùng nguồn,8.4.3 | Hạn chế thu thập cho huấn luyện/tối ưu AI và sản phẩm dữ liệu thương mại; không đánh đồng với suy luận OCR/MT | OFFICIAL_RESTRICTION, phạm vi nêu trong điều khoản |
| Cùng nguồn,9.1 và11.7 | Bảo lưu quyền nội dung; quyền chưa cấp cần chấp thuận riêng | OFFICIAL_RESTRICTION / không có grant tương ứng |
| Cùng nguồn, policyData1.13 | Mô tả tải ảnh/video trong app và quyền ghi bộ nhớ; chưa cấp quyền tải CDN bằng app khác | INSUFFICIENT_EVIDENCE |
| [FAQ chính thức](https://www.kuaikanmanhua.com/webs/help), phần đọc miễn phí | Nêu đọc trực tuyến không đăng nhập; không nói tự động tải ngoài app | OFFICIAL_PERMISSION, chỉ đọc |
| [VIP agreement](https://www.kuaikanmanhua.com/anim/vipAgreement.html),II.2.2 vàVI.1.3 | Có mục đích cá nhân/phi thương mại nhưng vẫn hạn chế sao chép/tải/dịch chưa được phép; chỉ áp dụng nội dung VIP | OFFICIAL_RESTRICTION, không gán cho chương free |
| [Trang service agreement khác](https://www.kuaikanmanhua.com/anim/protocol2.html) | Đã đối chiếu; không tìm được grant phù hợp, phiên bản/trích xuất có khác biệt | INSUFFICIENT_EVIDENCE |

Trích ngắn từ serviceData11.7: **“未明示授权的其他权利仍由快看保留”** — nghĩa là
những quyền chưa được cấp rõ vẫn được bảo lưu. Từ FAQ: **“不登录也可以免费阅读”** —
có thể đọc miễn phí không đăng nhập. Hai câu có phạm vi khác nhau.

Lưu ý nguồn: `/webs/agreement` chứa nhiều tài liệu. Bản trích web mặc định có
thể chỉ hiện **thỏa thuận upload**, không phải service agreement cho người đọc.
Đã đọc literal Nuxt bằng decoder hiện có, không thực thi JS, để đối chiếu đúng
`data[0].serviceData.content` và `policyData.content`. Số mục hiện phục vụ là
11.7/1.13; một số bản tìm kiếm cũ dùng11.8/1.12. Không ghép số mục của hai bản
hoặc dùng quyền tác giả cấp cho nền tảng upload làm quyền của downloader ngoài.
Hash/tên tài liệu/vị trí mục ghi tại `official-policy-anchors.json`,
`review-addendum.json`, cùng hash response HTML trong `stage-a-evidence.json`.
Ngày phát hành/cập nhật chính xác của từng bản chưa xác minh; ngày đọc ở trên.

**Đánh giá của dự án:** chưa có căn cứ cho phạm vi tự tải/lưu/dịch này. Không dùng
việc miễn phí, mục đích cá nhân, chức năng tải trong app hoặc cấm AI training để
tự suy ra cho phép hay cấm toàn bộ thao tác OCR/MT cá nhân. Không gán
DOWNLOAD_ALLOWED hoặc DOWNLOAD_RESTRICTED cho chương free từ các suy diễn đó.

## 3. Quyền đọc và điều kiện sử dụng dự kiến

| Thao tác | Mức xác minh |
| --- | --- |
| Đọc chương281106 | PUBLIC theo metadata hiện tại; free/unlocked/noVIP/noPay |
| Lưu ngoại tuyến bằng chức năng chính thức | Có mô tả tính năng chung; chưa xác minh cho chương này và xuất ra ngoài app |
| Tải ảnh chương bằng công cụ ngoài | Chưa có grant áp dụng được |
| Cache tạm + OCR/MT cá nhân + xuất ảnh dịch | Chưa có grant áp dụng được; tách khỏi AI training |
| Phát hành/chia sẻ kết quả | Không thuộc yêu cầu; không suy quyền từ mục đích cá nhân |

HTTP metadata thật của topic/chapter vẫn200,26 mục/23 main và116 URL manifest.
Chương15 ID281106, tên `第15话 查出死因`, cờ `is_free=true`, `locked=false`,
`locked_code=200`, `need_vip=false`, `is_pay_comic=false`. Đây là
**TECHNICAL_OBSERVATION**, không phải quyền tải. `download_decision` thực tế vẫn
DOWNLOAD_UNKNOWN và có link nguồn điều khoản. Metadata không thay giấy phép.

## 4. URL CDN — phân tích trong bộ nhớ, không request ảnh

| Thuộc tính | Quan sát thật từ manifest response |
| --- | --- |
| HTTPS / host | Chỉ HTTPS, hostname chính xác `tn1.kkmh.com` |
| Manifest / lựa chọn parser | 116 record /116 URL chọn, thứ tự theo manifest |
| url và url1280 | Mỗi trường116 URL, mỗi biến thể116 path duy nhất |
| Query keys | sign,t |
| Hình dạng sign/t | sign32 ký tự hex, t8 ký tự; không ghi giá trị |
| Path suffix quan sát | `.webp-t.w640.jpg.h`, `.webp-t.w1280.jpg.h` |
| Metadata width/height | width1280; height23–1000; chưa phải kích thước decode |
| Kiểm tra cú pháp/allowlist hiện có | Cả232 URL biến thể hợp lệ;0 record bị loại trong lựa chọn116 |
| Thời hạn/chức năng mật mã chữ ký | NOT_TESTED, không suy từ tên hoặc giải mã t |
| CDN DNS/TLS/status/rate-limit/Referer | NOT_TESTED: không HEAD/GET CDN |
| MIME/bitmap thực tế | NOT_TESTED; suffix không chứng minh định dạng |

`sources/kuaikan_dom.py:image_url` kiểm tra HTTPS/host chính xác, credential,
placeholder và dạng sign/t đã thấy. Kiểm tra này không chứng minh ảnh truy cập
được hoặc được phép tải. Không tạo, đổi, gia hạn hoặc dò chữ ký; không lưu URL
còn chữ ký vào log/fixture/báo cáo. Không có cookie/token tài khoản được lấy.

`stage-a-evidence.json` chỉ chứa thống kê, cờ đọc, status page và policy decision.
Audit trong script chỉ cho GET HTML các path pháp lý/topic/reader đã định;
request CDN/ảnh bị từ chối trước gửi. **Số request ảnh:0; số ảnh:0; số byte ảnh:0**.

## 5. Cổng quyết định và trạng thái giai đoạn B

Quyết định cuối tại `decision.json`: **case C / DOWNLOAD_UNKNOWN**. Có tài liệu
chính thức nhưng chưa xác minh grant phù hợp cho tải tự động ảnh chương miễn
phí bởi Image Translator VN. Do đó không đánh dấu DOWNLOAD_POLICY_VERIFIED,
DOWNLOAD_ALLOWED hoặc LIVE_IMAGE_DOWNLOAD_PASS.

| Bước | Trạng thái |
| --- | --- |
| Stage A / review chính sách / thiết kế kỹ thuật | Hoàn thành theo bằng chứng trong báo cáo |
| Stage B live image HEAD/GET | BLOCKED_BY_POLICY,0 request |
| Decode ảnh Kuaikan / cache ảnh web | NOT_TESTED |
| Downloader / mocked downloader mới | Không triển khai / NOT_TESTED |
| Kuaikan URL → OCR/MT → output | NOT_TESTED; không gán KUAIKAN_URL_TO_TRANSLATION_E2E_PASS |
| Metadata / URL ảnh discovery | LIVE_HTTP_PASS / IMAGE_DISCOVERY_PASS, giữ |
| Ảnh cục bộ và Offline | LOCAL_OFFLINE_E2E_PASS / OFFLINE_REGRESSION_PASS |

BLOCKED_BY_POLICY ở đây là **gate thiếu bằng chứng cho phép**, không phải HTTP
403, CDN lỗi hoặc kết luận mọi hình thức đọc cá nhân bị cấm. Chapter locked hoặc
restricted vẫn cho DOWNLOAD_RESTRICTED theo cờ riêng, không phải chương mẫu.

## 6. Khả năng tái sử dụng cache/pipeline nếu sau này đủ điều kiện

Đã đọc interface thật, không tạo framework/downloader mới:

- `KuaikanAdapter.download_chapter` hiện kế thừa stub từ WebsiteAdapter. Khi đủ
  điều kiện, implementation phải trả `ImageCollection` đã kiểm tra, nằm đúng
  `_incoming/<site>/<comic>/<chapter>` được cấp, không lấy path từ URL tùy ý.
- `sources/collection.py:ImageCollection.discover/request`: danh sách file/natural
  sort, chuyển sang Options + only paths cho pipeline gốc.
- `sources/cache.py:ChapterCache.stage`: kiểm tra ảnh thật/hash, cache/quota,
  manifest, resume/cancel; `inspect_image` có giới hạn32MB/65 triệu pixel,
  verify rồi decode Pillow. Quota cache mặc định2GB. Đây chưa phải HTTP download.
- `sources/service.py:LocalComicJob` kiểm tra lại policy từng chương/capability/
  containment; giữ provenance website, đưa qua ChapterCache và ProcessingManager.
  Mỗi batch tái dùng OCR/TranslationService, cưỡng chế Offline/không online fallback.
- `ui/comic_sources.py`: bật tải chỉ khi ALLOWED và có implementation; UNKNOWN
  vẫn phân tích/chọn được. QThread/progress/cancel hiện có tiếp tục dùng được.

Một HTTP downloader tương lai vẫn cần allowlist/TLS/DNS-public/redirect validation,
byte/timeout/rate/connection limits, MIME/magic/decode/hash, tên file do app tạo,
atomic write, manifest/cache integrity, pause/cancel và retry hữu hạn. Dừng
401/403/429; không request lặp để dò chữ ký. Không dùng transport HTML2MB làm
download ảnh bằng cách bỏ validation. Không cleanup nguồn/job chưa hoàn tất.
Đây là đánh giá thiết kế, không phải implementation hoặc integration PASS.

## 7. Kiểm thử đã chạy

**Pytest:180 PASS,10 SKIPPED,0 FAIL. Unittest:190 ca,180 PASS,
10 SKIPPED,0 errors/failures.** Baseline172/10 giữ nguyên, thêm8 policy tests tại
`tests/test_kuaikan_download_policy.py`:

1. PUBLIC reading vẫn UNKNOWN.
2. Locked → RESTRICTED.
3. Restricted → RESTRICTED.
4. Thiếu policy source không cho phép tải.
5. Link policy đơn lẻ không thành grant.
6. Cờ legacy/enum ALLOWED đơn lẻ không vượt thiếu grant Kuaikan.
7. Discovery fixture có URL ảnh không tải hoặc tự cấp quyền.
8. Mocked HTTP200 + manifest vẫn UNKNOWN, chỉ1 GET page giả lập.

Các nhánh ALLOWED của generic fixture adapter đã có trong `test_source_tabs.py`
vẫn PASS: đó là **mô phỏng quyết định để test UI/pipeline**, không phải bằng
chứng chính thức cho Kuaikan. Không tạo fixture quyền cho phép giả. Trường hợp
grant thực tế và downloader Kuaikan được phép vẫn NOT_TESTED.

- Captured DOM/SSR và policy/HTTP/GUI unit regression PASS. Hai DOM gốc không đổi.
- Live metadata/parser thật trong stage A: topic/chapter200,26 mục/116 URL;
  không tải ảnh. Không chạy thêm3 opt-in live test trong suite để tránh request
  thừa. Lý do skip cũ nhắc sandbox không mô tả phiên hiện tại.
- 7 skip còn lại giữ lý do thiếu model ngôn ngữ/M2M100 và Online opt-in;
  không ép skip thành PASS, không thay dependencies để xóa cảnh báo.
- MainWindow Windows Qt + ảnh đơn/folder/OCR/MT thật, pause/resume/cache/output,
  responsive/config/ảnh nguồn integrity PASS:
  `output/source-tabs-validation/20261107T100313Z-b089e3/report.json`.
- **LOCAL_OFFLINE_E2E_PASS**: `output/e2e-validation/20261107T100357Z-afa34a/report.json`:
  ảnh Trung tổng hợp, OCR/Argos/mask/inpaint/render/export/model reuse thật.
  Không nhập tay kết quả, không là Kuaikan download E2E hay nghiệm thu chất lượng MT.
- GUI smoke Windows Qt PASS: `logs/gui-smoke-20261107T100353Z-1db06e/report.json`;
  không thay nghiệm thu desktop thủ công bằng smoke.
- Test logs: `logs/kuaikan-download-policy-20261107T095823Z/pytest.xml`,
  `pytest.log`, `unittest/test-results.json`.

## 8. File thay đổi và bảo toàn

**Không sửa production source.** Thêm `tests/test_kuaikan_download_policy.py`
và báo cáo này; cập nhật PROJECT_STATUS, KUAIKAN_CHAPTER_281106_ANALYSIS và
WEBSITE_ADAPTER_AI_GUIDE. Script/evidence QA chỉ trong logs/ bị loại khỏi Git.
Không thêm package, cài lại Python/.venv, thay model/native guard hoặc build.

`preservation.json`: **102 file trước nhiệm vụ giữ hash**, gồm source/test cũ,
config, DOM, BAT/spec,4 EXE và model receipts. 5 model integrity PASS. Không
xóa cache/output/backup/ảnh người dùng, không ghi Git metadata hoặc liên hệ ai.
Không có ảnh Kuaikan mới để nối cache/OCR/MT; pipeline cục bộ vẫn nguyên trạng.

## 9. Điều chưa xác minh và bước tiếp

Chưa xác minh quyền cho công cụ ngoài với chapter281106; thời hạn chữ ký, CDN
network/MIME/bitmap/rate-limit và grant phù hợp vẫn chưa có. Giai đoạn B dừng đúng
phạm vi theo yêu cầu người dùng, không cố hoàn thành bằng dữ liệu giả.

Muốn mở gate cần nguồn chính thức hoặc chấp thuận có hiệu lực đủ phạm vi:
tải tự động ảnh chương, dùng CDN/giới hạn request, lưu cache và thời hạn lưu,
xử lý OCR/MT cá nhân và xuất bản dịch; phân biệt quyền nội dung với quyền truy
cập nền tảng. Một checkbox tự khai hoặc link điều khoản không thay bằng chứng.
Không cần gửi lại DOM hoặc cookie/token. Trong lúc chưa đủ điều kiện, tiếp tục
metadata/discovery và dịch ảnh người dùng đã lưu hợp lệ qua tab cục bộ.
Không yêu cầu tự thực hiện thao tác nghiên cứu này mỗi lần dùng app; chỉ đánh
giá lại khi quyền, điều khoản hoặc nguồn dữ liệu có thay đổi liên quan.
