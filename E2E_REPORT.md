# E2E thực tế — 06/11/2026

## Cache/fresh/reopen trong source và EXE — 10/11/2026, 15:25 UTC

Source và release frozen EXE PASS normal → cache hit → fresh DB, có OCR/MT
Offline thật; fresh không đọc DB cũ, old DB/output giữ nguyên. Hủy sau OCR
thật rồi mở lại GUI/khôi phục/tiếp tục: cùng namespace, OCR cache hit của
chính run, dịch/render thật hoàn tất. PNG cùng fixture source/EXE giống hệt.
GUI backup và dọn OCR/translation scope selected run PASS, giữ journal/receipts.

AGY thật hai request trên 0003 PASS (normal 1, cached 0, fresh 1); sau khi
được cho phép thêm, request thứ 3 hoàn tất 0002–0004 trên production code cuối.
Gate nút GUI của QA kiểm trước queued finished báo FAIL; giữ nguyên báo cáo
gốc. QA sửa cách chờ, EXE cuối replay cache thật PASS/idle không thêm request,
và Offline fresh/cancel/reopen/resume PASS. Production 60 module + main
bytecode giống bản chạy AGY, chỉ QA đổi ở lần đóng gói cuối. Không tuyên bố
website live. Full release: 607 PASS/0 FAIL/12 SKIP.

Evidence `output/cache-ui-acceptance-20261110T140037Z/`: `exe-pipeline` (AGY),
`exe-batch` (3 ảnh AGY, gate sớm FAIL), `source-release-pipeline3`,
`exe-handoff-offline`, `exe-handoff-cached-agy`, `equivalence.json`.
[Báo cáo đầy đủ](docs/CACHE_UI_REPORT.md).

## Nghiệm thu AGY source và frozen EXE — 10/11/2026

**PASS** pipeline OCR → AGY → mask/inpaint → layout → render → export với
0002/0003/0004 thật của Chap 20. Source GUI Batch, Source Whole, EXE GUI Batch
và EXE Whole đều hoàn tất 3/3, 0 failed/fallback. Bốn request AGY thật, còn 2/6.
Không dùng provider mock hoặc cache translation để gọi lượt real này là PASS.
Đã xem JPEG xuất bởi EXE 1280×720; nét Trung cũ không còn gây nhiễu, Việt không
chồng/cắt. Có vệt nền tại dải chữ, không yêu cầu phục chế hoàn hảo.

Lượt cached riêng kiểm tra 10 ảnh; source/EXE inpaint/final/layout giống hệt,
0 inference. Unit/regression được báo tách biệt: 582 PASS/0 FAIL/12 SKIP.
Evidence: `output/acceptance-20261110T114108Z/`; xem
[báo cáo nghiệm thu và giới hạn](docs/READABILITY_ACCEPTANCE_20261110.md).
Một chuẩn bị Whole đầu tiên bị guard confirmation chặn trước transport;
driver đã sửa đi đúng prepare/confirm/run và giữ báo cáo FAIL đầu tiên.
Không tuyên bố kiểm chứng website live, màn hình vật lý hoặc máy sạch.

## Mới nhất 07/11/2026 — GUI tab và EXE mới

Source E2E chuẩn PASS tại `output/e2e-validation/20261107T045351Z-fd62c9/`.
**EXE mới E2E ảnh truyện thật PASS** tại
`output/e2e-validation/20261107T045858Z-42bf8c/`, không mock OCR/MT.
Binary tab workflow PASS tại `output/source-tabs-validation/20261107T045845Z-6f3417/`:
ảnh đơn + folder + pause/resume + lỗi URL/network + source/config integrity.
Live Kuaikan chapter/downloader chưa xác minh, không dùng các kết quả local này
để tuyên bố URL → ảnh PASS. Chi tiết `docs/GUI_URL_FLOW_REPORT.md`.

## Bổ sung 07/11/2026 — nguồn ảnh/chương cục bộ

Pipeline Offline cũ vẫn PASS sau tích hợp nguồn mới; lượt cuối:
`output/e2e-validation/20261107T042612Z-cd1450/report.json` (fixture tổng hợp,
OCR/MT thật, không dùng mock). Evidence cuối và source fingerprint hiện tại xem
`docs/ONLINE_COMIC_TEST_REPORT.md`.

