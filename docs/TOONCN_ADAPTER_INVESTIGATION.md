# ToonCN — khảo sát và tích hợp Chrome đã cấp quyền

## Kết quả hiện tại — 10/11/2026

**HOẠT ĐỘNG với metadata, GUI và tải mẫu thật; chưa nghiệm thu toàn chương
hoặc dịch ToonCN thật.** Không chỉ là fixture hay nhận diện domain.

| Hạng mục live | Kết quả |
|---|---|
| Native host đã đăng ký | Đúng tên, manifest/launcher và extension origin ở HKCU |
| Dữ liệu v1 trước điều tra | 0snapshot, chưa có inbox; không yêu cầu gửi lại dữ liệu đã tồn tại |
| Chrome thật qua native port v2 | Đã kết nối, peer version0.3.0 |
| Truyện | 为民服务App, https://tooncn.net/webtoon/5701569/ |
| Danh sách chương |32liên kết thực, từ1đến33 nhưng không có19; không tự bù/invent chương |
| Chương thử | Ep1, https://tooncn.net/5701569-Ep-1/ |
| Ảnh thực trong reader |316URL duy nhất, DOM order khớp0001.jpg…0316.jpg |
| Tải mẫu thật |3/316JPEG,720×800,3hash khác nhau, filename/thứ tự1–3 đúng |
| GUI Qt Windows offscreen + Chrome thật |32dòng, chọn1,316ảnh phân tích, nút Tải và dịch enabled |
| Chạy OCR/MT/render ToonCN thật |CHƯA KIỂM THỬ; không gọi AGY/API dịch |

Không yêu cầu người dùng cung cấp DOM/HTML/cookie/selector. Người dùng tự
Reload extension hai lần để cấp kênh nhận và nạp phần ảnh dựa trên DOM thật.
Không tạo profile QA mới, đóng Chrome hoặc trích xuất session. Không tải cả
truyện/chương. Bật kết nối không tự dịch hoặc tải mọi chương.

### Cấu trúc đã quan sát và tích hợp

Topic nhận780node trước lọc scope; h1.entry-title có tên truyện,
#chapterlist .eph-num a có32chapter links. Reader nhận528node, trong đó316
img.ts-main-image dưới #readerarea. data-src trỏ ảnh JPEG thật cùng origin
/wp-content/uploads; src/currentSrc là readerarea.svg200×200 placeholder.
Parser chỉ dùng reader, không lấy thumbnail/sidebar, kiểm duplicate/gap/order.
Fixture giữ cấu trúc quan sát, topic excerpt200node và reader excerpt3ảnh;
đường dẫn ảnh được ẩn danh, provenance ghi316ảnh live khác với3ảnh fixture.

URL/ID không hardcode sample: adapter nhận /webtoon/<id>/ và /<id>-Ep-<số>/,
source_kind chapter cho URL đọc trực tiếp. Extension cho các route công khai
tooncn.net, không đọc auth/admin. Chưa thấy website dùng www.tooncn.net trong
DOM đã nhận, không tự thêm quyền www hoặc CDN khác. Không dùng <all_urls>.

Kênh v2: nút ToonCN BẬT/TẮT → lease20s, heartbeat5s → native host chỉ chuyển
request capture/image → extension đọc đúng tab/URL đã yêu cầu. Khi cần mở
chương, chỉ dùng tab ToonCN do extension tạo trong Chrome hiện có, không chiếm
tab website khác. Load/stability wait hữu hạn90s; challenge/denied dừng. Lượt
đầu mở tab mới từng báo UNEXPECTED_NAVIGATION khi tab chưa load xong; đã đổi
thứ tự chờ status complete trước kiểm URL. Đọc lại chương đang mở thành công.

