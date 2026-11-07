# Báo cáo kiểm thử Image Translator VN

## Kết quả cuối sau ImgTest — 06/11/2026

**Unittest: 83 ca, 76 PASS, 7 SKIPPED, 0 lỗi** (`logs/real-image-fix-unittest-20261106/`). **Pytest: 76 PASS, 7 SKIPPED** trong build log `logs/build-ImageTranslatorVN-20261106T101857052219Z.log`. 3 test thêm sau corpus kiểm tra số nguyên dạng, chặn mất/đổi/thêm/đảo số, giữ nguyên pixel vùng chỉ có số. Unit dùng mock có nhãn; không coi là suy luận model thật.

Batch corpus thật: trước 58/61, sau sửa 61/61, 0 lỗi, hash/kích thước nguồn giữ nguyên; 75 vùng chữ dịch thật. GUI 61 ảnh PASS (100%, 494 heartbeat). EXE cuối GUI smoke, workflow điều khiển và E2E ảnh truyện thật PASS kỹ thuật. Ảnh ghép dài 1280×3385 cũng PASS kỹ thuật, có provenance. **Chất lượng dịch/mask/OCR corpus chưa nghiệm thu**, xem REAL_IMAGE_REPORT.

7 skip gồm OCR en/ko/zt, MT ko/zt, Online opt-in và M2M100 chưa có trọng số. M2M100 mock contract PASS tách biệt với inference SKIPPED. Bản EXE cũ và bằng chứng FAIL trước sửa được giữ nguyên. Các mục phía dưới là lịch sử.

## Sau khôi phục — 06/11/2026

Trước sửa: unittest/pytest **63 PASS, 6 SKIPPED**, audit/import/model/GUI/E2E của EXE cũ xác minh lại, không lấy kết quả trước mất điện làm kết quả mới. Sau sửa: **80 ca unittest: 73 PASS, 7 SKIPPED** tại `logs/recovery-final-unittest-20261106/`; pytest trong build log `logs/build-ImageTranslatorVN-20261106T100146952450Z.log`: **73 PASS, 7 SKIPPED**.

10 test mới PASS gồm 4 OpenCV geometry thực thi thật và 6 contract/provider M2M100 unit tests có mock (không phải model inference). Test M2M100 thật SKIPPED vì thiếu model; 6 skip cũ giữ nguyên. GUI workflow nút thật, OCR/dịch thật và cache riêng: `output/gui-workflow/20261106T095851Z-b1fa60/report.json` PASS. GUI Windows smoke và E2E chuẩn sau sửa PASS, xem RECOVERY_REPORT để biết đường dẫn.

Mask benchmark fixture: 600→0 pixel tối còn sót, viền màu thay đổi 0. Chưa có corpus truyện thực tế, không suy rộng độ chính xác. Argos còn sai nghĩa; M2M100 corpus comparison SKIPPED. Build mới đang kiểm chứng binary; xem BUILD_REPORT. Các mục dưới đây là lịch sử.

## Cập nhật cuối lượt sửa WinError 127 — 06/11/2026

- Unittest: **69 ca, 63 PASS, 6 SKIPPED, 0 failure/error**, `logs/runtime-final-unittest-20261106/test-results.json`.
- Pytest: **63 PASS, 6 SKIPPED**, `logs/runtime-final-pytest.log`, XML cùng tên. Build chạy lại pytest cũng 63 PASS, 6 SKIPPED. Bộ test gồm unit/mock và integration suy luận thật; không gọi toàn bộ 63 ca là test AI thật.
- 7 regression fresh-process kiểm tra negative control WinError 127, thứ tự native runtime, OCR→MT cùng process, lặp/reuse, restart QThread và hủy job. Raw Paddle-first bypass adapter vẫn tái hiện lỗi theo kỳ vọng; các đường ứng dụng đã guard PASS.
- GUI offscreen và Qt Windows-platform PASS, tiếng Việt đã xem qua screenshot. GUI QThread với OCR/MT thật, heartbeat/restart/cancel PASS. Desktop vật lý/native picker chưa test.
- Python E2E không mock PASS: `output/e2e-validation/20261106T084804Z-4a9386/`. Chính EXE E2E không mock PASS: `output/e2e-validation/20261106T085546Z-e14cdf/`. Input là fixture tổng hợp; không phải bằng chứng độ chính xác trên truyện/photo.
- Build PASS; EXE GUI smoke PASS: `logs/gui-smoke-20261106T085536Z-fb0e84/`. Toàn bộ thao tác nút GUI dịch ảnh bằng EXE và máy sạch khác NOT TESTED.
- 6 SKIPPED: OCR en/ko/zt thiếu model, MT ko/zt thiếu model, Online chưa opt-in. Không tải lại model hoặc thay dependencies.
- Corpus 24 câu Trung đã suy luận và lưu hai chặng thật. Chất lượng model pivot **chưa đạt nghiệm thu**, còn sai nghĩa và mask còn sót nét. Xem TRANSLATION_QUALITY_REPORT, E2E_REPORT và BUILD_REPORT.

