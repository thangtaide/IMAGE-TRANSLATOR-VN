# Tích hợp Qoder CLI — 13/11/2026

Đã triển khai provider thứ ba trong Settings, Batch nhiều ảnh, Whole Chapter tự
chia batch, receipt/checkpoint/resume và EXE Windows. Không đánh giá chất lượng
dịch hoặc benchmark. Không thay đổi OCR/mask/inpainting/renderer/layout.

## CLI và catalog thực tế

- Executable trực tiếp: `%USERPROFILE%/.qoder/bin/qodercli/qodercli.exe`.
- `qoder` là wrapper `%USERPROFILE%/.qoder/entry/qoder.cmd`; ứng dụng gọi `.exe`
  trực tiếp với `shell=False`. Cả hai tên đã chạy version/help/list-models.
- Version: **1.1.89**. `status -o json`: `logged_in=true`, browser/local auth.
  Không đọc token, cookie hoặc auth file; không đưa dữ liệu tài khoản vào báo cáo.
- `--list-models`: **Ultimate**, **Sonus**. CLI help cho phép dùng model name;
  ứng dụng giữ chính xác hai tên này làm giá trị `--model`.
- Catalog không có năm model tiết kiệm được yêu cầu ưu tiên và không có effort
  capability. Không tự đoán slug/effort. `Ultimate` đã live; `Sonus` chỉ catalog.
- Metadata modelUsage của lượt Ultimate xác nhận tier `ultimate`. Không khẳng
  định backend cụ thể, context limit hoặc effort nội bộ khi CLI không cung cấp.

## Thay đổi source

- `providers/qoder.py`: detection, preflight không sinh nội dung, catalog,
  batch contract, parser hai lớp, receipt và phân loại lỗi.
- `providers/qoder_process.py`: transport bị giới hạn, UTF-8 stdin, timeout,
  cancel, drain hai pipe và reuse Windows Job Object helper hiện có.
- `core/types.py`, `config/settings.example.json`: thêm trường cấu hình Qoder.
- `core/pipeline.py`, `core/multipage.py`: chọn Qoder và reuse orchestration.
- `core/resume.py`, `providers/agy_models.py`: snapshot và nhãn Qoder; loại
  trường Qoder không hoạt động khỏi identity/recipe của provider khác.
- `core/whole_chapter.py`: adapter Qoder trong transaction/manifest hiện có,
  chia batch tự động và commit tiến độ sau batch.
- `core/provider_preflight.py`: kiểm tra cấu hình cục bộ, không network startup.
- `ui/settings_dialog.py`, `ui/main_window.py`, `ui/whole_chapter.py`,
  `ui/comic_sources.py`, `ui/provider_notice.py`, `ui/qoder_retry.py`: Settings,
  trạng thái lỗi và xác nhận một lần cho batch chưa rõ kết quả.
- `scripts/validate_qoder.py`, `main.py`: smoke có thể chạy từ source/EXE,
  fixture riêng và ledger giới hạn live. CLI không là dependency được bundle.
- `tests/test_qoder.py`, `tests/fixtures/qoder_models_1_1_89.txt`: contract/
  lifecycle/resume tests và catalog đã quan sát.
- Tài liệu: `QODER_CLI_SETUP.md`, báo cáo này, `PROJECT_STATUS.md`,
  `AI_MODEL_SETTINGS.md`, `EXPORT_AND_BUILD.md`.

`providers/base.py`, provider AGY/Groq, process helper AGY, OCR và imaging không
cần sửa. `ImageTranslatorVN.spec` và `build.bat` giữ nguyên; static import đủ
để PyInstaller đóng gói module Qoder.

## Batching và validation

Mặc định tối đa **10 ảnh / 60 vùng / 3.000 ký tự OCR**. Đồng thời giới hạn
prompt 24.000 byte UTF-8 và output cap 4.096 token; ước lượng bảo thủ output
(gồm ID/JSON) tối đa 3.072 đơn vị. Xem công thức và giới hạn trong setup guide.
Không coi contextWindow/maxOutputTokens=0 trong metadata là vô hạn.

