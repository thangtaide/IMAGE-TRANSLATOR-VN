# IMAGE TRANSLATOR VN

Kho Git chỉ lưu mã nguồn, kiểm thử, script chạy/build, cấu hình mẫu và báo cáo: `https://github.com/thangtaide/IMAGE-TRANSLATOR-VN`. Không đưa `.venv`, model AI, EXE/build, backup, cache, log/evidence, ảnh `ImgTest` hoặc cấu hình cá nhân lên Git. Các đường dẫn artifact trong báo cáo là bằng chứng cục bộ của máy đã kiểm thử, không phải file kèm repository. Khi clone sang máy khác cần cài dependencies/model và build riêng; `run_updated.bat` dành cho binary đã xác minh tại máy hiện tại, `run.bat` hỗ trợ chạy mã Python khi chưa có EXE.

Ứng dụng Windows OCR, dịch sang tiếng Việt, xóa chữ gốc và chèn bản dịch theo vùng OCR. Mã nguồn nằm trực tiếp tại **D:\TransTool**.

**Đã khôi phục và xác minh lại sau mất điện 06/11/2026:** nguồn/EXE cũ khớp fingerprint/hash, 5 model hợp lệ, Imports 16/16, dependencies 18/18, Ready: True. Sau cải tiến: unittest/pytest **76 PASS, 7 SKIPPED**, GUI và E2E Offline không mock PASS. Corpus `ImgTest` **61/61 ảnh xử lý, 0 lỗi, nguồn không đổi**, có 75 vùng chữ dịch thật; ảnh không có chữ hoặc chỉ có số/ký hiệu được bảo toàn. **Chưa nghiệm thu chất lượng:** Argos còn sai nghĩa/tên riêng và mask truyện có thể còn nét; M2M100 đã có adapter nhưng thiếu trọng số nên chưa suy luận thật. Xem [RECOVERY_REPORT.md](RECOVERY_REPORT.md), [REAL_IMAGE_REPORT.md](REAL_IMAGE_REPORT.md), [PROJECT_STATUS.md](PROJECT_STATUS.md), [M2M100_SETUP.md](M2M100_SETUP.md).

Chạy ngay bằng **`run.bat`** hoặc nhấp đúp **`dist\ImageTranslatorVN\ImageTranslatorVN.exe`**. Giữ toàn bộ thư mục onedir và `models` tại vị trí hiện có. Không cần cài lại môi trường hoặc tải lại năm model đã hợp lệ. GUI dùng font Windows đã cài tại chỗ, không sao chép font Windows để phân phối. Desktop vật lý người dùng/máy Windows sạch chưa kiểm thử.

**Mở bản cải tiến bằng `run_updated.bat`**. Bản này đã được kiểm thử GUI, các nút điều khiển và E2E trên ảnh truyện thật. `run.bat` vẫn mở bản MVP cũ, được bảo vệ nguyên vẹn. Build mới nằm cạnh bản cũ với timestamp `20261106T101857052219Z`; xem [BUILD_REPORT.md](BUILD_REPORT.md). Không sao chép riêng một file EXE ra khỏi thư mục onedir. Provider M2M100 cần model cài riêng; chọn khi chưa có model sẽ báo thiếu và không tự tải hoặc chuyển Online.

Các đoạn dưới đây về lỗi proxy/dependencies/build ban đầu là **lịch sử**, không phải hiện trạng. Các lệnh cài đặt chỉ dùng khi thiết lập máy mới; không nâng setuptools quá 80.9.0 trong môi trường CT2 4.6 hiện tại.

Lượt tiếp tục đã xác định proxy `127.0.0.1:9` và cờ tắt mạng do sandbox Codex; proxy Windows tắt, WinHTTP Direct, DNS hoạt động. Người dùng đã đồng ý cấp mạng nhưng profile thực thi chưa đổi. Xem [INSTALL_REPORT.md](INSTALL_REPORT.md) để áp dụng quyền đúng tại host, không xóa proxy quản lý. Regression hiện **49 ca PASS bằng unittest**, log riêng `logs/qa-followup-unit-20261106`. E2E thật không dùng mock đã được chạy và **FAIL tại OCR thiếu engine**, xem [E2E_REPORT.md](E2E_REPORT.md). Build hiện có gate chặn nếu GUI/E2E thật chưa PASS, xem [BUILD_REPORT.md](BUILD_REPORT.md).

## Sử dụng khi đã cài đủ thư viện

