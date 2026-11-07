# Trạng thái Image Translator VN

## Quản lý Git — 06/11/2026

Đã `git init -b main`; chưa có commit và chưa thêm được remote vì sandbox chặn ghi `.git/config`/index. Remote dự kiến `https://github.com/thangtaide/IMAGE-TRANSLATOR-VN.git`. `.gitignore` loại model, môi trường Python, EXE/build, backup, cache, log, output/evidence, ảnh ImgTest và cấu hình riêng. Giữ mã nguồn/test/script, cấu hình mẫu và các báo cáo Markdown. Không xóa dữ liệu cục bộ. Truy cập GitHub cũng lỗi proxy `127.0.0.1:9`. Yêu cầu nâng quyền ghi Git metadata đã bị chính sách `sandbox_approval=false` từ chối. Cần môi trường cho phép ghi `.git` và HTTPS tới GitHub để commit/push; không đổi quyền ACL hoặc bỏ proxy để vượt giới hạn. Xem `GIT_PUBLISH_REPORT.md`.

## Kết quả cuối lượt khôi phục — 06/11/2026, sau 10:26 UTC

**MVP đã khôi phục và mở rộng, chưa nghiệm thu chất lượng dịch.** Audit cuối `logs/install-audit-20261106T102603Z`: **16/16 imports, 18/18 pin, Ready True**; 5 model vẫn hợp lệ. Không cài package, đổi model/.venv/setuptools/CT2 hoặc DLL hệ thống.

- Unittest **83 ca: 76 PASS, 7 SKIPPED**, `logs/real-image-fix-unittest-20261106/`. Pytest cuối **76 PASS, 7 SKIPPED**, trong `logs/build-ImageTranslatorVN-20261106T101857052219Z.log`.
- Corpus người dùng `D:\TransTool\ImgTest`: **61/61 ảnh xuất, 0 lỗi**, nguồn giữ hash và kích thước; **75 vùng chữ dịch thật**, 2 vùng số/ký hiệu bảo toàn. 24 ảnh raw OCR không tìm thấy chữ; không gọi mọi ảnh là bản dịch đạt. Evidence `output/real-image-validation-20261106-numeric-fix/`.
- Lượt trước có 3 lỗi marker số, đã sửa bằng giữ nguyên vùng chỉ có số/ký hiệu và kiểm tra số nguyên dạng sau dịch; mất/đổi/thêm số vẫn bị chặn. Các output/cache/job có revision mới, không ghi đè kết quả cũ. Backup trước sửa `backups/pre-numeric-fix-20261106T101537Z`.
- GUI với 61 ảnh thật: PASS, 494 heartbeat, 61 hàng, progress 100%. Chính EXE cuối: GUI smoke, workflow nút và E2E ảnh truyện thật PASS kỹ thuật. Ảnh dài ghép panel 1280×3385 cũng PASS kỹ thuật; ghi rõ là fixture ghép, chưa chấm accuracy.
- Mở bản mới bằng **`run_updated.bat`**. EXE `dist/ImageTranslatorVN-20261106T101857052219Z/ImageTranslatorVN-20261106T101857052219Z.exe`, SHA-256 `bc3227317d216e32ed34831402df159f8aad8b21540d5670a93887a7376db1b0`. Bản gốc và bản build trung gian đều giữ nguyên; `run.bat` vẫn mở bản gốc.
- **Còn hạn chế:** Argos sai nghĩa/tên riêng trên truyện, còn nét màu/dấu câu ở một số mask. M2M100 chỉ tích hợp adapter, chưa có trọng số/Transformers; so sánh thật SKIPPED do sandbox mạng tắt. Không tuyên bố bản dịch đã tốt hoặc M2M100 đã chạy được.

