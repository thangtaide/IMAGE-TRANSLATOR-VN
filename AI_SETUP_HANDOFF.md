# IMAGE TRANSLATOR VN — hướng dẫn cho AI setup và tiếp tục trên máy mới

Cập nhật: **07/11/2026**. Đây là tài liệu bàn giao mã nguồn đã có, **không phải yêu cầu tạo lại dự án**. Khi người dùng yêu cầu setup theo file này, AI phải trực tiếp kiểm tra môi trường, thực hiện các bước khả thi, chạy xác minh và báo kết quả thật. Không chỉ trả kế hoạch hoặc bắt người dùng sao chép từng file mã nguồn.

## 1. Đọc trước và xác định đúng trạng thái

Đọc theo thứ tự:

1. [AGENTS.md](AGENTS.md) và file này.
2. [PROJECT_STATUS.md](PROJECT_STATUS.md), ưu tiên mốc thời gian mới nhất về ứng dụng.
3. [INSTALL_REPORT.md](INSTALL_REPORT.md), [E2E_REPORT.md](E2E_REPORT.md), [BUILD_REPORT.md](BUILD_REPORT.md).
4. [REAL_IMAGE_REPORT.md](REAL_IMAGE_REPORT.md), [TRANSLATION_QUALITY_REPORT.md](TRANSLATION_QUALITY_REPORT.md), [M2M100_SETUP.md](M2M100_SETUP.md).
5. `requirements.txt`, `install.bat`, `run.bat`, `build.bat` và mã nguồn liên quan trước khi sửa.

Các báo cáo chứa nhiều đoạn **lịch sử**. Không coi các câu “chưa có Git”, “thiếu dependencies”, “chưa build” trong đoạn cũ là trạng thái của checkout hiện tại. Ngày viết tài liệu này, máy gốc có commit `bd7016f` (`first init`), local `main` và `origin/main` cùng trỏ commit đó. Trên máy mới phải đọc `git status`, `git log`, `git remote` thật; không hardcode commit hoặc suy ra trạng thái server từ báo cáo cũ.

Mốc gần nhất trên **máy gốc**, không phải kết quả mặc định của máy mới:

| Hạng mục | Đã ghi nhận |
| --- | --- |
| Imports / requirements | 16/16 PASS, 18/18 pin, Ready True |
| Unittest / pytest | 76 PASS, 7 SKIPPED; tổng 83 ca unittest |
| Model | 3 OCR Trung giản thể + 2 model dịch zh→en→vi hợp lệ |
| GUI / EXE | GUI, điều khiển worker và E2E của EXE đã chạy thật |
| Corpus thực tế | 61 ảnh xử lý, 0 lỗi sau sửa bảo toàn số; 75 vùng chữ dịch thật |
| Chất lượng | Chưa nghiệm thu: sai nghĩa/tên riêng, OCR và mask còn hạn chế |
| M2M100 | Có adapter; chưa có trọng số, chưa suy luận hoặc so sánh thật |

**Tất cả kết quả trên phải xác minh lại trên máy mới.** Đọc báo cáo không thay thế việc chạy lệnh.

## 2. Thư mục, dữ liệu và giới hạn công việc

- Gốc dự án theo yêu cầu hiện tại: **`D:\TransTool`**, Windows 10/11 x64, CPU-first. Nếu máy không có ổ D hoặc không có quyền truy cập, báo rõ và hỏi về đường dẫn thay thế trước khi sửa cấu hình đường dẫn; không giả vờ đã lưu vào D.
- Nếu chưa clone và thư mục đích chưa tồn tại/còn trống, có thể clone repository dưới đây. Nếu đã có dữ liệu, kiểm tra trước; không clone đè, không `reset --hard`, không `git clean` hoặc xóa file để làm sạch.

```bat
git clone https://github.com/thangtaide/IMAGE-TRANSLATOR-VN.git D:\TransTool
cd /d D:\TransTool
git status --short
git log -1 --oneline
git remote -v
```

Các lệnh `bat` trong tài liệu dùng cú pháp **CMD**. Từ PowerShell có thể mở CMD tại thư mục dự án; không ghép nguyên cú pháp CMD vào PowerShell rồi giả định chạy tương đương. Không cần quyền Administrator để chạy ứng dụng trong thư mục đã có quyền ghi.

