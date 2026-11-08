# Tra cứu lỗi ảnh — Stage 1–2

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
