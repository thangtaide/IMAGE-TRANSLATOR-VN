# Điều tra Stage3C tạm dừng dịch — 08/11/2026

## 1. Kết luận và mức độ chắc chắn

**ROOT_CAUSE_CONFIRMED cho điều kiện trực tiếp làm pipeline pause:** phản hồi
AGY bị guard giao thức từ chối với mã **INVALID_RESPONSE**, lý do
**Unexpected tool use**. Không phải DOWNLOAD_UNKNOWN, numeric rejection,
request budget hoặc thông báo quota trong lần lỗi này.

Diagnostic thật, dòng1:

`AGY trả JSON/ID/schema không hợp lệ (Unexpected tool use); giữ nguyên ảnh nguồn.`

**Chưa chứng minh được nguyên nhân sâu hơn của dấu hiệu tool use.** Không có
NDJSON/event path/protocol metadata được lưu cho request lỗi; chưa biết là
tool_call/tool_use/permission_request thực, tool đã bị từ chối, hay metadata
tool_name/function_call bị recursive guard nhận nhầm. Không khẳng định shell,
file hoặc tool nào đã thực thi, không khẳng định AGY hết quota. Không nới guard.

Đây là điều tra chỉ đọc, không hotfix. Không chạy CLI AGY kể cả metadata,
MyMemory, download, Resume/Start, retry production, model install hoặc build.

## 2. Job thực tế và bằng chứng

- Topic6677; chapter **276337 — 第4话 登门道歉**. Không nhầm chapter277859 hoặc274872.
- Pipeline job: `09fdd5220d603a2b858558a99828da9d02bde84e13d6251c195c493db3cb9baf`.
- Source journal: `cache/online_comics/pipeline-resume-v1/12b9e375e04b46929eb843a075206200.json`.
- Chapter journal: `cache/online_comics/pipeline-resume-v1/3d46f3a26f0f4a4b81b9bfda6dbd60e0.json`.
- Manifest: `cache/online_comics/kuaikanmanhua/6677/chapter_276337/manifest.json`.
- Download receipt: `cache/online_comics/_incoming/kuaikanmanhua/6677/276337/download-manifest.json`.
- Diagnostic: `logs/diagnostics/09fdd5220d603a2b858558a99828da9d02bde84e13d6251c195c493db3cb9baf/errors.jsonl:1`.
- SQLite: `cache/online_comics/pipeline.sqlite3`; bảng jobs/items và cache.

Diagnostic xác nhận TRANSLATION, trang57/0057.jpg, ProviderSuspended,
error_code=INVALID_RESPONSE, provider=AGY Gemini, mode=AI Gemini AGY,
checkpoint_state=paused_provider, fallback_action=NONE. Có đúng1diagnostic cho
job này; raw_translated_target=null. Không dựng lại target hoặc response bị thiếu.

Nguồn/cache là113ảnh. Download manifest state=downloaded,113page receipts.
Chapter/source journals, jobs.state và manifest đều paused_provider. SQLite
items có56done và1paused_provider (0057.jpg, detail=INVALID_RESPONSE); 56trang
chưa được vòng render đi tới không nhất thiết có row items.

Output người dùng:
`output/test_download-orc/权妃之帝医风华__6677/0006_第4话 登门道歉__276337/run_09fdd5220d603a2b`.
56output đã publish, trang1–56;57pending, trang57–113. Không có fallback hoặc
numeric-error trong summary job này. Trong56trang hoàn tất,32trang có vùng chữ
cần dịch và24trang không có vùng chữ cần dịch theo cache/filter; không gọi cả56
là56trang đều đã dịch chữ. Chapter274872 cũ/trang111 fallback không được chạy lại.

## 3. Timeline (UTC+07)

