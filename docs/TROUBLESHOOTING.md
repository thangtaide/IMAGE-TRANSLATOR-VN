# Tra cứu lỗi ảnh — Stage 1–2

## Stage3J — preflight pause và log chỉ khi lỗi (chưa kiểm thử)

- `AGY_AUTOMATIC_EXTENSIONS`: factory dừng ở cấp provider; phần pending không
  được xuất Origin hoặc đánh dấu done. GUI báo pause, chưa gửi OCR để dịch.
  Guard và file hooks/MCP giữ nguyên; quota nhiều không thay điều kiện này.
- Các lỗi AGY_NOT_FOUND/MODEL/CAPABILITY/INITIALIZATION cũng đi qua suspension
  tại factory. Capability probe có thể đã chạy trước lỗi capability; chỉ mã
  hooks/MCP mới chứng minh chặn trước mọi CLI. Xem process_started/role.
- Whole mới kiểm tra guard sau xác nhận nhưng trước chốt budget, constructor
  vẫn recheck. Workspace lịch sử đã agy_attempt_used=true không được reset.
  Dùng thao tác **Dịch lại toàn bộ chương** để tạo lượt mới, không sửa journal.
- TIMEOUT không phải quota: giữ deadline90s Batch/600s Whole. Metadata ghi
  elapsed, exit code nếu quan sát được, nguồn CLI_TIMEOUT và backend UNKNOWN.
  Partial stdout/stderr nhận được có thể lưu mã hóa, không coi là terminal hoàn chỉnh.
- Parser/ID/tool-use hoặc numeric/glossary rejection vẫn bị chặn như cũ. Có
  evidence lỗi để điều tra, không nới guard hoặc tự gửi lại.
- Đường log: logs/diagnostics/agy_errors/<attempt_id>/. metadata.json và
  outcome.json là metadata; stdout.raw.dpapi/stderr.raw.dpapi nếu có là raw
  **mã hóa**, cần đúng ngữ cảnh Windows CurrentUser để giải mã. Không đổi đuôi
  rồi coi như plaintext. Không có bytes thì không tạo file giả; response từ
  stdout chỉ tham chiếu cùng artifact, không lưu bản trùng.
- `AGY_RAW_EVIDENCE_INCOMPLETE`, `AGY_EVIDENCE_WRITE_FAILED` hoặc
  `AGY_EVIDENCE_STORE_FULL`: lỗi gốc vẫn giữ. Raw có thể chưa lưu; kiểm tra
  not_saved/partial/captured_bytes/observed_bytes. Kho tối đa64MB và giới hạn
  số entry; không tự xóa log cũ. Quyền/DPAPI không xác minh được thì metadata-only.
- Không gửi raw/config/command/token ra ngoài. Yêu cầu Codex điều tra theo
  attempt ID/job ID trước; chỉ đọc raw khi người dùng chủ động cho phép.
- Fresh Batch: dùng cache/staging/output riêng; nếu cache mới đã tồn tại thì
  fail closed, không dùng lại MT. Resume lượt mới qua cache_root đã lưu, không
  quay sang manifest276880 lịch sử. Fresh chỉ hỗ trợ một chương đã chọn/lượt.

Các hành vi mới chưa được chạy; không có test PASS mới. Xem
[báo cáo Stage3J](STAGE3J_AGY_PREFLIGHT_AND_FRESH_RERUN.md).

## Stage3I — AGY_AUTOMATIC_EXTENSIONS / 109 ảnh Origin

Đã điều tra thật từ dữ liệu lưu, không gọi AGY hoặc chạy test. Guard dùng
`%USERPROFILE%\.gemini\config\hooks.json` và `mcp_config.json` cấp người dùng;
không phải file source trong project hoặc settings riêng từng invocation.
Tại lúc điều tra hooks.json có cấu trúc khai báo sự kiện với5trường command;
JSON hợp lệ nhưng không có key hooks cấp đầu, guard xét object không rỗng và
chặn. Không chứng minh lệnh đã thực thi; không đủ cơ sở coi là metadata vô hại.
Không sửa guard hoặc tự đổi cấu hình này. MCP file hiện rỗng.

1. Không sửa/xóa/đổi tên file để lách kiểm tra, không thêm `hooks: {}` bên
   cạnh khai báo hook thực. Không mở quyền file/shell/MCP hoặc đổi model/key.
2. Người dùng có thể sao lưu riêng hai file cấu hình rồi kiểm tra các hook
   Stop/PreToolUse/PostToolUse và các sự kiện còn lại bằng cơ chế cấu hình
   chính thức mà AGY hỗ trợ. Không gửi command/token/config thô vào báo cáo.
3. Chỉ thử lại khi đã chủ động tắt các hook/MCP tự động thực sự và có thể xác
   minh schema an toàn. Chưa kiểm chứng cách tắt hoặc profile cách ly của AGY
   trong nhiệm vụ này. Nếu vẫn cần hooks cho công việc khác/không xác minh
   được, giữ BLOCKED và dùng Offline do người dùng tự chọn; không bypass.
4. Whole bị chặn đã có `agy_attempt_used=true` dù chưa tạo subprocess dịch.
   Đây là ngân sách đã chốt, không phải bằng chứng quota đã tiêu thụ. Không
   sửa journal/reset cờ. Sau khi cấu hình an toàn, nếu muốn thử AGY thì người
   dùng chủ động chuẩn bị workspace mới và xác nhận mới; lượt cũ vẫn giữ.