Git có mã nguồn `core/`, `providers/`, `ui/`, `tests/`, `scripts/`, tài liệu, cấu hình mẫu và script build. Git **không kèm** `.venv`, trọng số model, `dist`, `build`, `cache`, `logs`, `output`, `ImgTest`, backup hoặc cấu hình cá nhân. Các đường dẫn evidence trong báo cáo có thể chỉ tồn tại ở máy gốc. Đây không tự động là lỗi pull thiếu file.

Không sao chép `.venv` từ máy khác để dùng lại; không coi `run_updated.bat` là launcher chạy được ngay sau clone: nó trỏ tới một bản EXE timestamp của máy gốc, không nằm trong Git. Trên máy mới chạy source bằng `run.bat` hoặc build bản riêng.

Luôn bảo vệ ảnh gốc, model hợp lệ và công việc chưa hoàn tất. Không dùng API trả phí. Offline không gửi ảnh/văn bản lên mạng, không tự tải model trong job hoặc tự chuyển Online. Không nâng cấp hàng loạt dependencies để thử sửa một lỗi.

## 3. Kiểm tra môi trường trước khi cài

Kiểm tra CPU/RAM/dung lượng trống, Python Launcher, Python x64, Git, quyền ghi thư mục và `.venv` hiện có. Máy gốc dùng **Python 3.10.9 x64**; ưu tiên Python 3.10 x64. Phiên bản khác phải kiểm chứng riêng, không mặc định Python mới nhất tương thích.

```bat
cd /d D:\TransTool
py -0p
py -3.10 --version
git status --short
```

Nếu `.venv` đã có: kiểm tra `.venv\Scripts\python.exe --version` và chạy audit bên dưới; chỉ sửa phần thiếu/hỏng. Không tạo lại môi trường đang hoạt động. Nếu chưa có `.venv`, mới tạo:

```bat
py -3.10 -m venv .venv
```

Nếu thiếu Python Launcher, dùng đường dẫn Python 3.10 x64 đã xác minh để tạo venv. Việc cài Python hoặc runtime Windows phải dùng nguồn chính thức. Không tải DLL rời từ website không rõ nguồn hoặc chép DLL giữa các framework.

Trước cài/tải, kiểm tra Internet và proxy. Khi đã có Python, script chỉ đọc dưới đây ghi chẩn đoán vào `logs`:

```bat
.venv\Scripts\python.exe scripts\diagnose_network.py
```

`WinError 10061`, proxy `127.0.0.1:9` hoặc `CODEX_SANDBOX_NETWORK_DISABLED=1` từng xuất phát từ sandbox máy gốc. **Không giả định máy mới cũng bị lỗi đó.** Nếu hiện tại bị chặn, ghi nguyên nhân, yêu cầu môi trường thực thi có mạng hợp lệ hoặc wheelhouse/model cục bộ. Không tự tắt proxy hệ thống/VPN/firewall, bỏ proxy quản lý hoặc lặp lại lệnh tải đã biết sẽ thất bại.

## 4. Cài dependencies có kiểm soát

Các phiên bản chính đã kiểm thử nằm trong `requirements.txt`: PaddlePaddle CPU 2.6.2, PaddleOCR 2.9.1, CTranslate2 4.6.0, PySide6 6.8.3, NumPy 1.26.4. **Giữ setuptools 80.9.0**: CT2 4.6.0 còn dùng `pkg_resources`, setuptools mới hơn từng làm import FAIL.

**Lưu ý bootstrap:** `requirements.txt` chưa pin setuptools và `install.bat` chưa tự áp dụng pin này. Không coi chỉ chạy `install.bat` hoặc pip exit 0 là setup đã xong. Với venv mới và kết nối được phép, dùng constraint bổ sung tại `config` (không commit file constraint cục bộ này):

```bat
cd /d D:\TransTool
if not exist config mkdir config
if not exist cache mkdir cache
echo setuptools==80.9.0>config\bootstrap-constraints.txt
.venv\Scripts\python.exe -m pip install setuptools==80.9.0 --cache-dir cache\pip
.venv\Scripts\python.exe -m pip install -c config\bootstrap-constraints.txt -r requirements.txt --cache-dir cache\pip
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe scripts\check_installation.py
```

`bootstrap-constraints.txt` là file setup riêng; nếu đã tồn tại phải đọc trước, không ghi đè cấu hình khác. Với môi trường đã đủ và hoạt động, **không chạy lại toàn bộ khối cài đặt**. Dùng `.venv\Scripts\python.exe -m pip ...`, không dùng nhầm pip/Python hệ thống. Không tự nâng pip/setuptools/CT2 hoặc dùng `--no-deps` để che xung đột resolver.

