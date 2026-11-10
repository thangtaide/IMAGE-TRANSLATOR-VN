# Stage3J — AGY preflight, fresh chapter và error-only evidence

09/11/2026 — **STAGE_3J_IMPLEMENTED_NOT_TESTED**.

Chỉ triển khai source, đọc AST/diff và đối chiếu hash. Không chạy pytest,
unittest, mock/regression/smoke, GUI/BAT/OCR/MT, AGY kể cả help/version, API
dịch hoặc production resume. Không build/cài dependency/billing/Git mutation.
Mọi kết quả dưới đây mô tả **thiết kế và source**, không phải nghiệm thu runtime.

## 1. Baseline và nguyên nhân

Đã đọc AGENTS/PROJECT_STATUS, các báo cáo Stage3G/H/I, AGY provider/runner,
TranslationService, MultiPageAGY, WholeChapterJob, diagnostic, source/resume/UI.
Git main/HEAD `a0ea3bbc0479b0215645c83df0593571e167c4e7`; baseline còn14tracked
modified và4untracked của Stage3G/H/I. Không staged/conflict; giữ nguyên nền đó.

Stage3I xác định guard hooks/MCP đọc file cấp user và chặn trước subprocess.
Whole cũ đã chốt budget dù chưa CLI; Batch mới9646fde0… nhận preflight_error
OnlineProviderError, tái raise mỗi trang và generic fallback tạo109Origin.
Không phải109request. Journal timeout e8ddd939…/bc961120… vẫn có59done,
50pending/44receipts, nhưng manifest chung trỏ job109Origin. Không khôi phục,
đổi pointer, ghép receipts hoặc triển khai Stage3K.

## 2. AGY preflight pause một lần

`AGYProvider.__init__` bọc đúng **AGY factory boundary**, giữ implementation
cũ trong `_initialize`. Chỉ các lỗi OnlineProviderError/OSError/ValueError/
TypeError phát sinh tại factory này được chuyển thành ProviderSuspended; giữ
mã lỗi có sẵn, hoặc AGY_INITIALIZATION_ERROR khi không có mã. Cancel vẫn cancel.
Không chuyển mọi exception của pipeline hoặc engine khác thành suspension.

`check_automatic_extensions()` giữ nguyên toàn bộ predicate và nội dung mã.
Không sửa hooks.json/mcp_config.json; không thêm key rỗng, đổi tên/xóa file,
mở file/shell/web/MCP hoặc tăng quyền. Guard vẫn chặn cấu hình không xác minh.
Không đổi provider identity, prompt, command/session settings, model hoặc timeout.

Batch: identity() thất bại → preflight_error typed → vòng xử lý giữ/skip
receipt done hợp lệ → tại pending đầu tiên vào nhánh ProviderSuspended sẵn có
→ một diagnostic chính và PAUSED_PROVIDER → break. Không đi generic fallback,
không tăng failed/fallback, không đánh dấu pending done, không báo hoàn tất MT.
Nếu chưa xử lý trang nào thì toàn bộ vẫn pending. Nhánh lỗi OCR/source/render/
publication từng ảnh giữ policy cũ. Khởi tạo không gọi lại provider để lấy log.

Lỗi AGY_AUTOMATIC_EXTENSIONS nằm trước mọi CLI probe/generation; process_started
false, response_observed false. Lỗi capability có thể xảy ra sau help/version
probe cũ: không được tuyên bố mọi preflight error đều chưa CLI. Metadata ghi
invocation_kind và trạng thái quan sát được; không suy ra backend/quota.

Whole mới: sau người dùng xác nhận/hash, kiểm tra guard local **trước** chốt
budget mới. Constructor vẫn recheck guard trước CLI để không bỏ điều kiện nếu
config đổi giữa hai bước. Lỗi preflight đầu này không chốt cờ mới. Workspace
cũ agy_attempt_used=true vẫn bị quy tắc cũ chặn; không reset hoặc migration.
Sau bước chốt vẫn một generation tối đa, probe_cli=False, không retry/fallback.

## 3. GUI và lượt dịch lại mới

### Batch từ nguồn chương

Menu **Thêm → Dịch lại toàn bộ chương (AGY)…** chỉ bật cho AGY Batch/Whole,
một chương đã chọn, khi không busy. Hộp xác nhận nói rõ lượt mới, không tiếp
job cũ, không dùng MT AGY cũ, giữ kết quả cũ và có thể tiêu thụ quota. Hủy không
khởi chạy worker. Không chọn provider thay người dùng.