| Thời điểm 08/11 | Bằng chứng | Diễn giải và giới hạn |
|---|---|---|
| 14:13:28 | Metadata tiến trình pythonw | App đã mở; không phải log chính xác lúc job bắt đầu. |
| 14:16:38.284–14:16:43.914 | Creation/mtime source cache1–113 | File cache được ghi; không tự suy toàn bộ thời gian download/CDN. |
| 14:16:55.017 | request-ea3bd43fa625409fb0b0ad4649f6b461 creation time | Khớp request batch1; thư mục hiện rỗng, không phải transcript. |
| 14:17:33.508 | Output trang1 creation time | Batch1 đã được chấp nhận trước khi xuất trang này; không có timestamp response riêng. |
| 14:17:44.436 | request-77fd40f8cc59474db3f4b63f581cfad0 creation time | Khớp request batch2. |
| 14:18:50.921 | Output trang56 creation time | Output cuối trước pause. |
| 14:19:01.289 | request-04d33a5962c44a95a6e386951a823af4 creation time | Khớp request batch3 bị từ chối. |
| **14:20:05.916793** | Diagnostic timestamp07:20:05.916793Z | INVALID_RESPONSE / Unexpected tool use. |
| 14:20:05 | jobs.updated và items | paused_provider,0057.jpg. SQLite timestamp chỉ chính xác tới giây. |
| 14:20:05.921254 | Chapter journal updated | paused_provider,56done/57pending. |
| 14:20:05.927 | Manifest mtime | Summary paused_provider,56output. |
| 14:20:05.928490 | Source journal updated | Source job paused_provider. |

Không có timestamp GUI nhận signal hoặc OCR từng trang/validation từng vùng.
Ba request-directory metadata phù hợp3batch; request counter thực trong memory
không được persist. Không trình bày timestamps filesystem như log HTTP/CLI.
logs/app.log có mtime07/11, không ghi nhận lượt này; diagnostic mới là bằng chứng.

## 4. Đường đi chính xác từ lỗi tới UI

1. `providers/agy.py:213`, parse_response: parse NDJSON, tìm terminal result.
   Tại dòng237–243, used_tool đệ quy nhận key truthy tool_call/tool_calls/
   tool_name/function_call ở bất kỳ dict lồng nhau, hoặc event tool_call/
   tool_use/permission_request. Nhánh này raise ValueError('Unexpected tool use').
2. `providers/agy.py:269` đổi thành OnlineProviderError(INVALID_RESPONSE).
   `AGYProvider.translate_batch:378–381` latch thành ProviderSuspended, không retry.
3. `core/multipage.py:114–118` gọi batch; lỗi propagate qua for_page tới
   `ProcessingManager.run`, tại trang đang chờ57. Chưa tới numeric/ID-target
   validation của batch3. Trang57 là điểm chờ, không chứng minh tool do riêng
   vùng OCR của trang57 gây ra.
4. `core/pipeline.py:562–579`: catch ProviderSuspended → diagnostic → items
   paused_provider → emit provider_paused có code/detail/diagnostic_path và57
   pending paths → break. Finally lưu journal/job state, emit finished.
5. `sources/service.py:315–316` bọc event thành pipeline với
   pipeline_event_type=provider_paused; tại321–332 lưu manifest và result
   paused_provider, paused_chapter và pending_chapters. Dòng405 emit job_finished.
6. `ComicSourceWorker.run`, `ui/comic_sources.py:35` và nhánh process, truyền
   emit=self.event.emit; `ComicSourcesPanel.launch:356` nối signal tới handle_event.
7. `handle_event:588–592` đặt provider_paused=True, paused_chapter, show_error,
   status=INVALID_RESPONSE + thông báo tạm dừng. `ui/provider_notice.py:15–21`
   hiển thị code + detail trong banner có nút×.
8. **`handle_event:633–638`**, nhận job_finished(state=paused_provider), **ghi
   đè status bằng hai câu chung người dùng báo**, rồi return. Hai câu không
   chứa code/lý do thực; không phải bằng chứng hết quota hoặc lỗi quyền tải.
9. QThread.finished → set_busy(False), `ui/comic_sources.py:426–436`; nếu
   provider_paused thì bật Resume. Worker đã dừng là đúng cơ chế pause; job
   dịch113trang chưa hoàn tất. Không được đồng nhất thread finished với job done.

Có ít nhất7mã trong nhánh AGY runtime hiện tại có thể đi tới cùng banner chung:
QUOTA_EXCEEDED, RATE_LIMITED, AUTH_REQUIRED, PROVIDER_UNAVAILABLE, TIMEOUT,
INVALID_RESPONSE và REQUEST_LIMIT. Một câu UI không phân biệt các nguyên nhân này.

## 5. Ma trận các khả năng trong code