Các phần phía dưới là kết quả lịch sử lúc chưa cài đủ thư viện/model.

Ngày: **06/11/2026**. Root: **D:\TransTool**. Kết luận: **CHƯA ĐẠT nghiệm thu end-to-end**.

**Cập nhật lượt tiếp tục:** 49 ca unittest PASS (44 cũ + 5 build gate), 0 fail/error, log riêng `logs/qa-followup-unit-20261106`. Chẩn đoán mới và audit `.venv`: [INSTALL_REPORT](INSTALL_REPORT.md). E2E không mock đã thực hiện nhưng FAIL vì thiếu `paddle/paddleocr`: [E2E_REPORT](E2E_REPORT.md). Build hiện SKIPPED theo prerequisite gate: [BUILD_REPORT](BUILD_REPORT.md). Các bảng 44 ca và build attempt bên dưới lưu kết quả lịch sử lượt triển khai ban đầu.

## Kết quả thực tế

| Hạng mục | Kết quả | Bằng chứng |
| --- | --- | --- |
| Truy cập root / tạo mã nguồn | Đạt | Thư mục ban đầu trống; source thực tế và `logs/source-manifest.json` |
| Kiểm tra cú pháp Python | Đạt | `python -m compileall -q main.py core providers ui scripts tests`, exit 0; `logs/compile.log` |
| Core/CV/workflow khả dụng | **44 PASS, 0 fail, 0 error** | `python scripts/run_tests.py`, `logs/test-results.json`, `logs/tests-unittest.log` |
| Integration methods OCR/Offline/Online | 9 method SKIP trong suite mặc định | Thiếu engine/model; Online live opt-in |
| GUI PySide6 integration | Class SKIP, gồm 3 test GUI chưa chạy | Thiếu PySide6 |
| pytest runner | Không chạy được | `logs/pytest-attempt.log`: `No module named pytest` |
| Cài dependencies đầy đủ | Thất bại vì mạng | `logs/install.log`: proxy không kết nối được / WinError 10061 |
| Tải OCR `det-ch` | Thất bại vì mạng | `logs/model-download-attempt.log` |
| Tải Offline `translate-en_vi-1_9` | Thất bại vì mạng | `logs/translation-model-download-attempt.log` |
| Tải font Noto Sans | Thất bại vì mạng | `logs/font-download-attempt.log` |
| MyMemory gọi API thật | **Thất bại kết nối** sau tối đa 3 lần thử | `python scripts/probe_online.py`, `logs/online-probe.json` (`mock=false`, `success=false`) |
| LibreTranslate thật | Chưa thử: không có instance được cung cấp/cài đặt | Unit HTTP mock đã đạt |
| PyInstaller | Thất bại trước build | `logs/build-attempt.log`: `No module named PyInstaller` |
| EXE | **Chưa có** | `logs/runtime-readiness.json`: `exe_exists=false` |

Thông tin runner: unittest báo `testsRun=53`, gồm 44 PASS và 9 method SKIP; `skipped` có 10 mục vì thêm một mục setUpClass GUI. Ba method GUI không được thực hiện. Không đổi tên kết quả unittest thành pytest. Các test dùng unittest.TestCase để pytest cũng có thể discover sau khi cài được pytest.

## Môi trường đã thực sự dùng