5. 109 ảnh Origin của chapter276880 là job mới: lỗi constructor local đi vào
   fallback từng trang. Không có bản dịch/MT validation nào thành công trong
   lượt đó, không phải109request. COMPLETED_WITH_WARNINGS chỉ đủ file dự phòng.
6. 59 output và44target cache của job timeout cũ vẫn còn/khớp hash. Nhưng
   manifest hiện trỏ journal mới109fallback. Không tự sửa pointer/hash hoặc
   resume mù để "khôi phục"59trang. Cần phương án phục hồi riêng, kiểm tra
   receipt và yêu cầu chủ động trước khi chạy production.

Không sửa source hoặc cấu hình trong Stage3I. Nếu muốn đổi lỗi preflight AGY
thành pause một lần thay vì xuất fallback mọi trang, đó là thay đổi hành vi
cần hotfix/kiểm thử riêng, không phải tắt guard. Xem
[forensic Stage3I](STAGE3I_AGY_BLOCK_AND_ORIGIN_FORENSIC.md).

## Stage3H — Whole từ provider chính và TIMEOUT trang60

- Không thấy lựa chọn Toàn chương: mở `run_source.bat`, kiểm tra dropdown Dịch;
  EXE cũ chưa được build lại. Chọn **AI Gemini AGY — Batch** và **Toàn chương
  (1 lần)** là hai đường riêng. Whole không nằm trong Auto Fallback.
- Nút Chuẩn bị chưa bật: chọn đúng một chương; đợi tác vụ nguồn kết thúc.
  Chỉ phân tích link/chương không tự tải ảnh hoặc dịch. Chuẩn bị dùng cache
  hợp lệ, hoặc tải qua gate nếu chưa có cache; không có quyền thì báo lỗi nguồn.
- `WHOLE_SOURCE_ACCESS_DENIED` / `WHOLE_SOURCE_DOWNLOAD_NOT_ALLOWED`: lỗi nguồn
  truyện/điều kiện tải, không phải quota AGY. Không vượt login/VIP/paywall.
- `WHOLE_SOURCE_CACHE_INCOMPLETE` / `WHOLE_SOURCE_CACHE_CHANGED`:
  cache chưa xác minh đầy đủ hoặc hash không khớp; giữ dữ liệu để kiểm tra.
  Không sửa manifest/hash hoặc xóa cache để ép tiếp tục.
- `WHOLE_INPUT_CHANGED` / `WHOLE_INPUT_CONTEXT_CHANGED`: ảnh hoặc nguồn khác
  lượt đã lưu; không dùng receipt nhầm chương. Kết quả cũ vẫn được giữ.
- Mở lượt cũ không gọi AGY. Bấm Tiếp tục để kiểm tra; nếu cần bản dịch mới thì
  phải xác nhận riêng. `WHOLE_AGY_ATTEMPT_ALREADY_USED` không được tự retry.
- Kết quả Whole ở thư mục riêng; bảng/tổng kết Batch cũ không tự đổi thành done.
  Không chạy lại toàn chương chỉ để sửa con số hiển thị của Batch.

TIMEOUT `2026-11-09T05:01:21Z` thuộc **Batch** chapter276880: timeout subprocess
90s, 24 trang có chữ trong khoảng60–102, 39 vùng/226 ký tự, generation ordinal2.
59/109 output/receipt còn nguyên, pending60–109. Không có bằng chứng hết quota.
Pacing5–10s diễn ra trước subprocess, không thuộc đồng hồ90s. Không tự tăng
timeout hoặc gửi lại để xác minh. Raw terminal không được lưu nên chưa biết
vì sao CLI chưa kết thúc. Xem [forensic Stage3H](STAGE3H_MAIN_UI_AND_TIMEOUT_FORENSIC.md).
Stage3H chưa chạy test/GUI/AGY; người dùng tự nghiệm thu.

## Stage3G — AGY Whole Chapter (chưa kiểm thử)

- `WHOLE_AGY_CONFIRMATION_REQUIRED`: chưa có xác nhận gắn với manifest hiện
  tại. Chuẩn bị lại manifest rồi dùng nút xác nhận riêng; không sửa journal.
- `WHOLE_AGY_ATTEMPT_ALREADY_USED`: ngân sách workspace đã chốt, thiếu response
  hợp lệ. Không biết chắc process đã gửi/tiêu quota hay chưa; không tự gọi lại.
- `WHOLE_AGY_RESPONSE_CHANGED`, `WHOLE_AGY_BINARY_CHANGED`: hash response/binary
  không khớp; giữ artifact, không bỏ kiểm tra hoặc sửa hash để ép chạy.
- `WHOLE_AGY_NEW_WORKSPACE_REQUIRED`: AGY cần workspace Stage3G mới, không đổi
  translator của journal Argos Stage3F để sử dụng lại kết quả khác provider.
- `WHOLE_COMMAND_LIMIT`, `WHOLE_PAYLOAD_LIMIT`: argv/schema quá30kUTF16 hoặc
  stdin vượt16MB local; không cắt OCR/chia batch tự động. Backend context limit
  thực tế vẫn chưa xác minh. Output1MB/vùng4.000ký tự vẫn có thể bị chặn.
