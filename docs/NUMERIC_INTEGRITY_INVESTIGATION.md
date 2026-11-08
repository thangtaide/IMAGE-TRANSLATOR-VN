# Điều tra hai ảnh bị numeric integrity validation từ chối

Ngày điều tra: 07/11/2026. Phạm vi: chỉ đọc dữ liệu hiện có, kiểm thử unit/mock
trong vùng tạm riêng. Không sửa production source, settings, checkpoint hoặc
manifest; không gọi lại OCR/MT thật, không truy cập mạng, không tải ảnh, không
resume và không build EXE.

## 1. Đúng job và dữ liệu hiện có

- Truyện `6677`, chương **274872 — 第1话上 换新娘**. Đây không phải chương QA
  `281106` và không phải lượt QA hai ảnh.
- Pipeline job ID:
  `e82b4eb8abed1050602c5d01b62322bd021684c54cebb1715d62b206fd9feca8`.
- Ảnh tải đã lưu:
  `D:\TransTool\cache\online_comics\_incoming\kuaikanmanhua\6677\274872`.
- Nguồn pipeline:
  `D:\TransTool\cache\online_comics\kuaikanmanhua\6677\chapter_274872`.
- Output nội bộ:
  `D:\TransTool\output\online_comics_work\12cb0a10b74907b58b9d\6677\274872`.
- Output người dùng:
  `D:\TransTool\output\test_download-orc\权妃之帝医风华__6677\0002_第1话上 换新娘__274872\run_e82b4eb8abed1050`.
- Chapter manifest:
  `cache/online_comics/kuaikanmanhua/6677/chapter_274872/manifest.json`.
- Download receipt:
  `cache/online_comics/_incoming/kuaikanmanhua/6677/274872/download-manifest.json`.
- Checkpoint: bảng `jobs` và `items` trong `cache/online_comics/pipeline.sqlite3`.
  Database gốc không được mở bằng `TranslationCache` trong điều tra; đã sao
  chép rồi đọc bản sao SQLite bằng URI `mode=ro` và `PRAGMA query_only=ON`.
- Log: `logs/app.log`, dòng 1448–1493. Lỗi đầu quan sát được lúc
  **17:55:03,436** ở trang 74 và **17:55:32,691** ở trang 111; lỗi chương lúc
  **17:55:37,636**. Lượt thử lại lỗi lúc **18:01:01,933** / **18:01:02,426**,
  lỗi chương lúc **18:01:02,533**, ngày 07/11/2026, giờ máy +07.
- `jobs.updated = 2026-11-07 11:01:02` UTC, tương ứng 18:01:02 +07.
  Database không lưu thời điểm bắt đầu riêng hay lịch sử từng lần chạy; không
  suy thời điểm bắt đầu từ thời điểm lỗi.

Manifest mới nhất ghi `total=120, completed=0, failed=2, skipped=118,
state=errors`. Đây là trạng thái **lượt thử lại**, không phải 0 ảnh thành công
trong toàn bộ lịch sử. `images_exported` của luồng URL tính cả các output đã
được xác minh và tái sử dụng khi nhận sự kiện `Bỏ qua`.

### Kiểm tra chỉ đọc đối với toàn bộ 120 trang

| Hạng mục | Kết quả có bằng chứng |
|---|---|
| Download receipt | 120/120 trang, `state=downloaded`, mỗi receipt HTTP 200 |
| Ảnh trong `_incoming` | 120/120 giải mã bitmap được, SHA-256/kích thước/số byte khớp receipt |
| Ảnh staging của ChapterCache | 120/120 giải mã được, SHA-256/kích thước khớp manifest |
| Cache OCR đúng nội dung/model/cấu hình | 120/120 ảnh |
| Ảnh có vùng chữ được đưa vào MT | 56 ảnh, tổng 104 vùng |
| Ảnh không có vùng cần dịch | 64 ảnh; pipeline giữ nội dung gốc |
| Ảnh hoàn tất có vùng dịch | 54 ảnh, 96 vùng được dịch và lưu metadata |
| Cache bản dịch được chấp nhận trong 120 ảnh | 99 vùng = 96 vùng hoàn tất + 3 vùng đầu trang 111 |
| Metadata hoàn tất và checkpoint `done` | 118 ảnh |
| Checkpoint `error` | 2 ảnh: 0074.jpg và 0111.jpg |
| Output nội bộ và output người dùng | Mỗi nơi 118/118 bitmap hợp lệ; SHA-256 và kích thước khớp receipt |
| Fingerprint checkpoint của ảnh thành công | 118/118 khớp recipe hiện tại |

