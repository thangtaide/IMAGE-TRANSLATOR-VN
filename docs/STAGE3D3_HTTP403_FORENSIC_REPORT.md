# Gemini API HTTP 403 — điều tra forensic

Ngày kiểm tra: 08/11/2026. Phạm vi: đọc bằng chứng cục bộ, source và tài liệu
Google công khai; kiểm thử local/mock. Không gọi Gemini API, AGY, MyMemory hay
nguồn truyện. Không resume hoặc sửa dữ liệu production.

**HTTP_403_CONFIRMED** cho sự kiện GUI 14:39:36 UTC.
**ACCESS_DENIED_ROOT_CAUSE_UNPROVEN** cho nguyên nhân quyền cụ thể.

## A. Bằng chứng HTTP và timeline

Diagnostic gốc:
`logs/diagnostics/e26eec3c8595a4a98a5ec74a7c18757773483d01d8f82ba33727c63be5f85d1a/errors.jsonl`,
**dòng 3**. Bản trích metadata đã lọc nằm ở
`logs/http403-forensic-20261108T144556Z/matches.json`.

| Trường | Giá trị đã lưu |
|---|---|
| Timestamp record | 2026-11-08T14:39:36.014436+00:00 |
| Job | e26eec3c8595a4a98a5ec74a7c18757773483d01d8f82ba33727c63be5f85d1a |
| Chapter / page | 276880 / 1 |
| Provider / model | Gemini API / gemini-2.5-flash |
| Preflight | READY_UNVERIFIED |
| Request state | RESPONSE_RECEIVED |
| HTTP attempt / response | true / true |
| HTTP status | 403 |
| Error code / category / reason | ACCESS_DENIED / ACCESS / PERMISSION_DENIED |
| Request attempt ID | 0d8666d4d28c4371a99d1082c2847b5c |
| Batch ID | 2466b62cf92cc5a8a95e7a6bf904c671c6487124360ba653ff6366db027ebb6e |
| Pending / checkpoint / cache | 109 / paused_provider / RETAINED |
| Retry-After | null |

Timestamp diagnostic là thời điểm ghi/quan sát, không phải timestamp phía server.
Source đặt RESPONSE_RECEIVED ngay khi `client.post` trả response object, trước
khi đọc body: `providers/gemini_api.py:148–152`. HTTP 403 sau đó đi qua nhánh
status khác 200 tại dòng 168–185. Vì vậy sự kiện này có bằng chứng response thật,
không chỉ là tên lỗi trong enum, preflight hoặc journal cũ.

| UTC cùng ngày | Bằng chứng và giới hạn |
|---|---|
| 10:28:55 | Dòng 1: FREE_TIER_UNCONFIRMED; không có HTTP metadata. |
| 11:50:21 | Dòng 2: ACCESS_DENIED; chưa có HTTP metadata. Không hồi tố coi đây là 403 đã chứng minh. |
| 14:38:41 | Hai SAVED_ERROR do người dùng quan sát trên GUI. Không có record SAVED_ERROR tương ứng trong diagnostic đã rà. |
| 14:39:36 | Dòng 3: response HTTP 403 và attempt ID cụ thể như bảng trên. |

`ui/provider_notice.py:152–153` tạo SAVED_ERROR bằng thông báo local với
`origin=journal`; không gọi provider. Các nhánh restore ở
`ui/comic_sources.py:393`, `ui/main_window.py:631` có thể gọi thao tác này.
Nhật ký panel là QPlainTextEdit trong bộ nhớ. Không xác định được chính xác
nhánh nào đã tạo hai dòng người dùng thấy; **không tính chúng thành hai request**.
Một attempt ID được xác minh trong record mới; không suy tổng số request của
tài khoản hoặc mọi lần chạy từ đó.

## B. Thông tin lỗi Google đã lọc

FACT_CONFIRMED: reason lưu được là **PERMISSION_DENIED**. Không lưu Google
`message`, toàn bộ `details`, `ErrorInfo.metadata`, hoặc riêng `error.status` và
`ErrorInfo.reason`. Không có raw response/header/prompt/OCR trong record này.
`error_message` cấp ngoài là câu tĩnh của logger, không phải message gốc Google.