Đọc **RECOVERY_REPORT.md, REAL_IMAGE_REPORT.md, BUILD_REPORT.md, M2M100_SETUP.md** trước khi tiếp tục. Bước tiếp theo: cung cấp môi trường thực thi có HTTPS hợp lệ/model M2M100 chính thức để chuyển đổi và so sánh; đánh giá corpus có bản chép chuẩn và mask trên nền phức tạp. Các phần dưới ghi lịch sử từng giai đoạn, không thay thế trạng thái này.

## Khôi phục sau mất điện — trạng thái mới 06/11/2026, sau 10:00 UTC

Đã xác minh lại MVP trước khi sửa: fingerprint nguồn và SHA-256 EXE khớp, SQLite quick_check ok, 5 model hợp lệ, audit 16/16 imports và 18/18 pins, Ready True. Baseline unittest/pytest 63 PASS, 6 SKIPPED; GUI và E2E Offline chính EXE cũ PASS. Không tạo lại dự án/.venv, không cài package hoặc đổi model. Backup 70 file tại `backups/recovery-20261106T095010Z`.

Sau sửa: **unittest và pytest 73 PASS, 7 SKIPPED**; GUI smoke và E2E chuẩn không mock PASS. Mask thích ứng giảm pixel tối còn sót **600 → 0**, viền màu thay đổi **0** trên fixture đã kiểm tra. GUI nút thật + QThread/OCR/MT thật PASS cả pause/resume/cancel/retry/skip/error/preview/zoom/settings/verify model; có cache QA riêng và khôi phục cấu hình.

Provider M2M100 CPU riêng đã tích hợp, không thay Argos mặc định. **Chưa có model M2M100; suy luận/so sánh thực tế SKIPPED**, không có bản dịch giả. Sandbox vẫn tắt mạng, không tải lớn hoặc cài Transformers. Chi tiết `M2M100_SETUP.md`, `RECOVERY_REPORT.md`. Chưa có corpus truyện thực tế được cung cấp; chưa nghiệm thu ngữ nghĩa/nền phức tạp/chữ dọc.

`build.bat` giữ gate và ghi build mới vào tên timestamp để bảo vệ bản EXE cũ. Log hiện tại `logs/build-ImageTranslatorVN-20261106T100146952450Z.log`: pip check PASS, pytest 73 PASS/7 SKIPPED; PyInstaller đang chạy. Xem BUILD_REPORT để biết kết quả kiểm chứng binary sau đó.

Kiến trúc chỉ mở rộng factory/provider local M2M100, mask và injection đường dẫn SQLite QA cho MainWindow; native runtime guard vẫn giữ nguyên. Cache/job identity bổ sung `adaptive-mask-v2` để không tái sử dụng ảnh xuất mask cũ.

Ưu tiên tiếp: có quyền mạng thực thi hợp lệ và model M2M100 chính thức → chuyển đổi/kiểm thử CPU → so sánh 24 câu; nhận đường dẫn corpus truyện thực tế để nghiệm thu. Giữ nguyên model/EXE cũ hợp lệ. Các trạng thái phía dưới là lịch sử trước lượt khôi phục này.

**Hiện trạng mới nhất 06/11/2026:** audit `.venv` **16/16 imports, 18/18 pin, Ready: True**. Đã sửa WinError 127 trong luồng chuẩn, **E2E kỹ thuật không mock PASS**. GUI offscreen và native Windows platform PASS, screenshot hiển thị chữ Việt. Unittest và pytest đều **63 PASS, 6 SKIPPED**. **Build onedir PASS, chính EXE đã chạy GUI smoke và E2E Offline thành công**. Chất lượng model pivot còn lỗi ngữ nghĩa và mask còn sót nét; không coi sản phẩm đã nghiệm thu chất lượng. Dữ liệu/model/bằng chứng cũ được giữ nguyên.

## Kết quả binary và công việc tiếp theo hiện tại