Đây là xác minh đầy đủ file và tính toàn vẹn bitmap/hash, không phải nghiệm thu
chất lượng ngữ nghĩa hoặc bố cục của toàn bộ 118 ảnh đã xuất.

Không gọi 118 output là 118 ảnh đều đã dịch văn bản: 64 ảnh không có vùng cần
dịch. Không có bản dịch hoàn tất cho hai ảnh lỗi. Những vùng phía sau vùng lỗi
của trang 111 chưa có cache bản dịch tương ứng. Không có inference mới để có
được các số liệu trên.

## 2. Hai ảnh lỗi và văn bản thực tế

Options của đúng job: `mode=Offline`, `offline_provider=Argos`,
`allow_online_fallback=False`, `language=zh`, `glossary={}`, confidence=0.55.
Provider theo cấu hình và đường thực thi là **Argos/CTranslate2 CPU int8**, với
hai package `translate-zh_en-1_9` và `translate-en_vi-1_9`. Route hiện có là
Trung → Anh → Việt. Không có log output từng chặng để quy lỗi cho chặng cụ thể.
`ProviderError` được định nghĩa trong `providers.online`, nhưng việc exception
nằm ở module đó không biến job này thành dịch Online.

Job ID đã được tính lại từ metadata/model identity/font hash/cấu hình và khớp
chính xác checkpoint. OCR cache key và translation cache key được tính theo
source hiện tại, không tìm văn bản gần giống rồi gán cho job.

### Trang 74 — `0074.jpg`

- Thứ tự trang: 74 (manifest đánh số từ 1).
- OCR lưu đúng một vùng: **`3子`**, confidence **0.5835464000701904**.
- Polygon: `[[577,220],[725,220],[725,480],[577,480]]`.
- Văn bản gửi provider suy ra từ code và OCR cache: **`3子`**. Glossary rỗng,
  Offline không chia chunk, nên không có thay thế chuỗi ở bước này.
- Số nguồn validator phát hiện: **`["3"]`**.
- Cache bản dịch của vùng này: không có.
- Bản dịch thô bị từ chối: **KHÔNG CÓ BẰNG CHỨNG** trong cache/log/manifest.
- Bản dịch sau hậu xử lý, số target và số chính xác bị mất/đổi/thêm:
  **KHÔNG CÓ BẰNG CHỨNG**. Chỉ biết danh sách token target khác `["3"]`.
- Quan sát trực tiếp ảnh nguồn tại polygon cho thấy **hoa văn trên rèm**, không
  thấy văn bản `3子`. OCR đã nhận một phần hình vẽ thành chữ/số; confidence chỉ
  nhỉnh hơn ngưỡng, nhưng kết luận này dựa cả đối chiếu pixel, không chỉ điểm số.
- Phân loại nguyên nhân đầu vào: **C. OCR_NUMERIC_ERROR**, cụ thể false positive
  trên hoa văn. Chưa đủ bằng chứng để phân loại riêng hành vi MT là A/B/D.
- Nguyên nhân trực tiếp dừng ảnh: danh sách token số của kết quả provider không
  bằng danh sách nguồn theo validator. Ảnh không tới bước xóa chữ/render/lưu.

### Trang 111 — `0111.jpg`

Đây là trang thông tin chương trình quà tặng, không phải hội thoại nhân vật.
OCR cache theo thứ tự dịch:

