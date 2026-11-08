# Stage3D — Gemini API chính thức

Ngày kiểm tra: 08/11/2026. **STAGE_3D_IMPLEMENTED_QA_PENDING**.

Đã tích hợp REST provider và GUI, kiểm thử local/mock. **Không gọi Gemini API
thật, không dùng key để xác minh tài khoản/billing/model**, không build hoặc
chuyển Stage4. Không nhận kết quả mock là chất lượng dịch Gemini thực tế.

## 1. Baseline và công việc có sẵn

Root `D:/TransTool`, branch `main`, HEAD
`eb5554ba51e51708fc082c09687f293cfb07a732`. Trước sửa có7tracked modified và
6untracked files từ Stage3C.1/điều tra; không staged hoặc unmerged. Snapshot đầy
đủ status/ls-files và source trước sửa tại `logs/stage3d-20261108T100403Z/`.
Baseline báo cáo Stage3C.1 là368PASS/10SKIPPED mỗi runner; đây là lịch sử, không
phải test đã chạy lại trước khi sửa Stage3D.

Trạng thái production thực tế khác yêu cầu lịch sử56output/57pending: người dùng
đã tự tiếp tục trước Stage3C.1. Chương276337 có113output,112pipeline-normal và
fallback106, needs_retry106. Chương274872 giữ120output/119normal/fallback111.
Normal không đồng nghĩa tất cả trang đều có chữ đã dịch. Không rollback trạng
thái, resume hoặc retry bất kỳ jobproduction nào.

## 2. Tài liệu Google đã kiểm tra

Chỉ nghiên cứu tài liệu công khai; các GET tài liệu không gửi key/OCR/ảnh.
Bản tham khảo công khai đã lưu trong evidence `official-*.txt`, không commit.

