# Stage3C.1 — AGY Unexpected tool use diagnostics

08/11/2026. **STAGE_3C1_DIAGNOSTICS_WITH_WARNINGS**.
Diagnostic hotfix đã được kiểm thử local/mock; không sửa verdict/guard hoặc gọi AGY.

## 1. Lỗi lịch sử và baseline thực tế

Lỗi lịch sử chapter276337 第4话 登门道歉, job09fdd522… được diagnostic ghi
INVALID_RESPONSE / Unexpected tool use tại trang chờ57. Batch tái dựng lúc đó
16trang có chữ/25vùng/166ký tự. Không có NDJSON/protocol metadata để biết tool
request thực, declaration, metadata false positive hay dạng giao thức khác.
Không dùng fixture để kết luận nguyên nhân sâu hơn hoặc nói ROOT_CAUSE_CONFIRMED.

**Trước khi sửa**, snapshot phát hiện người dùng đã tiếp tục job: manifest
completed_with_warnings,113output/112pipeline-normal+1FALLBACK_ORIGINAL106,
needs_retry=[106]. Người dùng xác nhận đã tự tiếp tục. Baseline Stage3C.1 là
trạng thái mới này, không phải56output/57pending. Không rollback/retry57/106/111,
không làm lại56output đã hoàn thành. 112normal không đồng nghĩa112trang đều có chữ dịch.

Evidence: `logs/stage3c1-20261108T092810Z/`, pointer logs/latest-stage3c1.json.
Snapshot1058file gồm113source/cache/download receipts,113pipeline/published outputs,
DB/journal/config/model/BAT/spec/4EXE và các module không được sửa. Không copy
raw job texts/transcripts vào report. Git main/HEADeb5554b; có sẵn PROJECT_STATUS
sửa và báo cáo điều tra chưa track; không hoàn nguyên hai thay đổi này.

## 2. Audit parser/CLI trước can thiệp

`AGYProvider.translate_batch` dùng executable đã cấu hình/tìm cục bộ, shell=False,
stdin NDJSON event=user,message.content là JSON task/regions/reference_only.
CLI flags hiện có: input/output-format stream-json, json-schema, model/effort,
mode=plan, disable-slash-commands, sandbox, print-timeout, settings session-only,
log-file=os.devnull. PROMPT_VERSION/SESSION_SETTINGS/deny file/shell/web/MCP
giữ nguyên; không API key/credits. Không chạy --help/--version hoặc model ở stage này.
Lịch sử đã xác minh AGY1.5.3; code preflight theo capabilities/version hiện có,
không tạo version policy mới bằng diagnostic.

Luồng hiện tại (line theo source hotfix):

`run_bounded:providers/agy.py:107` → `_parse_response_legacy:220` → guard
used_tool:244 → `parse_response:281` (wrapper observer) → ProviderSuspended →
`core/multipage.py:translate_batch` attach batch → `core/pipeline.py:run` log →
checkpoint/signal pause cũ. `core/diagnostics.py:DiagnosticLog.write` lọc lại ở biên ghi.

Legacy đọc từng dòng NDJSON không trống, strict_json (cấm duplicate key/NaN),
đòi đúng1terminal event=result, statusSUCCESS/exit0/num_turns1, response là string
JSON translations với đủ ID duy nhất. Các event phụ trước đây không có một
allowlist đóng; hotfix **không tự thêm allowlist** hoặc sửa schema được chấp nhận.

Guard đệ quy toàn bộ object/list của event: key truthy tool_call/tool_calls/
tool_name/function_call hoặc top event tool_call/tool_use/permission_request.
Không quét tên công cụ trong text string, không parse stderr thành tool use.
Event có cả text và marker vẫn bị chặn; declaration và invocation từng bị gộp
trong guard. Metadata có tool_name hoặc properties.tool_call cũng có thể kích
hoạt theo source, nhưng chưa chứng minh đó là wire response của job lịch sử.

## 3. Observer và phân loại

Module mới **providers/agy_diagnostics.py**, không mạng/file/tool executor.
Wrapper chỉ quan sát verdict của legacy. Predicate tool guard giữ byte-identical;
exception code/message và pause/fallback/cancel behavior không đổi. Thêm thuộc
tính diagnostic trên exception, không migration journal/DB hoặc thay cache.

| Classification | Bằng chứng được dùng | Hành vi |
|---|---|---|
| ACTUAL_TOOL_REQUEST | Request tag có trong contract guard cũ, action name không rỗng và argument/input object rõ ràng | Legacy reject giữ nguyên; không khẳng định tool đã thực thi. Chỉ là contract mô phỏng, chưa chứng minh schema AGY thực. |
| TOOL_METADATA_ONLY | Toàn bộ marker thuộc khai báo kiểu JSON Schema hẹp, vocabulary từ output_schema hiện có | Legacy reject vẫn reject. Không coi mọi tools/metadata là an toàn. |
| MALFORMED_RESPONSE | Malformed JSON/NDJSON hoặc envelope/response/ID/schema được nhận diện nhưng không đúng | Không retry/cache/render phản hồi bị reject. |
| UNKNOWN_PROTOCOL_SHAPE | Marker mơ hồ, declaration chưa xác minh, unknown envelope, không có protocol lúc transport dừng | Không nới guard; ghi fingerprint/types/path có giới hạn. Mã operational TIMEOUT/quota… vẫn riêng. |
| VALID_TRANSLATION_RESPONSE | Canonical translation được legacy chấp nhận, không marker mà guard hiện tại nhận diện | Vẫn qua numeric/glossary/image validation; không chứng nhận ngữ nghĩa hoặc toàn bộ protocol ngoài phạm vi đã biết. |