| Vùng (0-based) | OCR / văn bản vào provider | Confidence | Số nguồn | Bản dịch đã được cache chấp nhận |
|---|---|---:|---|---|
| 0 | 上线大礼包 | 0.9960833 | `[]` | `Túi quà lớn.` |
| 1 | 活动时间和活动内容 | 0.9936352 | `[]` | `Name` |
| 2 | 活动时间 | 0.9968730 | `[]` | `Name` |
| 3 | **5月20日—5月30日** | **0.9618488** | **`["5","20","5","30"]`** | Không có |
| 4 | 活动内容 | 0.9970769 | `[]` | Không có |
| 5 | 截止时间内 | 0.9467055 | `[]` | Không có |
| 6 | 我们将抽取是佳评论！ | 0.8677164 | `[]` | Không có |

- Polygon của dòng ngày tháng:
  `[[284,791],[663,791],[663,830],[284,830]]`.
- Đối chiếu pixel xác nhận ngày tháng nguồn là **5月20日—5月30日**. Không thấy
  bằng chứng OCR đọc sai những con số của dòng này.
- Vùng bị chặn được khoanh vào vùng 3 bằng thứ tự vòng lặp và cache: ba vùng
  trước đã cache, trả ngay; vùng 3 là vùng đầu tiên chưa cache. Nếu vùng đó
  thành công thì cache phải được ghi trước khi dịch vùng sau. Log exception
  không tự ghi số thứ tự vùng; đây là suy luận từ đường thực thi + cache.
- Bản dịch thô của dòng ngày tháng: **KHÔNG CÓ BẰNG CHỨNG**.
- Bản dịch sau hậu xử lý, danh sách token số target và con số cụ thể bị thay
  đổi: **KHÔNG CÓ BẰNG CHỨNG**. Chỉ xác định target tokens không bằng
  `["5","20","5","30"]` theo thứ tự và cách viết nguyên văn.
- Phân loại: **F. INSUFFICIENT_EVIDENCE** để chọn A/B/D cho dòng ngày tháng.
  Không khẳng định provider làm sai ngày; cũng không khẳng định target là cách
  viết ngày Việt đúng. Cả hai cần bản dịch thực tế bị từ chối để đối chiếu.
- Hai chuỗi `Name` là dữ liệu cache thật của các vùng khác, cho thấy vấn đề
  chất lượng dịch ở những vùng đó; chúng không chứng minh lý do sai số của vùng 3.
- Ảnh dừng trước xóa chữ/render/lưu; không có output cho trang 111.

## 3. Validator thực sự kiểm tra gì?

Vị trí: `core/pipeline.py`, `TranslationService._translate_using`, khoảng dòng
103–136; exception phát sinh ở **dòng 127**. Traceback từ vòng lặp ảnh:

```text
core/pipeline.py:284  translations.append(self.service.translate(...))
core/pipeline.py:142  return self._translate_using(self._offline(), ...)
core/pipeline.py:127  raise ProviderError(...)
```

Regex nguồn và target giống nhau:

```python
number_pattern = r'\d+(?:[.,:/%+−-]\d+)*%?'
expected_numbers = re.findall(number_pattern, protected)
# Sau provider.translate(...), trước khôi phục glossary:
if re.findall(number_pattern, translated) != expected_numbers:
    raise ProviderError('Provider làm mất, đổi hoặc thêm số; không xuất ảnh này.')
```

- So sánh **hai list chuỗi theo thứ tự**, không phải giá trị số hay ngữ nghĩa.
  Thay đổi cách viết, ngăn cách hoặc đảo vị trí đều có thể bị từ chối.
- `\d` nhận Unicode decimal digits, gồm chữ số Ả Rập và fullwidth; không đọc
  `三`, `十五`, `ba`, `mười lăm` thành số. Chữ số fullwidth và ASCII vẫn là
  hai chuỗi khác nhau khi so sánh.
- Regex chỉ gom những dấu được liệt kê ở giữa các dãy chữ số và `%` ở cuối;
  không có bộ phân tích ngày/tuổi/tiền/ID/điện thoại/phép tính theo ngữ cảnh.