- Chạy bằng `run.bat` hoặc `D:\TransTool\dist\ImageTranslatorVN\ImageTranslatorVN.exe`. Giữ nguyên thư mục onedir và model ngoài tại `D:\TransTool\models`.
- EXE GUI: `logs/gui-smoke-20261106T085536Z-fb0e84/report.json` PASS, Windows Qt platform; đã xem screenshot tiếng Việt. Desktop vật lý/native Windows picker chưa xác minh.
- EXE E2E: `output/e2e-validation/20261106T085546Z-e14cdf/report.json` PASS kỹ thuật, OCR/dịch thật, đủ artifact, kích thước giữ nguyên và nguồn không đổi. Đây là fixture tổng hợp.
- Build: `logs/build.log`, binary SHA-256 và ma trận nghiệm thu trong `BUILD_REPORT.md`; không có model/dependency nào bị thay trong lượt sửa DLL.
- Sau kiểm thử EXE, chạy lại E2E chuẩn `.venv` PASS tại `output/e2e-validation/20261106T085912Z-51c063/` và build prerequisite check PASS. Đây là evidence Python mới nhất; evidence EXE riêng vẫn giữ nguyên.
- Việc tiếp theo: đánh giá và tích hợp model trực tiếp zh→vi sau khi quyết định dung lượng/RAM; sửa mask còn sót nét dựa trên ảnh thật; kiểm thử corpus truyện/photo, OCR chữ dọc và các ngôn ngữ thiếu model; kiểm thử workflow thao tác đầy đủ trên desktop người dùng và máy sạch. Chưa thực hiện các mục này.
- Mục “Công việc tiếp theo” trong lịch sử phía dưới mô tả thời điểm môi trường còn thiếu thư viện; **không chạy lại install hoặc tải lại model đã hợp lệ**.

## Lượt sửa WinError 127 và hoàn thành E2E
- Root cause đã xác minh bằng PE imports/exports và loaded-module path: Paddle nạp `paddle/libs/libiomp5md.dll`, bản này thiếu `__kmpc_masked` và `__kmpc_end_masked` mà `torch/lib/torch_cpu.dll` yêu cầu. Torch bị import gián tiếp tại `ctranslate2/specs/model_spec.py:18`; loader báo WinError 127 tại shm.dll/dependency.
- Bằng chứng chính xác: `output/runtime-validation/20261106T084730Z-ca8bd9/report.json` (negative control `REPRODUCED`, không phải pipeline thành công).
- Thêm `core/runtime.py`: khóa và cache khởi tạo CT2/Torch trước Paddle. Entry point và package UI cũng gọi trước Qt để tránh lỗi typing.Self phát hiện ở worker Python 3.10/PySide6. Hai adapter OCR/Offline tự bảo vệ đường gọi trực tiếp. Model vẫn lazy/reuse, suy luận ở QThread.
- Không đổi dependencies/setuptools, không sửa site-packages/PATH/DLL hệ thống; không xóa/tải lại model. Chưa cần kiến trúc subprocess suy luận: thứ tự nạp ổn định qua các ca fresh-process.
- Worker hỗ trợ SQLite state riêng qua tham số tùy chọn; validation dùng DB mới để đảm bảo OCR/MT thực sự chạy thay vì cache. Hủy trước/sau khởi tạo runtime được xử lý an toàn.
- `tests/test_runtime_integration.py` chạy 7 ca tiến trình mới: tái hiện raw legacy order; CT trước Paddle; chuẩn bị runtime rồi import Paddle; OCR adapter trước dịch; 4 lần OCR/MT cùng model; restart QThread worker hai lần; cancel job thật. Các đường được guard PASS; raw legacy order vẫn tái hiện lỗi đúng như negative control.
- `logs/runtime-final-unittest-20261106/test-results.json`: 69 ca, **63 PASS, 6 SKIPPED**, không lỗi. `logs/runtime-final-pytest.log` và XML: **63 PASS, 6 SKIPPED**, không lỗi. Các skip: OCR en/ko/zt, MT ko/zt thiếu model; Online opt-in.
- Full suite đầu phát hiện một test dùng literal `.venv/python.exe` làm ví dụ “Python khác”; khi chạy bằng chính `.venv` giả định này sai. Đã sửa test tạo đường dẫn khác interpreter thực tế; không thay logic build gate hay sửa output test.
- E2E chuẩn mới nhất `output/e2e-validation/20261106T084804Z-4a9386/`: PASS toàn bộ, đủ source/OCR/translation/mask/erased/final/report, input fixture Trung tổng hợp, không hardcode OCR/MT. Đã xem ảnh cuối; còn vết nhỏ ở rìa mask và bản dịch câu thứ hai sai nghĩa.
- Font: Qt offscreen không có font directory/family mặc định. `ui/fonts.py` đăng ký font đã cài tại Windows qua đường dẫn, kiểm tra glyph bằng Unicode codepoint; không sao chép/phân phối font Windows. Screenshot đã đọc được tiếng Việt, native Windows platform cũng PASS trong desktop của sandbox, chưa xác minh desktop vật lý của người dùng.
- GUI bằng chứng mới nhất `logs/gui-smoke-20261106T084804Z-d4ffe4/`. Khởi tạo, picker Qt, bảng ảnh, model dialog, preview, heartbeat, glyph và screenshot PASS.
- Corpus 24 câu và từng chặng: `output/translation-quality/20261106T083515Z-bdb3f5/`. Tokenizer khớp Argos; pivot khớp hai chặng riêng, direction đúng, không lỗi giới hạn token. Câu mục tiêu zh→en đã lệch cách diễn đạt, en→vi làm mất nghĩa hoàn toàn. Xem `TRANSLATION_QUALITY_REPORT.md`.
- Đã nghiên cứu `facebook/m2m100_418M` MIT, hỗ trợ zh/vi, trọng số chính thức 1.94 GB; CT2 4.6 hỗ trợ chuyển đổi CPU/int8. Chưa tải hoặc kiểm thử model lớn này.
- `build.bat` đã hoàn tất sau khi gate PASS và full tests đạt; binary đã PASS GUI smoke và E2E thật. Xem BUILD_REPORT để biết phạm vi kiểm chứng và giới hạn.