Với Batch, sau xác nhận:

1. Cấp workspace độc lập bằng mkdir không ghi đè:
   `output/stage3j-batch-<uuid>/`.
2. Worker dùng prepare_input: cache nguồn phải đầy đủ/khớp bitmap/hash, đọc
   ảnh local hiện có. Nếu chưa có ảnh, vẫn phải qua adapter/download/access
   gate và incoming riêng. Không sửa cache nguồn cũ hoặc vượt hạn chế website.
3. LocalComicJob nhận ImageCollection đã xác minh, stage vào
   `cache/online_comics/_fresh/<run>/...`; từ chối nếu fresh root đã tồn tại.
   Manifest ở nhánh mới, không sửa manifest/journal109Origin hoặc59done.
4. Pipeline staging có suffix `fresh_<run>`, publication ở
   `<workspace>/published/`. Không ghi đè staging/published output cũ.
5. Dùng ResumeStore/DB hiện có, tạo source/chapter journal và record job mới.
   DB chung chỉ thêm record/cache của lượt mới; không chép/ghép/xóa row lịch sử.
   cache_root mới được source journal lưu theo cơ chế hiện có.
6. Trong cùng phiên, Resume/Retry lượt fresh dùng restore_source_request từ
   source ID hiện tại, không đi lại default ChapterCache. Qua restart, luồng
   khôi phục source mới nhất hiện có đọc cache_root đã lưu và chỉ chạy khi bấm.
   Không thêm historical picker. Hủy trước khi có source journal có thể cần
   chuẩn bị lượt mới; không tự đoán/chọn một job cũ để tiếp.

**Bảo đảm fresh MT theo mã:** source/output/staging paths chứa run UUID mới
→ job ID mới → item IDs chứa job/page/source → batch context digest mới.
Journal regions mới rỗng, nên không lấy context receipt lịch sử; translation
key hiện có chứa context/provider. Vì vậy không cache-hit MT AGY từ lượt cũ
(dựa trên hash SHA256 thông thường, không thay công thức provider identity).
Resume cùng lượt fresh được dùng lại target đã validated của chính lượt đó.
OCR cache vẫn có thể reuse khi source hash/model/recipe khớp, không xóa cache.

### Whole

Tái sử dụng nút tạo lượt mới trong Whole dialog, đổi nhãn **Dịch lại toàn bộ
chương (lượt mới)…**, thêm xác nhận chuẩn bị. Main source fresh action đặt
force_new để không tự chọn workspace lịch sử. DB/receipt/output riêng trong
`output/stage3g-…`; cấp thư mục exclusive, không dùng lại nếu trùng tên.
Giữ đúng danh sách ảnh được chọn, kể cả một ảnh riêng trong thư mục nhiều ảnh.

OCR/manifest của lượt mới trước → thống kê → **Xác nhận dịch bằng AGY…** riêng
→ preflight → một invocation toàn chương → guard → durable receipt → render.
Không cache MT từ DB/workspace Whole cũ hoặc chuyển sang Batch. Mở/chọn/OCR/
resume không tự gửi. Whole vẫn không nhập output/tổng kết vào Batch cũ.

## 4. Kiến trúc error-only evidence

Module mới `core/agy_error_evidence.py`: AGYErrorCapture là bộ quan sát nhỏ,
giữ tối đa stdout1MB/stderr64KB trong RAM, chỉ persist khi lỗi. Không tạo
bundle mới trên đường generation + validation thành công. Các receipt/cache/
metadata vận hành cũ, kể cả response receipt Whole để resume, giữ nguyên.

`logs/diagnostics/agy_errors/<attempt_id>/` có thể gồm:

- metadata.json: trường được allowlist/giới hạn, không raw message/exception,
  OCR/prompt/environment/header/command-line hoặc giá trị cấu hình hooks.
- outcome.json: final_job_state quan sát tại kết thúc job, tạo exclusive một
  lần; metadata ban đầu có thể ghi UNKNOWN khi kết quả job chưa biết.
- stdout.raw.dpapi và/hoặc stderr.raw.dpapi: **raw bytes nhận được, mã hóa**.
  Không sửa/redact bytes trước khi mã hóa. Không tạo artifact khi không có bytes.
  Response nằm trong stdout nên chỉ tham chiếu stdout, không tạo bản trùng.