Mỗi batch một subprocess, một JSON dịch, không vòng lặp invocation theo ảnh.
JSON envelope thật 1.1.89 được kiểm tra type/result/success/is_error/num_turns/
stop_reason/permission_denials/modelUsage; chỉ `result` được parse thành JSON
dịch. Không trích bằng regex, không dùng stderr làm dịch. Kiểm tra batch_id,
đúng tập ảnh/vùng thuộc ảnh, kiểu, thiếu/thừa/trùng ID và duplicate JSON key.
Mapping theo ID; response đảo thứ tự vẫn phân phối chính xác.

Whole Chapter Qoder reuse manifest/hash/progress/renderer, tự pack nhiều batch;
test offline 11 ảnh chia 10+1, không đổi hành vi Whole AGY/Groq. Một vùng không
vừa ngân sách bị chặn, không cắt nội dung giữa vùng.

## Checkpoint và an toàn

Receipt done chỉ ghi sau validation toàn response, trước commit cache từng
vùng. Resume có thể replay một phần response dù tập pending đã thay đổi.
Test quota batch thứ hai giữ 10 vùng của batch đầu; resume chỉ gửi phần còn
thiếu. Thử timeout tạo unknown; resume bị chặn trước subprocess. Xác nhận
gửi lại mặc định Không, chỉ cho phép một lần, timeout tiếp lại thành unknown.

Start dùng preference hiện tại; Continue pin provider/model/effort/contract của
run. Binary identity đổi không được tự gửi lại batch pending. Test Groq xác
nhận các trường Qoder không đổi job fingerprint/cache. Không migrate database
hoặc sửa/xóa checkpoint cũ.

Kiểm kê baseline 316 file: 315 file giữ nguyên SHA256, không thiếu file nào;
chỉ `config/settings.example.json` là source mẫu sửa có chủ đích. Bao gồm config
riêng, cache database/journal và EXE cũ trong tập được theo dõi. Ba ảnh test thật
giữ nguyên hash; mọi QA chạy trong thư mục mới. Không có job production được
khởi chạy. Chưa kiểm chứng toàn bộ ảnh/output cũ bằng hash.

## Kết quả test

- **36 test Qoder offline PASS**: detection/missing CLI, catalog/effort,
  preflight không prompt, Settings Save/Cancel/reopen, ba ảnh một invocation,
  parser/ID, split, local subprocess timeout/cancel, quota, unknown/retry,
  recipe/fingerprint, binary pin, Batch và Whole resume.
- Bộ cuối **206 PASS, 1 deselected**, hai warning dependency; không phải full
  repository suite. Gồm Qoder, Groq, AI settings/model sync, multipage/resume,
  Whole Chapter, run cache, preflight UI, source tabs và AGY timeout/finish.
- Lần mở rộng trước đó: 127 PASS, 1 FAIL do test cũ
  `CompactUITests.test_confirmation_does_not_automatically_resume` kỳ vọng
  `start(pending)` trong khi baseline HEAD đã gọi `start(pending,resume=True)`.
  AST phương thức resume HEAD/current giống nhau. Không sửa test/hành vi cũ;
  loại rõ test này khỏi bộ cuối, không báo full regression sạch.
- Source GUI và EXE GUI: Save/Cancel/reopen, Qoder/model, popup dark theme,
  nhãn chính và dialog Whole PASS ở DPI hiện tại 100%; không test nhiều DPI.
- Source/EXE fixture: Batch ba ảnh và Whole ba ảnh, render và resume PASS;
  fixture không gọi model, không đại diện live Whole Chapter.

Hai lỗi QA đã sửa: fixture Whole ban đầu dùng workspace không đúng prefix
stage3g; test authorization ban đầu đọc receipt bằng encoding mặc định và sau
đó bị đặt nhầm phần assertion. Không dùng kết quả thất bại làm bằng chứng PASS.

## Qoder thật: 2/3 invocation đã dùng