Các phần lịch sử bên dưới mô tả những trạng thái FAIL cũ, không thay thế bằng chứng hiện tại.

## Lượt sửa import CTranslate2 (sau evidence 20261106T080950Z)
- Import duy nhất FAIL: `ctranslate2` 4.6.0, `ModuleNotFoundError: No module named 'pkg_resources'` tại `ctranslate2/__init__.py:8`.
- Nguyên nhân: setuptools 84.2.1 đã bỏ pkg_resources; không phải thiếu model hay DLL trong lỗi import ban đầu.
- Đã hạ riêng setuptools xuống 80.9.0 từ wheel cache, SHA-256 khớp PyPI. Inventory trước/sau xác nhận **chỉ setuptools thay đổi**. Không tạo lại `.venv`, không cài lại requirements, không đổi CTranslate2/Torch/Paddle và không sửa mã runtime chính.
- Chạy lại check_installation.py: **Imports PASS 16/16, Required packages satisfied 18/18, Ready: True**, pip check PASS. Evidence `logs/install-audit-20261106T081441Z/installation.json`.
- Bằng chứng sửa và traceback: `logs/ctranslate2-repair-20261106T081432Z-3ca7ce/`.
- GUI smoke **PASS Qt offscreen**, process exit 0; picker/model manager/preview/list ảnh/heartbeat đạt. Screenshot vẫn hiện ô vuông thay chữ ở offscreen, chưa xác minh font và desktop/native dialog. Evidence `logs/gui-smoke-20261106T081510Z-263830/`.
- Model có và verify OK: det-ch/rec-zh/cls + translate-zh_en-1_9/translate-en_vi-1_9. Không tải lại/xóa model nào.
- Model còn thiếu: OCR det-en/rec-en/det-ml/rec-ko/rec-zt; dịch translate-zt_en-1_9/translate-ko_en-1_1. Không tải tự động.
- OCR Trung thật trên fixture tổng hợp: `你好，世界！` confidence 0.993094; `欢迎使用图像翻译。` confidence 0.982723, tọa độ hợp lệ. Evidence `output/e2e-validation/20261106T081543Z-83d0a4/ocr.json`.
- Offline en→vi độc lập PASS suy luận; cùng tiến trình Paddle trước CT FAIL WinError 127 ở torch/lib/shm.dll; CT trước Paddle rồi dịch zh→en→vi PASS suy luận. Xác nhận vấn đề thứ tự nạp, chưa chỉ rõ symbol/DLL phụ thuộc bị xung đột. Evidence `logs/engine-interop-20261106T081715Z-e403eb/`.
- Bản dịch câu thứ hai là `Không có gì.`, sai nghĩa so với nguồn. Không coi suy luận thành công là đạt chất lượng.
- Luồng E2E chuẩn hiện FAIL tại translation; mask/inpaint/render/export SKIPPED. Không build EXE.
- Thêm hai script chẩn đoán phạm vi hẹp: `repair_ctranslate2_import.py`, `probe_engine_interop.py`. Đã cập nhật INSTALL_REPORT, giữ nguyên bằng chứng các lượt trước.
- Việc tiếp theo: xử lý khởi tạo CT trước Paddle trong worker, kiểm thử lại E2E và chất lượng; xác minh font/desktop. Yêu cầu hiện tại về sửa import đã hoàn tất; chưa thay đổi mã xử lý chính để mở rộng sang lỗi runtime mới.