Metadata gồm UTC timestamp, internal attempt ID, job/journal ID, chapter ID
hoặc hash identity, batch/manifest hash khi có, configured provider/model,
error source/category/code, preflight step/CLI role, process started/exit code,
elapsed/configured timeout, observation state/response scope, byte counts,
payload SHA256, parser code/reason, validation failure code, artifact sizes/
hashes/partial/not_saved và backend_received=UNKNOWN. Init trước khi có pipeline
job ID dùng journal ID để tương quan; errors.jsonl của pipeline có hash job và
cùng attempt reference. Không tạo job ID giả hoặc suy ra request backend.

Nguồn lỗi: APP_PREFLIGHT,CLI_START,CLI_TIMEOUT,CLI_EXIT,CLI_RESPONSE,PARSER,
VALIDATION,UNKNOWN. Chỉ gán theo dữ kiện: Popen failure khác JSON/parser reject;
protocol báo quota/auth khác timeout; preflight local không phải CLI response.
Mã/chapter/batch không an toàn được bỏ hoặc thành UNKNOWN, không echo metadata
bất kỳ từ CLI. Giá trị error reason chỉ từ enum tĩnh hiện có.

### Timeout và validation

- Reader dùng read1 thay read4096 chờ đầy, giữ bytes khả dụng dưới cap cũ.
  Khi lỗi, runner gắn capture transient, stop process như cũ, join hữu hạn,
  thu prefix thực nhận. Không đổi deadline90s Batch/600s Whole hoặc payload.
- Partial stream không coi là terminal hoàn chỉnh. observed_bytes có thể lớn
  hơn captured_bytes nếu vượt cap; artifact đánh dấu partial. Hash là hash
  prefix đã giữ, không giả là hash toàn response bị thiếu.
- Process start không chứng minh backend nhận request. Exit code sau cleanup
  là exit code quan sát được, không đoán backend. Elapsed có thể gồm cleanup
  sau timeout; không phải thời gian reset quota hoặc cam kết latency.
- Safe protocol snapshot lúc exception có thể ghi ít bytes hơn bundle được
  thu sau cleanup. Đây là hai thời điểm quan sát, không sửa bytes raw để ép khớp.
- Parser/schema/tool guard lỗi: giữ stdout/stderr thực nhận, không nới guard.
- Numeric/glossary reject sau CLI response: dùng capture transient của đúng
  batch/lượt đó, ghi VALIDATION, không dùng target bị reject làm cache hợp lệ.
  Một attempt chỉ có một bundle, dù nhiều vùng lỗi; region/page diagnostic
  vận hành hiện có vẫn ghi theo kiến trúc cũ.
- AGY_AUTOMATIC_EXTENSIONS: APP_PREFLIGHT, process_started=false, không bytes/
  response artifact giả. Không khẳng định đã tiêu thụ quota. Lỗi trước CLI
  hoặc không nhận byte nào không thể có response để lưu.

## 5. Bảo mật và dung lượng

Raw **không plaintext**: Windows CryptProtectData dùng CurrentUser DPAPI và
CRYPTPROTECT_UI_FORBIDDEN; thư mục attempt có protected DACL owner/SYSTEM.
Không tự cấp Administrator hoặc thêm quyền tool. Chỉ ciphertext ghi xuống
file bằng exclusive create + fsync; không file tạm raw. Metadata không chứa
nội dung truyện/credential. Không giả rằng raw đã được loại bỏ mọi bí mật.

Nếu DACL/DPAPI không khả dụng/thất bại, không ghi raw; ưu tiên metadata-only,
ghi not_saved/incomplete. Non-Windows cũng metadata-only. Quyền/khóa/dung lượng
không cho ghi metadata thì báo AGY_EVIDENCE_WRITE_FAILED/STORE_FULL, giữ lỗi
provider gốc. Nếu có artifact lỗi ghi dở thì đó vẫn chỉ là ciphertext, không
phải plaintext. Không tự xóa evidence cũ hoặc mở file cho người dùng.

Kho64MB, stdout prefix1MB/stderr64KB mỗi attempt (+overhead DPAPI), reserve
metadata/outcome, giới hạn số entry. Có thread lock và quota lock file liên
process không chờ vô hạn; khi không lấy khóa được thì báo lỗi diagnostic,
không ảnh hưởng kết quả dịch. Không có chính sách auto-delete/rotation raw.

**Windows DACL/DPAPI, quota/collision/cancel và tất cả IO path này chưa chạy
test**, chỉ rà source/AST. Metadata/hashes không thay thế bằng chứng raw thật
khi không lưu được. Logging failure không đổi lỗi provider, retry hoặc kết
quả thành công. Caller không tự đọc/decrypt/upload artifact.

