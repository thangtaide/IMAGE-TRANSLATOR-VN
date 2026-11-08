# Stage 2 — OCR/numeric repair và phục hồi hai trang

Ngày: **08/11/2026 (+07)**. Trạng thái: **STAGE_2_COMPLETED_WITH_WARNINGS**.
Chỉ Stage2; chưa Stage3/4/5, không build EXE, không tải model hoặc gọi Online.

## 1. Job và cổng kiểm tra trước ghi

Job ID không đổi:
`e82b4eb8abed1050602c5d01b62322bd021684c54cebb1715d62b206fd9feca8`.
Topic6677, chương274872, `第1话上 换新娘`. Không dùng chương281106 hoặc QA hai ảnh.

Nguồn:
`cache/online_comics/kuaikanmanhua/6677/chapter_274872`.
Output:
`output/test_download-orc/权妃之帝医风华__6677/0002_第1话上 换新娘__274872/run_e82b4eb8abed1050`.
Database: `cache/online_comics/pipeline.sqlite3`.

Trước thay đổi userdata đã kiểm tra 120 ảnh staging và incoming: SHA-256,
bitmap decode, kích thước; 118 output published/internal có receipt, hash,
fingerprint và checkpoint `done` đúng recipe. Job ID tính lại khớp. Tập pending
chính xác `0074.jpg` và `0111.jpg`. Chụp manifest/download receipt, bản sao DB,
toàn bộ row jobs/items/cache và hash ảnh, config, model, DOM, BAT/spec,4 EXE.

Thử riêng trên bản sao DB/output QA trước khi chạy job thật. Cổng commit yêu cầu
pytest/unittest đầy đủ không lỗi, toàn bộ hash trước chạy còn khớp, đúng scope2,
model/provider identity không đổi và không có output hai trang ở đích mới.
Snapshot bổ sung ngay trước và sau commit. DB gốc chỉ được mở ghi khi các
kiểm tra này đã qua; không sửa hàng loạt/checkpoint bằng tay.

## 2. Trang74: OCR false positive và override

Raw OCR vẫn là `3子`, confidence `0.5835464000701904`, polygon
`[[577,220],[725,220],[725,480],[577,480]]`.
Đây là hoa văn rèm đã đối chiếu ảnh trong điều tra trước và xác nhận trong task.

Image SHA-256:
`d1df7f273a1e40941c3018d866d684536e57affa430765bbb6f02a00ea915f9c`.
Profile `overrides/ocr_regions.json`, rule
`verified-curtain-decoration-d1df7f273a1e4094`, version1, enabled=true,
action `SKIP_FALSE_POSITIVE_REGION`, reason/evidence cụ thể.

`core/ocr_overrides.py` áp dụng sau khi đọc OCR cache, trước dịch:

- Hash đúng và text/polygon khớp duy nhất mới bỏ vùng. Không fuzzy match.
- Locator tương đối nhận đúng ảnh dự kiến để phát hiện hash mismatch; engine
  không hardcode filename/chapter. Ảnh khác hash/path không bị rule ảnh này ảnh hưởng.
- Hash mismatch hoặc region mismatch gây diagnostic và fallback để xem lại.
- Có `enabled=false` để thu hồi, có version và revision receipt. Thu hồi không
  tự xóa output hoặc tự chạy lại ảnh đã xong; có hiệu lực khi ảnh được xử lý lại.
- Không tăng confidence toàn cục, không loại mọi vùng có số, không sửa OCR cache.
- Chỉ fingerprint ảnh có rule active thêm revision. Job identity và118
  fingerprint/checkpoint cũ không đổi. Thay đổi profile không ghi đè output cũ.

Kết quả thử riêng và job thật: provider **không được gọi cho trang74**, không
còn vùng cần dịch, metadata `no_text_to_translate=true`, receipt override đầy đủ.
Giữ định dạng gốc nên output sao chép nguyên byte nguồn, hash bằng SHA trên,
hoa văn giữ nguyên. Đây là **hoàn tất bình thường không cần MT**, không phải
fallback và không tuyên bố đã dịch chữ. Output mới: `run_.../0074.jpg`.