1. Nhấp đúp `install.bat` để tạo `.venv`, cài bộ phiên bản trong `requirements.txt` và tải font Noto Sans. Cần Python 3.10 hoặc 3.11 **64 bit** đã có Python Launcher. Máy hiện tại có Python 3.10.9. Script báo lỗi và lưu log nếu cài không thành công; không bỏ qua hạn chế mạng/proxy của máy.
2. Nhấp đúp `run.bat`. Sau khi cài thành công, người sử dụng không cần terminal. Khi đã có bản build, script ưu tiên EXE trong `dist\ImageTranslatorVN`.
3. Mở **Quản lý mô hình AI**. Chọn từng model cần thiết và bấm **Tải**, sau đó **Kiểm tra model**. Đây là thao tác riêng có truy cập Internet, không gửi ảnh hoặc văn bản OCR. Kiểm tra model hiện xác minh cấu trúc và SHA-256; kiểm thử suy luận thật là bước riêng.
4. Chọn thư mục ảnh nguồn, thư mục xuất trong một thư mục con của `D:\TransTool` (mặc định `output`), ngôn ngữ OCR và chế độ dịch.
5. Chọn **Cài đặt** nếu cần đổi font/cỡ chữ/màu/viền/căn lề, thứ tự đọc, inpaint/nền trắng/mask tùy chỉnh, định dạng và chất lượng ảnh, thuật ngữ/tên riêng.
6. Bấm **Bắt đầu dịch**. Theo dõi tên file, công đoạn, số ảnh đã hoàn thành/lỗi/bỏ qua và tiến trình phát sinh từ worker thật. Nhấp đúp hàng kết quả để xem trước/sau và cảnh báo.
7. **Tạm dừng**, **Tiếp tục**, **Hủy** có hiệu lực ở checkpoint an toàn. OCR hoặc một yêu cầu mạng đang thực hiện cần kết thúc trước khi dừng. **Thử lại ảnh lỗi / chưa xong** chỉ xử lý danh sách đó. Các kết quả đã hoàn tất được giữ lại.
8. Dùng **Mở kết quả** để mở Explorer. Ảnh nguồn luôn được giữ nguyên; tên ảnh xuất có hậu tố `.vi-<mã công việc>`.

Khi khởi động lại, nút **Khôi phục cấu hình công việc chưa hoàn thành** nạp công việc trước. Bấm Bắt đầu dịch; các ảnh thành công có fingerprint và checksum đầu ra đúng sẽ được bỏ qua. Công đoạn OCR/dịch bị gián đoạn giữa một ảnh sẽ được thực hiện lại qua cache; checkpoint hoàn tất ghi sau mỗi ảnh.

## Model cần tải

| OCR | Model phát hiện | Model nhận diện | Model hướng |
| --- | --- | --- | --- |
| Trung giản thể | `det-ch` | `rec-zh` | `cls` |
| Trung phồn thể | `det-ch` | `rec-zt` | `cls` |
| Hàn | `det-ml` | `rec-ko` | `cls` |
| Anh | `det-en` | `rec-en` | `cls` |
| Tự động | Cả ba model phát hiện | Cả bốn model nhận diện | `cls` |

Tự động thử bốn bộ model tuần tự và cảnh báo nếu điểm gần nhau; chưa có bộ phân loại ngôn ngữ đã hiệu chỉnh. Nên chọn rõ ngôn ngữ, đặc biệt với giản thể/phồn thể hoặc ảnh nhiều ngôn ngữ.

| Nguồn dịch Offline | Gói cần có | Đường dịch dự kiến |
| --- | --- | --- |
| Anh | `translate-en_vi-1_9` | en → vi |
| Trung giản thể | `translate-zh_en-1_9`, `translate-en_vi-1_9` | zh → en → vi |
| Trung phồn thể | `translate-zt_en-1_9`, `translate-en_vi-1_9` | zt → en → vi |
| Hàn | `translate-ko_en-1_1`, `translate-en_vi-1_9` | ko → en → vi |

Danh mục dựa trên [index chính thức Argos](https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json). Đây là model được chọn để tích hợp; **chưa có model nào được tải/cài hoặc kiểm thử suy luận trong phiên này**. Bộ cài từ chối model thiếu file, sai cặp ngôn ngữ hoặc không có cấu trúc SentencePiece/CTranslate2 được hỗ trợ. Không tuyên bố mọi gói Argos/BPE khác đều tương thích.

Model OCR nằm trong `models\ocr`, model dịch trong `models\translation`. Model được tải qua HTTPS từ PaddlePaddle và Argos. Sau tải, phần mềm kiểm tra archive, chống đường dẫn thoát thư mục, kiểm tra file bắt buộc và lưu SHA-256 cho từng file. Hash cục bộ giúp phát hiện hỏng/thay đổi về sau; danh mục chưa có checksum được nhà phát hành ký, nên không coi receipt cục bộ là chữ ký nguồn phát hành. Không tải lại model đã cài hợp lệ. Model hỏng cần xóa qua GUI rồi tải lại.