- `AGY_START_FAILED`, `AUTH_REQUIRED`, `ACCESS_DENIED`, `MODEL_UNAVAILABLE`,
  `CLI_EXIT_ERROR`, `EMPTY_RESPONSE`: xem mã cụ thể, không tự đổi model/key hoặc
  coi mọi lỗi là quota. Không đăng nhập/thay config AGY tự động.
- `INVALID_RESPONSE` có thể do JSON/ID/tool-use guard; không chứng minh tool
  invocation thật hoặc hết quota. `NUMERIC_MISMATCH` vẫn bị từ chối như cũ.
- `TIMEOUT`/Cancel: dữ liệu OCR/receipt được giữ; không biết quota có bị tiêu
  thụ không. Nếu có response đã lưu, có thể validation/render local khi chủ
  động Tiếp tục; thiếu response sau budget chốt thì không gửi lại.

Batch AGY thường có dòng Đang chờ trước batch tiếp theo với countdown. Đây là
pacing5–10giây, không phải retry/quota reset. Rate/quota/permission lỗi vẫn
dừng. Các thay đổi Stage3G chỉ được đọc diff/AST, chưa có kết quả test mới.

## Stage3F — Whole Chapter Translation offline

- `awaiting_translation`: OCR/manifest đã có; chưa được cho phép dịch phần còn
  thiếu trong lượt này. Đây không phải quota. Kiểm tra rồi tích cho phép Argos
  và bấm Tiếp tục QA; không tự chuyển provider.
- `MISSING_MODEL`: thiếu model Argos cục bộ. Job không tải model hoặc fallback
  Online. Có thể tiếp tục kiểm thử cấu trúc bằng mock trong QA.
- `WHOLE_RESPONSE_IDS*`, `WHOLE_JSON_INVALID`, `WHOLE_RESPONSE_SCHEMA`: mock
  response sai/thiếu/trùng/lạ ID, target rỗng hoặc JSON bị cắt. Không render khi
  cả chương chưa đủ bản dịch đã qua guard; không tự retry.
- `NUMERIC_MISMATCH`: numeric guard hiện có từ chối. Không tự sửa số hoặc nới
  guard để xuất. Các vùng đã xác nhận trong QA vẫn được giữ để xem lại.
- `WHOLE_MANIFEST_CHANGED`, `WHOLE_ARTIFACT_CHANGED`, `WHOLE_SOURCE_CHANGED`,
  `WHOLE_RECIPE_OR_SOURCE_CHANGED`, `WHOLE_OCR_RECEIPT_CHANGED`: dữ liệu/hash/
  recipe không khớp. Giữ nguyên QA artifacts, nguồn và output; không sửa hash
  bằng tay để ép resume. Dùng lượt QA mới nếu chủ động thay nguồn/cấu hình.
- `WHOLE_TRANSLATION_RECEIPT_CHANGED`: bản dịch đã xác nhận khác receipt. Không
  dùng bản đã thay đổi để render, không ghi đè ảnh đã hoàn thành.
- `WHOLE_JOB_ACTIVE`: đã có whole job trong ứng dụng hoặc workspace đang được
  tiến trình khác khóa. Chờ job dừng; không xóa lock file để tranh quyền ghi.
- `WHOLE_QA_WORKSPACE_REQUIRED`, `WHOLE_QA_SYMLINK_FORBIDDEN`: đường dẫn không
  thuộc `output/stage3f-…` hoặc có symlink. Không dùng cache/output production
  làm workspace. Giữ các artifact liên quan để điều tra.
- `RESUME_RECEIPT_CHANGED`/`RESUME_PUBLICATION_CHANGED` trong render: output cũ
  không khớp receipt. Pipeline giữ file cũ; không xóa DB/journal để ép ghi đè.

Chi tiết kiến trúc, kiểm thử và giới hạn AGY:
[STAGE3F_WHOLE_CHAPTER_OFFLINE_REPORT.md](STAGE3F_WHOLE_CHAPTER_OFFLINE_REPORT.md).

## Gemini API — HTTP403 đã xác minh ngày08/11/2026

Diagnostic lúc14:39:36UTC của chapter276880 xác nhận RESPONSE_RECEIVED/403 với
reason PERMISSION_DENIED. Đây là lỗi response của translation provider;
SAVED_ERROR chỉ hiển thị trạng thái đã lưu, không chứng minh thêm request.
Reason chung chưa xác định API disabled, restriction của key, quyền project
hay model: message/details không được lưu. Không bật billing, thay key/model
hoặc resume production chỉ dựa vào mã này.

Đối chiếu project ID/number trong AI Studio và Cloud Console; chỉ đọc trạng
thái Generative Language API và API/application restrictions của key hiện hữu,
không chia sẻ key. Xem các bước và giới hạn bằng chứng trong
[STAGE3D3_HTTP403_FORENSIC_REPORT.md](STAGE3D3_HTTP403_FORENSIC_REPORT.md).
Cuộc điều tra không gọi API; kết quả này không thay thế smoke tổng hợp đang
bị chặn vì environment QA thiếu key trong báo cáo lịch sử.

## Stage3D.3 — GUI có key nhưng QA/Codex báo API_KEY_MISSING

Biến môi trường được kế thừa theo tiến trình. Key xuất hiện trong GUI không
chứng minh tiến trình QA của phiên Codex hiện tại cũng thấy biến đó. Lượt smoke
Stage3D.3 đã dừng trước HTTP vì key_present=false trong chính interpreter QA;
không phải lỗi Google403, key bị từ chối hoặc model không khả dụng.

