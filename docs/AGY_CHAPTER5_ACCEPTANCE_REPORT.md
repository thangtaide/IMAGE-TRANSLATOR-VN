# AGY chương5 — khôi phục và nghiệm thu thực tế, 09/11/2026

**Cập nhật sau sửa timeout: Batch và Whole đều có109/109ảnh,93vùng dịch hợp lệ,
0fallback lỗi.** Mỗi chế độ có51trang chứa OCR cần dịch và58trang không có vùng
cần dịch. Kết quả dưới đây giữ lịch sử lỗi; mục bổ sung cuối báo cáo là trạng
thái nghiệm thu hiện tại. Không tuyên bố đã chứng minh nguyên nhân chậm ở backend.
Sau timeout, người dùng phê duyệt riêng một invocation Whole mới; không coi
phê duyệt này là quyền tự retry Batch hoặc reset ngân sách.
Root D:/TransTool, main, HEAD9f530cfabcb051cdebdcca3268f4c781be58190c;
working tree sạch trước nhiệm vụ. Không sửa các job/workspace lịch sử.

## Kết quả thật

| Chế độ | Output hợp lệ | Trang có chữ đã dịch | Vùng đã validated | Fallback lỗi |
|---|---:|---:|---:|---:|
| Batch mới, sau sửa |59/109 |24 |44 |0 |
| Whole mới |109/109 |51 |93 |0 |

35/59trang Batch không có vùng cần dịch, được giữ nguyên nguồn theo metadata;
không được gọi cả59trang là59trang đã dịch chữ.50trang còn pending. Whole có
58trang không có vùng cần dịch;51trang có93target hợp lệ. Đã kiểm tra bitmap,
mapping và render; không gọi cả109ảnh là109ảnh đều có chữ cần dịch.

## Lỗi và sửa tối thiểu

- CLI thực tế --version=1.5.3; --help có headless/schema/session settings.
  plugin list báo không cài plugin; mcp list không có server. Không đổi tài
  khoản/key/model/billing, không dùng provider khác hoặc mua quota.