| Chủ đề | Nguồn chính thức và kết luận |
|---|---|
| SDK | [Libraries](https://ai.google.dev/gemini-api/docs/libraries): Google khuyến nghị Google GenAI SDK, Python `google-genai`. Không cài SDK vì chưa được duyệt; dùng REST với `requests` sẵn có. |
| REST | [Generate content API](https://ai.google.dev/api/generate-content): `POST /v1beta/models/{model}:generateContent`, systemInstruction/contents/generationConfig, usageMetadata. Dùng `x-goog-api-key` header theo [API keys](https://ai.google.dev/gemini-api/docs/api-key), không query string. |
| JSON | [Structured output](https://ai.google.dev/gemini-api/docs/structured-output) và REST reference: JSON Schema chỉ ràng buộc cấu trúc, không bảo đảm đúng nghĩa. Stage3D dùng responseMimeType/application-json và responseJsonSchema, kiểm tra ID/kiểu/keys lại tại client. Trang hướng dẫn mới ưu tiên Interactions; Stage3D không sử dụng API đó. Chưa xác minh wire compatibility bằng request thật. |
| Model | [Gemini2.5Flash](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash): model ID `gemini-2.5-flash`, hỗ trợ structured output, input1.048.576/output65.536token theo trang model. Google giới hạn model2.5 cho dự án/người đã sử dụng; không chứng minh key mới truy cập được. [Deprecations](https://ai.google.dev/gemini-api/docs/deprecations) chưa công bố shutdown model text2.5Flash tại thời điểm kiểm tra. |
| Free | [Pricing](https://ai.google.dev/gemini-api/docs/pricing): Standard text input/output2.5Flash có Free tier. Không sử dụng dịch vụ Batch API tính phí, tools hoặc grounding. Free tier có chính sách dùng dữ liệu cải thiện sản phẩm. |
| Billing | [Billing](https://ai.google.dev/gemini-api/docs/billing): key kế thừa tier của project; model có Free tier không khiến key Paid trở thành miễn phí. UI yêu cầu người dùng xác nhận đã kiểm tra project Free/không billing. Đây không phải xác minh billing của ứng dụng; không có bảo đảm chi phí cho key Paid hoặc project bị đổi tier về sau. |
| Quota | [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits): RPM/TPM/RPD theo project/model/tier, xem mức hoạt động tại AI Studio. Không hardcode quota Google hoặc số lượt còn lại; budget64lượt là giới hạn của app. |
| Lỗi | [Troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting): phân biệt client/server/rate errors. App chọn không tự retry generation để tránh request trùng/quota không mong muốn. Không tự chuyển model/provider hoặc bật billing. |

## 3. Kiến trúc triển khai

`GUI → worker hiện có → ProcessingManager → OCR/cache cũ → MultiPageAGY
(chọn transport theo mode) → GeminiAPIProvider → guard từng vùng → cache/region
receipt → render/export/receipt cũ`.

Giữ tên lớp planner cũ để tương thích; không chạy AGY hoặc dùng NDJSON cho API.
Không sửa AGYProvider/AGY diagnostics trong Stage3D. Không thêm engine OCR/dịch.

- Mode mới `AI Gemini API`; không xóa AGY/MyMemory/Argos hoặc đổi default Offline.
- Chỉ allowlist model2.5Flash, host cố định generativelanguage.googleapis.com,
  TLS verification, không theo redirect, không customendpoint/SDK phụ thuộc mới.
- Key đọc từ GEMINI_API_KEY trong bộ nhớ lúc gọi; không có key trong Options,
  model identity, journal, DB/cache hoặc log. Không duyệt credential AGY/OAuth.
- JSON task/source_language/target_language/regions/reference_only qua user
  content; systemInstruction coi OCR/context là dữ liệu không đáng tin, không
  lệnh. Không gửi ảnh/path/DB; không khai báo tool/function/search/codeexecution.
- Mỗi item có ID job/chapter/page/sourcehash/region/readingorder cũ. Schema yêu
  cầu translations[id,text]; client từ chối thiếu/trùng/lạ/sai kiểu/extra keys,
  duplicate JSON keys, NDJSON, empty target, candidate không STOP và part ngoài
  text. Không thực thi bất cứ tool nào kể cả response chứa functionCall.
- Mapping trả về theo ID input, không dựa thứ tự response. Numeric/glossary guard
  và chính sách cache từng vùng giữ nguyên byte (trừ mode label diagnostic).
  `literal-numbers-v2-signed` không đổi; không promotion date handler QA.

## 4. Giới hạn và pause/resume

| Thành phần | Giới hạn thực thi |
|---|---|
| Planner | Target3.000ký tự/60vùng/16trang có chữ; dùng cùng cấu hình AGY/API |
| Một vùng / batch cứng | 6.000 / 12.000ký tự; không cắt mất văn bản |
| Context | 8vùng đã qua guard /1.600ký tự JSON, tùy chọn tắt |
| Payload / response | 128KiB /1.000.000byte, target tối đa4.000ký tự |
| Generation | temperature0, candidateCount1, thinkingBudget0, maxOutputTokens32.768 |
| Request budget | Mặc định64, cấu hình1–128 trong một provider session/lượt chạy |
| Timeout | Mặc định90giây tổng, connect8giây/read tối đa10giây; kiểm tra checkpoint/deadline khi đọc, kể cả response trickle |
| Retry | 0 tự động; không replay HTTP400/401/403/429/5xx/timeout/JSON lỗi |

Giới hạn trên được kiểm tra mock, chưa đo latency/token/output của Gemini thật.
Budget không phải quota và không giới hạn tổng số token cả ngày. Không có
metadata quota remaining đáng tin từ test thật để hiển thị; UI dùng `?` nếu
thiếu token counters và dẫn người dùng xem AI Studio.

HTTP400→INVALID_REQUEST,401→AUTH_REQUIRED,403→ACCESS_DENIED,404→MODEL_UNAVAILABLE,
429→RATE_LIMITED; chỉ quotaId có PerDay trong QuotaFailure mới QUOTA_EXCEEDED.
Giữ HTTP status/Retry-After số nguyên an toàn. 5xx/redirect→PROVIDER_UNAVAILABLE,
network/TLS→NETWORK_ERROR, timeout→TIMEOUT, payload/JSON/ID/finish/tools được
phân loại riêng. Thông báo dùng static message; không log response body hoặc
raw exception chứa URL/header. × chỉ ẩn thông báo; không tự tiếp tục/chuyển.

Namespace `gemini-api-comic-json-v1:literal-numbers-v2-signed:<model>:...` độc lập
AGY/MyMemory/Argos, tính đến generation settings và context/batch policy. API
fields được loại khỏi recipe các mode cũ để không đổi old job identity; API
batch config có recipe riêng. Các field API operational tham gia PROVIDER_FIELDS
để resume đổi provider có kiểm soát, không sửa journal schema hoặc migrate DB.
Key không tham gia identity. OCR cache giữ nguyên; output receipt cũ vẫn kiểm
tra source/output/hash trước skip. Không đánh dấu trang done chỉ vì nhận JSON.

## 5. Kiểm thử

Fixture trong tests/test_gemini_api.py là **giả lập thủ công**, không phải capture
Gemini thật. Dùng HTTPFixture trả requests.Response tại bộ nhớ, fake OCR/bitmap
cho integration mới; không mở socket. Runner toàn bộ cấm socket.connect và
getaddrinfo, redirect DB mặc định GUI/evidence integration sang QA riêng.

33test mới bao gồm: header/HTTPS/schema/no tools, Unicode/60regions, exact IDs,
malformed/duplicate JSON/NDJSON, tool/text distinction, finish/truncated/safety,
response/payload/context bounds, timeout tổng/trickle/cancel, HTTP errors,
quota/request budget/no retry, usage allowlist, key không lọt diagnostic/SQLite,
numeric/glossary, batch3trang, cache separation, restart/API→Offline, giữ output
receipt/OCR cache, old workrecipe, GUI4mode/keypresence/usage và sourcejob mode.

Kết quả cuối từ hai runner chạy tuần tự (không sửa test cũ). Evidence:

- Focused reviewed:34PASS (33Gemini +1test downloader cũ).
- Pytest reviewed: **401PASS /10SKIPPED /0FAIL**,72,92giây.
- Unittest reviewed: **401PASS /10SKIPPED /0FAIL**,72,42giây,411ca tổng.
- Một lượt pytest trước:399PASS/10SKIPPED/1FAIL tại test mock downloader Kuaikan,
  StopIteration do danh sách response giả hết. Unittest chạy cùng lúc PASS400/10.
  Test đó chạy riêng PASS và pytest toàn bộ tuần tự PASS. Không xác định chắc
  nguyên nhân nhất thời, không đổi/xóa test hoặc downloader; giữ traceback
  `pytest-final.txt/xml`. Không gộp lượt lỗi vào PASS hoặc bỏ qua lịch sử.
- Windows Qt offscreen/GUI4mode, OCR Trung và Argos Offline/E2E thực **PASS**
  trong full suite; xem pytest-reviewed.xml và unittest-reviewed.json/txt.
  10SKIPPED là model ngôn ngữ chưa có và live tests opt-in không chạy. Chuỗi lý
  do skip cũ nhắc sandbox không phải bằng chứng môi trường hiện tại chặn mạng.
  Không gọi mock API là real Gemini E2E; chưa kiểm thử cửa sổ GUI thủ công có
  người thao tác hoặc EXE mới trên máy khác.
- **REAL_GEMINI_API_QA: NOT_TESTED / NOT_AUTHORIZED**.0request API,0OCR ra Google,
  không liveAGY/MyMemory/CDN, không thử lại production. Model eligibility/free
  quota/độ chính xác nghĩa/latency trên key thật chưa xác minh.
- EXE: NOT_TESTED, không build. Không cài SDK/dependency hoặc model mới.

## 6. Bảo toàn và file thay đổi

Snapshot1.058file và `preservation.json`:1.058/1.058hash không đổi, gồm source/cache/
output/DB/journal/receipt/model/config/BAT/spec/4EXE và native/offline/online guards.
Manifest276337/274872 giữ counts/fallback/needs_retry như baseline. Không ghi
production DB/checkpoint, không publish output production mới.

Giữ nguyên byte: providers/agy.py, providers/agy_diagnostics.py,
core/diagnostics.py, core/runtime.py, OCR/override, Offline/MyMemory, AGENTS và
ba báo cáo Stage3C.1/điều tra. Các chỉnh sửa3C.1 trong pipeline/multipage được
giữ; thêm nhánh API, không nới guard AGY hay đổi protocol allowlist.

Source sửa: core/types.py, core/resume.py, core/pipeline.py, core/multipage.py,
sources/service.py, ui/main_window.py, ui/comic_sources.py, ui/provider_notice.py,
ui/settings_dialog.py. Source mới providers/gemini_api.py; test mới
tests/test_gemini_api.py. Docs sửa README/PROJECT_STATUS/USER_GUIDE/TROUBLESHOOTING;
báo cáo mới này. Không sửa .gitignore/AGENTS hoặc dependency manifests.

## 7. Git & Fork Handoff

Root/branch/HEAD như mục1. .gitignore đã đủ: logs/cache/output/config cá nhân/
.env/dist được check-ignore đúng; model/.venv/runtimeDB/EXE tiếp tục bỏ qua.
Source/test/docs mới không bị ignore; .spec/config mẫu vẫn track. Không có
runtime binary hoặc key được thêm vào danh sách review. Git diff --check cuối
PASS, không staged files. Status cuối15tracked modified và9untracked, gồm cả
13file Stage3C.1 có sẵn. Evidence git-final.json lưu status/stat/untracked/ignore;
không dùng git diff --stat để bỏ sót provider/test/report mới chưa track.

**File nên review/commit Stage3D:**9source sửa và provider/test mới liệt kê mục6,
README.md, PROJECT_STATUS.md, docs/USER_GUIDE.md, docs/TROUBLESHOOTING.md,
docs/STAGE3D_GEMINI_API_REPORT.md. Các file runtime/evidence dưới logs, output,
cache, model, SQLite, config cá nhân/.env, EXE và .venv không commit.

**Thay đổi có sẵn cần review riêng:**7tracked modified baseline là
PROJECT_STATUS.md, core/diagnostics.py, core/multipage.py, core/pipeline.py,
docs/TROUBLESHOOTING.md, docs/USER_GUIDE.md, providers/agy.py.6untracked baseline:
docs/STAGE3C1_AGY_TOOL_USE_DIAGNOSTICS_REPORT.md, docs/STAGE3C1_WORK_PROGRESS.md,
docs/STAGE3C_PAUSE_ROOT_CAUSE_INVESTIGATION.md, providers/agy_diagnostics.py,
tests/fixtures/agy_protocol_manual_cases.json, tests/test_agy_diagnostics.py.
Không nhận các file này là Stage3D tạo. Pipeline/multipage/docs có cả hai stage;
review diff/hunks cẩn thận. Commit Stage3C.1 trước hoặc cùng snapshot đầy đủ,
tránh bỏ sót module/test mà source hiện tại phụ thuộc.

Mở Fork → repository D:/TransTool → Local Changes → xem từng diff → chỉ tự stage
source/test/docs/config cần thiết → xem staged diff → tự commit khi hài lòng.
Đề xuất `feat(translation): add official Gemini API provider`; không gọi đó là
đã nghiệm thu API thật. **NO_COMMIT / NO_PUSH / NO_TAG / NO_DESTRUCTIVE_GIT**.

## 8. Bước tiếp theo

Chờ người dùng review và duyệt riêng phạm vi QA API. Đề xuất sau khi xác minh
project Free tier và quyền model:1request2.5Flash,3vùng OCR QA tổng hợp (không
production), tối đa100ký tự nguồn, không retry, không tools/ảnh/path/DB, cache/DB
QA riêng. Chưa thực hiện hoặc coi đề xuất là chấp thuận. Nếu model bị từ chối,
báo đúng HTTP/lỗi và chờ quyết định, không tự đổi model/paid tier. Chưa xác nhận
chất lượng hơn Argos/AGY/MyMemory hoặc portable EXE; không chuyển Stage4.