Các dòng dưới mô tả nhánh **request dịch**, không đồng nhất lỗi preflight với
lỗi lúc dịch. Tất cả nhánh AGY không tự đổi provider hoặc retry generation.

| Trường hợp | Code/điều kiện | Trạng thái/lưu/hiển thị |
|---|---|---|
| Quota/usage | agy.py:224–227, terminal error code QUOTA_EXCEEDED/RESOURCE_EXHAUSTED | ProviderSuspended/QUOTA_EXCEEDED → diagnostic/items/journal paused, banner riêng rồi status chung. |
| Rate limit | :228–229, RATE_LIMITED/429 hoặc RATE_LIMIT trong error | RATE_LIMITED → pause; không suy daily reset. |
| Auth/session | :230–231, AUTH_REQUIRED/UNAUTHENTICATED | AUTH_REQUIRED → pause; không login/key tự động. |
| CLI exit≠0/model/server error | :223–232, không hoàn tất nhưng không thuộc mã trên | PROVIDER_UNAVAILABLE → latch pause; message chung không xác định chắc model unavailable. |
| Timeout | run_bounded:146–147 | TIMEOUT → latch pause; giữ pending. |
| stdout/stderr overflow/không drain hết | :144–152 | INVALID_RESPONSE → latch pause; không nhận output bị cắt là hợp lệ. |
| JSON/NDJSON, thiếu/trùng/lạID/schema | parse_response:213–269 | INVALID_RESPONSE → pause, chưa validate/cache targets. |
| Tool use indicator | :237–243 | INVALID_RESPONSE/Unexpected tool use → pause; đúng lỗi runtime lần này. |
| Request budget | :339–341, requests_sent≥max_requests | REQUEST_LIMIT → pause trước request mới. Counter không lưu trong journal. |
| Batch input/context/payload quá lớn | :322–338 và355–356, trước try gọi runner | INVALID_REQUEST/OnlineProviderError; thường vào fallback/error page, không tự thành ProviderSuspended ở vị trí này. |
| Numeric/glossary rejection | pipeline.py:135–190, multipage.py:119–130 | Vùng bị từ chối không cache/context; trang fallback, trang khác có thể tiếp tục; không phải provider pause trực tiếp. |
| Người dùng Pause | JobControl.pause và comic_sources.py:660 | Condition wait/checkpoint, không tạo diagnostic INVALID_RESPONSE. |
| Cancel | run_bounded:142–143, JobControl.cancel | CancelledError → cancelled; không phải paused_provider. |
| Lỗi khác | Tùy vị trí/lớp Exception | Generic page error thường fallback; không được quy mọi lỗi thành quota/pause. |

Preflight AGY_NOT_FOUND/CAPABILITY hoặc OSError tạo process có đường xử lý khác;
không có bằng chứng xảy ra ở lượt này. Không chạy AGY để kiểm tra auth/quota.

Theo thứ tự parse_response, để tới Unexpected tool use thì code đã qua điều
kiện terminal status SUCCESS, exit_code0 và num_turns1. Đây là **suy luận từ
source + reason đã ghi**, không phải raw protocol/exit-code log được lưu lại.
Sau guard này còn ID/schema parsing: chưa thể biết có lỗi ID đồng thời hay không.

## 6. Batch tái dựng từ cache — không phải live request log

Đọc SQLite bằng URI mode=ro&immutable=1; thời điểm đọc không có WAL nên không
bỏ sót WAL đang chờ. PRAGMA integrity_check=ok. Tái tính OCR key từ model
receipts/options/hash ảnh, đọc cache và lặp số học pack_pages, không import/run
pipeline, provider hay model. Không có override áp dụng lên ảnh chapter này,
glossary0, nên số ký tự protected bằng nguồn. Digest ID/receipt khớp toàn bộ57
validated-region entries, làm đối chiếu độc lập cho phân nhóm.

| Batch tái dựng | Trang có chữ | Vùng | Ký tự | Receipt vùng hợp lệ |
|---|---:|---:|---:|---:|
| 1 | 16 | 33 | 218 | 33 |
| 2 | 16 | 24 | 201 | 24 |
| **3 — bị từ chối** | **16** | **25** | **166** | **0** |
| Lookahead trang89, chưa phải batch đã gửi | 1 | 2 | 6 | 0 |