Các phần bên dưới lưu **lịch sử lượt triển khai/chẩn đoán trước**, bao gồm trạng thái từng thiếu thư viện/model; xem phần hiện trạng mới nhất trước khi tiếp tục.

## Lượt tiếp tục: chẩn đoán WinError 10061 và kiểm thử thật
- Đã chẩn đoán chỉ đọc: `CODEX_SANDBOX_NETWORK_DISABLED=1`, HTTP_PROXY/HTTPS_PROXY/ALL_PROXY cùng là `http://127.0.0.1:9`, PIP_NO_INDEX=1. Cổng proxy trả 10061.
- Proxy Windows HKCU tắt; WinHTTP Direct; DNS của các nguồn chính thức PASS. HTTPS theo môi trường FAIL; không bỏ proxy để vượt sandbox.
- Người dùng **đã đồng ý cấp môi trường thực thi có mạng**. Kiểm tra lại vẫn thấy hạn chế như cũ. Yêu cầu thực thi có quyền mạng bị auto-review từ chối vì `sandbox_approval=false`. Không cần hỏi lại quyền đã được đồng ý; cần host áp dụng quyền có hiệu lực.
- Không sửa proxy hệ thống/VPN/firewall/Codex config và không lặp lại pip/model downloads khi biết chắc bị chặn.
- `.venv` được tái sử dụng, pip 22.3.1; audit import từng module: 0/16 đạt, 0/18 pin được đáp ứng. Cài đặt đầy đủ SKIPPED vì mạng chưa hợp lệ.
- Thêm `scripts/diagnose_network.py`, `check_installation.py`, `validate_e2e.py`, `smoke_gui.py`, `gui_smoke_actions.py`, `qa_common.py`, `check_build_ready.py`; không viết lại core/providers/UI.
- Thêm nhánh QA tùy chọn `main.py --smoke-test --smoke-report ...`; chạy bình thường giữ nguyên entry point.
- Đã thực hiện E2E **không dùng mock**: ảnh Trung tổng hợp 1200×430 được tạo và kiểm tra trực quan; OCR FAIL vì thiếu Paddle/PaddleOCR, các bước dịch/mask/inpaint/render/export SKIPPED. Không tạo ảnh dịch giả.
- Bằng chứng E2E: `output/e2e-validation/20261106T070513Z-a4c481/report.json`; nguồn, OCR/translation JSON lỗi và traceback nằm cùng thư mục. Các lần trước được giữ lại.
- GUI smoke SKIPPED vì thiếu PySide6; chưa mở GUI/desktop thật. `logs/gui-smoke-20261106T070512Z-5fe844/report.json`.
- `build.bat` có gate mới: yêu cầu GUI/E2E PASS thật, đúng fingerprint và interpreter. Gate thực tế trả SKIPPED; không gọi PyInstaller ở lượt này, không có EXE.
- Regression hiện tại **49 PASS**, 0 fail/error, bằng unittest; 5 ca gate mới đều là unit fixtures, không phải AI PASS. Log riêng `logs/qa-followup-unit-20261106/`, không ghi đè 44 ca ban đầu.
- Đã tạo `INSTALL_REPORT.md`, `E2E_REPORT.md`, `BUILD_REPORT.md`. Xem các báo cáo này trước khi tiếp tục; báo cáo 44 ca dưới đây là lịch sử lượt đầu.