Kiểm tra cách cấu hình GEMINI_API_KEY bằng cơ chế môi trường Windows phù hợp,
mở phiên terminal/ứng dụng cha mới rồi khởi chạy lại Codex. Không dán key vào
chat, source, config Git, log hoặc báo cáo. Không cần gửi key/prefix/hash để
Codex so sánh. Codex không tự tìm key trong file nhạy cảm, registry hoặc kho
credential để vượt bước này.

Sau khi khởi chạy đúng môi trường, chỉ kiểm tra presence/preflight cục bộ trước.
Ngân sách1request đã duyệt trong Stage3D.3 **chưa được sử dụng**; không resume
production để thử key. Khi có thể chạy smoke, phải hoàn tất guard một request,
không retry, không fallback và chỉ gửi3câu tổng hợp đã duyệt. Nếu chưa có key,
tiếp tục dừng trước mạng; không thay model/billing để thử vận may.

## Stage3D.2 — ACCESS_DENIED và bằng chứng request

Tại runtime chương276880, có diagnostic ACCESS_DENIED mới lúc18:50:21 ngày
08/11/2026; config/journal mới đã Free=true. Source chỉ ánh xạ403 thành mã này,
nhưng log lịch sử chưa lưu HTTP status/attempt/response fields. Có suy luận
mạnh từ code về nhánh403, chưa có bằng chứng độc lập về response hoặc lý do
quyền bị từ chối. Không tự kết luận hết quota, sai key/project, region hay model
eligibility. Không yêu cầu bật billing hoặc tạo key mới chỉ từ mã lỗi đó.

Diagnostic mới có nhóm `gemini_api_request`, không raw request/response/OCR:

| request_state | Có thể kết luận |
|---|---|
| NOT_ATTEMPTED | Attempt hiện tại dừng trước HTTP; không suy các lượt trước. |
| ATTEMPT_STARTED | Client đã gọi HTTP; chưa chứng minh Google đã nhận hoặc đã trả response. |
| RESPONSE_RECEIVED | Client đã nhận response/header status; xem http_status và reason allowlist. |
| UNKNOWN | Không có đủ metadata; không đồng nghĩa chưa gửi. |

HTTP status giữ riêng code lỗi:401 AUTH_REQUIRED,403 ACCESS_DENIED,404 model,
429 rate/quota. Timeout đọc body vẫn có thể ghi nhận status đã nhận trước đó;
không đổi nó thành ACCESS_DENIED. Quota ngày chỉ theo QuotaFailure/PerDay cũ.
`error_reason` chỉ giữ enum trong allowlist, không phải toàn bộ thông báo Google;
UNSPECIFIED nghĩa chưa biết. Model/status/attempt ID/batch ID không chứa key.

Nếu báo **Công việc có lỗi đã lưu**, đó là lịch sử; khôi phục cấu hình chưa tạo
request mới. Nếu banner chỉ **Gemini API chưa thể tiếp tục**, hãy đọc Chi tiết,
không suy có403 từ chữ ACCESS_DENIED. HTTP403 được xác minh vẫn chưa giải thích
vì sao tài khoản bị từ chối: kiểm tra quyền model/project trên AI Studio, không
mặc định có lỗi billing hoặc cần thay key. Key đọc từ môi trường tiến trình;
ứng dụng không thể xác nhận key thuộc project nào bằng cách nhìn chuỗi key và
không lưu/hiển thị key hoặc prefix để đối chiếu.

Lỗi source adapter có nhãn riêng **Nguồn truyện từ chối truy cập**. Không vượt
login/VIP/paywall/CAPTCHA hoặc né401/403/429. Nút phân tích chương nằm trên bảng,
không còn trong cache/nâng cao; tooltip giải thích thiếu selection/busy/giới hạn
1–10. Dán URL hoặc discovery không tự tải/dịch. Stage3D.2 chỉ dùng mock/Qt QA;
Gemini API thật vẫn cần QA nhỏ được duyệt riêng, không lấy chương production
đang pause làm phép thử tự động.

## Stage3D.1 — phân biệt preflight với lỗi dịch

| Trạng thái | Đã xác minh / cách xử lý |
|---|---|
| API_KEY_MISSING | Không thấy key trong môi trường; không phải HTTP401. Đặt GEMINI_API_KEY rồi mở lại app, không gửi key trong log. |
| FREE_TIER_UNCONFIRMED | Flag cấu hình false. Bấm Mở Cài đặt Gemini API, tự kiểm tra project ở AI Studio, xác nhận chỉ khi đúng rồi chủ động tiếp tục. |
| READY_UNVERIFIED | Đủ key presence/xác nhận cục bộ; chưa xác minh mạng, billing, quyền model hoặc quota. |
| PAUSED_BY_USER | Người dùng bấm Pause; worker dừng tại checkpoint, không tự đổi phương thức. |
| AUTH_REQUIRED / ACCESS_DENIED | Lỗi remote401/403; không gộp với thiếu thiết lập trước HTTP. |
| INVALID_RESPONSE: Unexpected tool use (AGY) | Guard/parser AGY từ chối. Chưa đủ chứng cứ invocation thật hay metadata; không gọi là quota. Không nới guard. |

