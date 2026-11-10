# Báo cáo build — lượt tiếp tục 06/11/2026

## Sửa nhận diện AGY cần đăng nhập — 10/11/2026, 09:15 UTC

Build mới thành công exit0, không chạy bộ test/GUI/dịch:
`dist/ImageTranslatorVN-20261110T091547241775Z/ImageTranslatorVN-20261110T091547241775Z.exe`,
19.969.570 byte; SHA256
`bbf770ece2f2b25ed480e20d62195e342cd3bb5b12752123aff656e35f1ede6a`.
Log `logs/build-ImageTranslatorVN-20261110T091547241775Z.log`.

Binary chứa sửa nhận diện authentication failed/timed out thành AUTH_REQUIRED
và hướng dẫn đăng nhập AGY thủ công. Không thay model/account/guard, không
tự gửi lại OCR. Đã xác định nguyên nhân từ đúng attempt được người dùng cho
phép giải mã trong RAM; không ghi bản rõ. Người dùng xác nhận quên đăng nhập
và sẽ thử lại. Chưa xác minh đăng nhập hoặc dịch lại thành công.
Evidence `logs/agy-auth-fix-20261110.json`; xem
[báo cáo](docs/AGY_AUTH_REQUIRED_20261110.md). Giữ nguyên binary trước.

## Máy hiện tại — build không test thành công, 10/11/2026

Root người dùng chọn: `D:\WebLocal\IMAGE-TRANSLATOR-VN-main`. Do yêu cầu
không chạy test, đã đổi `build.bat` mặc định thành pip check → PyInstaller,
không đòi GUI/E2E evidence. `build.bat --validated` giữ gate + pytest cũ;
scripts/check_build_ready.py và evidence không sửa/giả.

Thực chạy `cmd /c "build.bat <nul"`: exit 0; pip check không có dependency
hỏng, PyInstaller 6.12.0 hoàn tất onedir khoảng 84 giây. Binary:

`dist/ImageTranslatorVN/ImageTranslatorVN.exe`, 19.969.246 byte,
SHA256 `2338105c0564e15e548e8991287aefc3f29cf5d573b964336ae6273f0a802c2f`.

Evidence: `logs/build-ImageTranslatorVN.log`,
`logs/build-packaging-handoff-20261110.json`. `_internal` tồn tại. Chưa mở
chính binary, chưa chạy GUI/OCR/MT/E2E/unittest/pytest hoặc xác minh portable;
đây chỉ là **packaging thành công**, không phải runtime/quality PASS.
Build mới chứa sửa cho phép output batch ngoài project.

Mở bằng `dist\ImageTranslatorVN\ImageTranslatorVN.exe`; giữ toàn bộ thư mục
build cùng `_internal` và vị trí dưới project/dist. Models vẫn ở project/models.
Build lại khi bản mặc định tồn tại sẽ dùng tên timestamp để giữ binary cũ.
Xem [hướng dẫn hiện tại](docs/EXPORT_AND_BUILD.md).

Git & Fork Handoff: GIT_REPOSITORY_NOT_INITIALIZED; branch/HEAD/index không
có, baseline là các sửa source/docs của phiên setup trước. Thay đổi lượt này:
build.bat, README.md, PROJECT_STATUS.md, AI_SETUP_HANDOFF.md, BUILD_REPORT.md,
docs/EXPORT_AND_BUILD.md. `.gitignore` không đổi; runtime build/dist/log/venv/model
không nên commit, source/BAT/docs cần review. Git diff/check/stat/check-ignore
không khả dụng, không ghi PASS. Không thêm secret. Người dùng review trong Fork;
message đề xuất `build: make application validation optional for packaging`.
NO_COMMIT, NO_PUSH, NO_TAG, NO_DESTRUCTIVE_GIT.

## Adapter chương 281106 — 07/11/2026, lượt sau GUI tab

**Không build EXE mới cho thay đổi adapter này.** URL chương đã được hỗ trợ và
fallback HTML parser có fixture test, nhưng thiếu DOM Kuaikan thật để nghiệm thu
chapter/image parser; runtime mạng bị chặn. Không biến fixture PASS thành live
hoặc EXE website PASS. Giữ nguyên bản GUI tab đã kiểm thử ở mục dưới.
Mã nguồn mới có thể chạy bằng run_source.bat; cần captured DOM/kiểm tra live hợp lệ
trước khi phát hành binary adapter mới. Xem docs/KUAIKAN_CHAPTER_281106_ANALYSIS.md.

## Mới nhất — GUI ba tab, 07/11/2026

**Build onedir PASS và chính EXE đã kiểm thử thật.** Chạy build.bat không chỉnh
gate/BAT/spec; prerequisite GUI/E2E + pip check + pytest 116 PASS/7 SKIPPED, sau đó
PyInstaller thành công. Tên riêng bảo toàn các EXE trước.

`dist/ImageTranslatorVN-20261107T045417969128Z/ImageTranslatorVN-20261107T045417969128Z.exe`
(19,799,672 byte), SHA-256 `99baadc76bc0836781ac7db43674f1a4e7b93be3e5344d6d47c0b5357bbe517c`.
Log `logs/build-ImageTranslatorVN-20261107T045417969128Z.log`.

- Tab workflow Windows thật: PASS, frozen=True,
  `output/source-tabs-validation/20261107T045845Z-6f3417/report.json`.
- GUI smoke chính binary: PASS,
  `logs/gui-smoke-20261107T045856Z-bf49d7/report.json`.
- E2E Offline ảnh truyện thật chính binary: PASS,
  `output/e2e-validation/20261107T045858Z-42bf8c/report.json`.
- Model/font/DLL/import/export hoạt động trong các ca đã chạy. Source fingerprint
  `a7e5b4f70ca01a409f00ab02205a12bfd164c5ad498ba8ac781e47226ffa87ea`.
- URL error UI PASS; Kuaikan live chapters/downloader vẫn UNVERIFIED/UNKNOWN,
  không gọi là đầy đủ website SUPPORTED. Không dùng binary PASS để thay live test.

Xem `docs/GUI_URL_FLOW_REPORT.md`. Những mục SKIPPED bên dưới là lịch sử lượt trước.

## Tính năng nguồn ảnh/URL — 07/11/2026

**Build mới: SKIPPED; EXE có tính năng URL: NOT TESTED.** Source đã thêm adapter,
cache/chương và GUI; Kuaikan chưa có quyền tải tự động/danh sách chương/ảnh được
xác minh, nên chưa đủ nghiệm thu luồng URL để đóng gói bản phát hành tính năng này.
Không chạy PyInstaller rồi suy diễn tính năng URL đã PASS.

BAT/spec và ba EXE cũ giữ nguyên SHA-256; evidence
`logs/online-comic-20261107/preservation-after.json`. Không ghi đè hoặc xóa bản cũ.
`scripts/qa_common.py` bổ sung `sources/*.py` vào fingerprint, giữ nguyên các gate
GUI/E2E thật, cùng source và interpreter. Các import mới là module Python local
thông thường; mới rà soát tĩnh, chưa xác minh dependency collection bằng build.

Chạy mã mới bằng **`run_source.bat`**. Khi sau này build tên mới, phải kiểm thử
chính binary với Offline và trạng thái URL thực; source PASS không phải EXE PASS.

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
