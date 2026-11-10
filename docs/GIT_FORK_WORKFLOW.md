# Git & Fork — quy trình bàn giao sau mỗi Stage

Áp dụng từ yêu cầu bổ sung Stage 3A ngày 08/11/2026 cho mọi Stage sau.
Codex chuẩn bị working tree để review; **người dùng tự stage/commit bằng Fork**.
Quy trình này không triển khai tính năng Stage 3A và không biến commit thành
điều kiện nghiệm thu kỹ thuật. Stage 3 chất lượng vẫn là RESEARCH_ONLY.

## Trước khi sửa

Đọc AGENTS.md, PROJECT_STATUS.md và .gitignore. Lưu kết quả chỉ đọc:

```powershell
git status --short
git branch --show-current
git rev-parse --show-toplevel
git ls-files
git diff --cached --name-status
git ls-files --unmerged
```

Ghi baseline thay đổi có sẵn, file staged/untracked, root, branch và HEAD trong
evidence runtime dưới logs/. Không sửa index, branch hoặc lịch sử. Nếu chưa có
repository, ghi GIT_REPOSITORY_NOT_INITIALIZED và hướng dẫn mở/tạo repo bằng
Fork; không git init. Nếu có xung đột hoặc ownership chưa rõ, báo riêng và dừng
các thao tác Git có nguy cơ; không hoàn nguyên thay đổi người dùng.

## Sau triển khai, kiểm thử và cập nhật tài liệu

Kiểm tra bảo toàn dữ liệu rồi chạy chỉ đọc:

```powershell
git status --short
git diff --check
git diff --stat
git diff -- .gitignore
git ls-files --others --exclude-standard
git ls-files --cached --ignored --exclude-standard
```

Dùng git check-ignore -v trên đường dẫn runtime thật. Dùng thêm
`git check-ignore --no-index -v -- <path>` để kiểm tra quy tắc cho source đã
track hoặc đường dẫn manifest/fixture giả định, không tạo file thử trong model.
Exit 1 có thể chỉ nghĩa là không bị ignore; có negation thì đọc quy tắc cuối.
Kiểm tra git diff --cached --name-status để chắc index không bị thay đổi.

- Không ignore rộng JSON/CSV/MD/PY/BAT/spec hoặc SQLite toàn repo. Runtime DB
  thuộc cache/output/logs/config; DB ở đường dẫn lạ phải hiển thị để review.
- Giữ manifest/checksum phân phối, loader, fixture nhỏ đã làm sạch, config mẫu.
  Manifest chứa đường dẫn cá nhân hoặc signed URL thật vẫn phải được rà soát;
  không suy rằng một file tên manifest luôn an toàn để commit.
- Rà file đang track dưới runtime và file lớn; ignore không untrack file cũ.
  Chỉ liệt kê/đề xuất xử lý trong Fork, không git rm --cached.
- Rà secret trong thay đổi dự kiến và untracked text, chỉ lưu tên file/dòng/loại,
  không lưu giá trị. Regex không chứng minh không có mọi loại secret; cần review
  diff. Nếu secret từng commit, ignore không xóa lịch sử: cần thu hồi/đổi credential
  và quyết định cách xử lý lịch sử riêng, không tự làm.
- Không chạy lại OCR/MT khi chỉ sửa tài liệu/ignore. Khi production thay đổi,
  chạy test/regression thích hợp và ghi kết quả thật của Stage đó.
- Nếu diff --check lỗi sẵn từ baseline, tách riêng; chỉ sửa lỗi do Stage gây ra.

## Git & Fork Handoff — kiểm tra bổ sung 08/11/2026

Root: `D:/TransTool`; branch: `main`. Repository hợp lệ; baseline không staged,
không unmerged entries. Baseline có **18 file tracked bị sửa + 61 untracked files**
(status mặc định gộp các thư mục). Đây là thay đổi có sẵn từ các Stage trước,
không tự nhận toàn bộ là thay đổi của lượt Git này.

Evidence: `logs/git-fork-handoff-20261108T013905Z/` gồm baseline.json,
review-scan.json, final.json và danh sách file review. logs/ được ignore.

Thay đổi riêng lượt này: `.gitignore`, `AGENTS.md`, `PROJECT_STATUS.md`,
phần bổ sung báo cáo Stage 3 và tài liệu này. Không sửa source/test ứng dụng.
Final status: **19 tracked modified + 62 untracked files**, index vẫn trống.
Danh sách đầy đủ cuối lượt ở final.json/review-files.txt; kiểm tra lại trong Fork
vì working tree có thể đổi sau báo cáo.

### .gitignore

- Giữ ignore venv/build/dist/cache/log/output/ảnh nguồn người dùng và settings riêng.
- Thêm root tmp/temp/downloads cho runtime.
- Bỏ ignore SQLite/DB toàn cục; DB runtime vẫn nằm trong các thư mục ignore.
  SQLite fixture và checksum/source metadata không bị che mất.
