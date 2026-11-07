# Báo cáo build — lượt tiếp tục 06/11/2026

## Binary cuối đã kiểm chứng — 06/11/2026, sau sửa số trên corpus thật

**Build PASS; chính binary chạy PASS các luồng bên dưới.** Đã dùng `build.bat < nul` và spec hiện có, gate PASS đúng source/interpreter; pip check PASS, pytest **76 PASS, 7 SKIPPED**. Log `logs/build-ImageTranslatorVN-20261106T101857052219Z.log` kết thúc `Build complete!`.

- EXE: `dist/ImageTranslatorVN-20261106T101857052219Z/ImageTranslatorVN-20261106T101857052219Z.exe` — **19,756,572 byte**.
- SHA-256: `bc3227317d216e32ed34831402df159f8aad8b21540d5670a93887a7376db1b0`.
- Source fingerprint: `8a2a571f67e1a7303944d9d7a1a4dae23795d7732e34d924e527e777ca64d6f4`.
- **Mở bằng `run_updated.bat`**. Không ghi đè bản MVP gốc (`run.bat`) hoặc build trung gian `...100146952450Z`. SHA-256 bản gốc vẫn `25974010ed75fdc6a46e6b169bd730ddf16ffccc2a9de88b4cc1a39bf6182da1`.

| Kiểm chứng EXE cuối | Kết quả và evidence |
| --- | --- |
| Khởi động GUI Windows Qt, font/glyph tiếng Việt, picker Qt, model dialog, preview | PASS, `logs/gui-smoke-20261106T102342Z-c7d5c8/report.json`, exit 0 |
| OCR và dịch Offline trên ảnh truyện thật, đọc model/font, xuất đúng kích thước và giữ nguồn | PASS kỹ thuật, `output/e2e-validation/20261106T102347Z-9dbcba/report.json`, exit 0 |
| Nút start/pause/resume/cancel/retry, checkpoint skip, ảnh hỏng, progress, preview/zoom/fit, settings, verify model | PASS, `output/gui-workflow/20261106T102357Z-67edd2/report.json`, exit 0; bài điều khiển dùng fixture tổng hợp |
| Thiếu DLL/thư viện trong các luồng đã chạy | Không ghi nhận lỗi; không suy rộng tới tính năng/ngôn ngữ chưa test |
| GUI 61 ảnh truyện thật | PASS qua Python cùng mã nguồn; không chạy lại 61 ảnh qua nút của binary |
| Model M2M100 thật | SKIPPED: chưa có trọng số |
| Desktop vật lý/native Windows picker/máy Windows sạch khác | NOT TESTED |
| Ngữ nghĩa, OCR recall, mask trên mọi panel | Chưa đạt nghiệm thu; xem REAL_IMAGE_REPORT |

Giữ toàn bộ thư mục onedir và model ngoài tại `D:\TransTool\models`. Bản mới không chứa model M2M100. Chưa tuyên bố ứng dụng đạt chất lượng dịch thương mại/sản phẩm hoàn thiện. Các phần phía dưới là lịch sử build trước bản cuối.

Sau kiểm thử binary, đã chạy E2E bằng `.venv` trên ảnh truyện thật tại `output/e2e-validation/20261106T102613Z-a47b44/`, PASS, để latest pointer trở lại đúng interpreter. `check_build_ready.py` chạy lại PASS. Không sửa tay evidence/gate. Tổng hợp hash và các kiểm chứng cuối tại `logs/recovery-final-audit-20261106.json`.

## Build sau khôi phục — 06/11/2026, sau 10:01 UTC

Bản EXE cũ đã được kiểm tra lại GUI/E2E thật PASS, SHA-256 khớp và được giữ nguyên. `build.bat` giờ tự chọn tên timestamp khi bản mặc định đã tồn tại; spec nhận tên và giữ cùng độ sâu thư mục để đường dẫn model/root không đổi. Không ghi đè EXE cũ hoặc log build cũ.