Ví dụ runtime xác minh Stage3D.1: job e26eec3c…/chapter276880 bị chặn
FREE_TIER_UNCONFIRMED tại trang1 lúc17:28:55 ngày08/11/2026. Settings và hai
journal đều false, journal109pending/0done,35trang ocr_ready. Lần gọi gây lỗi
đi vào nhánh trước HTTP; không thể gọi đó là Gemini dịch thất bại. Không suy
key hợp lệ hoặc quota còn chỉ vì key đã có; không tổng quát thành mọi lần chạy
lịch sử đều0request vì chưa có bộ đếm lịch sử đầy đủ.

Thông báo mới không dùng nguyên raw detail/response để hiển thị. Bằng chứng
`local_preflight/request_sent=false` chỉ áp dụng thao tác chưa khởi chạy worker;
`provider_preflight/current_batch` chỉ nói batch đó dừng trước HTTP. Thiếu bằng
chứng thì thông báo trung lập. Quota/rate/auth/timeouts vẫn giữ code riêng.

Khôi phục job cũ không được lấy flag Free=false trong journal ghi đè xác nhận
mới hoặc phương thức đang chọn. Bản sửa chỉ merge PROVIDER_FIELDS như luồng
source resume, giữ OCR/render/receipt/recipe cũ; không migration journal.
Nếu recipe/source/receipt không hợp lệ, tiếp tục bị chặn như trước.

Các mục Stage3D dưới đây là lịch sử triển khai. Hiện ô xác nhận nằm ngay đầu
Cài đặt, provider phụ ở phần nâng cao và các nút ít dùng nằm trong menu Thêm.

## Stage3D — Gemini API REST

Key chỉ lấy từ `GEMINI_API_KEY`. Không gửi key/log chứa key cho người khác.
Chỉ báo presence; không gọi API khi mở app hoặc chọn phương thức.

| Mã | Ý nghĩa và thao tác |
|---|---|
| FREE_TIER_UNCONFIRMED | Chưa xác nhận project Free/không billing trong Cài đặt. Kiểm tra AI Studio trước khi tích. Không có API tự kiểm tra billing trong ứng dụng. |
| AUTH_REQUIRED | Thiếu key hoặc HTTP401; kiểm tra biến môi trường, mở lại app. |
| INVALID_REQUEST | Cấu hình/payload không hợp lệ hoặc HTTP400; không tự retry. Key lỗi cũng có thể được Google trả HTTP400. |
| ACCESS_DENIED | HTTP403; kiểm tra quyền key/project/khu vực. Không đổi endpoint để né. |
| MODEL_UNAVAILABLE | HTTP404; 2.5 Flash có thể không được cấp cho project. Không tự đổi model; cần QA/quyết định riêng. |
| RATE_LIMITED | HTTP429 chưa đủ bằng chứng quota ngày; xem AI Studio, không tự đoán thời gian reset. |
| QUOTA_EXCEEDED | HTTP429 kèm QuotaFailure/quotaId PerDay; dừng, không mua thêm. |
| REQUEST_BUDGET | Đạt budget cục bộ, mặc định64lượt/phiên, không phải quota Google. |
| PROVIDER_UNAVAILABLE | HTTP5xx/response khác200; không tự chuyển provider/model hoặc retry. Redirect không được theo. |
| NETWORK_ERROR / TIMEOUT | Kết nối/TLS/proxy hoặc timeout. Giữ cấu hình mạng do môi trường quản lý. |
| INVALID_RESPONSE / RESPONSE_BLOCKED | JSON/ID không hợp lệ hoặc candidate không STOP (gồm truncated/safety); giữ pending, không render. |
| UNEXPECTED_TOOL_USE | Có part ngoài text, gồm functionCall hoặc metadata chưa hỗ trợ; fail closed. Không chứng minh công cụ đã được thực thi. |

HTTP status được giữ trong exception provider; thông báo và diagnostic chỉ dùng
mã/static message, không lưu body lỗi/URL chứa key. Token usage chỉ lấy các bộ
đếm số nguyên allowlist. Không nhầm thông báo usage với bản dịch đã validation.
Lỗi số vẫn theo `literal-numbers-v2-signed`: không nới guard cho provider API.

Cancel/pause được kiểm tra trước request và trong đọc response; request đang
chờ network có thể cần tới timeout kết nối8giây/đọc10giây để quay về checkpoint.
Timeout tổng mặc định90giây. Không gửi lại request tự động vì một request đã
được máy chủ nhận có thể tiêu thụ quota dù client timeout.

Trước khi Tiếp tục, kiểm tra diagnostic và nguồn/output còn hợp lệ. Đổi provider
chỉ thực hiện theo lựa chọn chủ động; không xóa cache/receipt để thử lại. Chưa
nghiệm thu Gemini API thật, không dùng kết quả mock làm bằng chứng key Free tier.

## Stage3C.1 — INVALID_RESPONSE / Unexpected tool use

Không mặc định đây là quota, OCR sai, prompt injection hoặc quyền nội dung.
Trong record mới, agy_protocol cho biết enum classification và event/path/type
đã lọc; không có tool args hoặc raw response. ACTUAL_TOOL_REQUEST cần request
tag + tên action + argument/input object trong contract mô phỏng; thiếu bằng
chứng sẽ UNKNOWN_PROTOCOL_SHAPE. TOOL_METADATA_ONLY chỉ nhận khai báo kiểu
JSON Schema hẹp, không phải mọi metadata/tools list. Tất cả vẫn theo guard cũ.