Trang trong batch3: **57,58,60,62,64,67,68,70,73,74,77,79,81,86,87,88**.
Các trang trống xen giữa không có item gửi. Cache đã OCR trang1–89:
84vùng cần MT/591ký tự,40trang không có vùng chữ cần MT,49trang có vùng chữ.
Trang90–113 chưa có OCR cache theo recipe này. Pending gồm33trang đã OCR và24
trang chưa OCR; empty pages pending bình thường vì vòng render đã dừng ở57.

Batch được flush ở giới hạn **16trang có chữ**, sau OCR lookahead89; không cần
đợi3.000ký tự. Chưa chạm60vùng, ngưỡng3.000, hard limit12.000 hay6.000/vùng
(max cached region26ký tự). Không có oversized page trong dữ liệu đã OCR.
Không có receipt hợp lệ của batch3 bị treo pending; 57receipt thuộc hai batch
đã xuất. Không có numeric-reject record trong job này.

Số request thực/counter64, bytes stdout/request payload và exact event sequence
không được persist. Ba request directories và hai nhóm receipt + lỗi sau đó phù
hợp3request; không dùng chúng giả làm request-counter log. REQUEST_LIMIT không
phải mã lỗi này. Không đủ bằng chứng runtime để chấm toàn bộ mapping/ngữ nghĩa
response3; parser dừng trước ID validation, không được coi missingID đã PASS.

## 7. Journal/UI và provider

Source/chapter journals **thật sự có**, tạo cho lượt Stage3C mới, không giả định
job lịch sử đã migration. Chúng lưu state/pending nhưng **không lưu pause code,
reason, request number, batch metadata hoặc protocol**. Lý do chi tiết nằm trong
diagnostic; DB item chỉ detail=INVALID_RESPONSE. last_batch/last_protocol ở
AGYProvider là transient; production không ghi chúng ra journal/diagnostic.
Các request directories trên đều rỗng; CLI --log-file=os.devnull. Không đọc
credential/session/OAuth hoặc private environment để tìm transcript khác.

Diagnostic có image57 nhưng ocr_source_text thực khớp vùng cuối của trang88.
Code multipage.translate_batch:95–113 chuẩn bị deferred cả batch, để last_attempt
ở vùng cuối; lỗi request chung propagate khi for_page57 đang chờ. **Không gán
source-text đó cho trang57 hoặc kết luận trang57 chứa prompt injection.** Đây
là thiếu sót diagnostic batch scope cần sửa sau, không sửa OCR/cache hiện tại.

Settings chọn lọc và options trong source/chapter journal đều xác nhận zh,
AI Gemini AGY, model gemini-3.8-flash-medium, online MyMemory/offline Argos,
allow_online_fallback=False. Config settings chưa có hai field batch thì default
được materialize thành3000/60 trong journal. Diagnostic xác nhận provider thực
AGY Gemini, identity agy-account-headless-v1:23c9ea76a563e088ab707b37d3e6c863466f320b86b6fdce0b8a8af3ce504aca.

`TranslationService.translate:193–200` đi nhánh AGY độc lập; LocalComicJob cũng
tắt allow_online_fallback. Combo MyMemory/Argos hiển thị không chứng minh đã gọi.
Không có bằng chứng chúng xử lý phần dịch đang lỗi.

`quyền nội dung vẫn UNKNOWN` đến từ sources/download_policy.py:decide_download,
nhánh ALLOWED_BY_USER_POLICY. Manifest ghi PUBLIC/default_allow_public/
content_permission UNKNOWN và allowed decision. Download113ảnh/cache đã xong
trước lỗi dịch. Đây là trạng thái độc lập, **không gây pause này**.

UI: banner riêng có code/detail tới khi × hoặc begin mới; status sau đó chung.
Đổi combo chưa begin không xóa notice cũ — chưa phải bằng chứng provider mới lỗi.
begin:449 reset flag/hide notice; không có bằng chứng job thực tế done mà UI
giữ stale pause. Tuy nhiên ProcessingState không có PAUSED_PROVIDER, nhánh
job_finished paused return trước gán state nên enum có thể còn TRANSLATING.
Resume enabled chỉ kiểm !busy và provider_paused, không kiểm pending hợp lệ.
Đây là rủi ro UI theo source, **chưa chứng minh lỗi nút ở runtime này**: thực tế
có57pending và paused_chapter276337 khớp lựa chọn một chương. Không lẫn chương
chưa bắt đầu; câu UI về chúng là generic, source journal lần này chỉ chọn1chương.
Không có click log để khẳng định người dùng chưa từng Pause/Cancel/đóng banner;
nguyên nhân pause được ghi lại là ProviderSuspended, không phải thao tác ấy.