- Windows 10.0.26200, Python **3.10.9 x64**, `C:\Program Files\Python310\python.exe`.
- NumPy **2.2.6**, Pillow **11.3.0**, opencv-python-headless **4.12.0.88**, requests **2.32.4** của Python hệ thống.
- `.venv` đã tạo tại dự án nhưng chưa cài đủ dependencies. Không sử dụng hoặc thay đổi Python môi trường của dự án khác.
- Chưa có PySide6, PaddleOCR/PaddlePaddle, Argos, CTranslate2, SentencePiece, pytest, PyInstaller tại môi trường dự án.
- `requirements-core-tested.txt` ghi bộ CV thực sự chạy. `requirements.txt` ghim bộ đầy đủ đề xuất tương thích PaddleOCR 2.x/Argos; **chưa được cài và xác minh đồng thời**. Không coi pin phiên bản là kiểm chứng tương thích.
- 0/12 model danh mục đã cài. Không có kiểm thử chất lượng OCR hoặc dịch Offline bằng model thật thành công.

## Phạm vi của 44 ca đạt

Trong `tests/test_core.py`:

- Điều khiển: pause chặn ở checkpoint, resume tiếp tục, cancel đánh thức worker đang pause.
- Files/storage: sắp xếp 1/2/10, quét thư mục con, loại thư mục xuất, đường dẫn có dấu, folder thiếu, cache/provider/context, checkpoint bền vững, JSON atomic, từ chối output trùng ảnh gốc hoặc thoát phạm vi.
- Xử lý ảnh thật: glyph mask không phủ toàn bong bóng, inpainting không sửa ngoài mask, không có vùng giữ nguyên pixel, render Unicode tiếng Việt, PNG giữ alpha/kích thước, JPEG/WEBP/BMP mở lại được, lỗi lưu dọn file tạm, mask sai kích thước báo lỗi, ảnh hỏng báo lỗi, nội dung không vừa báo lỗi thay vì cắt.
- Adapter OCR với output fixture: tọa độ tile quy về ảnh gốc, dedup vùng chồng, thứ tự đọc, gom dòng có kiểm tra viền, chặn downloader tự động, thiếu model không gọi mạng. Các ca này **không chứng minh OCR nhận đúng chữ**.
- Dịch với fixture/HTTP mock: Offline không tạo Online provider hoặc kết nối socket, thiếu model không fallback, pivot cần đủ hai chặng, cache theo context/model, glossary/số được giữ, marker bị phá báo lỗi, fallback cần đồng ý, MyMemory/LibreTranslate xử lý response, quota không retry, timeout tối đa ba lần, từ chối endpoint HTTP bên ngoài hoặc chứa credential/key.
- Workflow dùng OCR/MT fixture và **CV/SQLite/filesystem thật**: xuất ảnh không sửa nguồn, các stage/progress events, skip theo checksum, batch tiếp tục sau ảnh hỏng, retry chỉ ảnh lỗi, dịch lỗi không xuất ảnh, cancel không lưu ảnh dang dở, OCR rỗng giữ pixel, output người dùng sửa được bảo vệ, tên file trùng khi flatten được phân biệt.

Tests integration thật tách trong `tests/test_integration.py`. Không có FakeOCR/FakeProvider được dùng trong module integration. Khi có model, test thực sự gọi engine và chặn kết nối socket ở OCR/Offline; bản dịch được lưu trong `logs/real-offline-*.txt`. Test chất lượng dịch hiện chỉ là smoke test (không rỗng/khác nguồn), cần đánh giá ngữ nghĩa trên corpus thực tế để nghiệm thu sản phẩm.

## Lỗi phát hiện và đã sửa

1. Vẽ chữ lên RGBA làm alpha của glyph chuyển thành 255. Sửa bằng khôi phục kênh alpha gốc sau render. Regression test so sánh toàn bộ alpha đã PASS.
2. Console CMD khi chuyển hướng log dùng cp1252, làm thông báo tiếng Việt gây UnicodeEncodeError. Script tải model/font đã cấu hình stdout UTF-8; lượt thử lại ghi được thông báo thất bại rõ ràng.
3. Đối chiếu index chính thức cho thấy model Hàn → Anh hiện là phiên bản **1.1**, không phải 1.9. Danh mục đã dùng đúng `translate-ko_en-1_1.argosmodel`; suy luận vẫn chưa kiểm thử.

## Artifact CV đã kiểm tra trực quan