`requirements.txt` chưa phải lockfile toàn bộ dependencies chuyển tiếp; cài từ đầu trên máy sạch vẫn cần xác minh resolver/import/runtime. Nó đang có ba distribution OpenCV cùng cung cấp `cv2`; không tự gỡ hoặc đổi chúng chỉ vì tên giống nhau. Nếu có lỗi, đọc traceback và inventory trước, sửa phạm vi hẹp và chạy lại audit.

Nếu cài không có mạng nhưng có `wheelhouse` đáng tin cậy, thay hai lệnh pip install bằng các lệnh tương ứng có `--no-index --find-links wheelhouse`; giữ constraint. Wheelhouse phải đủ cả setuptools 80.9.0 và dependencies chuyển tiếp đúng Windows x64/Python, không chỉ 18 package chính.

Mục tiêu audit: **16/16 imports, 18/18 pin, pip check PASS, Ready True**. Script lưu JSON/traceback vào `logs/install-audit-*`. Nếu FAIL, không tiếp tục build. **Ready True chưa chứng minh đã có model, chạy Offline được hoặc dịch đúng nghĩa.**

## 5. Cài bộ model tối thiểu cho Trung giản thể → Việt

Ưu tiên sao chép **model đã hợp lệ** từ máy gốc nếu người dùng cung cấp đường dẫn. Sao chép nguyên thư mục, giữ `integrity.json` và toàn bộ file được receipt liệt kê; không tạo receipt giả để vượt kiểm tra. Nếu model đã có, verify trước, không tải lại.

| ID | Vị trí dưới `D:\TransTool` | Vai trò |
| --- | --- | --- |
| `det-ch` | `models\ocr\det-ch` | Phát hiện chữ Trung |
| `rec-zh` | `models\ocr\rec-zh` | Nhận diện Trung giản thể |
| `cls` | `models\ocr\cls` | Phân loại hướng 0/180 độ |
| `translate-zh_en-1_9` | `models\translation\translate-zh_en-1_9` | Trung → Anh |
| `translate-en_vi-1_9` | `models\translation\translate-en_vi-1_9` | Anh → Việt |

```bat
.venv\Scripts\python.exe scripts\manage_models.py list
.venv\Scripts\python.exe scripts\manage_models.py verify det-ch rec-zh cls translate-zh_en-1_9 translate-en_vi-1_9
```

Nếu còn thiếu, thao tác tải là bước setup riêng, dùng danh mục chính thức trong `core/models.py`, khi kết nối/quyền tải hợp lệ. Chỉ tải các ID thiếu, ví dụ:

```bat
.venv\Scripts\python.exe scripts\manage_models.py download det-ch rec-zh cls translate-zh_en-1_9 translate-en_vi-1_9
```

Sau tải, chạy lại verify. Không gọi download từ worker dịch Offline. Không dùng `verify` không có ID rồi hiểu lỗi các model tùy chọn chưa cài là bộ tối thiểu bị hỏng.

Các ngôn ngữ khác cần model bổ sung: Anh `det-en/rec-en`; Hàn `det-ml/rec-ko` và model ko→en; phồn thể `rec-zt` và model zt→en. Chế độ auto OCR cần nhiều bộ model; chưa cài đủ thì chọn **Trung giản thể**, không chọn auto rồi tuyên bố hỗ trợ tất cả.

Font: app có thể đọc Arial/Segoe UI đã cài trên Windows để render tiếng Việt; không sao chép font Windows vào Git/bản phân phối. Có thể chủ động tải Noto bằng `scripts/download_assets.py` nếu mạng hợp lệ, giữ giấy phép. Fixture Trung mặc định của E2E còn cần font Trung cài tại Windows; nếu thiếu, cung cấp ảnh Trung thật qua `--source`, không dựng ảnh ô vuông rồi coi là OCR test hợp lệ.

## 6. Giữ các sửa lỗi runtime đã có