1. Python Windows headless, JSON tối thiểu: exit 0; envelope thật có
   `type=result`, `subtype=success`, `is_error=false`, `num_turns=1`,
   `stop_reason=end_turn`, `result` chứa JSON, stderr rỗng.
2. Ba ảnh chữ Trung trung tính: OCR thật → **một invocation / ba ảnh / ba vùng**
   → validation → inpaint/render/lưu qua pipeline hiện có: 3 completed,
   0 failed/fallback. Resume: 3 skipped, không có invocation mới. Ảnh gốc
   không đổi; workspace subprocess nằm ngoài repository.

Invocation thứ ba không dùng. Không dịch chương thật, không test Sonus live,
không gọi AGY/Groq thật. Live chạy từ source; EXE dùng fixture cho smoke.
Các bổ sung cuối về pin binary, explicit cwd và environment được kiểm tra
offline/đóng gói; không phát sinh lượt dịch live thứ ba.

## Build và EXE

Build bằng **build.bat** hiện có, pip check và PyInstaller thành công.
Không dùng `--validated` và không giả tạo gate full-suite/E2E. Kiểm tra/test
nêu trên chạy riêng, có evidence thực tế.

EXE cuối:

```text
dist/ImageTranslatorVN-20261113T162335164318Z/ImageTranslatorVN-20261113T162335164318Z.exe
```

Gói onedir phải đi cùng `_internal`; máy chạy cần Qoder CLI/đăng nhập riêng.
Module Qoder/process/retry/QA có trong archive; bytecode bảy module quan trọng
khớp source cuối. Không có qodercli.exe/qoder.exe trong thư mục bundle.
Settings/private auth không nằm trong datas của spec. EXE GUI và fixture
Batch/Whole/resume PASS, frozen=true. Bản build trung gian mới của nhiệm vụ
ở `dist/ImageTranslatorVN/` được giữ lại; EXE có trước nhiệm vụ không bị sửa.

## Evidence và vấn đề còn lại

Evidence runtime: `output/qoder-integration-20261113T160329Z/`:
baseline.json, cli-help.txt, catalog.txt, headless-stdout.json,
live-ledger.json, source-live/report.json, source-live/invocations.json,
regression.xml, source/exe GUI screenshots, exe-fixture/report.json,
packaging.json, baseline-test-mismatch.json, data-preservation.json và
git-handoff.json. Build log: `logs/build-ImageTranslatorVN-20261113T162335164318Z.log`.

Còn giới hạn: catalog chỉ hai model, effort/context capability chưa được CLI
cung cấp; Sonus chưa live, Whole chỉ fixture, chưa thử máy sạch/DPI khác, có
một test UI baseline sai kỳ vọng như trên. Active hooks/plugins làm preflight
BLOCKED_BY_ISOLATION, không tự sửa global settings. Điều khoản/Credits/quota
đã nêu trong setup guide; thành công kỹ thuật không xác nhận billing hoặc
phạm vi cho phép của Terms 3.2.10.

## Git & Fork Handoff

PROJECT_ROOT suy ra từ workspace: `./IMAGE-TRANSLATOR-VN-main`, branch `main`.
Baseline sạch, không staged/untracked/unmerged. Chỉ chuẩn bị review working
tree; index/HEAD/branch giữ nguyên. `.gitignore` không đổi; output/dist/logs
được ignore, source/test/docs/config mẫu hiển thị để review. `git diff --check`
đạt. Không có file tracked runtime bị tự untrack.

Nên review/stage source/test/docs/config mẫu của nhiệm vụ trong Fork. Không
stage runtime evidence, settings riêng, cache/DB, ảnh, build/dist, CLI hoặc
credential. Review kỹ transport/isolation, receipt/retry và nhánh Whole mới.
Kết quả status cuối, danh sách file và kiểm tra secret theo mẫu ở
`git-handoff.json`; scan không thay cho review của người dùng.

Commit message gợi ý (chưa thực hiện):
`feat: integrate Qoder CLI OCR batch and resumable chapter translation`

NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT.