- Model weights và README đi kèm package tải về vẫn ignore; mở ngoại lệ cho cây
  thư mục, Python loader, README cấp OCR/translation, JSON manifest/checksum,
  .sha256 và .example.json. Hướng dẫn source khác ở models/README.md hoặc docs/.
- Giữ spec, BAT, config/settings.example.json, models/README.md, .env.example.

Đã kiểm tra ignore bằng đường dẫn runtime thật: .venv/pyvenv.cfg,
cache/online_comics/pipeline.sqlite3, logs/latest-git-handoff.json, output chương
274872, model.bin đã cài, và đủ bốn EXE cũ. Kiểm tra source/test/docs/qa,
spec/config mẫu và model manifest/checksum/loader giả định không bị che mất;
đường dẫn giả định chỉ kiểm tra rule, không phải file mới được tạo.

Không có runtime/model/EXE/database trong danh sách Git đang track; không có
file review nào lớn hơn 2 MiB hoặc binary build bị thêm ngoài ý muốn. Scan
text phát hiện query chữ ký ở hai fixture reader nhưng **toàn bộ là chuỗi 32
số 0 đã làm sạch**, và ba URL credential giả trong test từ chối URL. Không phát
hiện credential thật theo các mẫu đã kiểm tra. Không rà toàn bộ lịch sử Git;
đây không phải bảo đảm tuyệt đối thay cho review diff của người dùng.

### File nên commit sau khi review

- **Lượt quy trình này:** .gitignore, AGENTS.md, PROJECT_STATUS.md,
  docs/GIT_FORK_WORKFLOW.md, bổ sung docs/STAGE3_TRANSLATION_QUALITY_REPORT.md.
- **Stage 3 QA đã hoàn tất:** qa/*.py, tests/test_stage3_quality.py,
  docs/STAGE3_TRANSLATION_QUALITY_REPORT.md, README.md, M2M100_SETUP.md,
  TRANSLATION_QUALITY_REPORT.md, docs/USER_GUIDE.md và docs/TROUBLESHOOTING.md.
  Một số file tài liệu chứa nhiều Stage: kiểm tra hunk trước khi stage.
- **Thay đổi có sẵn cần review riêng:** core/, ui/, sources/, scripts/, main.py,
  tests/ khác, fixtures đã lọc, run_source.bat, các báo cáo build/install/E2E/URL,
  overrides/ocr_regions.json (override bằng chứng riêng chương 274872). Chúng là
  code/tài liệu có thể commit sau review; không tự coi là thay đổi Stage 3A mới.
- **Config mẫu/build:** config/settings.example.json, requirements*.txt, BAT,
  ImageTranslatorVN.spec đang track và không bị ignore. Không có sửa mới ở chúng
  trong lượt Git này; không cần stage lại khi không thay đổi.

### File không nên commit

Model/weights/tokenizer đã tải, .venv, cache ảnh/OCR/MT, logs/diagnostics và JSON
benchmark sinh ra, output ảnh, SQLite runtime/WAL/SHM, dist/build/EXE, backup,
ImgTest/DOM gốc, secret/cookie/session hoặc config riêng. Chúng được giữ trên đĩa.
QA source trong qa/ cần commit; QA kết quả sinh ra dưới logs/ không cần commit.

### File cần người dùng xem xét

Toàn bộ 18 modified/61 untracked files ở baseline là tiến trình chưa commit có
sẵn. Đặc biệt review fixtures HTML/provenance và overrides/ocr_regions.json trước
khi chia sẻ: không chứa chữ ký dùng được theo scan, nhưng có nội dung mẫu truyện
và hash/polygon gắn với nguồn kiểm thử. Không ignore hoặc xóa chúng để né review.
Không phát hiện tracked runtime cần untrack ở lần kiểm tra này.

### Kiểm chứng và commit message đề xuất

`git diff --check`: baseline PASS, cuối lượt PASS. HEAD, branch và nội dung index
giữ nguyên; không có stage, commit, push, tag hoặc thao tác Git phá hủy.
Đây là kiểm tra Git/ignore/tài liệu; không chạy lại pytest/unittest trong lượt này.
Kết quả Stage 3 lịch sử gần nhất: 261 PASS/10 SKIPPED mỗi runner, không gọi đó
là test chạy mới của lượt Git.

Commit riêng phần quy trình sau review: `docs(workflow): require safe Fork handoff after each stage`.
Stage 3 QA có thể dùng `stage(3): benchmark offline translation quality in QA`.
Không dùng message “add online provider” vì chưa triển khai tính năng đó.

### Thao tác trong Fork

1. Mở repository D:\TransTool, vào Local Changes.
2. Review từng file/hunk, phân biệt baseline cũ và bổ sung quy trình.
3. Tự stage source/test/docs/config cần thiết; không chọn tất cả khi còn file chưa rõ.
4. Đọc staged diff, tự nhập commit message và commit khi hài lòng.

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT**