Ảnh fetch same-origin trong Chrome, cookie chỉ được browser sử dụng nội bộ.
Native transfer chunk có ACK, ID/session/sequence/size/hash; quá8MiB/ảnh từ
chối. Python inspect_image kiểm MIME/decode/hash và loại placeholder1pixel.
Downloader cũ chỉ mở hai hook tùy chọn fetcher/URL validator; Kuaikan default
không đổi. Resume/atomic publish/ChapterCache/ProcessingManager dùng luồng cũ.
Tối đa500ảnh/chương, quota nguồn giữ như downloader hiện có; không tăng AGY
batch/timeout/budget hoặc thay provider. Lỗi nguồn không bị gọi là Gemini quota.

Không capture mọi trang liên tục: chỉ đọc lại theo request ứng dụng, đợi DOM
ổn định trong lượt đang xử lý. Native port idle khi TẮT không query/read tab.
TTL10phút chỉ áp dụng request/response/binary UUID của runtime-v2; cap metadata
16MB và binary64MiB. Không xóa inbox v1/cache nguồn/journal/DB/output cũ.
App crash hết lease sẽ ngừng thu; tắt ngăn kết quả đến muộn và abort ảnh đang
fetch. Mặc định TẮT sau restart app, không auto resume/translation.

### Kiểm thử và bảo toàn

- Full pytest: **561PASS,10SKIP,0FAIL**,181.47s.
- Full unittest bootstrap runtime: **561PASS,10SKIP,0FAIL/0ERROR**,571ca,193.130s.
  Wrapper đọc log sau test gặp UnicodeDecodeError vì log trộn encoding;
  process test exit0 và footer ASCII xác nhận kết quả, không rerun để che lỗi.
- Targeted cuối: **67PASS**,5.03s, gồm bridge, lease, callback fake Chrome,
  image chunk, decoder/ordered downloader, source tabs và nút OFF khi job busy.
  Sửa an toàn dọn file vừa được phía kia consume và đăng ký startup/install
  listener được kiểm tra targeted cuối. Không gọi mock là live website.
- Fixture mới dựa trên DOM thật; các response/byte/chunk sai dùng fake rõ ràng.
  Bộ test đầu có1lỗi đọc UTF-8 trong test manifest, đã sửa test, không skip lỗi.
- Ảnh thật đã vào được ImageCollection.request cho ProcessingManager; không
  chạy OCR/MT/render để giả chứng minh chất lượng bản dịch. Không có ảnh dịch
  ToonCN được tạo,3JPEG nguồn giữ riêng trong cache/tooncn_qa/.
- 30.950file size/mtime và244SHA chọn lọc giữ nguyên,0mất file; gồm ảnh chương5,
  provider/AGY lifecycle, cấu hình host đã cài, source cache/DB/journal/model/EXE
  trong snapshot. Không nói đã hash toàn bộ .venv/model.

Evidence: `logs/tooncn-connect-20261109T170347Z/`: acceptance.json, gui-live.json/
png, pipeline-input.json, pytest-full.txt, unittest-full.txt, preservation và
Git. Dữ liệu đầy đủ đã nhận chỉ nằm trong runtime-v2 có TTL; không lưu raw
cookie, token, profile hoặc auth header vào log. Snapshot v1 không có nên chưa
thể chứng minh lỗi cụ thể của lần gửi cũ; entry point local có trả đúng frame.
Sau Reload đã có bằng chứng IPC/DOM/ảnh thật, không suy đoán nguyên nhân cũ.

### Sử dụng và giới hạn nghiệm thu

Reload bridge để nạp mã cuối cùng (không thêm quyền), mở lại ứng dụng từ
run_source.bat, vào Link truyện online, bật ToonCN, dán URL và phân tích.
Chọn chương → Phân tích chương đã chọn → Tải và dịch. Không phải Gửi trang
thủ công nữa. Chỉ tải những chương người dùng chọn. Website có thể yêu cầu
xác minh lại ở lần khác; lượt QA chương1 không phải xác minh lại, không bảo
đảm mọi chương/tài khoản về sau. Nguồn đổi cấu trúc thì fail closed.

GUI screenshot offscreen đã nạp font UI/theme hiện có, không thay renderer;
CJK fallback ở môi trường offscreen có thể thiếu, không tuyên bố nghiệm thu
font CJK/desktop vật lý đầy đủ. Xem README extension để tắt/gỡ/tra mã lỗi.