- MALFORMED_RESPONSE: JSON/envelope/ID/schema hiện tại không hợp lệ.
- UNKNOWN_PROTOCOL_SHAPE: chưa phân loại chắc chắn; không tự sửa allowlist.
- guard_decision là verdict thật của parser cũ; classification không điều khiển
  acceptance. Event phụ lạ được legacy cho phép và observer-failure không được
  tự đổi verdict trong hotfix chỉ diagnostic. Xem unknown_event_count,
  scan_truncated/observation_failed; không coi chúng là chứng nhận an toàn mới.
- TIMEOUT/CANCELLED/REQUEST_LIMIT có thể không có stdout/exit code hoàn chỉnh;
  bytes khi overflow/cancel là phần stream đã quan sát, không phải transcript đầy đủ.
- Numeric reject vẫn không cache vùng sai/render dở; VALID_TRANSLATION_RESPONSE
  chỉ nói schema phản hồi đã qua parser, không bỏ qua numeric/glossary guard.

Lỗi276337 cũ chưa có protocol nên không thể retro-classify. Người dùng đã tự
hoàn tất113output với1fallback106 trước Stage3C.1; hotfix không chạy lại job đó.
Muốn xác minh sâu hơn cần diagnostic của lần sử dụng AGY chủ động trong tương
lai hoặc QA được duyệt riêng. Không bấm retry lặp lại để dò lỗi, không xóa cache.

## IMAGE_LIST_READY, 0%, chưa có ảnh tải (08/11/2026)

- Đây là kết thúc **phân tích**, chưa phải lỗi download. Giữ checkbox chương,
  xem cột Điều kiện tải, sau đó bấm **Tải và dịch** khi nút được bật.
- `ALLOWED_BY_USER_POLICY` + "quyền nội dung vẫn UNKNOWN" không chặn tải:
  UNKNOWN này thuộc bằng chứng quyền, không phải quyết định cuối của ứng dụng.
- `DOWNLOAD_UNKNOWN`: đọc lý do dưới bảng/tooltip. Ví dụ: chưa xác minh PUBLIC,
  chưa phân tích URL an toàn, hoặc `verified_only` thiếu bằng chứng phù hợp.
  Không đổi policy/giả quyền chỉ để bật nút. VIP/locked/restricted vẫn bị chặn.
- Nếu đã bấm nút được bật nhưng không chạy: ghi ID chương, trạng thái nút,
  cột Điều kiện tải và tooltip, thông báo sau khi bấm, giờ chạy, chạy source hay
  EXE nào. Không gửi cookie/token hoặc signed URL. Chỉ cần dữ liệu của lượt lỗi;
  không tải lại chương hoặc nộp lại toàn bộ DOM đã có.
- Điều tra chương277859/thứ tự10 chưa có response/log của lượt107 URL để kết
  luận lỗi HTTP/JavaScript hoặc quyền hiện tại. Không tự coi thiếu log là mạng PASS.
  Xem `docs/IMAGE_LIST_DOWNLOAD_FLOW_REPORT.md`.

## Stage3B — AGY

- AGY_NOT_FOUND: app chưa tìm được executable đã cài; nhập đường dẫn.exe trong
  Cài đặt. Không tự cài/đăng nhập lại. Phiên Codex cũ có thể thiếu PATH mới nhưng
  binary vẫn ở LocalAppData/agy/bin; không cần sửa PATH hệ thống.
- AGY_CAPABILITY: CLI thiếu headless/schema/settings hoặc không xác minh version;
  dừng, không tự update hoặc chuyển sang Gemini API.
- AGY_AUTOMATIC_EXTENSIONS: hooks/MCP tự động không rỗng/không xác minh được;
  không sửa user config hoặc cấp quyền rộng để chạy cho bằng được.
- INVALID_RESPONSE: JSON/envelope/schema/ID/tool-use không qua kiểm tra. Không
  suy là lỗi dịch/người dùng không có Pro. Live attempt đầu bị chặn ở đây, lượt
  bổ sung đã PASS; nguyên nhân lỗi đầu chưa rõ vì thiếu raw protocol/target lúc
  đó. Metadata an toàn giúp điều tra nếu tái xuất hiện. Không tự retry batch.
- TIMEOUT/CANCELLED: chỉ dừng process do app khởi tạo; không logout/clear auth.
- QUOTA_EXCEEDED/RATE_LIMITED/AUTH_REQUIRED/REQUEST_LIMIT: dừng dispatch, × chỉ
  đóng notice; không chuyểnmodel/provider/billing. Không biết reset thì báo chưa rõ.
- NUMERIC_MISMATCH: guard cũ vẫn áp dụng; không nới số/ngày hoặc dùng date handler
  QA để ép model thành PASS. Rejected target không ghi cache hợp lệ.

Diagnostic AGY chỉ giữ shape/count/code, không ghi stderr/OAuth/token thô. Nếu
cần chạy thêm QA thật phải nêu provider/phạm vi/request budget và duyệt lại;
phạm vi1batch ban đầu và1lượt bổ sung đã được dùng. Giữ nguyên artifact lỗi và
thành công, không xóa cache user hoặc gán cache replay thành generation live mới.

## Stage3A — lỗi Online Free

- QUOTA_EXCEEDED: provider báo quota đã hết, dừng dispatch. Không tự nâng gói.
- RATE_LIMITED: giới hạn tốc độ, không mặc định quota ngày. Retry-After nếu có
  chỉ là thời gian đợi được trả về; nếu không có, thời điểm khôi phục chưa biết.