## Môi trường
Windows, Python 3.10.9 x64. CMD hoạt động; PowerShell runner báo Access denied.

## Kiến trúc
PySide6 GUI → QThread batch → OCR PaddleOCR 2.x cục bộ → provider dịch độc lập → OpenCV mask/inpaint → Pillow render → atomic save. SQLite lưu cache và checkpoint. Model manager tải theo thao tác riêng.

## Module đã tạo
- `core/paths.py`, `types.py`, `storage.py`: đường dẫn, cấu hình, logging, SQLite.
- `core/ocr.py`, `models.py`: PaddleOCR CPU, tile/dedup/grouping, danh mục model, tải riêng, xác minh hash, cài đặt an toàn.
- `providers/base.py`, `online.py`, `offline.py`: MyMemory/LibreTranslate miễn phí, Argos/CTranslate2 cục bộ, đường dịch pivot có kiểm soát.
- `core/imaging.py`, `pipeline.py`: mask glyph/inpaint, Unicode renderer, atomic export, batch, checkpoint, retry, pause/resume/cancel.
- `ui/`: PySide6, bảng tiến trình thực, preview hai ảnh, quản lý model và settings.
- `scripts/`, `tests/`, các batch script và PyInstaller spec.

## Theo giai đoạn yêu cầu
| Giai đoạn | Kết quả |
| --- | --- |
| 1: môi trường/GUI/config/log | Mã nguồn và .venv đã tạo; GUI chưa mở được do thiếu PySide6 |
| 2: OCR | Adapter/model manager đã viết; test adapter đạt, OCR thật chưa có dependencies/model |
| 3: Online | Provider/cache/retry đã viết, mock đạt; MyMemory live thất bại kết nối |
| 4: Offline | Argos tokenizer/CT2/pivot/model manager đã viết; model thật chưa tải/cài, chưa suy luận |
| 5: inpaint/render/preview | CV/export chạy thật và xem artifact; Qt preview chưa chạy |
| 6: batch/progress/điều khiển | Core workflow fixture đạt; GUI/QThread integration chờ Qt |
| 7: QA/build | Lượt đầu 44 ca đạt; lượt tiếp tục 49 ca đạt. GUI/E2E chưa PASS, build được gate chặn; chưa nghiệm thu |