## 6. GUI và truy xuất sau này

Banner nhận diện AGY initialization, mã lỗi/model, pause và không tạo Origin
mới. AGY_AUTOMATIC_EXTENSIONS báo chặn trước CLI; lỗi init khác thừa nhận probe
có thể đã chạy. Timeout ghi cấu hình khi có, không gọi là quota. Có attempt ID
và đường log trong Chi tiết hoặc trạng thái Whole; không raw response, không
tự mở log, dashboard, viewer/replay riêng hoặc checkbox logging.

Khi cần điều tra, người dùng cung cấp attempt/job ID và chủ động yêu cầu đọc
metadata.json/outcome.json. Codex không tự giải mã/upload raw. Chỉ khi được
yêu cầu riêng mới đọc/decrypt ciphertext trong đúng ngữ cảnh Windows; không
đổi đuôi rồi coi là plaintext, không cần gọi lại AGY để thu evidence. Không
tích hợp công cụ replay hoặc tự gửi nội dung bundle tới dịch vụ ngoài.

## 7. File thay đổi và tương thích

Source Stage3J:

- core/agy_error_evidence.py (mới): bounded capture, safe metadata, DPAPI/DACL,
  quota/exclusive IO, outcome/reference; không network.
- providers/agy.py: typed factory suspension, runner partial capture và
  error-only persistence. Guard/identity/command/prompt giữ nguyên.
- core/pipeline.py: context/ref cho AGY, pause sẵn có và finish outcome.
- core/multipage.py: observation context, validation-error capture; không đổi
  planner/batch identity/context/cache/pacing hoặc nhánh Gemini API.
- core/whole_chapter.py: local preflight trước budget mới, capture đến sau
  validation và evidence refs. Không reset old budget/migration.
- sources/service.py: fresh verified input/cache/staging branch riêng.
- sources/whole_input.py: cho phép workspace prefix stage3j-batch cho input
  receipt; không tự nhận đó là Whole workspace lịch sử.
- ui/comic_sources.py: fresh chapter confirmation/action/worker/resume route.
- ui/whole_chapter.py: reuse fresh button, confirm độc lập và error reference.
- ui/provider_notice.py: AGY preflight/timeout notice, model/attempt ngắn gọn.

Tài liệu: báo cáo này, PROJECT_STATUS.md, docs/USER_GUIDE.md,
docs/TROUBLESHOOTING.md, docs/WEBSITE_ADAPTER_AI_GUIDE.md. Giữ lịch sử G/H/I.
Không đổi schema Options/ResumeStore, cache version/provider identity hoặc
native import guard. Không sửa Argos/MyMemory/Gemini API/Auto Fallback. Batch
vẫn24trang có chữ/60vùng/3.000ký tự, pacing5–10s giữa invocation thật; Whole
không chia batch/pacing. Không thêm invocation/retry/fallback. Một invocation
không chứng minh chỉ một backend request.

## 8. Kiểm tra và dữ liệu bảo vệ

Chỉ AST/diff/read-only hash. Rà AST giữ nguyên hàm check_automatic_extensions,
AGY identity/command, TranslationService._translate_using, pack_pages và
wait_before_next_invocation so với baseline Stage3I. Không đổi numeric guard
literal-numbers-v2-signed, glossary hoặc literal request prompt.

Mọi pytest/unittest/mock/GUI/regression/smoke/live/OCR/MT/crypto/ACL/IO test:
**NOT_TESTED** theo yêu cầu. Không có số PASS mới. Không tạo bundle lỗi giả
hoặc chạy fixture để nhận xét có raw evidence thật. logs/stage3j-* chỉ là
evidence triển khai/hash/Git, không phải bundle của invocation AGY.