- **WinError 127:** Paddle từng nạp `libiomp5md.dll` thiếu symbol Torch cần; CT2 import gián tiếp Torch rồi báo lỗi ở `torch/lib/shm.dll`. Không phải cứ cài lại Torch là sửa được.
- `core/runtime.py` phải chuẩn bị CTranslate2/Torch **trước Paddle và trước Qt**. Guard hiện có ở entry point, package UI, worker, OCR và provider. Đọc các đường import trước khi sửa; thêm một import vào cuối `main.py` không đủ.
- Nạp Qt trước Torch từng gây `Plain typing.Self is not valid as type argument`. Giữ thứ tự bootstrap và dùng tiến trình Python mới để xác minh; không để import cache che lỗi.
- Không sửa site-packages, chép/thay DLL hệ thống, thay PATH toàn hệ thống hoặc dùng `KMP_DUPLICATE_LIB_OK` để giấu lỗi.
- Số trong câu được giữ nguyên dạng, kiểm tra lại sau dịch. Vùng chỉ có số/ký hiệu giữ nguyên pixel; không dịch/vẽ lại false positive trên nét vẽ. Không bỏ các kiểm tra bảo toàn số hoặc thuật ngữ để ép batch PASS.

## 7. Kiểm thử và mở ứng dụng trên máy mới

Sau khi audit và 5 model hợp lệ, chạy bằng **cùng `.venv`**. Đổi hậu tố evidence trong ví dụ thành mốc thời gian mới nếu thư mục/file đã có, không ghi đè kết quả cũ.

```bat
.venv\Scripts\python.exe scripts\run_tests.py --evidence-dir logs\setup-new-machine-unittest
.venv\Scripts\python.exe -m pytest -q --junitxml=logs\setup-new-machine-pytest.xml
.venv\Scripts\python.exe scripts\smoke_gui.py --platform windows
.venv\Scripts\python.exe scripts\validate_e2e.py
.venv\Scripts\python.exe scripts\validate_gui_workflow.py
```

Chạy E2E trước `validate_gui_workflow.py` để tạo fixture nguồn mà bài điều khiển cần. Test GUI có fixture hỏng cố ý; đọc `report.json` để phân biệt lỗi dự kiến với lỗi app. QA có thể lưu đường dẫn thư mục thử vào cấu hình; trước khi dùng app chọn lại thư mục nguồn/xuất của người dùng.

Nếu không có desktop session, chạy GUI smoke `--platform offscreen`, ghi rõ chưa xác minh desktop/native picker và kiểm tra glyph/screenshot. Không coi offscreen PASS là đã quan sát giao diện vật lý. Không mở nhiều app/job cùng dùng cấu hình/cache một cách không kiểm soát.

Với ảnh thật do người dùng cung cấp:

```bat
.venv\Scripts\python.exe scripts\validate_e2e.py --source D:\TransTool\ImgTest\ten-anh.jpg
.venv\Scripts\python.exe scripts\translate_folder.py D:\TransTool\ImgTest D:\TransTool\output\new-machine-batch --language zh --mode Offline
```

Thay đường dẫn ví dụ bằng file/thư mục thực tế. Git không chứa `ImgTest` hoặc các runner audit từng được lưu dưới `output`; nếu cần corpus hãy hỏi đường dẫn hoặc xin bản sao được phép dùng. Không dựng kết quả OCR/bản dịch thủ công. Ghi hash/kích thước nguồn trước và sau, xem output thực tế; giữ mọi kết quả trong thư mục con phù hợp của `D:\TransTool`.

Không ép số lượng test đúng bằng 76/7: thiếu model sẽ làm skip khác; module test đã thay đổi có thể thêm ca. Đặc biệt negative control cố tái hiện thứ tự DLL cũ có thể khác trên máy khác: kiểm tra nguyên nhân, không thay DLL để cố gây lỗi hoặc sửa assertion để ép PASS. Các đường pipeline đã guard phải được kiểm chứng bằng inference thật.

Khi setup đạt, mở thử `.venv\Scripts\python.exe main.py` để nhìn lỗi console nếu có; người dùng bình thường dùng **`run.bat`**. Nếu có EXE cũ, `run.bat` ưu tiên nó; khi kiểm tra source cần gọi `main.py` trực tiếp.

## 8. Build EXE sau khi workflow thật đạt

```bat
.venv\Scripts\python.exe scripts\check_build_ready.py
build.bat
```

Gate yêu cầu GUI/E2E PASS thật, đúng source fingerprint và interpreter. Sau đổi source, chạy lại GUI smoke/E2E rồi mới build; không sửa JSON, fingerprint hoặc gate để vượt điều kiện. Model nằm ngoài EXE.