## 3. Trang111: raw target mới và nguyên nhân

Source thực tế lấy từ OCR cache có dấu gạch, không thay bằng chuỗi tham chiếu
đã lược dấu: **`5月20日—5月30日`**.
Confidence `0.961848795413971`, polygon
`[[284,791],[663,791],[663,830],[284,830]]`, region index3 (0-based).

| Chặng thực tế của lượt Stage2 | Kết quả |
|---|---|
| Trung→Anh | `20-30 May` |
| Anh→Việt / raw target cuối | **`20 giờ 30 tháng 5`** |
| Source numeric tokens | `["5","20","5","30"]` |
| Target numeric tokens | `["20","30","5"]` |

Quan sát cùng kết quả trong probe riêng và phục hồi job thật. Observer bọc
`ArgosTranslationProvider._decode`, gọi decode gốc và trả nguyên kết quả; không
đổi tokens, model, direction, beam, tokenizer hoặc hậu xử lý. Decode trace có
khoảng trắng đầu do tokenizer, provider chỉ `.strip()` như source cũ.

Provider **Argos Offline / CTranslate2 int8 CPU**, route `zh→en→vi`, hai model
`translate-zh_en-1_9`, `translate-en_vi-1_9`. Identity không đổi:
`Argos:ct2-int8-v1:19012e975e8ea65131be379cd6d4f033af4b3b50c6ea9089c7b145fac4fe43c0`.

Phân loại kết quả mới: **PROVIDER_NUMERIC_ERROR / lỗi nghĩa thời gian ở chặng
Anh→Việt**. English là khoảng ngày20–30 tháng5; target thêm `giờ`, không giữ
đúng hai mốc ngày. Việc month xuất hiện một lần tự nó chưa chứng minh sai nghĩa;
kết luận dựa vào cả từ/cấu trúc `20 giờ 30 tháng 5`, không chỉ số lượng token.
Không thấy hậu xử lý sửa số: glossary rỗng, kết quả này đã xuất hiện tại decode
chặng cuối. Không quy lỗi cho OCR của dòng ngày; pixel đã đối chiếu đúng.

Guard từ chối phù hợp, **không nới validator ngày**, không tự thay số để ép PASS.
Trang111 giữ **FALLBACK_ORIGINAL**, source pixels nguyên vẹn, không inpaint dở.
Output mới `run_.../original/0111.jpg`, `needs_retry=[111]`.

Đây là **raw target mới của Stage2**, không phải chứng cứ trực tiếp cho target
lịch sử ngày07/11. Raw target lịch sử vẫn không tồn tại. Thử riêng dùng QA job
ID riêng vì output QA khác; lượt phục hồi dùng đúng job ID gốc.

## 4. Numeric guard: siết dấu số, không nới ngày

Test C2 tái hiện guard cũ chấp nhận mất/thêm dấu đầu số (`-15→15`, `15→-15`),
kể cả legacy cache. Ba test đỏ được giữ tại `signed-guard-before.txt` trước sửa.
Đây là bằng chứng riêng về validator, không phải nguyên nhân trang111.

Bổ sung prefix dấu ASCII/Unicode minus/fullwidth plus-minus vào token regex,
vẫn so **list theo thứ tự**, không set/multiset. Version mới
**`literal-numbers-v2-signed`**. Không chuẩn hóa thập phân, số chữ, ký tự fullwidth
hoặc ngày tháng bằng suy đoán. Ngày hợp nghĩa đổi định dạng vẫn có thể bị từ
chối bảo thủ; Stage2 không thêm date parser vì target thật của trang111 sai nghĩa.

Policy cache/resume:

- Source có dấu hoặc legacy target có dấu dùng key namespace
  `glossary-v4-signed-numbers`, không trả mù quáng cache signed v3.
- Cache unsigned v3 giữ nguyên vì cách so sánh unsigned không thay đổi. Không
  xóa/migrate row cũ; test xác nhận signed cache cũ không được trả trực tiếp.