## Online miễn phí và quyền riêng tư

- **MyMemory** dùng GET API anonymous được công bố, không có API key/thẻ/credit. Hạn mức anonymous khoảng 5.000 ký tự/ngày/IP; mỗi truy vấn tối đa 500 byte. Phần mềm giới hạn truy vấn, dùng cache, giãn cách yêu cầu, timeout và tối đa 3 lần thử với backoff cho lỗi mạng/server. HTTP 429 dừng ngay; không né hạn mức. Tham khảo [đặc tả](https://mymemory.translated.net/doc/spec.php), [hạn mức](https://mymemory.translated.net/doc/usagelimits.php), [điều khoản](https://mymemory.translated.net/doc/en/tos.php). Thử gọi thật trong môi trường hiện tại thất bại kết nối; chưa xác minh dịch Online thành công.
- **LibreTranslate** chỉ dành cho endpoint tự host hoặc endpoint miễn phí người dùng có quyền sử dụng. Mặc định `http://127.0.0.1:5000`; ứng dụng không tự cài server. Không hardcode dịch vụ công cộng không được phép, không nhập API key. Endpoint bên ngoài phải dùng HTTPS. Provider đã được test bằng HTTP mock, chưa có instance thật được kiểm thử.
- **Offline** chỉ dùng OCR/model cục bộ, không gọi Online, không tự tải model, kể cả khi checkbox fallback đã được bật ở chế độ khác. Thiếu model sẽ báo lỗi. Argos provider dùng tokenizer của Argos và engine CTranslate2; tránh đường gọi Stanza có khả năng tải tài nguyên tự động.
- **Auto Fallback** thử Offline trước; chỉ gửi văn bản OCR tới Online khi ô đồng ý riêng được bật. Cả ảnh và xử lý phục hồi nền ở máy. GUI mô tả rõ chế độ hiện tại.
- Cache SQLite lưu văn bản OCR/bản dịch trên máy theo yêu cầu tính năng. Log không chủ động ghi nội dung OCR/bản dịch hoặc thông tin xác thực. Không có provider API tính phí trong chương trình.

## Chất lượng và giới hạn hiện tại

- PNG/JPG/JPEG/WEBP/BMP tĩnh, tên Unicode, quét thư mục con, sắp xếp tự nhiên. Ảnh động bị từ chối. Giới hạn 65 triệu pixel/ảnh để tránh cấp phát RAM không kiểm soát; ảnh dài được OCR bằng tile có overlap và dedup hình học. Một worker xử lý ảnh, OCR giữ một engine đang dùng, dịch giữ tối đa hai model CT2.
- Output giữ kích thước pixel được mã hóa trong file; không tự xoay theo EXIF. Giữ alpha khi định dạng hỗ trợ. JPEG/BMP được ghép nền trắng kèm cảnh báo; PNG/WEBP giữ alpha. Metadata/ICC/EXIF chưa được bảo toàn đầy đủ.
- Mask ước lượng nét chữ trong polygon OCR, nới mask có giới hạn; hỗ trợ Telea inpainting, nền trắng và mask từ ảnh PNG/BMP cùng kích thước. Mask tùy chỉnh hiện dùng chung cho batch, nên chỉ dùng khi các ảnh có cùng bố cục/kích thước hoặc xử lý từng ảnh.
- Chữ Việt tự xuống dòng và giảm font, tính cả dấu/viền. Nếu không vừa vùng OCR ở cỡ tối thiểu, ảnh được báo lỗi và không xuất ảnh đã tẩy chữ. Chưa có công cụ sửa polygon/bản dịch tương tác.
- Gom dòng bằng heuristic căn chỉnh/gap/viền tối. Chưa có segmentation bong bóng thoại hoặc bố cục truyện tranh đã được đánh giá. Thứ tự đọc phải chọn phù hợp; chữ dọc dựa trên xử lý crop của PaddleOCR, chưa được kiểm chứng bằng dữ liệu thật. Model sai/ngôn ngữ trộn có thể bỏ sót chữ: cần xem preview.
- Từ điển và số được bảo vệ bằng marker. Nếu provider làm thay đổi marker, ảnh báo lỗi thay vì mất tên/số. Cơ chế này có thể từ chối bản dịch model thật; cần đánh giá khi có model.
- Mặc định tải Noto Sans (SIL OFL 1.1). Tải font hiện bị chặn; runtime có fallback font Arial/Segoe UI đã cài trong Windows, không sao chép/phân phối font Windows. Noto chưa được đóng gói.

## Kiến trúc và thư mục

```text
D:\TransTool
  main.py                    Điểm vào GUI
  core\
    paths.py                 Root Python/EXE, thư mục model/cache
    types.py                 Options, OCRResult, lỗi nghiệp vụ
    storage.py               SQLite/cache/checkpoint/config/logging
    models.py                Danh mục, tải, kiểm tra và xóa model
    ocr.py                   PaddleOCR CPU, tile, dedup, thứ tự/gom dòng
    imaging.py               Mask, inpaint, renderer, atomic export
    pipeline.py              Providers/cache, batch và JobControl
  providers\                 Base, Online, Offline Argos/CTranslate2
  ui\                        MainWindow, QThread, settings, model manager, preview
  config\                    Cấu hình người dùng
  models\ocr\                Model OCR bên ngoài EXE
  models\translation\        Model dịch bên ngoài EXE
  assets\fonts\              Font và giấy phép khi tải được
  assets\icons\
  cache\                     SQLite, cache dependencies/framework
  logs\                      Log ứng dụng, kiểm thử và bằng chứng
  tests\                     Unit và real integration tách biệt
  scripts\                   CLI/QA, tải model/font chủ động, báo cáo môi trường
  output\cv-validation\      Artifact kiểm tra CV, không phải bằng chứng OCR/MT
  dist\                      Hiện chưa có EXE
  requirements.txt           Bộ pin đầy đủ đề xuất, chưa cài kiểm chứng
  requirements-core-tested.txt  Bộ CV đã chạy thật trong Python hệ thống
  install.bat / run.bat / build.bat
  ImageTranslatorVN.spec
  AGENTS.md / PROJECT_STATUS.md / TEST_REPORT.md
```

Đường dẫn framework được cấu hình về dự án khi có thể (Argos/XDG/Paddle/Torch/Hugging Face). PaddleOCR dùng đường dẫn model explicit và thay downloader bằng kiểm tra model cục bộ. Không sửa cache hay môi trường Python của dự án khác.

## Kiểm thử và build cho người phát triển

```bat
cd /d D:\TransTool
.venv\Scripts\python.exe -m pytest -q
set ITVN_TEST_ONLINE=1
.venv\Scripts\python.exe -m pytest tests\test_integration.py -v
```

Online test opt-in gửi chuỗi mẫu `Hello world`. Tests AI thật skip rõ lý do nếu thiếu engine/model; test GUI chạy nền với Qt offscreen và cần thêm kiểm tra trực tiếp trên Windows.

Môi trường hiện tại không có pytest; đã chạy cùng các test unittest bằng Python hệ thống có OpenCV/Pillow/NumPy/requests:

```bat
python scripts\run_tests.py
python -m compileall -q main.py core providers ui scripts tests
python scripts\runtime_probe.py
```

Các unit test workflow dùng OCR/MT fixture riêng trong `tests/test_core.py`; không có fake provider trong runtime ứng dụng. File `logs/test-results.json` lưu danh sách PASS/SKIP/error; log `tests-unittest.log` có chi tiết. `output/cv-validation/evidence.json` ghi rõ tọa độ và bản dịch nhập thủ công, chỉ xác minh CV và xuất ảnh.

`build.bat` chạy pip check, pytest rồi PyInstaller onedir. Đích là `dist\ImageTranslatorVN\ImageTranslatorVN.exe`, model bên ngoài. Giữ cấu trúc thư mục tại D:\TransTool để EXE tìm đúng root. **Build đã được thử nhưng thất bại vì chưa có PyInstaller; chưa có EXE để smoke-test.** Hooks Paddle/CT2 và đóng gói Qt còn phải kiểm tra trên môi trường có đủ dependencies. Không coi spec là bằng chứng build thành công.

## Xử lý lỗi cài đặt hiện tại

Xem `logs/install.log`: pip không kết nối được proxy (WinError 10061). `logs/pytest-attempt.log` và `logs/build-attempt.log` ghi thiếu module. `logs/online-probe.json` ghi thử provider thật không thành công. Cần kết nối hợp lệ được môi trường cho phép, hoặc wheelhouse đầy đủ đã được chuẩn bị cho Python/Windows tương ứng. `install.bat` hỗ trợ wheelhouse cục bộ và không tự tắt proxy/chính sách mạng.

Khi điều kiện này được giải quyết, đọc PROJECT_STATUS, cài đủ requirements, chạy pip check, tải các model trong bảng qua thao tác riêng, chạy integration thật, sửa lỗi tương thích phát hiện được, rồi mới build và nghiệm thu GUI/EXE. Chưa có kết quả cho các bước đó để tuyên bố hoàn tất.
