# Báo cáo cài đặt Image Translator VN

## Setup máy mới — 10/11/2026, installation only

Gốc người dùng chọn: `D:\WebLocal\IMAGE-TRANSLATOR-VN-main`. Python 3.10.9 x64
all-users tại `C:\Program Files\Python310`; `.venv` mới dùng chính interpreter
này. Giữ Python 3.15 và không thay PATH toàn hệ thống. Pip install requirements
exit 0, inventory 18/18 pin khớp, setuptools 80.9.0, pip check không có dependency
hỏng. Năm model tối thiểu zh→en→vi đã tải và verify checksum thành công.

Theo yêu cầu cuối của người dùng, không chạy test, import audit, GUI, E2E hay
build EXE. Không ghi Ready True hoặc runtime PASS chỉ từ pip exit 0.
Font dùng Windows đã cài, không sao chép/phân phối font Windows, chưa tải Noto.
Chi tiết, lệnh chạy và evidence: [setup](docs/SETUP_20261110.md).

## Xác minh sau mở rộng nguồn ảnh — 07/11/2026

`scripts/check_installation.py`: **16/16 imports, 18/18 requirements, Ready True**,
evidence `logs/install-audit-20261107T041423Z`. Không cài lại/nâng dependency,
không đổi `.venv`, setuptools/CT2, DLL/PATH hoặc model. Module nguồn mới dùng
stdlib và Pillow/PySide6 hiện có. Năm model xác minh lại và integrity receipt
không đổi: `logs/online-comic-20261107/preservation-after.json`.

Chế độ URL còn bị giới hạn mạng sandbox/proxy và quyền tải chưa xác minh; đây
không phải lỗi thiếu dependency. Không bỏ proxy để thử tải. `run_source.bat`
mới mở mã Python hiện tại, giữ nguyên các BAT và EXE đã có.

## Audit cuối sau sửa trên ảnh thật — 10:26 UTC

Chạy lại `scripts/check_installation.py`: **16/16 imports PASS, 18/18 dependencies, Ready: True**. Evidence `logs/install-audit-20261106T102603Z/installation.json`. Verify lại det-ch/rec-zh/cls/zh_en/en_vi đều OK. Không cài/thay package, không nâng setuptools 80.9.0 hoặc CT2 4.6.0, không tải/xóa model.

Regression cuối unittest/pytest **76 PASS, 7 SKIPPED**. Chính EXE cuối đã mở GUI, xử lý OCR/dịch/E2E trên ảnh truyện thật và chạy các nút điều khiển; không gặp lỗi DLL trong các luồng đã kiểm chứng. Xem BUILD_REPORT và REAL_IMAGE_REPORT. M2M100 vẫn thiếu trọng số; adapter được đóng gói nhưng suy luận NOT TESTED, không ảnh hưởng Argos hiện có. Các phần phía dưới giữ lịch sử.

## Audit sau mất điện — 06/11/2026, 09:46 UTC

Đã chạy lại bằng `.venv`: **Imports 16/16 PASS, dependencies 18/18, Ready: True**. Evidence `logs/install-audit-20261106T094611Z/installation.json`. Python 3.10.9 x64, setuptools 80.9.0 và CTranslate2 4.6.0 giữ nguyên; không cài/gỡ/nâng package. 5 model OCR/Argos xác minh lại OK. GUI Windows smoke, E2E Offline của EXE cũ và Python đều chạy thật PASS kỹ thuật.

Mở rộng provider M2M100 chỉ dùng CT2/SentencePiece đã có. **Không có trọng số M2M100, Transformers/huggingface_hub cũng chưa cài**. Không yêu cầu hai package đó để mở app hoặc chạy Argos. Converter là công cụ tùy chọn, chưa được chạy. Kiểm tra tài nguyên tại `logs/recovery-audit-20261106T094804Z/report.json`; kiểm tra mạng `logs/network-diagnostics-20261106T094805Z/diagnostics.json` vẫn ghi sandbox tắt mạng/proxy 10061. Không đổi proxy/PATH/DLL hoặc thử bỏ giới hạn.