### Git & Fork Handoff — lượt hoàn thiện adapter

Root D:/TransTool, main, HEAD9f530cfabcb051cdebdcca3268f4c781be58190c. Baseline
11tracked modified/19untracked từ AGY và cầu nối trước; giữ nguyên hunk cũ.
Cuối lượt15tracked modified/32untracked,0staged/conflict. .gitignore không đổi.
Source/test/docs mới không bị ignore; cache/config/logs/output/model/EXE runtime
không commit. git diff --check exit0; warning CRLF của agy.py có từ trước.

Review: sources/tooncn.py, tooncn_bridge.py, tooncn_connection.py,
tooncn_native_session.py; registry.py; kuaikan_download.py (hai hook default
giữ nguyên); scripts/tooncn_native_host.py; ui/comic_sources.py (BẬT/TẮT);
extensions/tooncn_bridge/; tests/test_tooncn_* và3fixture/provenance;
README, PROJECT_STATUS, USER_GUIDE, TROUBLESHOOTING, WEBSITE_ADAPTER_AI_GUIDE
và báo cáo này. register_tooncn_host.py và các hunk AGY có sẵn review riêng,
không coi chúng là thay đổi mới của adapter. Không stage runtime/private data.

Commit gợi ý: `feat(sources): integrate consent-based ToonCN browser adapter`.
Người dùng review từng hunk, tự stage/commit trong Fork. Không build EXE,
không thay billing, không gọi dịch thật hoặc tự tải thêm ảnh sau nghiệm thu mẫu.

**NO_COMMIT — NO_PUSH — NO_TAG — NO_DESTRUCTIVE_GIT.**

## Lịch sử khảo sát và các phương án trước (giữ để đối chiếu)

## Chrome cá nhân và cầu nối extension — cần người dùng tự cấp quyền

Chrome cá nhân đã mở được ToonCN theo xác nhận người dùng; việc chỉ thấy title
ToonCN trước đây không phải bằng chứng ứng dụng có DOM. Lượt kiểm tra mới chỉ
liệt kê process Chrome và các TCP listener loopback thuộc chúng:28process,
**0listener**,0request debug. Không có endpoint CDP TCP dùng được trong phạm vi
được cấp quyền. Không khẳng định Chrome không có mọi dạng IPC/pipe, không dò
port của ứng dụng khác, đọc argv/profile/cookie, đóng/restart hoặc bật debug.
Đây là thiếu kênh kết nối được cấp quyền, không phải lỗi parser ứng dụng.

Đã xác định cơ chế giao tiếp/quyền trước khi triển khai:

- Chrome extension ManifestV3, chỉ host `https://tooncn.net/*`, quyền
  `scripting` và `nativeMessaging`. Không cookies/debugger/tabs/history/
  webRequest/activeTab/all_urls, không content script thường trực hoặc server
  ngoài. Chỉ truy vấn tab ToonCN đang active và chạy khi người dùng bấm nút.
- DOM là projection tag/parent/thứ tự/text và thuộc tính ảnh/link đã lọc;
  không raw HTML/script/form/input/iframe, cookie/storage/header hay biến phiên.
  Bỏ query/fragment URL để không xuất giá trị token/chữ ký. Chưa dùng URL đã
  bỏ query để tải ảnh, chưa phân loại ảnh truyện/thumbnail khi chưa thấy reader.
