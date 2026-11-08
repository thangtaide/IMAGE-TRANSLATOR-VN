# Stage 3B — AGY Gemini translation

Ngày: 08/11/2026 (+07). **STAGE_3B_COMPLETED_WITH_WARNINGS**.
Đã triển khai provider/UI, local/mock và một E2E AGY thật trên ảnh QA tổng hợp.
Lượt live đầu bị reject, lượt bổ sung được duyệt riêng đã PASS; giữ cả hai bằng chứng.
Không chuyển Stage3C, không build EXE, không thay Argos/MyMemory mặc định.

## 1. Baseline và bảo vệ

Đã đọc AGENTS, PROJECT_STATUS, README, USER_GUIDE, TROUBLESHOOTING, báo cáo Stage3A,
provider/base/online, types/pipeline/storage, notice/worker/source job/settings.
Git trước sửa sạch, main, không staged/xung đột. Artifact Stage3A xác nhận281PASS/
10SKIPPED/0FAIL mỗi runner. Manifest274872 có120output,119pipeline-complete,
fallback111 và needs_retry=[111]. Không gọi119 là119trang đều đã dịch chữ.

Hash595 runtime/resource trước sửa tại
`logs/stage3b-agy-20261108T023844Z/protected-before.json`; snapshot manifest riêng.
Không sửa .venv/model/config/BAT/spec/4EXE/cacheDB/output production hoặc retry111.

## 2. AGY đã cài và interface chính thức

- Binary: `C:\Users\ADMIN\AppData\Local\agy\bin\agy.exe`, **1.5.3**.
- Process PATH cũ chưa cóAGY; tìm qua PATH user đã lưu trong Registry. Không sửa
  PATH, không cần restart/cài/đăng nhập lại. `gemini.cmd` có riêng nhưng không dùng.
- `--version`/`--help` thực tế exit0; `--settings` ghi rõ session-only, never saved.
- `agy models` trả Gemini3.8Flash high/medium/low; chọn pin
  **gemini-3.8-flash-medium**, effortmedium, không fallback sang Claude/model khác.
  Nếu người dùng chọn slug có suffixlow/high, effort đi cùng suffix; cache có
  identity riêng. Medium mặc định giữ identity của lượt QA thành công.
  Đây là chọn model khả dụng, không kiểm tra lại quyền lợi Pro của người dùng.
