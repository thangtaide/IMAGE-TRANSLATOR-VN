# Khôi phục sau mất điện — 06/11/2026

## Trạng thái cuối phiên

- Audit cuối 10:26 UTC: **16/16 imports, 18/18 pins, Ready True**, `logs/install-audit-20261106T102603Z/`. Cả 5 model verify lại OK.
- Sau các sửa từ corpus thật: unittest và pytest **76 PASS, 7 SKIPPED**. Unittest 83 ca tại `logs/real-image-fix-unittest-20261106/`; pytest tại `logs/build-ImageTranslatorVN-20261106T101857052219Z.log`.
- Người dùng cung cấp `ImgTest`: lượt đầu 58/61, 3 lỗi marker số; sau sửa bảo toàn số/ký hiệu và kiểm tra số nguyên dạng, **61/61 xử lý, 0 lỗi**, giữ hash/kích thước. Có 75 vùng chữ dịch thật; không gắn PASS chất lượng cho toàn corpus. Evidence `output/real-image-validation-20261106-numeric-fix/`, đánh giá `REAL_IMAGE_REPORT.md`.
- GUI batch đủ 61 ảnh thật PASS; ảnh dài ghép panel 1280×3385 PASS kỹ thuật; ghi rõ provenance ảnh ghép và hạn chế accuracy.
- **EXE cuối build và kiểm chứng thực tế PASS**: `dist/ImageTranslatorVN-20261106T101857052219Z/ImageTranslatorVN-20261106T101857052219Z.exe`. GUI smoke, workflow nút và E2E truyện thật đều PASS. Mở bằng **run_updated.bat**; bản cũ/run.bat và build trung gian vẫn còn nguyên. Hash trong BUILD_REPORT.
- Chưa đạt ngữ nghĩa/credit/tên riêng/mask truyện hoàn hảo. M2M100 thiếu trọng số, sandbox tắt mạng; inference/comparison SKIPPED. Không cài/nâng package hoặc tải/xóa model.

Các mục phía dưới ghi diễn tiến và bằng chứng từng thời điểm, không thay thế trạng thái cuối này.

## Xác minh trước khi sửa mã

1. Tìm thấy đầy đủ các thư mục và báo cáo tại **D:\TransTool**, không tạo lại dự án.
2. Fingerprint nguồn `d71827338053f78a99fe74bf1d9acc4ca5f61a54e5e238f5ac77bcb32b051027` khớp bản trước mất điện; không lỗi AST/file Python rỗng. SQLite `cache/state.sqlite3` đọc `PRAGMA quick_check`: `ok`. Không có manifest trước cho mọi file EXE/DLL nên không tuyên bố kiểm tra toàn bộ đĩa/OS.
3. `.venv` Python 3.10.9 x64 chạy được. Audit mới **16/16 imports, 18/18 pins, Ready: True**, `logs/install-audit-20261106T094611Z/installation.json`.
4. Kiểm tra lại receipt/hash **5 model OK**: det-ch, rec-zh, cls, translate-zh_en-1_9, translate-en_vi-1_9. Đủ Trung giản thể → Việt qua Anh; chưa đủ các ngôn ngữ còn lại.
5. EXE cũ giữ nguyên SHA-256 `25974010ed75fdc6a46e6b169bd730ddf16ffccc2a9de88b4cc1a39bf6182da1`. GUI Windows smoke `logs/gui-smoke-20261106T094708Z-1922c7/` PASS. E2E chính EXE `output/e2e-validation/20261106T094709Z-168cc8/` PASS kỹ thuật, không mock.
6. Baseline unittest **63 PASS, 6 SKIPPED**, `logs/recovery-baseline-unittest-20261106/`; pytest **63 PASS, 6 SKIPPED**, `logs/recovery-baseline-pytest-20261106.log/xml`. GUI Python `logs/gui-smoke-20261106T094708Z-1accfc/` và E2E `output/e2e-validation/20261106T094832Z-8100b8/` PASS.
7. Sau xác minh, tiếp tục provider M2M100 riêng, mask thích ứng, thao tác GUI và build mới bên cạnh bản cũ. M2M100 thiếu model/kết nối hợp lệ; không bỏ qua hạn chế để tải.