- CLI1.5.3 `plugin validate --strict --json` chấp nhận hook enabled boolean
  false, từ chối chuỗi false. Kiểm tra này chỉ parse local, không cài plugin
  hoặc chạy handler. Đối chiếu [Hooks chính thức](https://antigravity.google/docs/hooks/).
- Sao lưu hai config nguyên trạng vào thư mục DACL owner/SYSTEM dưới
  `logs/agy-chapter5-20261109T105339Z/private-config-backup/`. Chỉ thêm
  enabled=false vào đúng một definition hiện có; mọi handler/cấu hình khác
  giữ nguyên, MCP không đổi. Atomic replace bằng file có DACL riêng.
- `providers/agy.py`: guard nhận disabled-only theo schema đã kiểm tra,
  vẫn chặn active/default/sai kiểu/schema lạ, MCP không rỗng, plugin store
  không được review. Kiểm tra global và .agents tại workspace/ancestors;
  recheck trước mỗi invocation. Không thêm wrapper giả hoặc bỏ guard.
- Lượt thật đầu exit0 nhưng bị parser chặn: read_file ACTIVE rồi ERROR do
  permission denied, sau đó finish. Không chấp nhận hoặc reuse target đó.
- Session cũ dùng plan. [Tài liệu settings](https://antigravity.google/docs/settings?tab=cli)
  xác nhận plan chèn /plan; đổi session về default, giữ strict/deny/sandbox.
  Không đổi prompt, model hoặc timeout90s/600s.
- Chỉ nhận finish nội bộ khi parameters khớp response, structured_output và
  schema yêu cầu. Mọi file/shell/web/MCP hoặc tool bất thường, kể cả denied,
  vẫn từ chối. Fixture âm tính và phân tích response thật cục bộ đã kiểm tra
  ranh giới này. Không sửa numeric/glossary validator.
- SESSION_SETTINGS nằm trong identity Batch/Whole, nên thay đổi mode tự tách
  identity/cache khỏi lượt cũ; không migration hoặc reuse MT cũ.

## Ngân sách và timeline UTC

| # | Chế độ/phạm vi | Bắt đầu → kết thúc | Kết quả |
|---|---|---|---|
|1 |Batch đầu24trang có chữ/44vùng/228ký tự |11:03:54 →11:05:22 |CLI exit0,88.047s; parser từ chối tool use,0output |
|2 |Batch lượt mới24trang có chữ/44vùng/228ký tự |11:10:11 →11:11:07 |55.922s,44target hợp lệ,59output |
|3 |Batch tiếp24trang có chữ/39vùng/226ký tự |11:11:18 →11:12:48 |90.250s,TIMEOUT,partial4265byte,exit1 |
|4 |Whole109trang/93vùng/536ký tự, consent riêng |12:54:39 →12:56:11 |91.562s,exit0;93target validated,109output |

**4/6invocation dịch thật**, không chạy đồng thời hoặc retry tự động.
Lượt sửa sau lỗi cách lần trước289.59s (>60s); giữa batch2/3 có pacing ngẫu
nhiên5–10s của planner, cộng render/overhead tạo khoảng cách10.900s.
Whole chỉ gọi sau consent ngoại lệ cụ thể, cách timeout hơn101phút (>60s).
Help/version/config/schema validator không tạo yêu cầu dịch. Một invocation
không chứng minh chỉ có một request backend nội bộ AGY.

Lỗi cuối: attempt6585b2c5193446358275455ec4896c01, job QA
2d305cf5a83471edd4840fad12c3cb63473caf3d750992226ef3ac656265143d.
Metadata CLI_TIMEOUT/process_started=true/response_complete=false. Partial
chỉ có init và user_input DONE; **không có terminal result**, không chứng
minh backend đã kết thúc hoặc quota. Ban đầu ledger khóa tiếp, không gửi lại
payload hoặc tự chuyển Whole. Người dùng sau đó cho phép chính xác1Whole;
ledger ghi exception-used trước Popen và không xóa cờ timeout cũ. Whole hoàn
tất với terminal SUCCESS, không retry. Batch90s/Whole600s chưa thay đổi.

Raw hai lỗi thực được giữ mã hóa DPAPI/DACL tại logs/diagnostics/agy_errors/.
Chỉ giải mã response của lượt QA mới trong RAM để phân tích schema; không
lưu/in/upload plaintext, prompt, command, credential hoặc chain-of-thought.
Full tests có fixture lỗi riêng; không coi bundle mock không có job ID này
là quota/lỗi AGY thật. Log thành công không tạo raw error bundle.

## Ảnh và dữ liệu

Batch đọc tại:
`output/stage3g-chapter5-20261109T105339Z-corrected-batch/rendered/`.
Whole đầy đủ đọc tại:
`output/stage3g-chapter5-20261109T105339Z-corrected-whole/rendered/`.
Ảnh mở được; kiểm tra crop nguồn/kết quả0001/0026/0059 trong
`logs/agy-chapter5-20261109T105339Z/render-spot-check.png`.
Bubble0026 có tiếng Việt đọc được; title/logo trang1/59 cho thấy hạn chế OCR/
inpaint trên chữ trang trí/watermark. Không tuyên bố chất lượng toàn chương
hoặc100%đúng nghĩa. Whole kiểm tra thêm0004/0073/0104; bubble tiếng Việt đọc
được, chữ trang trí vẫn có hạn chế. Contact sheet whole-render-spot-check.png.
Không mở rộng sửa OCR/renderer ngoài mục tiêu.

Evidence và ledger: `logs/agy-chapter5-20261109T105339Z/`.
Hai workspace first/corrected và mọi dữ liệu mới tách khỏi run59done,
run109Origin và Whole cũ. Không tải ảnh/model, không build EXE.
Đối chiếu cuối29.285file theo size/mtime,2.514file chọn lọc theo SHA256:
không mất file; chỉ hooks.json đổi đúng phê duyệt.2.513SHA và29.284stat còn
lại giữ nguyên, gồm dữ liệu lịch sử/cache/DB/output/model/config/BAT/spec/EXE
trong phạm vi đã snapshot. Không tuyên bố đã hash toàn bộ model/.venv.
Chi tiết preservation-final.json của thư mục evidence.

## Kiểm thử và Fork

Test local guard+protocol:32pass;4ca GUI được cập nhật theo identity provider
và translator keyword của Stage3G/H:4pass. Lượt full đầu507pass/3fail/10skip;
ba lỗi là fixture GUI còn dùng nhãn cũ/translator keyword trùng, đã sửa test
để theo đúng contract hiện tại. Không sửa UI production để ép test.
Full pytest cuối: **510pass/10skip/0fail**,203.90s. Unittest bootstrap:
**510pass/10skip/0error**,520ca,209.616s. Giữ riêng lượt unittest trực tiếp
đã lỗi57error/487ca vì typing.Self khi import Torch sau Qt; nạp
prepare_inference_runtime trước discovery như bootstrap pytest/app khắc
phục mà không sửa runtime/dependency. Không xóa hoặc gọi lượt lỗi là pass.
GUI Windows Qt offscreen chọn được cả Batch/Whole, nút Phân tích chương
hiện rõ,0CLI trên thao tác chọn; screenshot gui-provider-choices.png.
Đây không phải Whole live hoặc nghiệm thu desktop người dùng hoàn chỉnh.

Source cần review: providers/agy.py; QA runner mới qa/validate_agy_chapter5.py.
Tests: test_agy_disabled_hooks.py, test_agy_finish_contract.py (mới), test_agy.py,
test_gemini_api.py, test_preflight_compact_ui.py, test_whole_chapter.py.
Docs: báo cáo này, PROJECT_STATUS, USER_GUIDE, TROUBLESHOOTING.
Không commit logs/private backup/DPAPI/config/output/cache/DB/models/EXE.
.gitignore không đổi; source/tests/docs hiện để review, logs/cache/output/
config vẫn ignore. Git cuối8tracked modified/4untracked, không staged/conflict;
HEAD/branch không đổi, git diff --check exit0. Người dùng review từng file/
hunk trong Fork, tự stage và commit. Commit gợi ý:
`fix(agy): handle disabled hooks and structured completion safely`.
Không mô tả đã nghiệm thu cả hai chế độ.

Bước tiếp theo của Batch chờ lựa chọn rõ từ người dùng: dùng resume QA có
sẵn cho50pending trong2lượt còn lại, hoặc xin thêm ngân sách để chạy mới.
Không phát triển resume mới hoặc tự vượt điều kiện timeout/ngân sách.

**NO_COMMIT — NO_PUSH — NO_TAG — NO_DESTRUCTIVE_GIT.**

## Bổ sung: sửa runner và nghiệm thu Batch đủ109ảnh, 09/11/2026

### Nguyên nhân đã chứng minh và giới hạn kết luận

Attempt6585b2c5193446358275455ec4896c01 bị watchdog tổng thời gian trong
`providers/agy.py:run_bounded` chặn ở90.250s. Runner cũ và CLI đều nhận90s,
không có khoảng dự phòng cho startup/serialize/shutdown. Partial4265byte chỉ
có init và user_input DONE, không có terminal result. Đây là lỗi timeout tại
wrapper; không phải bằng chứng lỗi numeric/parser, quota hay backend timeout.
Không thấy tràn buffer. Không coi init/input DONE là model đã hoàn thành.

Fixture local chạy lại runner cũ tái hiện được wrapper cắt terminal đến muộn;
fixture root exit nhưng child giữ pipe cho thấy runner kết thúc sau8.094s mà
child vẫn sống. Child fixture tự kết thúc sau12s. Đây là bằng chứng lỗi lifecycle
của runner cũ, không chứng minh một AGY mồ côi cụ thể đã tồn tại sau attempt cũ.

Whole hợp lệ91.562s vượt90s cũ, nên90s không đủ cho mọi lượt hợp lệ của route này.
Tuy nhiên, lượt39vùng sau sửa chỉ mất81.750s; không thể kết luận payload cũ chắc
chắn cần hơn90s. Nguyên nhân upstream của việc không có terminal trước90s trong
lượt cũ vẫn **chưa được chứng minh**; không suy diễn backend chậm, queue hoặc
retry nội bộ từ số giây. Một invocation cũng không chứng minh chỉ một backend
request. Không tuyên bố đã sửa triệt để hành vi của dịch vụ bên ngoài.

### Thay đổi tối thiểu

- `providers/agy.py`: CLI giữ tổng ngân sách hữu hạn theo setting, mặc định mới
  300s; wrapper chờ thêm15s dự phòng. GUI và constructor vẫn giới hạn Batch10–300s.
  300s là mức hữu hạn trong phạm vi setting đã có, khoảng3.3lần lượt hợp lệ lớn
  nhất đã quan sát91.6s; đây là chính sách dự phòng, không phải ước lượng latency
  theo số ký tự. Whole vẫn600s, wrapper615s. Không timeout vô hạn.
- Phân biệt `WRAPPER_TOTAL` và terminal CLI `print_timeout` (`CLI_TOTAL`), kể cả
  CLI exit0 và kèm JSON đầy đủ cũng không chấp nhận kết quả timeout. Không dùng
  idle timeout vì CLI không có heartbeat model đáng tin cậy: lượt#5 im lặng
  khoảng78s sau input DONE nhưng cuối cùng trả terminal hợp lệ.
- `providers/agy_process.py` mới: Windows Job Object kill-on-close, tạo child
  suspended rồi gán job trước khi resume. Chỉ cleanup cây thuộc invocation,
  kể cả root đã exit; không kill theo tên hoặc quét/kill psmux/Claude/Codex.
  Không cách ly được thì dừng trước khi child chạy code. Cleanup kiểm tra active
  count về0, thời gian chờ hữu hạn; lỗi cleanup chặn provider.
- Runner drain stdout/stderr đồng thời, giữ cap1.000.000/64.000byte, ghi partial
  lỗi theo evidence bảo vệ hiện có, không chấp nhận partial như bản dịch. Observer
  chỉ có mốc thời gian/count/exit/cleanup, không lưu prompt/OCR/response thô.
- `core/agy_error_evidence.py` bổ sung watchdog/timeout-layer metadata có giới hạn;
  `core/types.py` đổi default AGY300s. `config/settings.json` cá nhân chỉ đổi
  agy_timeout90→300, có backup DACL riêng; không đưa config vào Git.
- `qa/validate_agy_chapter5.py`: tiếp tục đúng journal QA đã có50pending, claim
  độc quyền và fsync trước Popen, chỉ cho2lượt cuối của ngân sách6. Không có retry,
  fallback hoặc framework resume mới. `tests/test_agy_timeout_lifecycle.py` có
  11fixture deadline/partial/cancel/process-tree/observer; không gọi dịch mạng.

Không sửa hooks/MCP, prompt, model, numeric/glossary, batch planner, pacing,
renderer hay cơ chế ResumeStore trong lượt sửa timeout. Batch vẫn24trang có
chữ/60vùng/3.000ký tự. Không sửa source của Argos/MyMemory/Gemini API.

### Live QA và ảnh thực tế

| # | Phạm vi | UTC bắt đầu → kết thúc | Kết quả |
|---|---|---|---|
|5 |Batch24trang có chữ/39vùng/226ký tự |15:26:54.497 →15:28:16.254 |81.750s,exit0,39target hợp lệ |
|6 |Batch3trang có chữ/10vùng/82ký tự |15:28:26.332 →15:28:48.660 |22.328s,exit0,10target hợp lệ |

Đã dùng **6/6invocation**. Không gửi thêm lượt nào. Trước#5 đã đánh giá rủi ro
backend attempt cũ UNKNOWN, local không còn AGY, đã qua nhiều giờ và người dùng
chủ động yêu cầu dùng2lượt còn lại; không tự retry tức thì hay dùng partial cũ.
Giữa#4/#5 hơn150phút; giữa#5/#6 có countdown ngẫu nhiên8s, gap thực10.078s gồm
render/overhead. Không chạy đồng thời. Hai invocation mới đều cleanup_ok=true,
active_processes_after_cleanup=0. Backend cũ vẫn không được tuyên bố đã kết thúc.

Existing ResumeStore skip59output đã xác minh, chỉ xử lý50pending; không sửa
journal bằng tay. Đổi timeout làm job fingerprint mới cho phần pending; receipt
của59output cũ được journal giữ đúng path/hash/recipe cũ, không giả đổi recipe.
Tổng Batch cuối109bitmap/109page duy nhất,51trang có chữ,58không có vùng cần
dịch,93target hợp lệ,0target rỗng,0fallback. Whole vẫn109/93/0fallback.

168/168SHA output trước lượt sửa (59Batch+109Whole) không đổi; receipt cũ còn
nguyên path/output hash/fingerprint. Kiểm tra ảnh nguồn/kết quả0026/0073/0104:
chữ Việt đọc được, đúng vị trí vùng trong mẫu, không lẫn thứ tự trang.
Contact sheet `timeout-repair-20261109T151519Z/batch-final-spot-check.png`.
Không gọi kiểm tra mẫu là đánh giá ngữ nghĩa độc lập toàn bộ chương; OCR chữ
trang trí/watermark vẫn có giới hạn đã ghi ở trên.

Đọc chương ngay bằng thư mục Batch/Whole ở mục Ảnh và dữ liệu phía trên.
Muốn mở ứng dụng: chạy `run_source.bat`, giữ model hiện tại, chọn Batch hoặc
Toàn chương từ dropdown như trước; không cần dịch lại để đọc ảnh QA đã xuất.

Evidence bổ sung: `logs/agy-chapter5-20261109T105339Z/timeout-repair-20261109T151519Z/`.
Không build EXE, không tải ảnh/model, không đổi billing/tài khoản/key.

### Regression và bảo toàn sau sửa timeout

- Full pytest: **521PASS,10SKIP,0FAIL**,203.01s.
- Full unittest bootstrap runtime trước discovery: **521PASS,10SKIP,0FAIL/
  0ERROR**,531ca,208.609s, log `unittest-sequential.txt`.
  Lượt full trước đó chạy đồng thời với pytest có1ERROR tại fixture downloader
  `test_temporary_timeout_retry_is_finite` (FileNotFoundError được wrapper thành
  NetworkUnavailable), không thuộc AGY. Giữ log `unittest-full.txt`; chạy riêng
  ca đó đạt1/1 và full tuần tự đạt toàn bộ. Chưa chứng minh nguyên nhân lỗi
  fixture ban đầu; không sửa hoặc bỏ qua test/source downloader để ép xanh.
- 11fixture mới chạy local process thật, không phải AGY/backend thật. Kiểm tra
  delayed terminal, silence, init lặp không gia hạn, exit0 thiếu terminal,
  CLI print_timeout, partial, cancel, cleanup child, sentinel không liên quan,
  startup containment thất bại và observer lỗi. Full suite gồm Qt offscreen;
  không gọi đây là nghiệm thu thao tác desktop của người dùng.
- Đối chiếu30.240file baseline bằng size/mtime:0mất file.6file đổi là QA Batch
  DB/WAL/SHM/journal, QA Whole SHM và config/settings.json. Whole SHM là vùng
  phối hợp SQLite thay đổi trong lúc mở kiểm tra receipt, không phải thay đổi
  dữ liệu dịch; DB Whole giữ hash cũ. Không báo mọi runtime byte bất biến.
- Đối chiếu2.514SHA từ baseline đầu quá trình khôi phục:2.512không đổi; chỉ
  hooks.json đã đổi có phê duyệt ở nhiệm vụ trước và settings.json đổi300s
  trong lượt này.168/168SHA ảnh Batch/Whole đã xong trước lượt sửa không đổi.
  Model/ảnh nguồn/output lịch sử/production DB/journal trong snapshot giữ nguyên.
  Không tuyên bố đã hash toàn bộ .venv/model; xem `preservation-final.json`.

### Git & Fork Handoff sau sửa timeout

Root `D:/TransTool`, branch `main`, HEAD
`9f530cfabcb051cdebdcca3268f4c781be58190c` không đổi. Trước lượt sửa timeout
đã có8tracked modified/4untracked từ khôi phục guard; giữ nguyên các hunk đó.
Cuối lượt có10tracked modified/6untracked,0staged,0conflict. Không reset,
restore, untrack hoặc chỉnh index/history. Baseline/full diff có tại
`timeout-repair-20261109T151519Z/git-before.json`, cuối tại `git-final.json`.

File nên review/commit (gồm thay đổi có sẵn; không tự nhận mọi hunk là mới):

- Source: `providers/agy.py`, **`providers/agy_process.py` mới**,
  `core/types.py`, `core/agy_error_evidence.py`.
- QA: `qa/validate_agy_chapter5.py` (đã untracked trước nhiệm vụ, bổ sung
  authorized resume/budget/observer). Script không tự chạy dịch khi import.
- Test: `tests/test_agy_timeout_lifecycle.py` mới; các file có sẵn đang chờ
  commit `tests/test_agy_disabled_hooks.py`, `tests/test_agy_finish_contract.py`,
  `tests/test_agy.py`, `tests/test_gemini_api.py`,
  `tests/test_preflight_compact_ui.py`, `tests/test_whole_chapter.py`.
- Docs: báo cáo này, `PROJECT_STATUS.md`, `docs/USER_GUIDE.md`,
  `docs/TROUBLESHOOTING.md`.

Không commit config cá nhân/backup/hooks/MCP, logs/raw DPAPI, DB/WAL/SHM,
journal, receipt runtime, cache, output ảnh, .venv, models hoặc EXE.
`.gitignore` không đổi. Check-ignore xác nhận logs/cache/output/config/.venv/
dist bị ignore;16file source/test/docs cần review đều hiển thị, không bị che.
Không có runtime đã track, file review lớn>1MB hoặc credential pattern thật
được phát hiện trong phạm vi scan; scan không chứng minh mọi secret đều bị
phát hiện, người dùng vẫn review diff. `git diff --check` exit0; chỉ có cảnh
báo CRLF→LF cho agy.py, không có lỗi whitespace.

Trong Fork mở Local Changes, review từng hunk, tự stage source/test/docs cần
thiết và xem staged diff trước commit. Commit gợi ý sau nhiệm vụ này:
`fix(agy): bound CLI timeout and contain subprocess lifecycle`.

Mục tiêu ảnh chương5 đã đạt; dừng phát triển, không gọi thêm AGY hoặc tạo
Stage mới. Giới hạn còn lại: chưa chứng minh nguyên nhân upstream stall cũ và
chưa có tham chiếu độc lập đánh giá toàn bộ ngữ nghĩa truyện.

**NO_COMMIT — NO_PUSH — NO_TAG — NO_DESTRUCTIVE_GIT.**