## 8. Bảng giả thuyết và mức chứng minh

| Giả thuyết | Code hỗ trợ | Bằng chứng runtime | Kết luận |
|---|---|---|---|
| Hết quota AGY | QUOTA_EXCEEDED/RESOURCE_EXHAUSTED → pause | Mã thật INVALID_RESPONSE/Unexpected tool use | **Ruled out là trigger lần này**; quota tài khoản hiện tại Unknown, không kiểm tra. |
| Rate limit/auth/model unavailable/exit≠0 | Có nhánh riêng | Không có mã tương ứng; guard tool chỉ chạy sau terminal-success checks | Ruled out là lỗi phát ra đầu tiên. |
| Timeout | TIMEOUT → pause | Reason khác; khoảng dir→diagnostic64,6giây, timeout cấu hình90 | Ruled out trigger, không đo latency API chính xác. |
| INVALID_RESPONSE/tool indicator | Guard tool → code này → latch | Diagnostic duy nhất khớp job/trang/time | **Confirmed**. |
| Tool thực thi hoặc metadata false positive | Recursive tool_name và event tool đều kích hoạt | Không lưu event/path/raw protocol | **Unknown**, không khẳng định bên nào. |
| Request budget64 | REQUEST_LIMIT trước call | Không có REQUEST_LIMIT, counter không persist;3directory phù hợp3batch | Ruled out trigger; exact counter Unknown. |
| Numeric rejection | NumericMismatchError → fallback | Summary failed0/fallback0; batch3 chưa đến guard vùng | Ruled out trigger; không chứng minh target3 đúng số. |
| Thiếu/trùng/saiID | Có thể INVALID_RESPONSE | Reason tool, trước bước mapID | Unknown có đồng thời không; không phải reason đã ghi. |
| User Pause/Cancel | Wait/cancelled, không reason tool | paused_provider + diagnostic parser | Ruled out trigger đã ghi; click history Unknown. |
| Resume/journal integrity mismatch | Các lỗi RESUME_* riêng |113source/56output+receipt valid, recipe khớp, DBok | Không có bằng chứng gây pause; audit hiện tại PASS. |
| UI state che nguyên nhân | job_finished ghi status chung | Chuỗi user báo khớp branch, backend cũng paused | Confirmed cơ chế thay status; không phải pause giả do UI. |
| Quyền nội dung UNKNOWN | Có thể cùng ALLOWED_BY_USER_POLICY | Manifest allowed/Public,113ảnh đã cache | **Ruled out** cho pause dịch. |

## 9. Dữ liệu và cách tiếp tục

Read-only xác minh SHA/bitmap113source,56pipeline outputs,56published outputs;
đối chiếu56items/output-hash receipts, work_recipe/font hash hiện tại khớp
journal và SQLite integrity_check=ok. Không phát hiện dữ liệu hỏng ở phạm vi này.
Không gọi ResumeStore.pipeline vì hàm đó có thể ghi/reconcile checkpoint;
tái tính các phép so sánh bằng code read-only riêng.

- **Không khuyến nghị bấm Tiếp tục nguyên AGY để dò lỗi**: sẽ là request mới,
  có thể lặp guard failure; không có bằng chứng rằng chờ quota/reset sẽ giải quyết.
- Nếu muốn tiếp tục mà không gửi thêm tới AGY: dữ liệu hiện đủ điều kiện để
  **chủ động chọn Offline/Argos rồi Tiếp tục**, giữ nguyên OCR/render/glossary.
  Code resume_job:682 → begin(chapter276337,retry_only=True) dùng cache/checksum,
  chỉ chọn57pending, giữ56output. Đây là hướng dẫn dựa trên audit/code; chưa
  thực hiện trong lượt điều tra, không hứa chất lượng/số fallback tương lai.
- MyMemory là lựa chọn online khác nếu người dùng chủ động chọn; có gửi OCR
  và quota riêng. Không cần tự đổi hoặc gọi thử trong điều tra này.