Audit cấu trúc/tài nguyên tại `logs/recovery-audit-20261106T094804Z/report.json`. Không dùng Git (`.git` không tồn tại). `tasklist` bị Access denied; đọc Win32 Toolhelp thành công sau đó tại `logs/recovery-process-inventory-20261106.json`, ghi tên/PID các tiến trình liên quan trong lúc test/build đang chạy. Không đọc command line hoặc dừng tiến trình ngoài tác vụ của phiên; không đủ bằng chứng loại trừ mọi tác vụ nền khác. Không tìm thấy `.part/.tmp/.itvn-*` trong phạm vi audit; không xóa dữ liệu tạm.

## Bảo vệ dữ liệu

Trước sửa, sao lưu **70 file** mã/cấu hình/tài liệu vào `backups/recovery-20261106T095010Z`, có `manifest.json`. Không sửa model, không cài lại `.venv`/requirements, không đổi setuptools/CT2/PATH/DLL hệ thống. Không xóa cache/evidence cũ. Bản build mới dùng tên có timestamp; EXE cũ và toàn bộ thư mục của nó được giữ nguyên.

## Thay đổi và kết quả hiện tại

- Provider local-only `M2M100`, factory lựa chọn rõ engine, GUI có tùy chọn M2M100, CLI nhập gói đã chuyển đổi. Không có model nên suy luận/so sánh M2M100 **SKIPPED/NOT TESTED**. Xem `M2M100_SETUP.md`.
- Mask mở ROI theo độ cao chữ, lấy cả connected component của nét, tránh component nối ra mép ROI và bảo vệ viền trước dilation. Cache/job identity có revision mask mới để không dùng nhầm ảnh xuất cũ.
- So sánh trên cùng fixture với implementation sao lưu: còn **600 → 0 pixel tối** trong vùng chữ; **0 pixel viền màu thay đổi**, nguồn giữ hash. `output/mask-validation/20261106T095833Z-c49a9e/report.json`. Chỉ có giá trị trên fixture/geometry đã test, không phải cam kết nền phức tạp.
- GUI nút thật + QThread/OCR/MT thật tại `output/gui-workflow/20261106T095851Z-b1fa60/report.json`: **PASS**. Pause/resume/cancel/retry, checkpoint skip, ảnh hỏng, progress thật, preview/zoom/fit, settings và nút verify OCR model. SQLite riêng, nguồn không đổi, cấu hình được khôi phục sau QA. Lỗi `UnidentifiedImageError` trong log là fixture hỏng cố ý, không phải model hỏng.
- Unittest sau sửa: **80 ca, 73 PASS, 7 SKIPPED**, `logs/recovery-final-unittest-20261106/`. 7 skip gồm 6 điều kiện thiếu model/Online trước đây và M2M100 chưa có model. Các test contract M2M100 là mock, các test mask dùng OpenCV thật.
- GUI smoke sau sửa `logs/gui-smoke-20261106T100028Z-a95056/` PASS; E2E chuẩn `output/e2e-validation/20261106T100031Z-4d4a08/` PASS kỹ thuật, không mock. Build gate PASS. Build mới đang chạy; kết quả binary sẽ cập nhật tại BUILD_REPORT.

## Chưa hoàn thành

M2M100 chưa tải/chuyển đổi/suy luận do sandbox mạng tắt và chưa có model cục bộ; chưa thể chứng minh chất lượng zh→vi cải thiện. Argos vẫn có câu sai nghĩa. Đã nhận và kiểm thử 61 panel truyện, nhưng chưa có ground truth/đánh giá ngữ nghĩa từng câu; không dùng PASS kỹ thuật để nghiệm thu chất lượng. Chữ dọc/nền phức tạp còn hạn chế; ảnh dài hiện mới thử bản ghép panel. Desktop vật lý/native Windows picker, model download/delete và máy Windows sạch chưa kiểm thử trong lượt này.