- Dấu âm ở đầu không thuộc token. Đổi chữ số Trung Quốc sang chữ số Trung Quốc
  khác cũng không được regex phát hiện. Đây là giới hạn khác của validator,
  không phải bằng chứng lỗi target của hai ảnh.
- OCR sai không được hiệu chỉnh tại đây. Vùng chỉ chứa số/ký hiệu không đi qua
  MT, nhưng `3子` chứa chữ `子`, nên vẫn được đưa vào provider.
- Kiểm tra xảy ra **trước** khôi phục glossary. Glossary của job rỗng: loại trừ
  việc hậu xử lý glossary làm thay đổi số để kích hoạt exception này.
- Cache hit trả thẳng trước validation. Cache chỉ ghi bản dịch sau khi mọi
  kiểm tra thành công; không lưu raw target bị từ chối.
- Không retry có giới hạn dành riêng cho lỗi numeric. Job Offline này không
  fallback Online; lỗi được chuyển thành checkpoint `error` cho ảnh rồi tiếp
  tục ảnh khác. Thử lại cả chương hiện tại gặp lại hai lỗi, không tự chữa chúng.

### Ca minh họa đã gọi validator thật với provider mock

| Nguồn → target mock | Hành vi hiện tại | Đánh giá |
|---|---|---|
| `15` → `15` | Chấp nhận | Đúng |
| `15` → `16` | Từ chối | Đúng |
| `3` → `ba` | Từ chối | Có thể là bản dịch đúng bị từ chối |
| `三` → `3` | Từ chối | Có thể là bản dịch đúng bị từ chối |
| `2024` → `2025` | Từ chối | Đúng |
| `1.5` → `1,5` | Từ chối | Có thể khác locale, cần ngữ cảnh |
| `第15话` → `Chương 15` | Chấp nhận | Đúng |
| `第15话` → `Chương 16` | Từ chối | Đúng |
| `5月20日—5月30日` → `20/5 đến 30/5` | Từ chối | Ví dụ ngày tháng đúng nghĩa vẫn bị từ chối |
| Điện thoại/ID giữ nguyên hoặc đổi một chữ số | Chấp nhận / từ chối tương ứng | Cần tiếp tục giữ kiểm tra chặt |
| `1+2=3` → `1 + 2 = 3` | Từ chối | Gom token phụ thuộc dấu/khoảng trắng |
| `三` → `四`; `-15` → `15` | Chấp nhận | Điểm mù, không nên coi guard hiện tại là đủ mọi ngữ cảnh |

Đây là **MOCKED VALIDATOR TEST**, hoàn toàn không phải bản dịch thật của hai
ảnh lỗi. Có false positive được tái hiện với ví dụ, nhưng chưa đủ target thực
tế để gán `VALIDATOR_FALSE_POSITIVE` cho trang 111.

## 4. Khả năng phục hồi, chưa thực hiện

- **Giữ được 118 ảnh thành công**: mỗi ảnh có manifest output/hash và item
  checkpoint `done`; bitmap, kích thước, output-hash và fingerprint đều khớp.
- **Không cần tải lại ảnh**: 120 ảnh incoming và staging đang hợp lệ, gồm hai
  ảnh lỗi; 120 OCR cache key đều có dữ liệu.
- `LocalComicJob` ở `sources/service.py` ép `skip_success=True` cho pipeline URL.
  Bằng chứng thực tế là summary lượt cuối `skipped=118`.
- Nút thử lại của URL chọn **chương lỗi**, không chọn từng ảnh; bên trong
  ProcessingManager có `run(only=[...])`, dùng được cho công cụ phục hồi riêng
  sau khi được cho phép. Chưa có thao tác phục hồi nào được chạy.
- Downloader có kiểm tra receipt/hash để tái sử dụng file thay vì tải CDN;
  luồng retry URL vẫn có thể đọc metadata/discovery. Phương án phục hồi từ cache
  cục bộ có thể tránh cả truy cập mạng, cần thiết kế trong nhiệm vụ sửa sau.