Trên máy mới chưa có bản build: thường ở `dist\ImageTranslatorVN\ImageTranslatorVN.exe`. Nếu bản mặc định đã tồn tại, script tạo tên timestamp để bảo vệ bản cũ. Đọc log và tên đích thực tế, giữ nguyên toàn bộ thư mục onedir và độ sâu thư mục (đường dẫn ROOT của EXE phụ thuộc cấu trúc này).

Sau build phải mở **chính binary**, đọc model/font, chọn folder và xuất ảnh; có thể dùng:

```bat
.venv\Scripts\python.exe scripts\smoke_gui.py --platform windows --exe dist\ImageTranslatorVN\ImageTranslatorVN.exe
dist\ImageTranslatorVN\ImageTranslatorVN.exe --validate-e2e
dist\ImageTranslatorVN\ImageTranslatorVN.exe --validate-gui-workflow
```

Thay bằng đường dẫn timestamp nếu build có tên khác. Build exit 0 không tự là EXE PASS. Chạy lại GUI/E2E bằng `.venv` trước lần build kế tiếp nếu latest E2E pointer đang trỏ bằng chứng EXE; gate yêu cầu đúng interpreter, không sửa pointer bằng tay.

## 9. Công việc phát triển còn lại và báo cáo bàn giao

Ưu tiên sau khi setup ổn định:

1. **Dịch Trung→Việt trực tiếp:** đọc `M2M100_SETUP.md`, giữ Argos đang chạy. Provider `providers/m2m100.py` chỉ là adapter cho model CT2 cục bộ, không có trọng số kèm Git. Xác minh nguồn/license, RAM/đĩa, mạng và dependency chuyển đổi trước khi tải lớn. Transformers là dependency chuyển đổi tùy chọn, không cần để chạy Argos/GUI. So sánh thật cùng 24 câu bằng `scripts/compare_translation.py`; thiếu model ghi SKIPPED, không hardcode output hoặc tự đổi provider mặc định.
2. **Mask:** giữ các regression trong `tests/test_adaptive_mask.py`. Fixture trắng từng giảm 600→0 pixel sót, nhưng truyện thật vẫn còn nét màu/dấu câu. Cần đánh giá trên nền phức tạp, bảo vệ viền bong bóng và nét nhân vật.
3. **OCR/corpus:** lập bản chép tham chiếu cho chữ nhỏ/chữ dọc/ảnh dài, phân biệt không có chữ với OCR bỏ sót; không lấy số ảnh xuất làm điểm accuracy.
4. **GUI/phân phối:** kiểm tra desktop thật, workflow đầy đủ và máy Windows sạch; chỉ đóng gói lại sau regression và E2E thật đạt.

Chỉ sửa phần liên quan, sao lưu/commit trước thay đổi lớn và không ghi đè EXE đã hoạt động. Tôn trọng `.gitignore`; không commit model, `.venv`, ảnh người dùng, cache, log, output, backup hoặc cấu hình riêng. Nếu không ghi được `.git`/không kết nối GitHub, báo đúng giới hạn, không đổi ACL/proxy để vượt chính sách.

Kết thúc phiên, cập nhật `PROJECT_STATUS.md` và báo cáo có liên quan; ghi rõ môi trường, lệnh đã chạy, evidence mới, **PASS thực tế / PASS mock / FAIL / SKIPPED / NOT TESTED**. Không tuyên bố fresh install, GUI, Offline hay EXE PASS nếu chưa thực sự chạy tương ứng trên máy đó. Không được tuyên bố chất lượng dịch đã nghiệm thu chỉ vì pipeline xuất đủ ảnh.

## Prompt bắt đầu dành cho người dùng trên máy mới

> Đọc AGENTS.md và AI_SETUP_HANDOFF.md trong checkout Image Translator VN này. Kiểm tra trạng thái Git/môi trường/model trước, rồi trực tiếp setup và chạy kiểm thử theo hướng dẫn. Giữ nguyên dự án hiện có và dữ liệu người dùng, không nâng cấp hàng loạt thư viện. Báo rõ kết quả thực tế và tiếp tục công việc còn dở từ PROJECT_STATUS.md; chỉ hỏi khi thiếu thông tin hoặc quyền môi trường cần thiết.

Tài liệu này được đối chiếu với mã nguồn hiện có ngày 07/11/2026; **không phải bằng chứng đã cài lại thành công trên một máy Windows sạch**.