Đã chạy `build.bat < nul` sau GUI/E2E source fingerprint `220bd6695793e54de9e4189598bcc1cb0bbcc48f4cffaf6ecc1394bea3be775c` PASS. Gate không thay đổi hoặc bỏ qua. Pip check PASS, pytest **73 PASS, 7 SKIPPED** trong log `logs/build-ImageTranslatorVN-20261106T100146952450Z.log`. PyInstaller đang đóng gói. Tên đích `dist/ImageTranslatorVN-20261106T100146952450Z/ImageTranslatorVN-20261106T100146952450Z.exe`. Chưa kết luận binary mới PASS cho tới khi chạy trực tiếp GUI/E2E/workflow nút thật.

M2M100 được đóng gói adapter, **không có trọng số và chưa kiểm thử suy luận**. Argos hiện có vẫn là mặc định. Các kết quả build phía dưới là lịch sử trước lượt khôi phục.

## Cập nhật build sau sửa WinError 127

Ngày 06/11/2026: full unittest/pytest **63 PASS, 6 SKIPPED**, GUI Windows-platform smoke và E2E chuẩn không mock đã PASS. Đã chạy `scripts/check_build_ready.py` với đúng source fingerprint và interpreter `.venv`: **PASS**.

Đã chạy xong **`build.bat < nul`**, giữ nguyên gate. Script tự chạy lại pip check/pytest (63 PASS, 6 SKIPPED) trước PyInstaller. **Build onedir PASS và binary đã được chạy kiểm chứng**, không chỉ dựa vào exit code build. Log `logs/build.log` kết thúc bằng `Build complete!`.

- EXE: `dist/ImageTranslatorVN/ImageTranslatorVN.exe`, **19,745,808 byte**.
- SHA-256 đo bằng `certutil`: `25974010ed75fdc6a46e6b169bd730ddf16ffccc2a9de88b4cc1a39bf6182da1`.
- Fingerprint nguồn lúc build/test: `d71827338053f78a99fe74bf1d9acc4ca5f61a54e5e238f5ac77bcb32b051027`.
- Chạy `scripts/smoke_gui.py --platform windows --exe dist\ImageTranslatorVN\ImageTranslatorVN.exe`: **PASS**, exit 0. Evidence `logs/gui-smoke-20261106T085536Z-fb0e84/report.json`, ảnh `window.png` đã xem trực tiếp: tiếng Việt rõ, không ô vuông. Có picker Qt thật, quét folder thật, đổi chế độ, mở Model Manager/Preview, heartbeat.
- Chạy `dist\ImageTranslatorVN\ImageTranslatorVN.exe --validate-e2e`: **PASS kỹ thuật**, exit 0. Evidence `output/e2e-validation/20261106T085546Z-e14cdf/report.json` ghi interpreter là chính EXE. OCR Paddle thật, dịch Argos/CT2 CPU qua hai model cục bộ, mask/inpaint/render/export, giữ nguồn và tái sử dụng OCR đều PASS. Ảnh 1200×430 giữ kích thước, tổng 8.984 giây, peak process working set 750,968,832 byte. Đây là fixture tổng hợp, không phải ảnh truyện/photo thực tế.

| Kiểm chứng binary hiện tại | Kết quả |
| --- | --- |
| EXE tồn tại, khởi động GUI | PASS thực tế |
| Đọc DLL/thư viện trong luồng đã chạy | PASS thực tế, không có lỗi loader |
| Đọc model cục bộ, chạy OCR và dịch Offline | PASS thực tế |
| Đọc font, glyph tiếng Việt, screenshot | PASS thực tế |
| Chọn folder bằng QFileDialog Qt, liệt kê ảnh | PASS thực tế |
| Xuất ảnh qua E2E bằng chính binary | PASS thực tế |
| Chạy toàn bộ OCR/MT từ thao tác nút GUI của EXE | NOT TESTED; QThread thật đã test bằng Python, EXE test GUI và E2E riêng |
| Native Windows folder picker, desktop vật lý người dùng | NOT TESTED |
| Ngữ nghĩa bản dịch, xóa hết nét chữ ở mọi ảnh | Chưa đạt nghiệm thu; còn lỗi đã ghi trong E2E_REPORT |

Mở `run.bat` hoặc nhấp đúp EXE tại vị trí hiện có. Phải giữ **toàn bộ thư mục onedir** và `D:\TransTool\models`, không chỉ sao chép một file EXE. Chưa kiểm thử trên máy Windows sạch khác.