- Giữ pipeline/service identity cũ để resume job này. Metadata output mới có
  validator version; **118 output cũ là receipt legacy được bảo toàn**, không
  tuyên bố đã kiểm tra lại chúng theo v2. Không reprocess118 ảnh để nâng version.
- Override revision chỉ ảnh hưởng fingerprint74, không thay nguyên tắc giữ output.

## 5. Phục hồi thật và dữ liệu sau chạy

Thao tác qua **nút Retry → ComicSourceWorker/QThread → LocalComicJob(retry_only=True)**,
ProcessingManager thật. Chặn cứng `only` đúng hai đường dẫn; một lần run phạm vi2.
Paddle recognize bị chặn trong recovery để chứng minh dùng cache OCR thật.
Argos suy luận thật, không mock output; `_online` và mọi socket/DNS đều bị chặn.

| Chỉ số | Sau phục hồi |
|---|---:|
| Trang hiện hành có output hợp lệ/hash/kích thước đúng | **120/120** |
| Hoàn tất pipeline bình thường | **119**, gồm trang74 không cần dịch |
| Dịch một phần | 0 |
| Fallback nguyên gốc | **1**, trang111 |
| Thiếu output | 0 |
| Trang cần xem lại | **1** |
| Ảnh được xử lý trong lượt recovery | **2** |
| Ảnh cũ được xử lý lại | **0** |
| Network attempts / download | **0 / 0** |

118 là các ảnh đã hoàn tất trước task; output/hash, checkpoint và page entry
giữ nguyên. Các output cũ có thể bao gồm ảnh không có chữ; không gọi119 là119
bản dịch văn bản đúng nghĩa. Counter skipped của lượt2 bằng0 vì118 ảnh không
được đưa vào pipeline, không phải chúng bị xử lý lại.

Thay đổi được phép:

- Item74: `error→done`, output nội bộ mới, fingerprint bổ sung override revision.
- Item111: `error→fallback_original`, output nguồn dự phòng, numeric diagnostic.
- Chỉ hai page entry tương ứng thêm output/hash/status/review/receipt;118 entry
  còn lại bằng hoàn toàn trước chạy.
- Target job row cập nhật options có diagnostic_text và state
  `completed_with_warnings`; không đổi job ID. Manifest top-level thêm counts,
  needs_retry và summary của lượt2. Không migration schema.
- Thêm **3 cache row**:2 output-hash và1 metadata trang74. **Mọi cache row cũ
  giữ nguyên**, gồm OCR và translation. Không sửa raw OCR `3子`.
- Không có job/item khác thêm, xóa hoặc thay đổi. SQLite integrity_check=ok.

GUI Windows thật hiện `COMPLETED_WITH_WARNINGS`,120/120,119 hoàn tất,1 gốc,
1 xem lại; bảng Review mở bằng nút thật chỉ có trang111, providerArgos,
NUMERIC_MISMATCH. Heartbeat71; screenshot và events được lưu. Nhãn “Dịch hoàn
chỉnh” hiện đếm hoàn tất pipeline, gồm ảnh không cần MT như đã giải thích trên.

## 6. Test Stage2 và bảo toàn

- **Pytest252 PASS,10 SKIPPED,0 FAIL**,262 ca,65,30 giây.
- **Unittest252 PASS,10 SKIPPED,0 FAIL**,262 ca,58,407 giây.
- Thêm21 test ở `tests/test_stage2_recovery.py`: hash/polygon/text mismatch,
  disable/revision/evidence, giữ chữ thật/cache OCR, fallback→success, guard
  chapter/year/date/phone/ID/money/negative/fullwidth và legacy cache policy.
- Unit overrides/MT dùng fixture/mock rõ ràng. Phục hồi thật dùng OCR cache thật
  và **real Offline inference**, không dùng OCR/provider kết quả viết tay.