Không chỉ dựa vào tên tool_name để gọi là request thực: nested function_call,
tool declaration chưa rõ hoặc request tag thiếu cấu trúc action đều UNKNOWN.
Khai báo kiểu chỉ là bằng chứng cú pháp, không khẳng định website/AGY đã phát ra.

**Giới hạn tương thích bắt buộc:** unknown auxiliary event hoặc tool_result
không marker mà legacy trước đây vẫn cho phép cùng canonical result **vẫn giữ
verdict cũ**. Diagnostic vocabulary EVENTS không phải protocol allowlist.
Nếu observer lỗi, observation_failed=True, không log exception và guard_decision
vẫn phản ánh verdict thực; classification UNKNOWN khi không quan sát được không
được tự thay thế translation validator. Muốn siết/nới các ca này phải duyệt riêng.

## 4. Diagnostic fields và bảo mật

`agy_protocol` version agy-safe-protocol-diagnostic-v1 gồm:

- timestamp UTC, model_identity_hash, cli_version nếu đúng dạng semver3số;
  job/chapter/provider/mode có sẵn ở record ngoài (không đưa path vào metadata).
- batch_id digest từ item IDs, page_count/region_count/source_characters,
  request_number nếu biết. Diagnostic không tham gia recipe/identity/cache key.
- stdout_bytes/stderr_bytes, exit_code nếu biết, ndjson_lines.
- events[index/type/value_type], tool_indicators[event_index/type/path/value_type/
  evidence], schema_fingerprint của key/type đã redacted.
- classification, parser_error_code/reason enum, guard_decision,
  pending_preserved, retry=False, translation_cached=False ở điểm lỗi/parse.
- scan_truncated, observation_failed, stream_limit_exceeded.

`guard_decision` là verdict giao thức legacy; khi numeric fail, protocol có thể
VALID/ACCEPT nhưng top error_code=NUMERIC_MISMATCH, vùng đó vẫn không cache/render.
Không biến schema-valid thành dịch thành công. Cancel/overflow có thể chỉ có
counts stream đã quan sát (prefix), exit_code=null; không bịa transcript đầy đủ.

Giới hạn:128physical lines/events quan sát,32tool paths,4096node/24depth,
path160ký tự,512shape tuples. Unknown field names thành [*], unknown event label
thành OTHER; không log values ngoài enum allowlist. JSON Schema declaration
matcher cũng bounded, không thực thi schema/JS. Fingerprint chỉ hash sanitized
structure, không hash raw transcript/OCR/unknown secret key name.

Log writer **sanitize lần2**: bỏ mọi key không cho phép/type sai/digest sai,
không tin dictionary diagnostic caller đưa vào. Tên trường/label chứa control,
URL/token/injection không được ghi nguyên. Mỗi chuỗi được giới hạn bằng enum,
regex hoặc path bounded. DiagnosticLog giữ cap4MB/1000records/atomic append+fsync
và chính sách torn-tail cũ. Không tạo raw file response/stderr/prompt.

Record AGY mới có agy_protocol luôn bỏ OCR text/raw target/numeric text tokens,
image/output private paths và raw exception message trước khi ghi, kể cả khi
diagnostic_text=True. Không thay review/checkpoint/GUI message đang dùng hoặc
logging Argos/MyMemory. Thông tin request lỗi không còn phải dựa vào last_attempt
vùng cuối trong batch để biết pages/regions/chars; legacy image index vẫn là
trang đang chờ, không tự sửa schema của record cũ.

Không sửa/xóa log lịch sử: lỗi cũ vẫn không có metadata mới và có thể còn text
theo diagnostic policy cũ. Không chia sẻ toàn bộ log cũ để lấy nhóm metadata mới.

## 5. Fixture và regression

Fixture mới `tests/fixtures/agy_protocol_manual_cases.json` có **20case**,
fixture_kind=MANUAL_CONTRACT_FIXTURES_NOT_CAPTURED_AGY. Envelope lấy từ parser/
fixtures hiện có; các nhánh tool/metadata là dữ liệu giả lập gắn nhãn, không phải
capture thực. Không gọi tên field quen thuộc là bằng chứng về wire schema AGY.

Case matrix: valid; explicit request; JSON Schema type metadata; declaration
chưa xác minh; text+request; permission request; malformed line; unknown-only;
unknown auxiliary giữ legacy verdict; response thiếu/sai kiểu/nested; duplicate
result; nested metadata marker; literal tool text; exit failure; wrong/missing/
duplicate ID; tool_result không marker (legacy accepts); function_call mơ hồ.