`providers/gemini_diagnostics.py:51–64` ưu tiên reason thuộc allowlist từ tối đa
16 ErrorInfo; nếu không tìm được thì lấy status thuộc allowlist. Do đó:

- Không xác định được PERMISSION_DENIED đến từ status hay ErrorInfo.reason.
- Một reason chi tiết không thuộc allowlist có thể đã bị bỏ rồi dùng status chung.
- Không thấy SERVICE_DISABLED hoặc API_KEY_*_BLOCKED trong record **không đủ
  để loại trừ** API bị tắt hoặc hạn chế key.
- Không có dữ liệu để khôi phục nguyên văn message/details; không dựng lại chúng.

`core/diagnostics.py:77–84` lọc lần nữa, chỉ giữ metadata cho phép và thay message
bằng câu tĩnh. Đây là giới hạn quan sát hiện tại, không phải bằng chứng Google
không trả thông tin chi tiết.

## C. Endpoint, authentication và mapping

Đọc source hiện tại, không gọi endpoint:

| Mục | Cấu hình thực tế |
|---|---|
| URL | https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent |
| HTTP method / API version | POST / v1beta |
| Authentication | Header x-goog-api-key lấy từ GEMINI_API_KEY của process lúc gọi; không đặt key vào query |
| Route | Gemini Developer API REST; không phải Vertex AI hoặc phiên AGY/OAuth |
| Payload | systemInstruction, contents chứa JSON ID/văn bản/context, generationConfig |
| Structured output | application/json, responseJsonSchema translations gồm id/text; candidateCount=1 |
| Generation | temperature=0, maxOutputTokens=32768, thinkingBudget=0 |
| Tools | Không khai báo tools/function calling/search |
| Transport | requests.Session; TLS verify=true, allow_redirects=false; response tối đa 1 MB |
| Giới hạn | Payload 128 KiB; timeout hữu hạn; request budget hiện có |
| Retry/fallback | retry_count=0; không có vòng replay, đổi model/provider trong provider |

Vị trí: `providers/gemini_api.py:20`, `:101–151`, `:163–198`. Header chứa key
không được đọc/in/ghi lại trong cuộc điều tra. Không xác định project của key
từ tên biến môi trường; không tìm key trong registry, file hoặc tiến trình khác.

HTTP 403 được ánh xạ ACCESS_DENIED tại dòng 170. HTTP 401, 404, 429 và exception
Timeout/RequestException có nhánh riêng. Không tìm được mapping timeout/429
thành ACCESS_DENIED. Preflight thiếu key hoặc Free tier chặn trước client.post
với mã khác. Numeric/glossary guard chạy sau phản hồi dịch hợp lệ, không sinh
HTTP 403. Không có sửa source được chứng minh là cần thiết để đổi endpoint,
authentication, schema hoặc guard trong lượt này.

Chứng cứ mạnh nhất là client đã nhận response 403 trên đường gọi endpoint Google
cấu hình sẵn, TLS verification bật. Diagnostic không có TLS peer/certificate hay
route proxy, nên không phải packet capture xác minh mọi trung gian mạng. Không
kết luận project/key/model được Google cấp quyền chỉ vì nhận được response.

## D. Nguyên nhân đã chứng minh và giả thuyết

| Nhận định | Mức bằng chứng | Kết luận |
|---|---|---|
| Response HTTP 403 khiến provider tạm dừng | FACT_CONFIRMED | Record mới + vị trí observer/mapping trong source. |
| Lỗi mới chỉ là preflight hoặc journal cũ | FACT_CONFIRMED | Loại trừ cho record 14:39:36 có attempt/response cụ thể. SAVED_ERROR vẫn độc lập. |
| Đây là lỗi quyền nguồn Kuaikan | FACT_CONFIRMED | Record thuộc translation provider Gemini API; không phải source denial. |
| Google từ chối quyền trên đường generateContent | INFERENCE | Phù hợp endpoint/TLS, status và reason; không có message chi tiết. |
| API disabled / service restriction | NOT_PROVEN | Không giữ ErrorInfo chi tiết/metadata. |
| Key bị giới hạn website/IP/API hoặc bị chặn | NOT_PROVEN | Không có key restriction metadata. |
| Key thuộc project khác | NOT_PROVEN | Không có project identity của key trong bằng chứng. |
| Thiếu quyền project/model, điều khoản hoặc điều kiện vùng | NOT_PROVEN | PERMISSION_DENIED chung không phân biệt được. |
| Free tier gây chặn / phải bật billing | NOT_PROVEN | Không có reason chứng minh; không đề xuất bật billing. |
| Hết quota ngày / rate limit | NOT_PROVEN | Record này là 403, không phải 429/QuotaFailure; không suy quota từ việc pause. |
| Payload/schema sai là nguyên nhân cụ thể | NOT_PROVEN | Không có message xác nhận; không sửa schema để thử vận may. |