## Kết quả giai đoạn kiểm thử
- 44 ca unit/CV/workflow khả dụng PASS bằng unittest; tests tương thích pytest.
- 9 method integration và 1 class GUI SKIP do thiếu model/thư viện hoặc Online opt-in.
- Lỗi alpha khi vẽ chữ đã sửa và regression test đạt.
- Cache theo hash font/mask/model/cấu hình, ảnh gốc giữ nguyên, lỗi dịch không xuất ảnh tẩy trắng đã được test.
- `compileall` đạt ở mã nguồn hiện tại.
- Đã xuất/xem artifact OpenCV/Pillow 960×520 trong `output/cv-validation`; alpha giữ nguyên. Đây là fixture CV, không phải OCR/MT thật.
- MyMemory live probe đã thực hiện và thất bại sau 3 lần kết nối; log `logs/online-probe.json`.
- PyInstaller đã được gọi thật nhưng không có module; **không có EXE**.
- README tiếng Việt, TEST_REPORT, THIRD_PARTY_NOTICES và config mẫu đã có.

## Trở ngại môi trường
- Pip có PIP_NO_INDEX và proxy không kết nối được (WinError 10061). Đã thử cài dependencies nhưng thất bại.
- Không có PySide6, PaddleOCR/PaddlePaddle, Argos/CTranslate2, SentencePiece, pytest, PyInstaller trong môi trường dự án.
- Model OCR, model dịch Anh → Việt và font Noto tải thất bại vì mạng. Không có model AI được cài.
- GUI thật, OCR thật, dịch Offline thật, EXE **chưa được xác minh**. MyMemory/LibreTranslate trong unit tests là mock.
- requirements là bộ phiên bản khóa đề xuất dựa trên metadata, chưa được kiểm chứng cài đủ.
- Danh mục model Hàn → Anh dùng bản 1.1 theo index chính thức; chưa tải hoặc kiểm thử tương thích binary.
- Font Noto chưa tải được; test CV dùng font Windows đã cài, không sao chép font Windows vào dự án.

## Giới hạn còn tồn tại
- Chưa đánh giá chất lượng OCR/dịch trên ảnh thật, chữ dọc, giản/phồn thể và truyện tranh.
- Gom dòng/thứ tự đọc là heuristic; chưa có segmentation bong bóng; chưa có chỉnh bản dịch/polygon thủ công trong preview.
- Metadata ảnh không được bảo toàn đầy đủ; ảnh động không hỗ trợ; giới hạn 65 triệu pixel.
- Marker bảo vệ thuật ngữ/số có thể bị MT biến đổi và sẽ khiến ảnh báo lỗi an toàn.
- Inpainting trên nền phức tạp cần kiểm tra thủ công; không hứa khôi phục hoàn hảo.
- Hook đóng gói Paddle/CT2/Qt cần chạy kiểm chứng thực tế.

## Công việc tiếp theo
1. Áp dụng quyền mạng ở host/profile (đã được người dùng đồng ý), mở lại phiên tại D:\TransTool; chạy script chẩn đoán trước. Khi có mạng hợp lệ hoặc wheelhouse đầy đủ: `install.bat`; chạy resolver/pip check/import audit.
2. Ưu tiên Trung giản thể theo yêu cầu mới: tải riêng det-ch/rec-zh/cls, sau đó en→vi và zh→en; xác minh đủ hai chặng. Không tải cả 12 model một lúc, không tải lại model hợp lệ.
3. Chạy pytest và integration thật; ghi kết quả rõ ràng, không đổi SKIP thành PASS.
4. Kiểm tra GUI/nút điều khiển, ảnh dài, RAM, câu dịch/tên riêng trên tập ảnh thật.
5. Chạy smoke_gui.py và validate_e2e.py bằng cùng `.venv`; chỉ khi gate đạt mới build onedir. Mở EXE thật để smoke-test, giữ model bên ngoài; cập nhật trạng thái.
Đọc TEST_REPORT và source manifest trước khi tiếp tục, không tạo lại dự án.

## Lệnh
- Người dùng cuối: `install.bat`, sau đó `run.bat`; build bằng `build.bat`.
- Kiểm tra hiện tại: `python scripts\run_tests.py` (unittest, không thay tên thành pytest).
- Sau khi cài: `.venv\Scripts\python.exe -m pytest -q`.
