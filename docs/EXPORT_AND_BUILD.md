# Thư mục xuất ngoài project và build EXE — 10/11/2026

## Release GUI/cache mới nhất

Mở `dist/ImageTranslatorVN-20261110T152147487436Z/ImageTranslatorVN-20261110T152147487436Z.exe`.
Đã chạy source/EXE pipeline, cache/fresh/cancel/reopen/resume thật; full release
607 PASS/0 FAIL/12 SKIP. Ba request AGY thật hoàn tất (2 ban đầu + 1 được
cấp thêm). Gate GUI sớm được sửa trong QA, cache AGY replay/idle trên EXE cuối
PASS và không thêm request. Production 60 module + main không đổi; release
cuối cũng chạy Offline fresh/cancel/reopen/resume thật.
Giữ `_internal` và models ngoài gói. Chưa nghiệm thu máy sạch.

Build.bat vẫn dùng PyInstaller hiện có, nay workpath riêng theo tên build để
giữ intermediates cũ. Không cần clear SQLite khi dùng **Dịch lại từ đầu**.
[Hướng dẫn cache](CACHE_UI_GUIDE.md) · [Báo cáo](CACHE_UI_REPORT.md).
Các release và ghi chú bên dưới là lịch sử.

## Bản đã nghiệm thu mới nhất

Source/EXE AGY thật, ảnh 0002/0003/0004 và GUI Windows đã PASS; regression
582 PASS/0 FAIL/12 SKIP. Mở
`dist/ImageTranslatorVN-20261110T115939410209Z/ImageTranslatorVN-20261110T115939410209Z.exe`.
Giữ `_internal` và vị trí dưới project/dist; models ngoài EXE, font Windows.
Chưa nghiệm thu máy sạch. [Báo cáo, ảnh và giới hạn](READABILITY_ACCEPTANCE_20261110.md).
EXE cũ và output cũ không tự cập nhật; tạo lượt dịch mới với binary mới.
Các ghi chú chưa chạy test/Git archive phía dưới là lịch sử setup trước đó.

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
Mở PowerShell tại PROJECT_ROOT được xác định từ workspace hiện tại.

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
dist\ImageTranslatorVN\ImageTranslatorVN.exe
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