Regression sau sửa: unittest và pytest **73 PASS, 7 SKIPPED** (M2M100 real inference thêm một skip). Xem RECOVERY_REPORT và M2M100_SETUP cho phạm vi thật/mock và bước còn thiếu. Các mục tiếp theo giữ lịch sử cài đặt trước.

## Xác minh bản đóng gói sau sửa runtime — 08:55 UTC

`build.bat` đã qua gate, pip check và pytest (63 PASS, 6 SKIPPED), PyInstaller onedir hoàn tất. **Chính EXE** đã chạy GUI smoke Windows-platform PASS (`logs/gui-smoke-20261106T085536Z-fb0e84/`) và E2E OCR → Offline MT → xuất ảnh PASS kỹ thuật (`output/e2e-validation/20261106T085546Z-e14cdf/`). Không gặp thiếu DLL/thư viện ở các luồng này; không cài/thay đổi dependency khi đóng gói. Giữ nguyên setuptools 80.9.0, CT2 4.6.0 và năm model hợp lệ. Xem BUILD_REPORT để biết hash binary và các mục NOT TESTED.

Chất lượng dịch còn lỗi ngữ nghĩa; không dùng việc cài đặt/build thành công để suy ra chất lượng. Trạng thái cũ ở các phần lịch sử phía dưới không thay thế kết quả mới này.

## Cập nhật runtime ngày 06/11/2026 (sau 08:31 UTC)

**Imports vẫn PASS 16/16, pin 18/18, Ready: True**; audit mới `logs/install-audit-20261106T084539Z/installation.json`. Không cài lại hoặc thay đổi package/model nào ở lượt này; setuptools giữ 80.9.0 và CT2 giữ 4.6.0.

### WinError 127 đã xác định chính xác và sửa

`ctranslate2` import `converters` → `specs/model_spec.py` dòng 18 → import `torch`. Nếu Paddle đã nạp native runtime trước, Windows giữ `paddle/libs/libiomp5md.dll`. Đối chiếu PE cho thấy `torch/lib/torch_cpu.dll` cần `__kmpc_masked` và `__kmpc_end_masked`, nhưng DLL OpenMP đã nạp từ Paddle không xuất hai symbol đó. Vì thế lỗi xuất hiện khi Torch nạp shm.dll/dependency, dù file shm.dll vẫn tồn tại và hoạt động trong thứ tự đúng.

Bằng chứng giữ nguyên trong `output/runtime-validation/20261106T084730Z-ca8bd9/report.json`: tên DLL chung, đường dẫn module đang nạp, missing exports, traceback/WinError 127. Negative control cố ý bỏ qua adapter vẫn **REPRODUCED**; không gắn nhãn đó là OCR/MT PASS.

Giải pháp nhỏ: `core/runtime.prepare_inference_runtime()` nạp CT2/Torch trước Paddle dưới RLock, dùng lại module đã nạp. Gọi ở entry point/package UI trước Qt, worker, adapter OCR và adapter Offline. Các đường CLI/direct adapter được bảo vệ, không chỉ main.py. Model chỉ nạp khi cần, vẫn dùng CPU và tái sử dụng.

Fresh QThread regression còn phát hiện PySide6 được import trước Torch có thể làm Torch import lỗi `Plain typing.Self is not valid as type argument` trên bộ phiên bản hiện tại. Khởi tạo native runtime trước Qt ở entry/package boundary đã giải quyết, không sửa typing hay site-packages.

Không tháo DLL khỏi tiến trình, không sửa PATH/DLL Windows, không copy DLL giữa package, không bật `KMP_DUPLICATE_LIB_OK` để che lỗi. Nếu một caller ngoài ứng dụng import Paddle trước guard, hệ thống báo cần tiến trình sạch. Chưa cần tách inference thành subprocess vì tất cả đường guarded đã vượt các bài kiểm tra runtime thật.

### Kiểm tra hiện tại