- AUTH_REQUIRED: HTTP401/403 hoặc API báo thiếu quyền; không thử cookie/key khác.
- TIMEOUT / NETWORK_ERROR / PROVIDER_UNAVAILABLE: tối đa3 thử với backoff hữu hạn,
  giữ nguồn/fallback; không chuyển provider/endpoint hoặc bật billing.
- INVALID_RESPONSE: JSON/MIME/size/target không hợp lệ; không coi HTTP200 là dịch xong.
- NUMERIC_MISMATCH: guard nguyên trạng từ chối mất/thêm/đổi thứ tự số. MyMemory
  có thể diễn đạt ngày đúng nhưng đổi5,20,5,30 thành20,5,30,5; không tự nới guard,
  thay số hoặc xóa cache để ép PASS. Diagnostic cục bộ có raw target khi bật.
- Cancel dùng CancelledError/state cancelled; đang chờ response có thể cần chờ
  read timeout tối đa25s hoặc OCR hiện tại đến checkpoint. Đóng × không cancel/resume.

Quota notice không chặn GUI. Trong phiên đang mở, đổi phương thức rồi Tiếp tục
chỉ pending; giữ receipt cũ khi recipe đổi. Cross-restart provider-switch pending
UI chưa làm: không đổi provider rồi chạy lại cảfolder nếu chỉ muốn phần chưa xong.
Đối với URL nhiều chương, resume current cached chapter; bắt đầu chương chưa chạy
là thao tác riêng. Giữ cache/manifest/log, không sửa DB/checkpoint bằng tay.

MyMemory có lưu/chia sẻ text với đối tác; không gửi text bí mật. Không có key
hoặc billing trong provider ẩn danh. QA thật6request/37ký tự không chứng minh
toàn bộ chất lượng ngữ nghĩa. Xem báo cáo Stage3A và diagnostic theo job.

## Stage3: phân biệt lỗi chất lượng với lỗi chương trình

- `Name` hoặc `Lỗi` có thể là **chuỗi model thật trả về**, không phải exception
  ứng dụng. Benchmark mới tái hiện chúng qua native decoder. Không xóa cache
  để giả định sẽ sửa được nghĩa;158 cached occurrences khớp output mới.
- Name của `活动时间` bắt đầu sai tại en→vi; tên riêng/chương13 có thể đã sai
  ở zh→en. Nếu source bị cắt/OCR sai, không tự đoán câu gốc hoặc quy hết cho MT.
- Numeric guard PASS không chứng minh giữ nghĩa, tên hoặc danh xưng. Ví dụ
  `第13话`→`Nguyên tắc13` giữ số nhưng cần xem lại nghĩa.
- Không áp dụng LP1.0 vào production: holdout sinh `Lỗi:% 1` ngoài nguồn. Không
  nới validator để chấp nhận dạng này. Các ứng viên chỉ có trong QA.
- Date QA dùng cấu trúc endpoint, không phải Argos mới dịch đúng. Chưa có
  production typed guard/cache policy, nên không dùng output QA để đánh dấu111
  done. Năm0001 có probe roundtrip chưa đạt, được giữ trong evidence.

Xem [báo cáo Stage3](STAGE3_TRANSLATION_QUALITY_REPORT.md) để biết dữ liệu đã
kiểm chứng và giới hạn. Những hướng dẫn Stage1/2 dưới đây vẫn áp dụng.

## Stage 2: OCR override và số có dấu

- `OCR_OVERRIDE_HASH_MISMATCH`: ảnh ở locator đã khác hash bằng chứng. Không
  bỏ qua vùng OCR; giữ nguồn/fallback. Kiểm tra đúng ảnh và profile trước retry.
- `OCR_OVERRIDE_REGION_MISMATCH`: text/polygon không khớp duy nhất. Không dùng
  tọa độ gần đúng hoặc tăng ngưỡng OCR toàn cục; cần bằng chứng mới/thu hồi rule.
- `OCR_OVERRIDE_INVALID`: schema/evidence/profile không đọc được. Giữ file
  profile và log để xem lại, không tự xóa OCR cache. Profile ở
  `overrides/ocr_regions.json`; tắt mục bằng `enabled=false`.
- Numeric version `literal-numbers-v2-signed` ngăn mất/thêm dấu đầu số; ký tự
  fullwidth không tự chuẩn hóa. Cache signed dùng v4; legacy unsigned giữ v3.
  Không đổi list thành set/multiset và không tự sửa số bằng nguồn.

Trang111 của chương274872: **lượt Stage2 mới** có source thật
`5月20日—5月30日`, zh→en `20-30 May`, en→vi `20 giờ 30 tháng 5`. Chặng cuối
sai nghĩa khoảng ngày. Giữ fallback và needs_retry; không lặp Retry vô hạn
với model/input y hệt. Raw target lỗi lịch sử vẫn không có; không gán kết quả
này cho lần lỗi cũ. Trang74 đã hoàn tất không cần MT theo override có evidence.
Chi tiết: [STAGE2_NUMERIC_OCR_RECOVERY_REPORT.md](STAGE2_NUMERIC_OCR_RECOVERY_REPORT.md).

Trước tiên mở **Trang cần xem lại / log**, xác định file, trang, stage và job.
`FALLBACK_ORIGINAL` có file nhưng chưa dịch hoàn chỉnh; `FAILED_NO_OUTPUT`
không có output hợp lệ. Không xóa receipt/cache để ép job chạy lại.