- [Headless](https://antigravity.google/docs/cli/headless/) công bố stdin NDJSON,
  JSON/schema và cached login; [reference](https://antigravity.google/docs/cli/reference/)
  mô tả flags; [permissions](https://antigravity.google/docs/permissions/) và
  [schema settings](https://antigravity.google/schemas/v1/settings.json) mô tả deny.
  Nguồn chính thức được đọc08/11/2026. Không reverse-engineer endpoint hoặc scrape.

Không gọi Gemini API riêng, không key/billing/login/logout/update. Child env loại
API-key/ADC switches; session settings modelProvider rỗng, useG1Credits=false.
Không mua/dùng thêm credits tự động; request dự kiến dùng quota account đã đăng
nhập củaAGY. Không xác minh lại subscription hoặc tự thay account.

## 3. Provider, GUI và giới hạn an toàn

`providers/agy.py` implements TranslationProvider online với identity riêng:
CLIversion+binarySHA/model/promptversion/permissionpolicy/numericvalidatorversion.
Không tái sử dụng cache Argos/MyMemory. Mỗi batch subprocess riêng, không resume
conversation cũ hoặc lấy dữ liệu cuộc hội thoại người dùng. CWD là scratch/cache.

Prompt OCR chỉ qua stdin NDJSON, không interpolated vào shell/command line.
`shell=False`, CREATE_NO_WINDOW; schema ID/text exact, không mất/thêm/duplicate ID,
mapping trả về thứ tự input. Reject JSON duplicate keys/NaN/markdown/extra fields,
tool-use hoặc sốturn bất thường; không xem numeric pass là đúng nghĩa tuyệt đối.
Prompt coi OCR là dữ liệu không tin cậy; không làm theo chỉ dẫn chứa trong OCR.

Per-session settings strict+deny command/unsandboxed/read_file/write_file/
read_url/execute_url/MCP, disable slash/skill expansion, sandbox; không dùng
dangerously-skip-permissions. StatusLine/title scripts tắt trong phiên. Hooks/MCP
tự động cấu hình ngoài settings phải rỗng; nếu không xác minh được thì từ chối
AGY_AUTOMATIC_EXTENSIONS, không sửa config người dùng. Đây là chính sách củaCLI,
không tuyên bố sandbox Windows là hàng rào tuyệt đối hoặc CLI không dùng metadata
riêng của nó. CLI tự quản lý auth/telemetry/conversations; app không đọc/copy token.

Tối đa12region/batch,12000ký tự/batch,6000ký tự/region,4000ký tự/target; quá giới
hạn báo lỗi, không cắt mất region. Mỗi request có timeout10–300s (default90),
stdout1MB/stderr64KB, drain hai pipe đồng thời. Không auto retry. Cancel/timeout
dừng PID/tree do app khởi tạo; không kill theo tên process hoặc logout session.
Default64lượt/job, configurable1–128; đạt giới hạn thì pause cho người dùng.

TranslationService batch cache misses theo language; target từng ID vẫn đi qua
**numeric/glossary guard cũ**, giữ key unsigned3/signed4. Không đưa QA date handler
vào production. Cả ảnh chỉ inpaint sau khi mọi vùng đã có target hợp lệ.
Các field AGY mới bị loại khỏi recipe khi mode khácAGY, bảo toàn identity Offline.

GUI chung3tab có **AI Gemini AGY**; Offline vẫn default. Settings hiện có thêm
executable/model/timeout/maxrequests và vùng cuộn; không có dialog tài khoản/key.
Quota/rate/auth/protocol/timeout latch stop dispatch; notice × chỉ đóng thông báo,
không đổi provider hoặc resume. Người dùng đổi phương thức rồi Tiếp tục pending
trong cùng phiên theo Stage3A. Chapter job chỉ cho AGY khi được chọn rõ; không
auto fallback. Giới hạn cross-restart/provider-switch từ Stage3A chưa được giải
quyết ở Stage3B; không âm thầm nhận đó là Stage3C đã xong.

## 4. Live QA — hai lượt được duyệt riêng

Người dùng đã duyệt **1 batch/3mẫu development/≤300ký tự/1lượt không retry**.
QA tạo một ảnh tổng hợp từ ba source development: `活动时间`,
`活动时间和活动内容`, `第13话`. PaddleOCR thật nhận đúng3region,17ký tự; đưa kết
quả OCR thật vào cache QA để ProcessingManager dùng lại, không hardcode OCR/target.

Artifact: `output/agy-validation/20261108T025128268404Z/report.json` và ocr.json.
Một CLI invocation với payload đã duyệt; không gửi ảnh/DB trong payload.
**INVALID_RESPONSE** tại parser,0target được chấp nhận,0ảnh dịch,1ảnh QA fallback
nguyên gốc hợp lệ. Không gọi đây làAGY E2E PASS hoặc kết luận model dịch sai/người
dùng không có quyền Pro. Số lượt backend thực sự sinh và raw target **không có
bằng chứng**, chỉ xác định được một CLI batch attempt đã khởi chạy.

Phiên bản provider lúc đó chưa lưu shape stdout nên chưa đủ dữ liệu phân biệt
envelope/state/schema lỗi ở đâu. Không dựng raw target hoặc suy đoán từ mock.
Đã thêm metadata an toàn: exitcode/bytecounts/SHA/events/status/field types và
stderr marker booleans; không ghi stderr thô, OAuth URI hoặc model reasoning.
Provider hiện dừng dispatch sau lỗi protocol/timeout để tránh tốn tiếp quota cho
các ảnh sau. Không chạy lại tự động. Người dùng sau đó đã **duyệt thêm đúng1lượt
với cùng3mẫu**, không mở rộng nội dung. Lượt2 dùng cùng contract parser, không
nới numeric/schema hoặc thay model để ép PASS.

Lượt2: `output/agy-validation/20261108T031617089759Z/report.json`, protocol.json,
ocr.json và ảnh export. AGY thật trả terminal SUCCESS, một result/turn, response
JSON string có translations đúng3ID (cũng có structured_output). Không báo tool
calls. Cả3target qua numeric guard:

| OCR thật | AGY thật |
|---|---|
| 活动时间 | Thời gian hoạt động |
| 活动时间和活动内容 | Thời gian hoạt động và nội dung hoạt động |
| 第13话 | Chương 13 |

ProcessingManager thực sự inpaint/render/export PNG1600×1000, bitmap verify PASS,
sourcehash không đổi,1ảnh hoàn tất/0fallback/0needs_retry. Đã xem ảnh xuất, tiếng
Việt có dấu hiển thị được. Đây là **REAL_AGY_OCR_TO_IMAGE_QA_PASS trên fixture tổng
hợp**, không phải nghiệm thu ảnh truyện phức tạp. Không manual OCR/target hoặc mock
trong lượt này; OCR cache được tạo bằng PaddleOCR thật ngay trước pipeline.

Tổng2CLI batch attempts được duyệt riêng,3unique source/17ký tự mỗi lượt, tổng34
ký tự OCR đưa vào stdin;0auto retry. Không xác minh backend đã sinh gì ở lượt1,
không quy lượt1 là model dịch sai. Chưa tìm được root cause lượt1 vì thiếu raw
protocol lúc đó; không tuyên bố đã sửa dứt điểm lỗi đầu. Mẫu quá ít/0human reference,
không accuracy hoặc kết luận ổn định/chất lượng hơn Argos. Prompt/schema/CLI context
cũng dùng quota account;17ký tự OCR không phải số token toàn request.

GUI Windows còn được kiểm thử bằng bản sao cache của lượt live thành công:
`gui-cache-location.json` dẫn đến output/agy-gui-cache-validation. QThread thực
sự export thêm1ảnh từ OCR/MT cache đã kiểm chứng,31heartbeat, nguồn/settings giữ
hash. Runner chặn mọi payload generation nên **0lượt sinh mới**; không gọi cache
replay này là một lượt model live mới. Screenshot window.png lưu tại đó.

CLI metadata, mock, cache replay và live model E2E được báo riêng, không gộp PASS.

## 5. Kiểm thử

28tests mới trong test_agy.py: NDJSON/schema/Unicode/ID order/missing/extra/
duplicates, injection-as-data, deny tools/credits/API-key environment isolation,
timeout/cancel/stdout limit bằng process Python cục bộ thật (không gọiAGY),
quota/rate/auth/requestlimit latch, cache misses batch/glossary/numeric reject,
Offline không constructAGY, recipe Offline không đổi, pause/resume chỉpending
và giữ output/receipt. Hooks/MCP fail-closed không sửa config. Captured translation
payload sanitized có fixture nhỏ; envelope trong test là manual fixture, không
phải byte-exact stdout hoặc live test. Test đổi model trong Settings cũng kiểm
tra privacy label cập nhật ngay, không lưu config user; effort đúng model slug.
Mock provider không đọc profile hooks/MCP của người dùng; guard extension có
fixture profile riêng trong test.

- Full pytest: **309PASS,10SKIPPED,0FAIL**.
- Full unittest: **309PASS,10SKIPPED,0FAIL** (319tests mỗi runner).
- Mười skip giữ nguyên; không đổi skip thànhpass. Legacy reason có chữ sandbox
  không phải chứng cứ môi trường hiện tại chặn mạng. Full runners chặn mạng,
  dùng database/evidence QA và chạy các integration OCR/Argos đã cài thật.
- Windows Qt test chọnAGY trên3tab, notice× không resume: **PASS**.
  Lần standalone đầu import Qt trước native guard bị lỗi typing.Self; sửa đúng
  bootstrap của test rồi PASS. Không sửa native guard, không che lỗi đầu.
- Windows ảnh đơn/thư mục/OCR+Argos thật:
  `output/source-tabs-validation/20261108T025635Z-dc3de7/report.json`: **PASS**.
- AGY quota thật: NOT_TESTED (mock only). Live lượt1 FAIL/reject; lượt2
  **REAL_AGY_OCR_TO_IMAGE_QA_PASS** như mục4. GUI cache replay PASS, không tạo thêm
  model request. Chưa có QA wholechapter/ảnh truyện production hoặc retry111.

## 6. Bảo toàn và file

Sau test đối chiếu595/595hash runtime/resource,120source/120output và configAGY
được hash riêng; giữ nguyên DB/checkpoint/manifest,models,BAT/spec,4EXE.
Chương274872 vẫn119normal+1fallback111/120file,needs_retry=[111]. Không thay model,
cài dependency, tải ảnh/model, bậtMyMemory hoặc Gemini API để thayAGY.

Production sửa: core/types.py, core/pipeline.py, sources/service.py,
ui/main_window.py, ui/settings_dialog.py. Thêm providers/agy.py,
tests/test_agy.py, tests/fixtures/agy_translation_payload_captured.json,
qa/validate_agy.py và qa/validate_agy_gui_cache.py. Docs: PROJECT_STATUS,README,USER_GUIDE,
TROUBLESHOOTING,adapter guide và báo cáo này. Không đổi requirements/BAT/spec/
.gitignore/nativeguard hoặc version thuật toán numeric production.

Evidence: `logs/stage3b-agy-20261108T023844Z/`: git-before.json,
protected-before.json,chapter-manifest-before.json,cli-discovery.json,
installed-cli.json,model-list.json,agy-config-before.json/agy-config-preservation.json,
live-qa-location.json,live-qa-attempts.json,gui-cache-location.json,
pytest-gate.xml/txt,unittest-gate.json/txt (kết quả cuối),
regression-results.json,preservation.json,git-final.json,summary.json.
Các run initial/verified/final/release được giữ; release308 là trước test effort
cuối, gate309 mới nhất. Không xóa artifact lượt live reject.

## Git & Fork Handoff

Root D:/TransTool, branchmain; baseline sạch/không staged/conflicts. .gitignore
không cần sửa: cache/agy,logs,output,model,venv,dist đã được ignore; không có
credential AGY trong source/config công khai. git-final.json cóstatus/diff/stat,
ignorechecks/danh sách file review; git diff --check PASS. Không untrack file.
Status cuối:10tracked modified +6untracked files,0staged; tổng16file cầnreview.
HEAD/branch/staged giữ nguyên; không có thay đổi có sẵn trước Stage3B.

Nên commit sau review:5tracked production files, providers/agy.py, test_agy.py,
fixture đã lọc,2QA scripts và6docs. Không commit ~/.gemini/auth/session, cache/agy,
runtime/evidence/logs/SQLite/ảnh/output/weights/EXE. Không commit mẫu target giả
như kết quả live. Không stage cảrepo bỏ qua kiểm tra diff.

Message đề xuất: `stage(3b): integrate AGY Gemini translation`.
Mở Fork→Local Changes→review từngfile/hunk→tựstage→xem stageddiff→tựcommit.
**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT**.

## 7. Việc tiếp theo

Đã hết phạm vi hai lượt được cấp, không tự tạo lượt3. Lần tiếp theo có thể đề
xuất QA rộng hơn khi người dùng duyệt, đặc biệt quota thực, câu dài/tên/ngày tháng
và độ ổn định protocol. Giữ guard/cache/provider isolation. Không tự chạy chương
production, retry111, build EXE hoặc Stage3C. Chưa có benchmark ngữ nghĩa độc lập
và vẫn cần điều tra nếu INVALID_RESPONSE tái xuất hiện.

**STAGE_3B_COMPLETED_WITH_WARNINGS**