Nguyên nhân trực tiếp đã rõ: **response 403 làm provider fail closed và giữ
pending**. Nguyên nhân quyền cụ thể sâu hơn vẫn chưa chứng minh. Free tier và
quota hiện trên AI Studio do người dùng quan sát không thay thế quyền thực thi
generateContent. Hướng dẫn Google cũng yêu cầu kiểm tra quyền key và project
khi gặp lỗi truy cập: [Gemini API errors](https://ai.google.dev/gemini-api/docs/api-errors).

Đây là lượt GUI của chương production, **không phải** smoke ba chuỗi tổng hợp
do Codex thực hiện. Giữ nguyên lịch sử báo cáo smoke bị KEY_MISSING với 0 request;
không dùng sự kiện GUI để đánh dấu smoke PASS hoặc khẳng định đã dùng ngân sách đó.

## E. Kiểm tra thêm trong Console — chỉ đọc

Không cần gửi request API để thực hiện các bước đối chiếu giao diện sau:

1. Google AI Studio → API keys/Projects: chọn project hiện hữu
   `image-translator-vn`; đối chiếu **project ID/number**, tên hiển thị của key
   và trạng thái/cảnh báo. Không sao chép key hoặc ảnh chụp có key.
2. Google Cloud Console, cùng project → APIs & Services → Enabled APIs & services:
   xem Generative Language API (`generativelanguage.googleapis.com`) có được
   bật không. Chỉ ghi nhận; chưa thay đổi service.
3. APIs & Services → Credentials → key hiện hữu: đọc API restrictions có cho
   Generative Language API không; đọc application restrictions có phù hợp
   desktop HTTP không (website/mobile/IP). Đây là hai lớp giới hạn riêng theo
   [Manage API keys](https://docs.cloud.google.com/docs/authentication/api-keys).
   Không bỏ mọi restriction hoặc giả Referer để vượt chặn. Google nêu ví dụ
   restriction chỉ cho website AI Studio có thể ngăn automation dùng key:
   [Google Cloud — securing API keys](https://cloud.google.com/blog/topics/developers-practitioners/api-keys-are-open-secrets).
4. AI Studio: xem thông báo quyền model/project, điều khoản, vùng và cảnh báo
   bảo mật hiện có; không suy chúng từ quota. Các điều kiện truy cập được nêu ở
   [Troubleshoot Google AI Studio](https://ai.google.dev/gemini-api/docs/troubleshoot-ai-studio).
5. Nếu project **đã có** log phù hợp: lọc khoảng 14:39:36 UTC, service trên,
   method GenerateContent và status 403. Khả năng có log phụ thuộc cấu hình;
   không hứa chắc tồn tại, không bật telemetry/billing/quyền mới. Chỉ cung cấp
   mã status/reason/service đã lọc; không gửi request body/header/key.

Nguồn Google công khai được tra cứu ngày 08/11/2026; không truy cập tài khoản
hoặc Console của người dùng. Nếu chưa có reason cụ thể, giữ nguyên key/model/
billing và chưa resume production. Không yêu cầu tạo key mới hoặc cấp Owner.

## F. Sửa tối thiểu, kiểm thử và bảo toàn

**Không sửa production source**: chưa có bằng chứng bug authentication/mapping
hoặc nguyên nhân cấu hình cụ thể để sửa. Không thay numeric/glossary/AGY guard,
cache namespace, journal, checkpoint hoặc logic resume.

Đề xuất cho nhiệm vụ riêng nếu Console không giải thích được: diagnostic tách
`google_error_status` và allowlisted `ErrorInfo.reason`, cờ có details/unknown
reason và enum service đã lọc; không lưu raw message/body/metadata tùy ý. Cần
test redaction/bounds trước khi áp dụng. Không triển khai đề xuất trong lượt này.

Local/mock bằng Python dự án, Qt offscreen:

- `tests/test_access_diagnostics_chapter_ui.py`
- `tests/test_gemini_api.py`

**60 PASS / 0 FAIL / 0 SKIPPED**, JUnit ghi thời gian 2.059 giây. Cài audit hook
chặn socket.connect/socket.getaddrinfo; test dùng fake HTTP/fixture QA, không
gọi dịch vụ thật. Bao gồm HTTP mapping, metadata/redaction, preflight, cache,
pipeline và GUI workflow. Đây không phải nghiệm thu dịch Online thật.
Full pytest/unittest và E2E production **NOT_TESTED trong lượt forensic** vì
không đổi source; không lấy baseline 454 PASS lịch sử làm kết quả mới.

Snapshot mới trước điều tra gồm **2.500 file**; đối chiếu sau test:
**2.500/2.500 giữ nguyên SHA-256**, 0 thay đổi, 0 thiếu. Gồm dữ liệu production
đã kiểm kê: nguồn/output/cache/SQLite/journal/receipt/config/models/BAT/spec và
**bốn EXE**. Dùng baseline mới, không so với snapshot trước các thao tác GUI hợp
lệ do người dùng đã thực hiện. Evidence:
`logs/http403-forensic-20261108T144556Z/` gồm protected-before.json,
preservation.json, git-before.json, matches.json, local-mock-tests.xml.

Điều tra này: **0 request API**, không retry/fallback, không resume, không sửa
DB/journal/output, không tải ảnh/model, không cài dependency hoặc build EXE.

## G. Git & Fork Handoff

- Root `D:/TransTool`, branch `main`, HEAD
  `9e20d094e70b2de78762e15b5e7bec7157a0527b`.
- Baseline: PROJECT_STATUS.md và docs/TROUBLESHOOTING.md đã modified;
  docs/STAGE3D3_GEMINI_API_LIVE_SMOKE_REPORT.md đã untracked từ nhiệm vụ trước.
  Không có staged file hoặc conflict; giữ nguyên thay đổi trước.
- Lượt này: thêm báo cáo forensic này; bổ sung status và troubleshooting.
  Không sửa báo cáo smoke lịch sử hoặc source/test/config.
- `.gitignore` giữ nguyên. logs/cache/output/config private/.venv/dist/model
  weights được ignore; source/tests/docs/spec/config mẫu vẫn nhìn thấy. Không
  có runtime dưới cache/logs/output/dist/.venv đang track theo ls-files đã rà.
- File nên review/commit cho nhiệm vụ này: báo cáo forensic, phần bổ sung
  PROJECT_STATUS.md và docs/TROUBLESHOOTING.md. Hai file sau có cả thay đổi cũ,
  cần xem từng hunk; báo cáo smoke untracked là công việc trước, review riêng.
- Không commit evidence runtime/log, ảnh, DB, journal, cache, model, .venv,
  credential hoặc EXE. Danh sách cuối và diff --check ghi trong git-after.json
  ở thư mục evidence; không stage để kiểm tra.
- Kiểm tra cuối: `git diff --check` exit 0; không staged/conflict, HEAD/branch
  không đổi. Status có hai tài liệu modified và hai báo cáo untracked như
  mô tả trên. `.gitignore` không đổi; check-ignore xác nhận runtime bị bỏ qua,
  provider/test/báo cáo mới/spec/BAT/config mẫu không bị che. Rà bốn tài liệu
  review bằng mẫu Google key/Bearer/private-key không có kết quả nghi ngờ;
  đây là kiểm tra mẫu có giới hạn, không phải bảo đảm mọi loại secret.
- Trong Fork: mở D:\TransTool → Local Changes → review từng file/hunk → chỉ stage
  tài liệu cần thiết → xem staged diff → tự commit khi hài lòng.
- Commit đề xuất: `docs(gemini): diagnose confirmed HTTP 403 permission denial`.

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT**