| Mã lỗi | Kiểm tra tiếp |
|---|---|
| `NUMERIC_MISMATCH` | So OCR nguồn, raw target mới và hai danh sách numeric tokens trong diagnostic. Không kết luận provider sai chỉ từ mã này; validator hiện so chuỗi theo thứ tự, chưa chuẩn hóa ngày tháng/số chữ. |
| `OCR_ERROR` | Kiểm tra nguồn, model OCR, bộ nhớ và giai đoạn lỗi. Confidence thấp không tự chứng minh OCR sai. |
| `TRANSLATION_ERROR` | Xem provider/mode/model identity/exception; thiếu model không tự bật Online. |
| `INPAINT_ERROR` | Kiểm tra giới hạn ảnh/mask; nguồn gốc vẫn được dùng làm dự phòng nếu xác minh được. |
| `RENDER_ERROR` | Xem font, kích thước vùng, độ dài bản dịch; không cắt chữ để giả thành công. |
| `EXPORT_ERROR` | Kiểm tra quyền ghi, dung lượng, file đích có sẵn. File khác nội dung được giữ nguyên; app thử bản gốc ở đường dẫn riêng. |
| `DOWNLOAD_ERROR` | Xem lỗi nguồn/mạng/quyền truy cập, trang cuối được progress xác nhận nếu có. Không retry vượt 401/403/429, CAPTCHA hoặc paywall. |

`retry_count=0` hiện là số retry tự động bổ sung ở cấp pipeline cho lỗi này,
không phải lịch sử số lần người dùng bấm Retry hay số lần HTTP transport retry.
Stage 1 không thêm retry suy luận MT. Lịch sử các lần lỗi là các record riêng.

Nếu `diagnostic_path` trống, xem `diagnostic_error`: hết quota, không có quyền
ghi hoặc I/O lỗi có thể làm log không ghi được. Bản dự phòng vẫn được thử xuất.
Log giới hạn 4 MB/1.000 record/job; không tự xóa log cũ để né giới hạn. Nếu dòng
cuối hỏng do mất điện, giữ file đó để điều tra; ứng dụng ghi record mới sang file
khác. Không gửi URL ảnh có chữ ký, cookie, token hoặc toàn bộ cache lên mạng.

Hai lỗi cũ của chương 274872 đã điều tra ở
[NUMERIC_INTEGRITY_INVESTIGATION.md](NUMERIC_INTEGRITY_INVESTIGATION.md). Không
gán raw target của lần retry tương lai cho hai lần lỗi lịch sử. Chưa phục hồi
hai trang thật trong Stage 1.

## Stage3C — batch và journal resume

- OCR chạy trước khi xuất nhiều trang là bình thường. AGY batch có ngưỡng3.000
  ký tự/60vùng, tối đa16trang có chữ; không gửi batch này trực tiếp sang MyMemory.
- INVALID_RESPONSE: ID thiếu/lạ/trùng, JSON/NDJSON sai, output lớn hoặc tool use
  bất thường. Dừng request; không auto retry hoặc nới parser. Diagnostic cục bộ
  không chứa raw stderr/OAuth/chain-of-thought. Không dùng × để resume.
- NUMERIC_MISMATCH: vẫn giữ literal-numbers-v2-signed. Vùng sai không cache hợp
  lệ/không dùng làm context. Trang lỗi fallback; các trang hợp lệ khác tiếp tục.
- RESUME_SOURCE_CHANGED: nguồn/cache thay hash; dừng, giữ output. Không tự tải
  lại hoặc sửa checkpoint bằng tay.
- RESUME_RECEIPT_CHANGED / RESUME_PUBLICATION_CHANGED: output, hash hoặc receipt
  không khớp. Không ghi đè; đối chiếu bản sao lưu và diagnostic.
- RESUME_RECIPE_CHANGED: khôi phục cấu hình OCR/render/font/glossary của journal.
  Có thể đổi phương thức/provider khi tiếp tục, nhưng không âm thầm đổi recipe
  output cũ. Muốn đổi render, dùng lượt mới/output khác.
- RESUME_INVALID: journal sai ID/phiên bản/quá16MB. Giữ nguyên file để điều tra.
- RESUME_CACHE_MISSING / RESUME_CACHE_INCOMPLETE: cache đã được ghi nhận đầy đủ
  nhưng hiện không còn hợp lệ; dừng. Khác với chương chưa tải từ đầu: chương đó
  chỉ được tải sau lệnh tiếp tục và kiểm tra quyền truy cập/policy mới.
- AGY_BATCH_CONFIG / INVALID_REQUEST: vượt giới hạn cấu hình, vùng6.000ký tự,
  tổng12.000ký tự hoặc payload128KB. Không cắt mất chữ; xem lại vùng OCR/cấu hình.
- AGY_CACHE_INTEGRITY / AGY_PAGE_INCOMPLETE: thiếu hoặc không khớp receipt vùng;
  không render trang dở. Giữ journal/database để kiểm tra, không xóa cache.

Source job lưu journal trước khi tải/OCR; pipeline lưu publication intent trước
atomic publish. Nếu mất điện sau publish nhưng trước checkpoint, resume có thể
đối chiếu hash/bitmap và hoàn tất receipt cũ mà không dịch lại. Kiểm thử này dùng
process/crash fixture, không phải nghiệm thu cắt điện máy thật.