- Muốn tiếp tục bằng AGY với nguyên nhân rõ ràng: duyệt hotfix diagnostic trước.
  Không xóa cache, sửa journal hoặc chạy lại từ đầu chương. 56output cần được giữ.

## 10. Hotfix đề xuất — CHƯA TRIỂN KHAI, chờ duyệt

1. `providers/agy.py:protocol_metadata/parse_response/translate_batch`: giữ guard,
   bổ sung safe event index/type và key-path/boolean đã kích hoạt tool detection,
   exit/status/num_turns/bytes/count/IDs hash (không tool args, tên nhạy cảm,
   stderr, OAuth, URL chữ ký hoặc model reasoning). Persist metadata bounded ở
   diagnostic khi reject. Chưa whitelist init metadata khi chưa có bằng chứng.
2. `core/multipage.py`: diagnostic dùng batch scope, request number/pages/regions/
   chars/flush reason/ID digests. Không gắn last_attempt vùng cuối88 vào ảnh57.
3. `core/pipeline.py` và `sources/service.py`: persist pause_code/reason/batch
   metadata vào summary/journal, không đổi state done/fingerprint/output/cache.
4. `ui/comic_sources.py`: giữ code/reason trên status kết thúc, state paused
   riêng, Resume chỉ bật khi pending đã xác định; banner× chỉ ẩn. Không mở guard
   hoặc auto retry vì mục tiêu chỉ quan sát/UX, không hợp thức hóa output bị reject.

Regression đề xuất sau khi được duyệt: fake NDJSON có tool_call, denied
permission_request, metadata quảng bá tool_name, chỉ literal text chứa từ tool,
quota/timeout/exit/schema/IDs; batch nhiều trang bị reject phải0accepted/0output,
diagnostic đúng scope, không retry. GUI giữ lý do qua job_finished/mode change/×,
restart restore reason, Offline pending-only giữ56hash. Chỉ dùng QA DB/journal
riêng. Không nới security rule tới khi phân biệt được metadata với action.

Rủi ro: nới recursive guard mù có thể chấp nhận tool execution; ghi protocol
không lọc có thể lộ credentials/reasoning; thay recipe/checkpoint để thử dễ làm
mất skip/resume. Diagnostic hotfix nên tách khỏi thay thuật toán/cache, có limits
và test riêng. Lượt này **không sửa source, không chạy mock hoặc regression**;
349PASS/10SKIPPED là lịch sử Stage3C, không phải test mới của điều tra.

## 11. Bảo toàn và Git & Fork Handoff

Baseline repository D:\TransTool, main, HEADeb5554ba51e51708fc082c09687f293cfb07a732,
Git clean/staged0: người dùng đã commit Stage3C. Chỉ đọc source/JSON/filesystem,
SQLite URI read-only immutable không tạo WAL/SHM. Không private environment,
cookie/token/OAuth/session credential. Snapshot hash tổng hợp868file trước khi
ghi báo cáo (source/config/cache/journal/DB/ảnh/output/models/BAT/spec/4EXE) để
so lại sau; không ghi snapshot vào production. Kiểm tra cuối ghi tại mục12.

Chỉ thay2tài liệu: báo cáo này (mới) và PROJECT_STATUS.md (tóm tắt điều tra theo
AGENTS). .gitignore giữ nguyên. Source production/model/config/cache/DB/journal/
output/EXE không được sửa. Không thêm test/script/runtime log trong lượt này.

Fork → Local Changes → review2tài liệu → tự stage/commit. Không commit runtime
logs/cache/model/output/SQLite/credential/EXE. Commit đề xuất:
`docs(stage3c): investigate translation pause root cause`.

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT**.

## 12. Kết quả kiểm tra cuối

868/868file trong snapshot tổng hợp giữ nguyên hash; source production không
diff so với HEAD. Git cuối chỉ PROJECT_STATUS.md sửa và báo cáo này untracked;
git diff --check PASS. .gitignore không đổi; cả2docs hiện để review, runtime
cache/log/output bị ignore đúng. Không có staged file, không thay HEAD/branch.

**ROOT_CAUSE_CONFIRMED — pause trigger INVALID_RESPONSE / Unexpected tool use.**
**Nguyên nhân sinh dấu hiệu tool use: ROOT_CAUSE_NOT_YET_PROVEN.**