Luồng GUI nguồn mới với 2 ảnh truyện do người dùng cung cấp có OCR/dịch thật,
3 vùng/3 bản dịch, 2 ảnh xuất và nguồn không đổi. Qt Windows đã kiểm tra thêm
ảnh đơn, pause/resume, worker mới, cancel/retry và lỗi URL/mạng. Dữ liệu này là
LOCAL, không phải ảnh được tải từ Kuaikan; URL → download → E2E vẫn BLOCKED.
Không đồng nhất PASS kỹ thuật với nghiệm thu chất lượng dịch/mask.

## Kết quả cuối với ImgTest và EXE mới

Người dùng đã cung cấp `D:\TransTool\ImgTest`. Pipeline chuẩn sau sửa số chạy **61/61 ảnh, 0 lỗi**, nguồn giữ nguyên hash và kích thước. Evidence đầy đủ từng ảnh ở `output/real-image-validation-20261106-numeric-fix/`, báo cáo đánh giá **REAL_IMAGE_REPORT.md**. Có 75 vùng chữ dịch thật, 2 vùng số/ký hiệu bảo toàn và 24 ảnh raw OCR không tìm thấy chữ; không suy ra 61 bản dịch đạt ngữ nghĩa.

Chính EXE cuối (`...101857052219Z.exe`) chạy `--validate-e2e --source ImgTest\0H9l8tBjR.webp-t.w1280.jpg`: **PASS**, exit 0, `output/e2e-validation/20261106T102347Z-9dbcba/report.json` (interpreter EXE, source 1280×1000). GUI workflow nút thật bằng EXE PASS tại `output/gui-workflow/20261106T102357Z-67edd2/`. GUI Python với đủ 61 ảnh thật cũng PASS, 100% và 494 heartbeat tại `output/real-image-validation-20261106-numeric-fix/gui-batch/`.

Stress ảnh dài 1280×3385 ghép từ bốn panel thật: `output/e2e-validation/20261106T102242Z-5024d1/` PASS kỹ thuật. Provenance trong `long-derived/` xác định đây là ảnh ghép thử tile; không gọi là ảnh dài gốc người dùng cung cấp.

**Chưa nghiệm thu chất lượng:** sai nghĩa/credit/tên riêng, mask có thể còn dấu câu/nét màu ngoài polygon; M2M100 chưa có model để suy luận. Kết quả kỹ thuật không thay thế review từng bản dịch. Các mục dưới là lịch sử.

## Sau khôi phục và cải thiện mask — 10:00 UTC

Đã kiểm chứng MVP còn hoạt động trước khi sửa: Python E2E `20261106T094832Z-8100b8` và EXE cũ E2E `20261106T094709Z-168cc8` đều PASS kỹ thuật. Nguồn/EXE/model không bị hỏng theo các kiểm tra đã chạy.

Sau thay đổi mask, chạy lại lệnh chuẩn `.venv\Scripts\python.exe scripts\validate_e2e.py`: **PASS kỹ thuật, không mock**, `output/e2e-validation/20261106T100031Z-4d4a08/`. Đủ source/OCR/translation/mask/erased/final/report, kích thước và hash nguồn được bảo vệ. Input vẫn là fixture Trung tổng hợp, không phải truyện người dùng.

So sánh mask cũ từ backup và mask mới trên cùng nguồn/polygon OCR thật: `output/mask-validation/20261106T095833Z-c49a9e/report.json`, **600 → 0 pixel tối còn sót**, **0 pixel viền màu thay đổi**. Ảnh cuối đã xem lại không còn các nét đen rìa trên fixture này. Chưa có bằng chứng đạt trên nền phức tạp/chữ dọc/corpus truyện.

GUI workflow thật: `output/gui-workflow/20261106T095851Z-b1fa60/report.json` PASS, có pause/resume/cancel/retry/skip/error và preview. Test dùng cache mới, fixture hỏng cố ý và không mock OCR/dịch.

**Chất lượng ngữ nghĩa vẫn chưa đạt:** Argos vẫn dịch sai câu chào mừng. M2M100 thiếu model nên chưa chạy E2E/suy luận; comparison 24 câu ghi SKIPPED đúng lý do. Bản build mới đang được kiểm tra; evidence binary mới sẽ bổ sung tại BUILD_REPORT. Các mục phía dưới là lịch sử.

## Kiểm chứng chính EXE — 08:55 UTC