- **Cẩn thận thay recipe**: sửa model/provider/identity/config hoặc đổi đường
  dẫn nguồn sẽ có thể tạo job ID/fingerprint mới; không được hứa nút retry sẽ
  luôn bỏ qua 118 ảnh sau mọi thay đổi. Đổi validator cũng cần version cache
  rõ ràng, tránh tái sử dụng kết quả không phù hợp.
- `publish_image` không ghi đè output đã khác hash; cùng hash trả lại file cũ.
  Cả hai đường output dự kiến của trang 74 và 111 đều chưa tồn tại. Không phát
  sinh ảnh đã xóa chữ dở được công bố là hoàn chỉnh cho hai trang này.

## 5. Đề xuất tối thiểu cho nhiệm vụ sửa tiếp theo — chưa áp dụng

1. **Diagnostic trước, không suy target**: khi numeric validation thất bại,
   ghi diagnostic cục bộ có job/page/region/provider identity, OCR confidence,
   source và raw target/tokens, phiên bản validator. Chỉ bật trong phạm vi cần
   thiết, không URL ký số/token/cookie, không log nội dung rộng vào app.log.
   Với Argos pivot có thể thêm output từng chặng để định vị lỗi model. Rủi ro:
   lưu nội dung riêng tư; giới hạn số vùng/dung lượng và vị trí diagnostic.
   Sau đó chỉ chạy lại hai ảnh được cho phép, không cả chương.
2. **Trang 74: xử lý false positive OCR**: kiểm tra lại đúng vùng hoa văn; cho
   phép đánh dấu giữ nguyên vùng này hoặc xác minh lại vùng OCR với bằng chứng
   ảnh. Không sửa `3子` thành một câu dịch đoán và không tăng ngưỡng toàn cục để
   bỏ qua mọi chữ nhỏ. Rủi ro: mất chữ thật; cần test vùng hoa văn và vùng chữ
   confidence thấp hợp lệ, kiểm tra pixel ảnh gốc vẫn được giữ.
3. **Trang 111: chỉ chuẩn hóa sau khi có target thật**. Nếu target đúng ngày,
   thêm so sánh ngày tháng theo tuple có cấu trúc trong ngữ cảnh rõ ràng;
   cho phép locale thập phân có kiểm soát, số chữ chỉ trong ngữ cảnh an toàn.
   Không đổi list thành set/multiset chung vì có thể che đổi vai trò số, ngày,
   số điện thoại và ID. Rủi ro: chấp nhận sai 5/20 hoặc ngày-tháng nhập nhằng;
   test cả giữ đúng, đổi 20→21, đảo mốc, số lặp, năm, tiền, ID, điện thoại,
   giờ, dấu âm, Unicode và phép tính.
4. **Nếu target thực sự sai số**: retry tối đa một lần có kiểm tra lại, chỉ
   khi có phương án decode/đường dịch hợp lý; giữ lỗi nếu tiếp tục sai. Chạy
   lại cùng input với cùng decode xác định có thể cho đúng lỗi cũ, không gọi
   đó là cách sửa. Không thay số mù quáng bằng source và không bật Online.
5. **Khôi phục hai trang riêng**: giữ nguyên 118 output/receipt, dùng OCR cache
   đúng key khi phù hợp; kiểm tra hash trước/sau, chỉ công bố hai output mới
   sau toàn bộ validation. Nếu sửa OCR, không âm thầm sửa cache OCR gốc; cần
   override/receipt mới có phiên bản. Không đánh dấu `done` bằng tay.

## 6. Kiểm thử đã chạy và giới hạn bằng chứng

- Unittest chọn lọc: **4 PASS, 0 FAIL, 0 SKIPPED**.
- Pytest cùng bốn ca: **4 PASS, 0 FAIL, 0 SKIPPED**, hai warning deprecation
  hiện có của pkg_resources; không đổi dependency để xử lý warning.
