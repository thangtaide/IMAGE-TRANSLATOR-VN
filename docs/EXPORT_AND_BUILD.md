# Thư mục xuất ngoài project và build EXE — 10/11/2026

## Thư mục xuất

Batch thư mục ảnh nay cho chọn đích ngoài project hoặc khác ổ đĩa, ví dụ
`D:\MangaTranslated` hoặc `E:\TruyenDaDich`. Thay đổi tại
`core/pipeline.py`: bỏ yêu cầu output nằm dưới ROOT, giữ chặn thư mục gốc/cha
của ứng dụng. Các kiểm tra nguồn, vùng mã/model/cache và containment của từng
file giữ nguyên. Output mới vẫn có tên kèm job ID; không sửa ảnh gốc.

Ảnh đơn/chương truyện đã cho phép đích ngoài ở sources/service.py. Workspace
Whole Chapter thử nghiệm (journal/OCR/receipt/rendered) vẫn dưới
`output/stage3g-*`; bản sửa này xử lý giới hạn batch, không chuyển workspace.

Đã sửa assertion cũ trong tests/test_core.py để kiểm tra ROOT/ROOT.parent bị
chặn thay cho một thư mục ngoài hợp lệ. Kiểm tra AST của hai file thành công;
**không chạy test hoặc ứng dụng** theo yêu cầu người dùng. Chưa xác minh runtime.

## Build bằng PowerShell

Môi trường `.venv` và PyInstaller đã cài. Đóng ứng dụng trước khi build.
Trong PowerShell, chuyển tới project:

```powershell
cd D:\WebLocal\IMAGE-TRANSLATOR-VN-main
```

Build mặc định chỉ kiểm tra dependency bằng pip check và đóng gói PyInstaller,
không đòi evidence GUI/E2E hoặc chạy test:

```powershell
.\build.bat
```

Nếu muốn build kèm kiểm chứng, tạo bằng chứng GUI/E2E thực rồi dùng tùy chọn:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_gui.py --platform windows
.\.venv\Scripts\python.exe scripts\validate_e2e.py
.\build.bat --validated
```

Chế độ `--validated` giữ gate cũ: hai bước đầu phải PASS thật, đúng fingerprint
và interpreter; sau đó chạy pip check, pytest và PyInstaller. Không giả báo cáo
để đạt gate. Packaging thành công không tự chứng minh EXE/GUI/OCR/dịch hoạt động.

EXE đầu tiên, nếu build thành công:

```text
D:\WebLocal\IMAGE-TRANSLATOR-VN-main\dist\ImageTranslatorVN\ImageTranslatorVN.exe
```

Nếu bản mặc định đã tồn tại, build.bat tạo tên timestamp:
`dist\ImageTranslatorVN-<timestamp>\ImageTranslatorVN-<timestamp>.exe`;
đọc đường dẫn cuối trong console và `logs/build-*.log`.

Giữ toàn bộ thư mục onedir, gồm `_internal`. Để chạy trong project, giữ đúng
cấu trúc `project/dist/<tên-build>/<tên-build>.exe`: ROOT của binary lấy theo
cấu trúc này. Models nằm ngoài EXE tại `project/models`; config/cache/output
cũng thuộc project. Chỉ chép EXE hoặc một mình thư mục build sang máy khác
không mang theo model. Cần mang nguyên cấu trúc project/runtime tương ứng;
chưa nghiệm thu portable trên máy sạch. Không đưa `.venv` sang máy khác để dùng.

Sau khi sửa source lần nữa, chế độ `--validated` cần evidence GUI/E2E mới.
Ứng dụng source mới nhất mở bằng `run_source.bat`; EXE cũ không tự cập nhật.

## Git & Fork Handoff

Root `D:\WebLocal\IMAGE-TRANSLATOR-VN-main`; branch/HEAD/index không có:
GIT_REPOSITORY_NOT_INITIALIZED. Baseline là archive không `.git`; không có
staged hoặc conflict Git để xử lý. Không tự init; người dùng review/tạo repo
trong Fork. Git diff/check/stat/check-ignore không khả dụng, không ghi PASS.

Thay đổi feature: core/pipeline.py, tests/test_core.py (assertion cũ), README.md,
PROJECT_STATUS.md, docs/USER_GUIDE.md và docs/EXPORT_AND_BUILD.md. Thay đổi
setup trước đó: AGENTS.md, AI_SETUP_HANDOFF.md, INSTALL_REPORT.md,
docs/SETUP_20261110.md. `.gitignore` không đổi. Source/model đã cài giữ nguyên
ngoại trừ đúng hai file Python nêu trên; không dùng ảnh người dùng.

Nên review/commit source/test/docs; không commit venv/model/cache/log/output
hoặc config bootstrap riêng. Không có secret mới trong patch. Evidence setup
tại logs/setup-*. Commit message đề xuất:
`fix: allow batch exports outside the project directory`.
NO_COMMIT, NO_PUSH, NO_TAG, NO_DESTRUCTIVE_GIT.