Lượt Python chuẩn cuối sau kiểm thử EXE: `output/e2e-validation/20261106T085912Z-51c063/report.json`, **PASS**, exit 0. `scripts/check_build_ready.py` chạy lại PASS với source/interpreter hiện tại. Bằng chứng EXE bên dưới không bị sửa hoặc thay thế.

Đã chạy `dist\ImageTranslatorVN\ImageTranslatorVN.exe --validate-e2e`, exit 0, **PASS kỹ thuật**. Báo cáo `output/e2e-validation/20261106T085546Z-e14cdf/report.json` ghi đúng interpreter EXE và fingerprint `d71827338053f78a99fe74bf1d9acc4ca5f61a54e5e238f5ac77bcb32b051027`.

Đủ `source.png`, `ocr.json`, `translation.json`, `mask.png`, `erased.png`, `final.png`, `report.json`, `report.md`. Không mock/nhập tay OCR hoặc bản dịch. Nhận diện hai vùng trên fixture Trung tổng hợp, dùng model cục bộ zh_en-1_9 + en_vi-1_9, xuất 1200×430, nguồn nguyên vẹn, tái sử dụng OCR PASS. Tổng 8.984 giây; peak process working set 750,968,832 byte. Chưa thử ảnh người dùng/truyện/photo thực tế.

Đã xem ảnh cuối: tiếng Việt render rõ, vẫn còn nét đen ở mép mask. Câu thứ hai vẫn sai ngữ nghĩa thành “Không có gì.”. **Chưa đạt nghiệm thu chất lượng dịch/xóa chữ**, dù tất cả công đoạn kỹ thuật chạy xong. Kết quả suy luận gốc được giữ nguyên. GUI của EXE cũng PASS với screenshot `logs/gui-smoke-20261106T085536Z-fb0e84/window.png`; desktop vật lý người dùng và toàn bộ thao tác dịch qua nút GUI của EXE chưa kiểm thử.

## Kết quả mới nhất: PASS kỹ thuật, chất lượng dịch chưa nghiệm thu

Đã chạy đúng lệnh chuẩn bằng môi trường sản phẩm sau sửa runtime:

```bat
D:\TransTool\.venv\Scripts\python.exe scripts\validate_e2e.py
```

**Exit 0; không mock; không nhập tay output OCR hoặc bản dịch.** Thư mục hiện hành:

`D:\TransTool\output\e2e-validation\20261106T084804Z-4a9386\`

| Bước | Kết quả |
| --- | --- |
| Nguồn | PASS: fixture Trung tổng hợp 1200×430, phân biệt rõ với ảnh thực tế người dùng |
| PaddleOCR | PASS: 2 vùng, polygon/confidence hợp lệ, output từ model thật |
| Offline translation | PASS suy luận: zh→en→vi từ đủ 2 model đã cài |
| Mask | PASS, lưu mask.png |
| Inpainting | PASS thực thi, lưu erased.png |
| Text rendering | PASS, Unicode tiếng Việt, không cắt/tràn ở fixture |
| Export | PASS, final.png mở lại đúng kích thước nguồn |
| Nguồn giữ nguyên | PASS: hash không đổi |
| Tái sử dụng OCR engine | PASS: lần nhận diện tiếp dùng cùng instance |

Đủ file: `source.png`, `ocr.json`, `translation.json`, `mask.png`, `erased.png`, `final.png`, `report.json`, `report.md`. Lượt PASS đầu tiên cũng được giữ tại `20261106T083125Z-46611f/`; các bằng chứng FAIL cũ không bị xóa.

Đã mở xem `final.png`. Chữ Việt hiển thị đủ dấu; còn speck nhỏ ở rìa polygon/mask OCR và câu thứ hai dịch sai. E2E PASS ở đây xác nhận mọi bước thật đã chạy và ghi ảnh đúng, **không có nghĩa ảnh hoặc bản dịch hoàn hảo**.

## Runtime và GUI regression

Root cause là OpenMP DLL của Paddle thiếu symbol Torch yêu cầu, đã có bằng chứng PE/loaded-module trong `output/runtime-validation/20261106T084730Z-ca8bd9/report.json`. Guard khởi tạo CT2/Torch trước Paddle và Qt ở nhiều entry boundary đã sửa luồng chuẩn.

`tests/test_runtime_integration.py` tạo tiến trình mới cho từng trường hợp. Raw legacy order cố ý bỏ guard vẫn tái hiện WinError 127 (negative control). Các ca guarded CT trước Paddle, prepared Paddle import, OCR→MT trong cùng process, 4 lần lặp/model reuse, worker restart và cancel PASS. QThread dùng SQLite mới để tránh cache che khuất suy luận thật.

Unittest và pytest đều **63 PASS, 6 SKIPPED**. Những ca thiếu model en/ko/zt và Online opt-in không bị đổi thành PASS. GUI mới kiểm tra font/glyph, picker, bảng, model dialog, preview, event loop; native Windows platform screenshot đã đọc được tiếng Việt. Desktop vật lý người dùng chưa quan sát trực tiếp được từ phiên sandbox.

## Chất lượng dịch và giới hạn

Corpus 24 câu: `output/translation-quality/20261106T083515Z-bdb3f5/`, báo cáo phân tích `TRANSLATION_QUALITY_REPORT.md`.

`欢迎使用图像翻译。` → `Image translation is welcome.` → `Không có gì.`

Lỗi ngữ nghĩa bắt đầu ở cách diễn đạt chặng đầu và nghiêm trọng ở chặng Anh→Việt. Tokenizer khớp Argos, model direction/hash đúng, pivot trùng với hai chặng chạy riêng. Chưa có bằng chứng lỗi grouping OCR/sentence splitting/thuật toán pivot trong câu này. Không hardcode sửa output.

Đã nghiên cứu model trực tiếp M2M100 418M (MIT, zh/vi, CT2 4.6 CPU có hướng dẫn chuyển đổi); chưa tải model lớn hoặc tuyên bố chất lượng của model đó. Corpus ảnh truyện/chụp thực tế, tên riêng và nền phức tạp vẫn cần đánh giá thêm.

---

## Lịch sử lượt đầu chưa đủ dependencies

**Kết quả: FAIL tại bước OCR vì thiếu dependencies. Không dùng mock. Không có ảnh hoàn chỉnh đã dịch.**

Bộ chạy mới `scripts/validate_e2e.py` gọi trực tiếp các module hiện có, giữ nguyên kiến trúc:

`Ảnh nguồn → PaddleOCREngine → Argos/CTranslate2 Offline → build_mask/erase_text → TextRenderer → atomic_save`.

## Lần chạy hiện hành

Lệnh đã thực hiện bằng Python hệ thống có đủ OpenCV/Pillow/NumPy:

```bat
python scripts\validate_e2e.py
```

Thư mục bằng chứng mới nhất:

`D:\TransTool\output\e2e-validation\20261106T070513Z-a4c481\`

Pointer: `output/e2e-validation/latest.json`. Những lần chạy trước được giữ lại trong các thư mục có timestamp riêng.

| Công đoạn | Kết quả | Bằng chứng / nguyên nhân |
| --- | --- | --- |
| Tạo ảnh nguồn | PASS thực tế | `source.png`, 1200×430, chữ Trung được vẽ bằng font msyh.ttc đã có trên Windows |
| Loại dữ liệu | Fixture tổng hợp | Không có ảnh Trung thực tế của người dùng được cung cấp; đã xem ảnh nguồn và xác nhận có chữ Trung rõ ràng |
| OCR | **FAIL** | `Missing OCR dependencies: paddle, paddleocr` |
| Translation | SKIPPED | OCR chưa thành công; không nhập văn bản thay thế |
| Mask | SKIPPED | Chưa có polygon OCR thật |
| Inpainting | SKIPPED | Chưa có bản dịch thật và vùng OCR |
| Render tiếng Việt | SKIPPED | Chưa có bản dịch từ model |
| Export final | SKIPPED | Không tạo ảnh hoàn chỉnh khi pipeline thất bại |
| Bảo vệ nguồn | PASS thực tế | SHA-256 nguồn giữ nguyên trong lần chạy |
| Tái sử dụng OCR engine | SKIPPED | Chưa khởi tạo được model |

## Các file đã lưu

- `source.png`: ảnh nguồn tổng hợp có chữ Trung, không sửa sau khi tạo.
- `ocr.json`: `status=FAIL`, lý do thiếu dependencies; không có output OCR được nhập tay.
- `translation.json`: `status=SKIPPED`, records rỗng; không có câu dịch được nhập tay.
- `failure.txt`: traceback thật.
- `report.json`: trạng thái từng công đoạn, interpreter, fingerprint mã nguồn, thời gian và bộ nhớ process ở giai đoạn đã chạy.
- `report.md`: báo cáo ngắn từng bước.

`mask.png`, `erased.png`, `final.png` **không tồn tại** trong lần chạy lỗi này. Không tạo các file giả để đáp ứng danh sách đầu ra. Khi OCR/MT thật thành công, bộ chạy sẽ lưu đủ các artifact đó.

## Offline model và chất lượng

- Model cài đặt: 0. Chưa có model đọc được bởi engine để chạy suy luận.
- Đường dịch dự kiến theo danh mục hiện có: zh → en → vi; phải có đủ hai model. Chưa xác minh suy luận tương thích binary.
- Dung lượng model: NOT MEASURED; không lấy ước tính trong GUI làm dung lượng thực tế.
- RAM/thời gian suy luận: NOT MEASURED. Counter bộ nhớ trong JSON là process đang tạo fixture/kiểm tra thiếu engine, không phải RAM của model dịch.
- Kết quả dịch và đánh giá ngữ nghĩa: NOT TESTED.
- Ảnh lớn, confidence/bounding box thật, engine reuse trên dữ liệu thật: NOT TESTED. Runner đã có kiểm tra tọa độ/confidence và reuse khi engine có thể chạy; cần bổ sung corpus ảnh lớn/truyện tranh để đánh giá chất lượng đầy đủ.

Không dùng marker/glossary để thay thế MT trong bộ E2E. Không lấy chuỗi dùng để vẽ fixture làm kết quả OCR hoặc làm đầu vào dịch. Chỉ `regions` do PaddleOCR thật trả về mới được chuyển sang provider Offline.

## GUI và provider Online

- GUI smoke: **SKIPPED**, vì `.venv` import PySide6 thất bại. Bằng chứng: `logs/gui-smoke-20261106T070512Z-5fe844/report.json`.
- Chưa khởi chạy GUI `main.py` hay cửa sổ hiển thị thực tế trong lượt này. Bộ smoke đã được nối vào entry point thật qua `main.py --smoke-test --smoke-report ...`; nhánh đó chưa được kiểm chứng do thiếu Qt.
- Kiểm thử Qt offscreen tương lai sẽ kiểm tra cửa sổ, picker Qt không dùng mock, danh sách ảnh từ filesystem, model dialog, preview, trạng thái nút lúc nghỉ và heartbeat event loop. Nó không thay thế kiểm thử progress/nút điều khiển trong job AI thực tế hoặc native dialog trên desktop.
- MyMemory live: lượt trước thất bại kết nối; lượt này DNS PASS, outbound vẫn bị sandbox chặn, không lặp lại request provider vô ích. Trạng thái Online hiện tại **NOT TESTED thành công**.
- LibreTranslate live: NOT TESTED, chưa có endpoint tự host/miễn phí hợp lệ để chạy. Unit HTTP mock, timeout/rate-limit/cache/fallback vẫn PASS trong suite core.

## Regression khả dụng

`python scripts\run_tests.py --evidence-dir logs\qa-followup-unit-20261106` đã chạy:

- **49 PASS**, 0 failures, 0 errors.
- 44 ca core/CV/workflow cũ và 5 ca kiểm tra điều kiện build mới.
- 9 integration method SKIP; 1 GUI class SKIP (3 GUI method chưa chạy). Runner ghi testsRun=58, skipped entries=10 do cách unittest ghi setUpClass.
- Đây là **unittest**, không phải pytest. Các fixture kiểm tra workflow/HTTP/build gate là unit fixtures; không gộp chúng thành PASS OCR/MT/GUI thực tế.
- Bằng chứng giữ riêng: `logs/qa-followup-unit-20261106/test-results.json` và `tests-unittest.log`. Log 44 ca ban đầu không bị ghi đè.

Để chạy bằng môi trường sản phẩm sau khi cài đủ:

```bat
.venv\Scripts\python.exe scripts\smoke_gui.py
.venv\Scripts\python.exe scripts\validate_e2e.py
.venv\Scripts\python.exe scripts\validate_e2e.py --source DUONG_DAN_ANH_THUC_TE --language zh
```

Chỉ công bố E2E PASS khi tất cả bước thật thành công. Sau đó vẫn cần xem nội dung dịch và ảnh kết quả để đánh giá chất lượng.