- Các ca: ba `NumberSafetyTests` và
  `TranslationTests.test_glossary_and_numbers_roundtrip`.
- 20 ca mock bổ sung gọi `TranslationService` thật với provider mock: **20/20
  khớp hành vi validator hiện tại**. Đây không phải 20 bản dịch đúng ngữ nghĩa,
  cũng không phải 20 test được thêm vào suite baseline.
- Network bị chặn chủ động bằng Python audit hook trong các lượt test/mock.
  Không gọi provider thật; pixel test dùng FakeOCR/FakeProvider.
- Bitmap/hash/checkpoint audit: PASS như bảng 120 nguồn/118 output ở trên.
- Không chạy toàn bộ suite 207/10, không chạy lại GUI/E2E inference trong nhiệm
  vụ điều tra; **NOT_TESTED mới**, giữ nguyên kết quả lịch sử, không tuyên bố
  một baseline mới. Không chạy job 120 ảnh hoặc resume hai ảnh.
- Source production đã sửa: **không có**. Không sửa test hiện có. Chỉ tạo báo
  cáo này và evidence dưới `logs/numeric-investigation-20261107T110620Z` cùng
  pointer `logs/latest-numeric-investigation.json`.
- Kiểm tra bảo toàn cuối cùng: **554/554 file theo dõi không đổi hash/existence**,
  gồm source đã theo dõi, cấu hình, DOM, manifest, ảnh nguồn/cache/output, model
  integrity receipt, BAT/spec và **cả bốn EXE**. Database gốc cũng giữ nguyên
  SHA-256. Không có lệnh sửa model/.venv hay cài dependency. Không hash lại toàn
  bộ trọng số model hoặc toàn bộ .venv; không tuyên bố đó là kiểm định toàn ổ đĩa.

## 7. Evidence

Thư mục: `D:\TransTool\logs\numeric-investigation-20261107T110620Z`.

- `job-identification.json`: nhận diện đúng job, trang lỗi và các job phân biệt.
- `chapter-manifest.json`, `download-manifest.json`: bản sao manifest tại thời
  điểm điều tra, không thay thế file gốc.
- `snapshot/pipeline.sqlite3`: bản sao database dùng cho truy vấn read-only.
- `ocr-and-cache-evidence.json`: OCR từng vùng, key/cache hit, cấu hình, model
  identity; không có raw target bị từ chối.
- `translation-cache-counts.json`: 104 vùng, 99 cache hit, 96 vùng hoàn tất.
- `read-only-integrity-audit.json`: hash/bitmap/kích thước/checkpoint từng trang.
- `numeric-error-log-excerpt.txt`: lỗi thực tế kèm số dòng của app.log.
- `validator-mocked-examples.json`: dữ liệu ví dụ, không phải output provider thật.
- `unittest-numeric.txt`, `unittest-result.json`, `pytest-numeric.txt`,
  `pytest-numeric.xml`: kết quả kiểm thử chọn lọc.
- `before.json`, `db-original-hashes.json`, `preservation.json`: bằng chứng
  bảo toàn file đã theo dõi, gồm cache/ảnh/output/config/source/DOM và bốn EXE.

Không cần người dùng tải lại ảnh hoặc nộp lại DOM. Dữ liệu còn thiếu để chốt
nguyên nhân MT/validator của trang 111 là **raw target của vùng ngày tháng trong
lần lỗi**, và nếu có thì output hai chặng. Hiện source không lưu dữ liệu đó;
không thể tái tạo lịch sử chắc chắn chỉ bằng việc dịch lại trong tương lai.

**ROOT_CAUSE_PARTIALLY_CONFIRMED**: xác định đúng job, hai ảnh, input OCR, guard
và vị trí từ chối; xác nhận false positive OCR trên hoa văn ở trang 74. Chưa đủ
raw target để quyết định lỗi provider hay bản dịch đúng bị validator từ chối ở
trang 111, hoặc xác định chính xác token target của hai lần lỗi.