`tests/test_agy_diagnostics.py`: **19test mới PASS**, với20case subtests, privacy/
key injection/redacted fingerprint/depth bounds, log-writer sanitization, batch
counts, no-cache/no-render khi reject, metadata classified vẫn reject, quota
budget/cache identity/permissions/prompt, local Python stdout+stderr overflow,
timeout/cancel, numeric reject và pause→manual Offline resume giữ receipt/hash.
Các local process tests chỉ chạy Python fixture, không executable AGY/account.
59test AGY/multipage cũ chọn lọc cũng PASS.

**Full pytest368PASS/10SKIPPED/0FAIL; full unittest368PASS/10SKIPPED/0FAIL,
378ca mỗi runner.** Logs pytest-final.xml/txt, unittest-final.json/txt trong
evidence. Skips giữ nguyên (model ngôn ngữ/M2M100/live opt-in); không ép PASS.
Runner cô lập QA DB/evidence, chặn socket/DNS, không bật live flags. Qt/native
import/OCR+Argos integration hiện có PASS trong suite; không gọi mock là live.

`behavior-preservation.json` kiểm AST/byte: PROMPT_VERSION, SESSION_SETTINGS,
REQUIRED_FLAGS, MODE, provider identity, predicate guard, prompt/CLI payload,
TranslationService numeric/glossary/cache method, job destination, BATCH_VERSION,
packing thresholds và receipt key không đổi. Không thay budget64, defaults
3.000/60/16trang, context8/1600, literal-numbers-v2-signed hoặc journal version.

## 6. Bảo toàn job và file thay đổi

`preservation.json`: **1058/1058file giữ hash**, SQLite read-only integrity=ok,
113source/113pipeline+published bitmap/receipt hợp lệ;112done+1fallback106.
Model/config/4EXE và báo cáo điều tra cũ nguyên. Không production resume, live
AGY/MyMemory, download, dependency hoặc build. Không sử dụng lại consent live
của Stage3B/3C; không fake result để kết luận lỗi lịch sử đã được giải quyết.

Source sửa: providers/agy.py, core/multipage.py, core/pipeline.py,
core/diagnostics.py. Source mới: providers/agy_diagnostics.py. Test/fixture mới
như mục5. Tài liệu sửa: PROJECT_STATUS.md, USER_GUIDE.md, TROUBLESHOOTING.md;
mới: báo cáo này và STAGE3C1_WORK_PROGRESS.md. Không sửa AGENTS/README vì workflow/
cách chạy không đổi. Không GUI/refactor/provider khác hoặc journal migration.

## 7. Git & Fork Handoff

Repo D:\TransTool, main/HEADeb5554b giữ nguyên. Baseline có2thay đổi từ điều tra:
PROJECT_STATUS.md và docs/STAGE3C_PAUSE_ROOT_CAUSE_INVESTIGATION.md. Tài liệu cũ
chưa track giữ nguyên hash; PROJECT_STATUS thêm mục mới, không xóa lịch sử.
.gitignore hiện đủ, không sửa; check-ignore/source/docs visibility và diff --check
**PASS**, được ghi trong git-final.json. Cuối lượt7tracked sửa/6untracked,
staged0; trong6file chưa track có báo cáo pause cũ giữ nguyên. Không phát hiện
secret/binary lớn/runtime mới trong danh sách review. Không untrack file hoặc
stage thay người dùng.

Review source4file +module mới, test+fixture,3tài liệu chung và2docs Stage3C.1.
Báo cáo điều tra cũ là file còn từ nhiệm vụ trước, review riêng trong Fork.
Không commit logs/evidence/cache/DB/journals/output/models/.venv/EXE/credential.

Fork → Local Changes → review từng diff/hunk → tự stage phần source/test/docs
cần thiết → xem staged diff → tự commit. Gợi ý sau regression PASS:
`fix(agy): add safe tool-use protocol diagnostics`.

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT**.

## 8. Giới hạn và bước tiếp theo

Không có evidence mới của response lịch sử276337; **chưa biết guard nhận nhầm**,
chưa biết có tool action thực hoặc nên đổi CLI/prompt. Chỉ có thể xác minh sâu
hơn khi có safe diagnostic của response thực tương tự, từ lượt sử dụng người
dùng chủ động hoặc QA được duyệt riêng. Không resume job đã hoàn tất để dò lỗi.

Nếu evidence là request thật: giữ block, xem cơ chế CLI chính thức trong nhiệm
vụ riêng. Nếu chỉ là metadata có schema đã xác minh: đề xuất parser hotfix hẹp,
test âm tính và xin duyệt riêng; không bỏ mọi tool_name/permission_request.
Nếu unknown: giữ trạng thái, không đoán endpoint/allowlist hoặc chạy live lặp.
Diagnostics và false-positive fix là hai việc khác nhau.

**STAGE_3C1_DIAGNOSTICS_WITH_WARNINGS** — local diagnostics validated,
nguyên nhân sâu hơn của lỗi lịch sử vẫn chưa được chứng minh.