- Unittest: **63 PASS, 6 SKIPPED**, không fail/error; `logs/runtime-final-unittest-20261106/`.
- Pytest: **63 PASS, 6 SKIPPED**, không fail; `logs/runtime-final-pytest.log`, `runtime-final-pytest.xml`.
- Regression có 7 ca fresh-process; model thật, model reuse, QThread restart và cancellation đều kiểm chứng. Các unit mock cũ vẫn được phân biệt với integration thật.
- GUI offscreen/native Windows platform: PASS. Đăng ký Segoe UI đã cài qua Qt, glyph tiếng Việt đạt và screenshot đã xem không còn ô vuông. Không sao chép font Windows; Noto vẫn chưa được tải/bundled.
- E2E chuẩn: **PASS kỹ thuật**, đủ artifact tại `output/e2e-validation/20261106T084804Z-4a9386/`.
- Chất lượng model pivot còn sai một câu mục tiêu; xem `TRANSLATION_QUALITY_REPORT.md`. Không báo nghiệm thu ngữ nghĩa chỉ vì inference chạy được.

Các mục tiếp theo lưu lịch sử sửa import và lỗi trước khi có runtime guard.

## Cập nhật mới nhất: sửa import CTranslate2 — 06/11/2026, sau 08:14 UTC

**Mục tiêu import đã đạt: Imports PASS 16/16; Required packages satisfied 18/18; Ready: True.** Đây là trạng thái import trong các tiến trình con độc lập, không phải kết luận toàn bộ pipeline đã hoạt động.

### Input và nguyên nhân gốc

Đã đọc `logs/install-audit-20261106T080950Z/installation.json` do người dùng cung cấp. Import duy nhất FAIL là **`ctranslate2` 4.6.0**. 15 import khác PASS và toàn bộ 18 pin trong requirements đã đúng phiên bản.

Đoạn cuối traceback thật:

```text
File "D:\TransTool\.venv\lib\site-packages\ctranslate2\__init__.py", line 8, in <module>
    import pkg_resources
ModuleNotFoundError: No module named 'pkg_resources'
```