- Native Messaging stdio theo [tài liệu Chrome](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging),
  chỉ đúng extension origin `jhcbfanogbihlfaklgcnkppcmcbeblgl`, không HTTP server,
  socket nhận dữ liệu từ website, command/path tùy ý hoặc RPC điều khiển máy.
  `.bat` host trên Windows có mẫu [manifest chính thức](https://raw.githubusercontent.com/GoogleChrome/chrome-extensions-samples/main/api-samples/nativeMessaging/host/com.google.chrome.example.echo-win.json).
- Host kiểm origin trước đọc payload; frame1MB, strictschema/duplicatekey,
  thứ tự/parent ID, URL và kiểu dữ liệu. Capture tối đa4.000node/20.000element,
  không báo bản cắt thiếu là hợp lệ. Snapshot publish atomic vào thư mục mới
  riêng DACL owner/SYSTEM tại `cache/tooncn_browser/inbox/`; quota16MB/32snapshot,
  không overwrite hoặc tự xóa dữ liệu cũ. Không coi valid snapshot là valid MT.
- Python native host không gọi OCR/AGY/provider hay network. Installer chỉ khi
  người dùng tự chạy: ghi riêng manifest/launcher ở config/tooncn_bridge và
  một HKCU NativeMessagingHosts; kiểm conflict cả32/64bit, không ghi đè host khác.
  Codex **chưa chạy installer/uninstaller**, chưa tự cài extension/profile.

Các bước ít thao tác để tiếp tục (không cần copy DOM):

1. Người dùng chạy `extensions/tooncn_bridge/register_host.bat`.
2. Chrome đang có tài khoản → `chrome://extensions` → Developer mode →
   Load unpacked → chọn `D:\TransTool\extensions\tooncn_bridge` và tự cấp quyền.
3. Tại trang truyện đã mở hợp lệ, bấm extension → **Gửi trang ToonCN đang mở**.
   Mở chương1 trong chính Chrome đó, đợi trang thật rồi bấm gửi tương tự.

Không cần tạo profile/debug/restart hoặc dán HTML/cookie. Nội dung tới thư mục
cục bộ theo mã snapshot để Codex/ứng dụng đọc sau khi người dùng cho phép.
Chi tiết quyền, mã lỗi, tắt/gỡ: [README extension](../extensions/tooncn_bridge/README.md).

**Chưa đọc được DOM thật, chưa có parser/adapter ToonCN, chưa tải ảnh** trong
lượt này. Không đăng ký adapter chỉ để nhận diện domain. Bước thiếu duy nhất
trước khảo sát reader là người dùng cài/cấp quyền và bấm gửi. Sau khi có DOM
thật mới chọn vùng chapter/reader và cơ chế lấy byte ảnh hợp lệ trong browser;
chưa biết cần quyền CDN nào hoặc cần xác minh lại ở chương khác.

Code mới: `extensions/tooncn_bridge/` (manifest, popup, capture, README và2BAT),
`sources/tooncn_bridge.py`, `scripts/tooncn_native_host.py`,
`scripts/register_tooncn_host.py`, `tests/test_tooncn_bridge.py`,
`tests/test_tooncn_capture.mjs`. Không sửa AGY/OCR/renderer hoặc adapter cũ.
Local test bridge cuối:20pytestPASS và20unittestPASS; gồm native-host Python process
thật nhưng input fixture, DOM JS tổng hợp, không Chrome/account/website thật.
Lượt collection đầu lỗi raw-string kết thúc bằng backslash đã sửa; giữ riêng
kết quả local sau sửa, không gọi lỗi đó là PASS hoặc test live ToonCN.

Full pytest cuối sau bổ sung ca gỡ host shared-registry/conflict:
**541PASS,10SKIP,0FAIL**,212.13s (`pytest-final.txt`). Lượt full trước có539PASS/
10SKIP trước2ca mới, được giữ tại pytest-full.txt. Unittest chỉ chạy module
bridge:20PASS/0FAIL/0SKIP,0.260s; không tuyên bố đã chạy full unittest của lượt
này. Static AST4file Python và node --check3file JS đạt. Các test registry dùng
mock WinReg, không đăng ký/gỡ host thật. Không có live ToonCN/Chrome-extension
integration vì người dùng chưa cài/cấp quyền.

Evidence lượt này: `logs/tooncn-extension-20261109T163757Z/`, gồm Git baseline,
cdp-check, preservation, test và review cuối. Key trong manifest là public key
định danh extension; không có private key được lưu, không phải API credential.

### Git & Fork Handoff — cầu nối Chrome cá nhân

Root D:/TransTool, main, HEAD9f530cfabcb051cdebdcca3268f4c781be58190c không đổi.
Baseline10tracked modified/7untracked từ AGY và điều tra ToonCN; giữ nguyên.
Cuối lượt11tracked modified/19untracked: mới12file extension/host/bridge/test,
thêm hunk docs vào PROJECT_STATUS, USER_GUIDE, TROUBLESHOOTING, báo cáo này và
WEBSITE_ADAPTER_AI_GUIDE. Không sửa source AGY/OCR/renderer/registry adapter.

File nên review của lượt này:

- `extensions/tooncn_bridge/{manifest.json,popup.html,popup.js,capture.mjs,README.md,register_host.bat,unregister_host.bat}`.
- `sources/tooncn_bridge.py`, `scripts/register_tooncn_host.py`,
  `scripts/tooncn_native_host.py`.
- `tests/test_tooncn_bridge.py`, `tests/test_tooncn_capture.mjs`.
- Các hunk docs nêu trên; các thay đổi AGY có sẵn phải review riêng.

Không commit config/native-host runtime, inbox snapshot, logs/public-key QA,
browser profile, cache, DB, output, model hoặc EXE. .gitignore không đổi;
12file mới không bị che, runtime cache/config/logs vẫn ignore, không có runtime
tracked hoặc binary lớn mới. Public key trong extension manifest là cấu hình
source cần commit; không phải secret/private key.

30.710stat/242SHA bảo vệ giữ nguyên,0mất file. Không thao tác Chrome/profile,
đăng ký HKCU thật, gọi AGY/API dịch hoặc build. Git diff --check exit0;
warning CRLF→LF của agy.py có từ baseline.0staged/conflict.

Mở Fork → Local Changes, review đúng hunk/file, tự stage/commit khi đồng ý.
Commit gợi ý phản ánh trạng thái hiện tại:
`feat(sources): prepare consent-based ToonCN Chrome DOM bridge`.
Không dùng commit message tuyên bố adapter đã tải/dịch được.

**NEEDS_USER_EXTENSION_PERMISSION — chưa nghiệm thu ToonCN live.**

## Bổ sung: Chrome có giao diện, đang chờ xác minh thủ công

Lượt mới mở Chrome có giao diện, profile QA riêng được bảo vệ DACL; không
headless, không dùng profile cá nhân/cookie có sẵn, không stealth hoặc sửa
fingerprint. Đã điều hướng đúng URL mẫu, chờ và quan sát trạng thái trong
chính browser context, không chuyển cookie/token sang HTTP client.

Tại mốc171giây vẫn `VERIFYING`, title `Just a moment...`, main document nhận
HTTP403 qua sự kiện Network.responseReceived của trình duyệt. Đây là bằng
chứng số status của lượt mới, khác probe HTTP cũ thiếu lưu status riêng.
Chưa có DOM truyện, chưa thấy bằng chứng content đã tải. Chưa đủ bằng chứng
phải bấm CAPTCHA hay chỉ chờ; đã hỏi người dùng về cửa sổ và giữ mở cho họ
tự thao tác, không tự click. Không đánh dấu challenge là nội dung hợp lệ.

Observer chỉ đọc trạng thái/DOM sau khi có nội dung, không gọi API cookie,
không đọc token, không gọi dịch. Chờ tối đa10phút, cửa sổ giữ thêm tối đa5phút
để người dùng xử lý; không có vòng lặp retry HTTP client hoặc tự reset profile.
Website có thể tự phát lại challenge bên trong trình duyệt; đây không phải
bằng chứng xác minh thành công. Không biết chương khác có yêu cầu xác minh
lại hay không. Nếu vẫn chỉ challenge thì dừng tải/parser.

Evidence: `logs/tooncn-browser-20261109T162445Z/`, `browser-state.json` và
`observe-browser.mjs` là QA observer, **không phải adapter đã tích hợp GUI**.
Chưa sửa source ứng dụng hoặc đăng ký ToonCN; đang chờ bước tương tác của
người dùng trước khi có thể đọc reader thật và triển khai parser.

[Tài liệu Cloudflare](https://developers.cloudflare.com/cloudflare-challenges/reference/supported-browsers/)
không bảo đảm browser automation giải được production challenge; không suy
ra chỉ tăng thời gian chờ là đủ và không thêm cơ chế né nhận diện.

**CHƯA HOẠT ĐỘNG.** Chưa thể nghiệm thu URL mẫu hoặc triển khai parser từ DOM
trang đọc đã xác minh. Không đăng ký một adapter chỉ nhận diện domain để gọi
đó là hỗ trợ ToonCN. Không thay đổi source của ứng dụng trong nhiệm vụ này.

## URL mẫu và bằng chứng đã quan sát

URL bắt buộc: https://tooncn.net/webtoon/5701569/.

- Công cụ web đọc được bản trang thông tin truyện: **为民服务App**, ID5701569,
  trạng thái Ongoing, tác giả EOLKKI&平衡&陵墓;11liên kết chương từ1đến11.
  Đây là nội dung công cụ web trả về, có thể từ cache; không chứng minh ứng
  dụng đang truy cập live thành công. Không lưu danh sách gợi ý nội dung khác.
- URL chương1 công cụ web trích được: https://tooncn.net/5701569-Ep-1/.
  Công cụ web mở chương này báo TimeoutError, lần mở tiếp báo inaccessible.
  Chưa đọc được HTML/DOM trang đọc, chưa xác minh chương này công khai/tải được.
- Gọi đúng `sources.metadata_http.fetch_public_html` hiện có với URL mẫu:
  phát sinh AccessRestricted ở nhánh HTTP401/403, không nhận HTML truyện.
  Probe đầu gặp lỗi console encoding khi in thông báo tiếng Việt nên không
  lưu được mã status riêng. Không coi số403 trong cập nhật tiến độ là một
  diagnostic HTTP số đã được lưu đầy đủ; không suy đoán thêm nguyên nhân.
- Máy không có Playwright/Selenium; không cài dependency. Có Chrome/Edge.
  Đã mở Chrome headless thông thường với profile QA mới, không dùng profile,
  cookie, phiên đăng nhập hoặc credential cá nhân; không stealth/đổi danh tính.
  `--dump-dom` kết thúc exit0 sau2.187s,44.748byte DOM, title **Just a moment...**,
  có Cloudflare challenge marker. Exit0 trình duyệt không phải truy cập truyện
  thành công. Dừng tại challenge; không giải CAPTCHA hoặc lấy cookie để vượt.

Evidence cục bộ: `logs/tooncn-20261109T161349Z/`, gồm
`browser-inspection.json`, `browser-topic.html` (chỉ trang challenge),
`observations.json`, `source-regression.txt`, `preservation.json` và Git baseline.
Không đưa profile trình duyệt/DOM/log runtime vào Git. Không cần người dùng
cung cấp DOM, selector, XPath, ảnh DevTools hoặc URL khác.

## Những phần chưa thể xác minh

| Hạng mục | Kết quả |
|---|---|
| URL truyện hay trang đọc | Bản công cụ web đọc được là trang truyện |
| Số chương hiện tại trong ứng dụng | Chưa xác minh; bản web tool có11liên kết |
| DOM/API/JS tải danh sách chương | Chưa quan sát HTML thực tế từ ứng dụng |
| Reader ảnh gốc/thumbnail | Chưa xác minh |
| Lazy loading/data-src/srcset/phân trang | Chưa xác minh |
| Thứ tự và tổng số ảnh | Chưa xác minh, không ghi N=0 giả |
| Referer/header/redirect ảnh | Chưa xác minh, không đoán |
| Số ảnh tải | 0/N, N chưa xác định |
| Trùng/thiếu/placeholder/bitmap decode | CHƯA KIỂM THỬ vì chưa có danh sách ảnh |
| OCR/dịch/render ToonCN | CHƯA KIỂM THỬ, không gọi AGY |

Không dùng giả định WordPress/theme hoặc selector thông dụng để viết parser.
Không tạo fixture trang đọc giả rồi tuyên bố đã quan sát site. Không tải toàn
bộ truyện, không thử CDN/endpoint chưa được quan sát. Điều kiện tiếp tục là
website cho phép truy cập bằng HTTP hoặc trình duyệt thông thường mà không
vượt cơ chế chống truy cập; lúc đó Codex tự khảo sát DOM/network reader và
thử tải mẫu hữu hạn. Chưa chứng minh cần Referer, cookie hay endpoint nào.

## Kiến trúc đã khảo sát và phạm vi giữ nguyên

`sources/registry.py` hiện chỉ đăng ký Kuaikan. `ComicSourceWorker` gọi
adapter cho metadata/chapter/images, rồi `LocalComicJob` thực hiện download
decision → downloader → ChapterCache → ProcessingManager. URL chương được
phân biệt bằng `source_kind='chapter'`. `sources/kuaikan_download.py` có
allowlist CDN Kuaikan, kiểm MIME/magic/decode/hash, retry hữu hạn, pause/cancel
và manifest; không nới allowlist đó cho ToonCN khi chưa thấy host ảnh thực tế.
GUI đã dùng interface adapter nên chưa có căn cứ cần viết lại pipeline.

AGY Batch/Whole, timeout300/315s và600s, Job Object, model, prompt, hooks/MCP,
OCR/renderer, numeric/glossary, cache/journal/DB và mọi output cũ không đổi.
Không gọi AGY/API dịch, không build EXE, không tải ảnh/model.

## Kiểm tra local và bảo toàn

Regression có liên quan: **40PASS,0FAIL,0SKIP**,1.67s:

```
.venv\Scripts\python.exe -m pytest -q tests/test_comic_sources.py::URLSourceTests tests/test_kuaikan_http_runtime.py tests/test_kuaikan_downloader.py
```

Đây là test local/mock của nguồn hiện có, không phải kiểm thử tích hợp ToonCN.
Không tạo test ToonCN parser khi chưa có cấu trúc reader đã quan sát. Không
chạy lại full pytest/unittest vì không có thay đổi source/test; baseline AGY
521PASS/10SKIP trước đó không phải kết quả regression toàn bộ của nhiệm vụ này.

30.710file được đối chiếu size/mtime:0đổi/0mất;243SHA chọn lọc giữ nguyên,
gồm AGY provider/runner, planner/pipeline/Whole/resume, config, BAT/spec và
218ảnh Batch+Whole chương5. Không tuyên bố đã hash toàn bộ .venv/model.

## Git & Fork Handoff

Root `D:/TransTool`; main; HEAD `9f530cfabcb051cdebdcca3268f4c781be58190c`.
Baseline10tracked modified/6untracked từ nhiệm vụ AGY trước,0staged/conflict;
không hoàn nguyên hoặc nhận các thay đổi đó là triển khai ToonCN.

Nhiệm vụ này chỉ sửa `PROJECT_STATUS.md`, `docs/USER_GUIDE.md`,
`docs/TROUBLESHOOTING.md` (đều đã modified trước đó) và thêm báo cáo này.
Cuối lượt10tracked modified/7untracked. Danh sách đầy đủ của cả working tree
có trong `git-final.json`; không chọn commit toàn bộ mà chưa review các hunk AGY.
`.gitignore` không đổi; logs/cache/output/profile runtime vẫn bị ignore,
source/test/docs và báo cáo này không bị che. Không có runtime tracked.
`git diff --check` exit0; cảnh báo CRLF→LF của agy.py đã có từ baseline.

Chỉ commit tài liệu cần thiết sau khi review trong Fork → Local Changes.
Không commit log/profile trình duyệt/cache/DB/output/model/EXE hoặc credential.
Commit gợi ý nếu chỉ lưu điều tra này:
`docs(sources): record ToonCN access blocker`.

**Không hoàn thành tích hợp; blocker là quyền truy cập thực tế từ môi trường
khảo sát. Không yêu cầu người dùng cung cấp DOM.**

**NO_COMMIT — NO_PUSH — NO_TAG — NO_DESTRUCTIVE_GIT.**