Sau kiểm thử EXE, đã chạy lại E2E chuẩn bằng `.venv`: `output/e2e-validation/20261106T085912Z-51c063/report.json`, **PASS**, exit 0. `latest.json` hiện trỏ tới bằng chứng Python hợp lệ và `scripts/check_build_ready.py` đã chạy lại **PASS**. Không sửa tay bằng chứng/gate. Khi build lại sau thay đổi nguồn, phải tạo lại GUI/E2E evidence phù hợp.

Spec chỉ bổ sung khởi tạo runtime đúng thứ tự cho chính tiến trình build. Model vẫn nằm ngoài EXE; không nhúng hoặc tải lại model. Chất lượng dịch pivot chưa nghiệm thu; bản build nếu thành công là bản MVP kỹ thuật với giới hạn được ghi trong TRANSLATION_QUALITY_REPORT.

## Lịch sử trước khi sửa runtime — không phải trạng thái binary hiện tại

Các mục dưới đây giữ nguyên bằng chứng SKIPPED/FAIL của lượt trước.

**Trạng thái lượt này: SKIPPED. PyInstaller không được gọi vì GUI/E2E thật chưa đạt. EXE chưa tồn tại.**

Đích vẫn giữ nguyên:

`D:\TransTool\dist\ImageTranslatorVN\ImageTranslatorVN.exe`

## Điều kiện build đã bổ sung

`build.bat` giữ kiến trúc PyInstaller onedir và có thêm một bước đầu:

```bat
.venv\Scripts\python.exe scripts\check_build_ready.py
```

Bộ kiểm tra yêu cầu bằng chứng GUI smoke và E2E:

- Có kết quả tổng thể PASS thật, `mock=false`.
- Đúng fingerprint mã nguồn hiện tại.
- Đúng interpreter/môi trường Python dùng để build.
- Các bước OCR, dịch, inpaint, render, export và bảo vệ nguồn đều PASS.

Nếu thiếu điều kiện, script trả exit code 2 và `build.bat` dừng với **SKIPPED**, giữ nguyên file/model hiện có. Một suite pytest có nhiều test SKIP hoặc một kết quả mock không đủ để build bản nghiệm thu.

## Kết quả kiểm tra đã chạy

Đã gọi thực tế `.venv\Scripts\python.exe scripts\check_build_ready.py`:

- GUI has no real PASS result.
- E2E has no real PASS result.
- E2E evidence uses another Python environment (fixture chẩn đoán hiện chạy bằng Python hệ thống, không phải `.venv`).
- E2E has missing/failed core stages.

Exit code của riêng gate: **2**. PyInstaller không được gọi trong lượt này. Lượt đầu từng thử PyInstaller và thất bại do thiếu module; giữ log cũ `logs/build-attempt.log`, không biến kết quả đó thành một build mới.

## Ma trận kiểm chứng EXE

| Kiểm tra | Trạng thái |
| --- | --- |
| EXE tồn tại | FAIL: chưa có file |
| Build PyInstaller lượt này | SKIPPED: chưa đủ prerequisite |
| Khởi động EXE | NOT TESTED |
| Thiếu DLL/thư viện | NOT TESTED |
| Đọc model cục bộ | NOT TESTED |
| Đọc font | NOT TESTED |
| Chọn folder | NOT TESTED |
| Xuất ảnh thật | NOT TESTED |
| Desktop hiển thị trực tiếp | NOT TESTED |

Không tuyên bố EXE PASS dựa vào spec hoặc exit code build. Sau khi GUI và E2E có bằng chứng thật bằng `.venv`, chạy `build.bat`, sau đó mở EXE tại Windows và thực hiện lại workflow với model/font cục bộ. Chỉ khi đó mới cập nhật từng mục thành PASS.

## Kiểm thử thay đổi điều kiện build

5 ca mới trong `tests/test_build_gate.py` đã PASS bằng unittest: thiếu bằng chứng, mock PASS, bước core SKIPPED/FAIL/NOT TESTED, sai mã nguồn/interpreter đều bị từ chối; fixture hợp lệ nhất quán đáp ứng gate. Các ca này chỉ kiểm tra logic gate, không chứng minh GUI/AI/EXE đã hoạt động.