- `output/cv-validation/before.png`: ảnh tổng hợp có chữ Anh.
- `output/cv-validation/after.png`: OpenCV phục hồi nền và Pillow vẽ câu tiếng Việt đủ dấu, không cắt; đã mở xem thực tế.
- `output/cv-validation/evidence.json`: ảnh 960×520, hash nguồn/đích, alpha được giữ.

**Giới hạn bằng chứng:** tọa độ vùng và câu dịch được nhập thủ công trong script fixture `scripts/validation_artifacts.py`. Artifact này chỉ xác nhận xử lý ảnh và render/export; không xác nhận OCR, Online/Offline MT hoặc workflow AI end-to-end. Nguồn tổng hợp không bị thay đổi.

## Ma trận 25 yêu cầu kiểm thử

| # | Yêu cầu | Trạng thái thực tế |
| --- | --- | --- |
| 1 | Khởi động ứng dụng GUI | Chưa xác minh: thiếu Qt |
| 2 | Chọn folder | QFileDialog có code; test GUI selection có mock, chưa chạy vì thiếu Qt |
| 3 | Quét ảnh | PASS filesystem thật |
| 4 | Đường dẫn tiếng Việt | PASS filesystem/CV/SQLite thật |
| 5 | OCR Trung | Chưa xác minh model thật, adapter fixture PASS |
| 6 | OCR Hàn | Chưa xác minh model thật |
| 7 | OCR Anh | Chưa xác minh model thật |
| 8 | Dịch Online | HTTP mock PASS; MyMemory live FAILED_CONNECTION |
| 9 | Dịch Offline | Chưa có model/engine; orchestration fixture PASS |
| 10 | Không Internet | PASS guard Offline/missing-model, Online timeout mock; live mạng bị chặn |
| 11 | Thiếu model | PASS báo lỗi không gọi mạng |
| 12 | Model lỗi | PASS hash/traversal với fixture cấu trúc; chưa chạy binary model |
| 13 | Cache | PASS SQLite thật và provider/context separation |
| 14 | Checkpoint | PASS SQLite thật / khôi phục / bỏ qua ảnh thành công |
| 15 | Pause | PASS JobControl; nút GUI chưa chạy |
| 16 | Resume | PASS JobControl; nút GUI chưa chạy |
| 17 | Cancel | PASS checkpoint/không lưu ảnh dang dở |
| 18 | Retry | PASS chỉ ảnh lỗi với OCR/MT fixture |
| 19 | Xóa chữ | PASS OpenCV thật trên fixture ảnh |
| 20 | Chèn chữ Việt | PASS Pillow thật, đã xem artifact |
| 21 | Giữ độ phân giải | PASS export thật |
| 22 | Giữ ảnh gốc | PASS hash nguồn giữ nguyên |
| 23 | Xuất file | PASS PNG/JPEG/WEBP/BMP thật / lỗi ghi atomic |
| 24 | Ảnh hỏng | PASS lỗi riêng từng ảnh, batch tiếp tục |
| 25 | Không treo GUI | Code QThread có; test event-loop chưa chạy vì thiếu Qt |

## Tiêu chí nghiệm thu sản phẩm

| Tiêu chí | Kết luận |
| --- | --- |
| GUI mở, chọn folder thực tế | Chưa đạt xác minh |
| Quét ảnh | Đạt phần core |
| OCR ảnh thật | Chưa đạt |
| Dịch thật sang tiếng Việt | Chưa đạt |
| Offline với model cài | Chưa đạt |
| Xóa chữ/chèn chữ/xuất ảnh | Đạt phần CV trên fixture; chưa có OCR/MT thật đầu vào |
| Progress/tên ảnh thực | Events core đạt; GUI chưa xác minh |
| Pause/resume | Điều khiển core đạt; GUI chưa xác minh |
| Lỗi từng ảnh / bảo vệ ảnh gốc | Đạt trong unit workflow |
| Test cốt lõi | 44 ca đạt bằng unittest; pytest chưa chạy |
| Script chạy/build | Đã tạo; cài/build chưa thành công |
| README tiếng Việt | Đã tạo |

Không có cơ sở kết luận ứng dụng hoàn chỉnh hoạt động thực tế trên Windows ở thời điểm báo cáo. Những bước tiếp theo cần môi trường cài dependencies/model được phép truy cập nguồn chính thức; không có yêu cầu người dùng sao chép mã nguồn hay tạo file thủ công.