- OCR zh thật và MT en→vi/zh→en→vi thật trong full suite PASS;10 SKIPPED vẫn là
  OCR thiếu model3, MT thiếu route2, Online1, liveKuaikan3, M2M1001. Không gọi
  skip reason lịch sử có chữ sandbox là bằng chứng môi trường hiện bị chặn.
- **Synthetic Offline E2E PASS**: ảnh fixture Pillow được OCR thật, MT thật,
  mask/inpaint/render/export thật,0 network. Đây là kiểm thử kỹ thuật, không
  benchmark chất lượng/ground truth và không phải tải Kuaikan mới.
- **Windows Qt recovery GUI PASS**, không phải EXE/portable/VM sạch.
- Live HTTP và download **NOT_TESTED trong task**, không cần tải lại để phục hồi.

Hash model/config/BAT/spec/DOM,120 nguồn incoming và120 staging,118 output
published và118 output nội bộ,4 EXE giữ nguyên. Chỉ hai file dữ liệu cũ được
cập nhật hợp lệ: database target và manifest target. Snapshot có529 bản ghi
hash, một DB có hai cách viết dấu phân cách; báo cáo preservation chuẩn hóa
đường dẫn để không đếm alias là hai database. Không cài package, sửa .venv,
native import guard, model/provider mặc định hoặc các database không liên quan.

## 7. Source, tài liệu và evidence

Source sửa: `core/pipeline.py`, `core/diagnostics.py`.
Tạo `core/ocr_overrides.py`, `tests/test_stage2_recovery.py`,
`overrides/ocr_regions.json`. Không sửa Paddle OCR engine, Argos provider,
sources/service, GUI production, downloader, BAT, spec hoặc model.

Cập nhật PROJECT_STATUS.md, README.md, USER_GUIDE.md, TROUBLESHOOTING.md,
WEBSITE_ADAPTER_AI_GUIDE.md và báo cáo này, giữ lịch sử Stage1/điều tra cũ.

Evidence: `logs/stage2-recovery-20261107T200532Z/`:

- `preflight.json`, `protected-before.json`, `items-before.json`, `jobs-before.json`,
  `cache-before.json`, `manifest-before.json`, `snapshot/`, `source-before/`.
- `probe-results.json`, `probe-diagnostics/`: thử riêng từng trang; trace mới.
- `signed-guard-before.txt`, `repair-targeted.xml`, `pytest-final.xml`,
  `unittest-final.json`: test trước/sau, không che ba test đỏ trước fix.
- `commit-gate.json`, `before-commit/`, `after-commit/`, `recovery-result.json`:
  scope2, real worker, logical row diff, output validation, trace và GUI summary.
- `recovery-windows-gui.png`, `recovery-review-dialog.png`.
- `synthetic-e2e-result.json` và `synthetic-e2e/output/e2e-validation/`.
- `preservation.json`, `summary.json`: đối chiếu hash và kết luận cuối.

Diagnostic gốc của lượt phục hồi:
`logs/diagnostics/e82b4eb8abed1050602c5d01b62322bd021684c54cebb1715d62b206fd9feca8/errors.jsonl`.
Không xóa cache/output/fallback hoặc tự restore snapshot sau khi đã commit.

## 8. Còn lại và Stage3

Trang111 chưa có bản dịch ngày đúng; guard từ chối và fallback là kết quả an
toàn, không phải translation success. Override chỉ giải quyết vùng có bằng
chứng, không phải thuật toán tự nhận biết mọi hoa văn. Guard vẫn so số theo chuỗi,
chưa là bộ phân tích semantic cho mọi số chữ/ngày tháng/locale.

Chờ người dùng nghiệm thu trước Stage3: benchmark mẫu có kiểm soát, so từng
chặng Argos và giữ nghĩa/ngày/tên riêng; chỉ cân nhắc phương án model khác sau
bằng chứng và kiểm tra tài nguyên/nguồn. Không tự tải model, bật Online hoặc
đổi engine trong Stage2. Stage4/5/portable/.gitignore chưa thực hiện; không build EXE.

**STAGE_2_COMPLETED_WITH_WARNINGS**