Snapshot gồm cache/journal/SQLite/output/models/EXE/config, logs cũ, BAT/spec
và hooks/MCP; không sửa nội dung các cây đó. Hash cuối lưu preservation.json.
Đối chiếu full lần đầu:30.922/30.922file giữ SHA256/size/mtime. Ở kiểm tra
cuối, `config/settings.json` đổi từ1184 sang1198byte lúc
`2026-11-09T10:07:42.271533Z`. Không có thao tác Codex ghi config. Người dùng
xác nhận không chủ động sửa/lưu Cài đặt nhưng đã **đóng ứng dụng** đúng khung
giờ đó; `ui/main_window.py:718` tự gọi save_options khi closeEvent. Thay đổi
phù hợp cơ chế tự lưu của ứng dụng; không có audit OS để gán chính xác PID
writer. Giữ nguyên config mới, không hoàn nguyên hoặc rebase snapshot để che.
Kết quả cuối: **30.921file không đổi**,1config thay đổi đồng thời nêu trên;
cache/DB/journal/output/log cũ/model/4EXE và hooks/MCP không đổi. Xem
preservation-final.json và concurrent-change.json. Không tuyên bố toàn bộ
30.922file giữ nguyên ở thời điểm bàn giao. Snapshot chỉ đọc, không dùng để
thay journal/cache hoặc gọi pipeline.
Không hash toàn bộ .venv hoặc cài package. Không đọc raw response cũ, key,
cookie hoặc token; không đổi dữ liệu lịch sử276880/274872/trang111 hoặc fixture
Stage3F. Không có production run từ Codex trong Stage này.

## 9. Người dùng tự nghiệm thu

1. Mở source, dùng ảnh QA/chương đã cache; không dùng production để nghiệm
   thu lần đầu. Giữ config hooks/MCP như hiện tại nếu muốn xác nhận nhánh
   guard: Batch phải pause tại pending đầu,0Origin mới,1lỗi chính, không CLI.
2. Xem attempt metadata local: APP_PREFLIGHT/process_started=false và không
   artifact response giả. Không thay config để lách guard hoặc reset cờ cũ.
3. Nếu người dùng đã xử lý cấu hình AGY an toàn bằng cơ chế chính thức, chọn
   Fresh, xác nhận quota/phạm vi; Whole vẫn cần xác nhận gửi sau OCR. Kiểm tra
   cache/output/job mới, không sửa run59done/109Origin hoặc dùng lại MT cũ.
4. Khi có timeout/parser/numeric lỗi trong tự nghiệm thu, xem metadata,
   observed/captured bytes, partial, not_saved và outcome. Không cần gọi thêm
   AGY để lấy log; không gửi raw cho Codex nếu chưa chủ động muốn điều tra.
5. Sau lượt thành công, kho error-only không được có bundle mới vì success;
   receipt vận hành vẫn có. Đóng/mở/tiếp tục phải dùng cache_root lượt mới,
   không tự gửi AGY khi chưa bấm, không chạy lại trang đã hoàn tất hợp lệ.

Các bước là tiêu chí tự nghiệm thu tương lai, không phải bằng chứng đã đạt.
Stage này không khắc phục cấu hình hooks bên ngoài; guard vẫn có thể chặn.

## 10. Git & Fork Handoff

Root D:/TransTool, main/HEAD nêu ở mục1. Giữ nguyên Stage3G/H/I chưa commit;
delta Stage3J được tách trong evidence để review. Không sửa .gitignore; logs,
cache, output, model, EXE và config cá nhân không vào Git. Source mới/docs/
tests/spec/config mẫu phải hiển thị bình thường. Không untrack hoặc xóa dữ liệu.

Review mười source và năm tài liệu ở mục7. Các file dùng chung đã có hunk
G/H/I, không commit cả working tree mù. Không commit logs/diagnostics/agy_errors,
ciphertext raw, hash/Git evidence, cache/DB/journal/output/model/.venv/EXE hoặc
config AGY. Không có API key/credential mới trong source/report dự kiến.

Evidence: logs/stage3j-20261109T092937Z/ gồm git-before/after.json,
review-baseline.json, diff-before.patch, stage3j-source-review.patch,
static-review.json, protected-stat-before.json, protected-hash-before.json,
preservation.json, preservation-final.json, concurrent-change.json và các
kết quả rà cuối. git diff --check/status/stat và
check-ignore được ghi nhận cuối lượt, không stage để kiểm tra.
Git cuối15tracked modified/6untracked, index trống/không conflict;
git diff --check exit0. Các con số bao gồm nền G/H/I, không chỉ Stage3J.

Fork → Local Changes → review hunk Stage3J và nền G/H/I → tự stage source/docs
cần thiết → review staged diff → tự commit nếu hài lòng. Gợi ý:
`fix(agy): pause preflight failures and add fresh runs with error evidence`.
Message không nói đã test hoặc xử lý xong cấu hình AGY bên ngoài.

**NO_COMMIT — NO_PUSH — NO_TAG — NO_DESTRUCTIVE_GIT.**

**STAGE_3J_IMPLEMENTED_NOT_TESTED** — dừng để người dùng tự nghiệm thu.