`.venv` đang dùng **setuptools 84.2.1**. CTranslate2 4.6.0 trên Windows gọi `pkg_resources` để tìm thư mục DLL; setuptools đã bỏ module này từ 82.0.0. Nguồn: [setuptools official documentation](https://github.com/pypa/setuptools/blob/main/docs/deprecated/pkg_resources.rst), [CTranslate2 4.6.0 source](https://github.com/OpenNMT/CTranslate2/blob/v4.6.0/python/ctranslate2/__init__.py).

Phân loại: **lỗi tương thích phụ thuộc Python CTranslate2 ↔ setuptools quá mới**, làm thiếu module `pkg_resources`. Traceback ban đầu dừng trước bước nạp DLL; không có bằng chứng lỗi proxy, model hay DLL bị thiếu là nguyên nhân của import FAIL này. `pip check` không phát hiện được vì metadata không mô tả đầy đủ giới hạn tương thích runtime.

### Thay đổi duy nhất trong môi trường

- Hạ **setuptools 84.2.1 → 80.9.0**, có `pkg_resources`.
- Giữ nguyên CTranslate2 4.6.0, Paddle, Torch và tất cả package khác. So sánh toàn bộ inventory trước/sau xác nhận chỉ setuptools thay đổi.
- Dùng wheel có sẵn trong pip cache, kiểm tra archive/metadata và SHA-256 khớp [PyPI chính thức](https://pypi.org/pypi/setuptools/80.9.0/json):
  `062d34222ad13e0cc312a4c02d73f059e86a4acbfbdea8f8f76b28c99f306922`.
- Cài bằng `--no-index --no-deps`, không cần mạng, không resolver toàn bộ requirements.
- Không cài lại requirements, không nâng cấp hàng loạt, không tạo lại `.venv`, không sửa source runtime trong `core/providers/ui/main.py`, không đổi `requirements.txt`, không sửa cấu hình proxy và không tải/xóa model.

Lệnh sửa đã thực hiện:

```bat
python scripts\repair_ctranslate2_import.py --apply --expected-sha256 062d34222ad13e0cc312a4c02d73f059e86a4acbfbdea8f8f76b28c99f306922
```

Lệnh pip thực tế do script gọi:

```bat
.venv\Scripts\python.exe -m pip install --no-index --no-deps cache\compat-wheels\setuptools-80.9.0-py3-none-any.whl --disable-pip-version-check
```

`pip check`: PASS. Import CTranslate2 sau sửa: exit 0, version 4.6.0. Vẫn có deprecation warning `pkg_resources`; warning không phải import FAIL. Giữ setuptools tương thích khi tiếp tục dùng CTranslate2 4.6.0; không tự nâng lại setuptools trong môi trường này.

Bằng chứng sửa: `logs/ctranslate2-repair-20261106T081432Z-3ca7ce/report.json`, `install.log`, `traceback-before.txt`. Script mới chỉ chẩn đoán nếu không có `--apply`; trước khi cài phải cung cấp SHA-256 đúng.

### Audit chạy lại

```bat
.venv\Scripts\python.exe scripts\check_installation.py
```

Kết quả thực tế:

```text
Imports PASS: 16 / 16
Required packages satisfied: 18 / 18
Ready: True
```

Bằng chứng: **`logs/install-audit-20261106T081441Z/installation.json`**. Báo cáo đầu vào 15/16 được giữ nguyên.

### GUI sau khi Ready: True

Đã chạy entry point thật bằng `scripts/smoke_gui.py`, Qt offscreen, không mock widget/picker:

- **PASS**: cửa sổ chính, chọn Online/Offline/Auto Fallback, trạng thái nút khi nghỉ, picker Qt chọn thư mục thật, quét/hiện hai file ảnh, mở Model Manager, mở Preview, lưu screenshot, heartbeat event loop (24 nhịp), process exit 0.
- **Chưa xác minh desktop hiển thị thực tế**, native Windows picker, progress/nút trong job OCR/MT thật.
- Đã mở xem screenshot: **glyph hiển thị dạng ô vuông trong offscreen**, nên functional smoke PASS không đồng nghĩa font/chữ tiếng Việt hiển thị đúng. Chưa sửa font hoặc giao diện trong lượt sửa import này.

Bằng chứng: `logs/gui-smoke-20261106T081510Z-263830/report.json`, `window.png`.

### OCR và model hiện có

Đã kiểm tra SHA-256/cấu trúc model bằng lệnh verify, tất cả các mục sau trả **OK**:

`det-ch`, `rec-zh`, `cls`, `translate-en_vi-1_9`, `translate-zh_en-1_9`.

Đã chạy PaddleOCR thật trên **fixture Trung tổng hợp 1200×430**, không nhập tay output OCR:

| OCR thật | Confidence | Bounding box (x0,y0,x1,y1) |
| --- | --- | --- |
| 你好，世界！ | 0.993094 | (134,137,473,197) |
| 欢迎使用图像翻译。 | 0.982723 | (134,238,657,296) |

Bằng chứng: `output/e2e-validation/20261106T081543Z-83d0a4/ocr.json`, `source.png`, `report.json`. Đây là suy luận model thật trên fixture, **chưa phải đánh giá ảnh truyện/ảnh chụp thực tế của người dùng**.

Các model còn thiếu, không tự tải trong lượt này:

| Chức năng | Model cần bổ sung |
| --- | --- |
| OCR Anh | `det-en`, `rec-en` |
| OCR Hàn | `det-ml`, `rec-ko` |
| OCR Trung phồn thể | `rec-zt` (đã có det-ch/cls) |
| Dịch Hàn → Anh → Việt | `translate-ko_en-1_1` (đã có en→vi) |
| Dịch phồn thể → Anh → Việt | `translate-zt_en-1_9` (đã có en→vi) |

Trung giản thể và hai chặng zh→en→vi đã có đủ model, không tải lại.

### Khả năng dịch Offline và lỗi runtime riêng vừa phát hiện

Đã chạy ba tiến trình kiểm tra thật, không mock và không đổi package:

| Trường hợp | Kết quả |
| --- | --- |
| Dịch Offline độc lập en→vi | PASS suy luận: `Hello world` → `Xin chào.`; khoảng 1.661 s cho gọi provider gồm tải model/kiểm tra hash/suy luận |
| PaddleOCR trước, CTranslate2 sau | **FAIL WinError 127** tại `torch\lib\shm.dll` hoặc phụ thuộc của nó |
| CTranslate2 trước, PaddleOCR sau, rồi dịch output OCR | PASS suy luận zh→en→vi: `Chào cả thế giới!`, `Không có gì.`; khoảng 0.527 s cho gọi provider |

**Chất lượng:** câu thứ hai dịch `欢迎使用图像翻译。` thành `Không có gì.` sai nghĩa. PASS suy luận chỉ xác nhận engine/model chạy, không chứng minh chất lượng dịch đạt yêu cầu.

Chuỗi lỗi runtime mới:

```text
providers/offline.py -> import ctranslate2
ctranslate2/specs/model_spec.py -> import torch
torch/__init__.py -> _load_dll_libraries()
OSError: [WinError 127] ... torch\lib\shm.dll ...
```

Kết quả đối chiếu xác nhận vấn đề **phụ thuộc thứ tự nạp runtime DLL trong cùng tiến trình**: cùng package/model nhưng đổi thứ tự nạp thì chạy được. Chưa xác định chính xác symbol/DLL phụ thuộc gây thiếu procedure; không khẳng định shm.dll bị mất. Audit import độc lập vẫn PASS 16/16.

Bằng chứng: `logs/engine-interop-20261106T081715Z-e403eb/report.json` và từng log case. Luồng E2E chuẩn hiện **FAIL tại translation**, các bước mask/inpaint/render/export SKIPPED; `output/e2e-validation/20261106T081543Z-83d0a4/failure.txt` lưu traceback.

Đã giữ phạm vi sửa ở import `pkg_resources`: không đổi Torch, không thay kiến trúc xử lý, không thêm workaround nạp thư viện vào source runtime. Bước cần xử lý tiếp là khởi tạo runtime theo thứ tự đã kiểm chứng (CTranslate2 trước Paddle), rồi chạy regression/E2E lại; chưa triển khai thay đổi đó trong lượt này. **Không build EXE** vì workflow chuẩn còn FAIL.

---

## Lịch sử: chẩn đoán mạng và cài đặt lượt trước

**Kết luận: chẩn đoán PASS; khắc phục quyền mạng chưa thực hiện được; cài dependencies SKIPPED.** Không sửa proxy Windows, WinHTTP, VPN, firewall, registry, pip.ini hoặc cấu hình bảo mật Codex. Dự án cũ được giữ nguyên tại D:\TransTool.

## Nguyên nhân WinError 10061 đã xác định

| Kiểm tra | Kết quả thực tế |
| --- | --- |
| Python | PASS: 3.10.9 x64 |
| `.venv` | Đã tồn tại, được tái sử dụng; không tạo lại |
| pip trong `.venv` | PASS: 22.3.1 |
| HTTP_PROXY | `http://127.0.0.1:9` |
| HTTPS_PROXY | `http://127.0.0.1:9` |
| ALL_PROXY | `http://127.0.0.1:9` |
| NO_PROXY | `localhost,127.0.0.1,::1` |
| PIP_NO_INDEX | `1`: pip không truy cập package index |
| CODEX_SANDBOX_NETWORK_DISABLED | `1`: phiên thực thi đang tắt mạng |
| Proxy endpoint 127.0.0.1:9 | FAIL: `ConnectionRefusedError`, `winerror=10061` |
| Proxy Windows HKCU | `ProxyEnable=0`, không có ProxyServer/AutoConfigURL |
| Proxy Windows HKLM | Không thấy giá trị proxy tương ứng |
| Proxy WinHTTP | PASS kiểm tra: Direct access (no proxy server) |
| pip config files | Không có pip.ini user/site/global; không có PIP_PROXY |
| DNS | PASS cho PyPI, files.pythonhosted.org, raw.githubusercontent.com, PaddleOCR CDN, Argos, MyMemory |
| HTTPS PyPI theo cấu hình hiện hành | FAIL: đi tới proxy bị từ chối 10061 |
| HTTPS trực tiếp bỏ proxy | SKIPPED: đã xác định sandbox tắt mạng; không bỏ proxy quản lý để vượt giới hạn |

Lỗi hiện tại phát sinh ở **proxy được đưa vào môi trường thực thi Codex**, kèm cấu hình tắt mạng và tắt pip index. Không có bằng chứng proxy hệ thống Windows gây lỗi. DNS hoạt động không chứng minh HTTPS hoạt động; không kết luận Internet của toàn bộ máy tính bị mất.

Bằng chứng chỉ đọc:

- `logs/network-diagnostics-20261106T065426Z/diagnostics.json`: chẩn đoán đầu tiên.
- `logs/network-diagnostics-20261106T065831Z/diagnostics.json`: kiểm tra lại sau khi người dùng chọn cấp môi trường có mạng. Các cờ và proxy vẫn giữ nguyên.

Đã yêu cầu thực thi `python scripts\diagnose_network.py` với quyền cao hơn một lần. Hệ thống duyệt tự động từ chối ngay vì `sandbox_approval=false`. Không chạy được lệnh ở môi trường có mạng. Người dùng đã đồng ý cấp mạng; sự đồng ý đó **chưa thay đổi cấu hình quyền đang áp dụng**. Không liên tục chạy lại pip/model downloader với cùng điều kiện lỗi.

## Quyền mạng cần được áp dụng ở đâu

Tài liệu OpenAI xác định quyền filesystem/network do sandbox profile áp dụng cho lệnh và tiến trình con; approval policy là cơ chế riêng. Với Windows, khi dự kiến có mạng nhưng lệnh vẫn không truy cập được, tài liệu hướng dẫn kiểm tra quyền và khởi động lại Codex. Xem [Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox).

Đơn vị/người vận hành host cần cấp một profile có outbound HTTPS được phép cho phiên tại `D:\TransTool`, sau đó mở lại/khởi động lại phiên để quyền có hiệu lực. Nếu tổ chức quản lý profile, cần quản trị viên áp dụng; chương trình dịch ảnh không có quyền sửa giới hạn này. Không cần bật full access hay tắt Windows firewall.

Đối với host dùng cấu hình Codex CLI legacy `workspace-write`, trường cấu hình chính thức là:

```toml
[sandbox_workspace_write]
network_access = true
```

Đây là ví dụ dành cho người/host có quyền quản lý cấu hình, **không được tự động ghi vào cấu hình trong phiên này**; profile quản lý có thể áp dụng ràng buộc khác. Xem [Configuration Reference](https://learn.chatgpt.com/docs/config-file/config-reference). Không xóa HTTP_PROXY/HTTPS_PROXY/ALL_PROXY/PIP_NO_INDEX của sandbox để thay thế việc cấp quyền.

Các nguồn cần được môi trường cho phép truy cập, tùy thao tác:

- Packages: `pypi.org`, `files.pythonhosted.org`.
- Font/index: `raw.githubusercontent.com`.
- OCR: `paddleocr.bj.bcebos.com`.
- Offline translation: `argos-net.com`.
- Online tùy chọn: `api.mymemory.translated.net`; LibreTranslate theo endpoint miễn phí/tự host được người dùng cấu hình.

## Kết quả kiểm tra thư viện

Đã thực sự chạy `python scripts\check_installation.py`, sử dụng **`.venv\Scripts\python.exe`** để import từng module trong tiến trình con riêng, timeout giới hạn. Không lấy thư viện Python hệ thống để kết luận `.venv` đã cài được.

| Thành phần | Import trong `.venv` |
| --- | --- |
| PySide6.QtWidgets | FAIL: missing PySide6 |
| paddle | FAIL: missing paddle |
| paddleocr | FAIL: missing paddleocr |
| cv2 | FAIL: missing cv2 |
| PIL.Image | FAIL: missing PIL |
| numpy | FAIL: missing numpy |
| scipy / skimage | FAIL: missing modules |
| google.protobuf | FAIL: missing google |
| argostranslate.tokenizer | FAIL: missing argostranslate |
| ctranslate2 | FAIL: missing ctranslate2 |
| sentencepiece | FAIL: missing sentencepiece |
| requests | FAIL: missing requests |
| pytest / pytestqt | FAIL: missing modules |
| PyInstaller | FAIL: missing PyInstaller |

Tổng: **0/16 import checks đạt; 0/18 package pin được đáp ứng trong `.venv`**. `.venv` có pip/setuptools. `pip check` trả exit 0 do môi trường hầu như trống; kết quả đó không phải bằng chứng ứng dụng sẵn sàng.

Bằng chứng: `logs/install-audit-20261106T065807Z/installation.json`.

Đã đọc và phân tích bộ pin `requirements.txt`; chưa thay đổi phiên bản. Có ba distribution OpenCV cùng cung cấp `cv2`; chúng đang được pin cùng bản 4.10.0.84 để giữ NumPy <2 cho PaddleOCR 2.x, nhưng chưa có resolver/import run để chứng minh chúng đồng thời tương thích. Phụ thuộc chuyển tiếp và DLL vẫn **NOT TESTED**. Không tự nâng phiên bản hoặc cài các wheel khác pin chỉ để có kết quả PASS.

Python hệ thống đã có NumPy/Pillow/OpenCV/requests và được dùng riêng để kiểm thử core/CV và tạo fixture; không thay đổi chúng. Đây không phải môi trường chạy đầy đủ của sản phẩm.

## Lệnh tiếp tục khi host có quyền mạng hợp lệ

Chạy trong một tiến trình/terminal **được phép truy cập nguồn chính thức**. Không thực thi phần cài nếu chẩn đoán vẫn báo sandbox tắt mạng:

```bat
cd /d D:\TransTool
python scripts\diagnose_network.py
.venv\Scripts\python.exe -m pip install --dry-run -r requirements.txt --report logs\dependency-resolution.json --cache-dir cache\pip
.venv\Scripts\python.exe -m pip install -r requirements.txt --cache-dir cache\pip
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe scripts\check_installation.py
.venv\Scripts\python.exe scripts\download_assets.py
.venv\Scripts\python.exe scripts\smoke_gui.py
```

Pip mặc định giữ package đã đáp ứng yêu cầu; không dùng force-reinstall/upgrade. Nếu resolver lỗi, xử lý xung đột theo báo cáo trước khi cài. Nếu dùng wheelhouse đầy đủ đã được xác minh cho Windows/Python tương ứng, có thể cài hoàn toàn cục bộ:

```bat
.venv\Scripts\python.exe -m pip install --no-index --find-links wheelhouse -r requirements.txt
```

Không có wheelhouse/model cục bộ phù hợp được cung cấp trong lượt này. `install.bat` vẫn có sẵn cho người dùng cuối, tôn trọng cấu hình mạng của môi trường.

## Thứ tự model tối thiểu sau khi cài đủ

Không tải toàn bộ 12 model. Bắt đầu với Trung giản thể và đường dịch Trung → Anh → Việt của danh mục hiện có, kiểm tra đủ hai chặng trước khi suy luận:

```bat
.venv\Scripts\python.exe scripts\manage_models.py download det-ch rec-zh cls
.venv\Scripts\python.exe scripts\manage_models.py download translate-en_vi-1_9
.venv\Scripts\python.exe scripts\manage_models.py download translate-zh_en-1_9
.venv\Scripts\python.exe scripts\manage_models.py verify det-ch rec-zh cls translate-en_vi-1_9 translate-zh_en-1_9
.venv\Scripts\python.exe scripts\validate_e2e.py
.venv\Scripts\python.exe -m pytest -q
```

Danh mục chính thức và giấy phép đã ghi trong README/THIRD_PARTY_NOTICES. Model manager không tải lại model hợp lệ. Trong lượt này **không tải/cài/xóa model nào** do chưa có kết nối hợp lệ; không có số liệu dung lượng/RAM/thời gian suy luận thật để báo Offline PASS.
