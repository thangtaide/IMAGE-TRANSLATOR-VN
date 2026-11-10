# Stage3H — Whole AGY trong provider chính và timeout forensic

Ngày 09/11/2026. **STAGE_3H_IMPLEMENTED_NOT_TESTED**.

Chỉ triển khai source, đọc diff/AST và forensic local read-only. Không chạy
pytest, unittest, mock, regression, smoke, GUI, BAT hoặc AGY (kể cả help/version).
Không gọi API/provider dịch mạng, download truyện, resume/retry production,
thay timeout, billing, dependency, model hoặc build EXE.

## 1. Provider và cách sử dụng

Dropdown **Dịch** của cửa sổ chính có sáu lựa chọn:

| Nhãn | Identity điều phối |
|---|---|
| Offline | Offline, giữ mặc định |
| Online Free | Online Free, không đổi MyMemory |
| AI Gemini AGY — Batch | `AI Gemini AGY`, identity/cache cũ |
| AI Gemini AGY — Toàn chương (1 lần) | `AI Gemini AGY Whole Chapter` |
| AI Gemini API | AI Gemini API, không đổi REST |
| Auto Fallback | Auto Fallback cũ, không đưa Whole vào route |

Tách nhãn hiển thị và itemData để cấu hình `AI Gemini AGY` cũ vẫn chọn đúng
Batch. Whole dùng adapter `whole-agy-v1:*` của Stage3G; không dùng identity
`agy-account-headless-v1:*` hoặc translation receipt của Batch. Không đổi
provider mặc định, model hoặc lựa chọn Auto Fallback của người dùng.

Hướng sử dụng mới, **chưa chạy nghiệm thu**:

1. Mở bản source bằng `run_source.bat` (Codex không chạy BAT).
2. Chọn Whole trong dropdown Dịch. Không phát sinh OCR/download/AGY chỉ vì đổi
   provider. Với Link truyện: phân tích link, chọn đúng một chương trong bảng,
   phân tích chương nếu cần xác minh điều kiện tải. Với ảnh đơn/thư mục: dùng
   nguồn đã chọn theo tab tương ứng.
3. Bấm **Chuẩn bị toàn chương**. Cửa sổ nhận đúng nguồn, ẩn chọn lại provider
   và duyệt thư mục. Lượt mới bắt đầu chuẩn bị ảnh/OCR trong QThread; chưa gọi
   AGY. Nhiều chương cùng chọn thì nút bị khóa/hiển thị hướng dẫn chọn một.
4. Xem số trang/vùng/ký tự sau OCR. Bấm **Xác nhận dịch bằng AGY…**, rồi đọc
   hộp xác nhận riêng. Hủy hộp này không gửi dữ liệu. Xác nhận mới cho phép
   adapter Stage3G gửi một invocation cho toàn chương, không chia batch.
5. **Hủy** dừng qua JobControl; **Tiếp tục** kiểm tra/OCR/render dữ liệu lưu,
   không cho phép AGY mới nếu thiếu xác nhận gắn manifest hash. **Mở thư mục
   kết quả** mở `rendered` của lượt Whole. Sau khi đóng cửa sổ, nút Mở kết quả
   ở nguồn ban đầu trỏ đến kết quả Whole vừa dùng khi provider vẫn là Whole.
6. Mở lại ứng dụng, chọn đúng nguồn/Whole rồi bấm Chuẩn bị: nếu tìm được lượt
   Whole đã lưu thì chỉ nạp metadata, chờ người dùng bấm Tiếp tục. Không tự
   resume khi khởi động/đổi provider. Cấu hình/model lượt đã lưu được giữ;
   muốn cấu hình khác phải chủ động chuẩn bị lượt độc lập mới và xác nhận mới.

Menu thủ công Stage3G giữ lại dưới **Công cụ → Whole Chapter Translation
(nâng cao)…**; là QMenu/QAction thực sự. Menu này vẫn có Argos/AGY và bộ chọn
nguồn thủ công. Không phải đường bắt buộc cho chương đang chọn.

## 2. Tích hợp nguồn, output và giới hạn

Luồng mới:

`Main / source panel → wholeRequested/context → cửa sổ modal → worker chuẩn bị
ảnh → WholeChapterJob OCR/manifest → xác nhận → AGYWholeChapterTranslator →
guard/receipt → render riêng`.

- `sources/whole_input.py` dùng ImageCollection và đúng thứ tự đã stage. Cache
  online cần manifest đúng site/comic/chapter, trạng thái stage đầy đủ, số ảnh
  khớp image_count nếu có, từng bitmap/hash khớp. Cache partial/copying/error/
  cancelled hoặc hash sai bị chặn, không tự trộn/tải bù vào cache cũ.
- Chương LOCKED/RESTRICTED bị chặn trước khi dùng luồng nguồn. Quyền nội dung
  UNKNOWN không được đổi thành quyền cấp chính thức. Đọc ảnh local đã cache
  không tạo request mạng; download chưa có cache vẫn cần decision/adapter gate.
- Nếu chưa có cache chương, chỉ sau lệnh Chuẩn bị của người dùng, worker mới
  dùng `adapter.download_chapter` hiện có (recheck policy/access/CDN). Đích mới
  `cache/whole_chapter_inputs/<workspace>/`, giữ điều kiện CACHE containment.
  Không nới URL/HTTPS/DNS/401/403/429 guard hoặc sửa source adapter. Codex không
  thực thi nhánh download này trong Stage3H.
- Context/input receipt có hash, danh sách path/SHA256 riêng trong workspace;
  không chứa signed URL, prompt hoặc credential. Resume xác minh lại input.
- `input_paths` giúp Whole chỉ OCR/render danh sách đã chọn, kể cả một ảnh
  trong thư mục có nhiều ảnh khác. Không lấy các ảnh lân cận để render thêm.
- Output/SQLite/OCR/accepted translation/render receipt nằm trong
  `output/stage3g-<timestamp>-<id>/`. Không sử dụng database/journal Batch làm
  nơi thử nghiệm, không sửa manifest cũ và không nhập output vào publisher cũ.
  Whole có thể OCR lại ảnh local; chưa reuse/migration OCR SQLite production.
- Chỉ một chương mỗi lượt. Khi chuyển từ Batch pending sang Whole, đây là
  **toàn chương trong workspace mới**, không phải tiếp riêng pending Batch.
  Retry ảnh lỗi cũ bị chặn ở lựa chọn Whole; dùng Batch để retry theo receipt
  Batch. Không thay đổi schema hoặc ép trạng thái journal Batch.
- Cửa sổ modal và kiểm tra worker ngăn chạy Whole cùng job batch/source trong
  cùng cửa sổ chính. Không tuyên bố khóa mọi cửa sổ/process khác trên máy.
- Nút/hành vi và layout mới chỉ được rà source/AST, chưa có bằng chứng GUI
  hoạt động, cancel/resume hoặc downloader tích hợp chạy đúng ở runtime.

Giới hạn Stage3G giữ nguyên: Whole một invocation/workspace, không retry/
fallback/pacing, payload stdin16MB, argv30k UTF16, output1MB, local500trang/
10.000vùng/1.000.000ký tự; timeout whole600s, cấu hình10–1800. Đây là giới hạn
an toàn local, không phải cam kết CLI/model xử lý mọi chương lớn. Một CLI
invocation không chứng minh một backend request. Batch vẫn24 trang có chữ /
60vùng /3.000ký tự và chờ5–10s giữa các invocation thật; API vẫn16trang.
Numeric `literal-numbers-v2-signed`, glossary, tool guard, budget/context/cache
và prompt không thay đổi trong Stage3H.

## 3. TIMEOUT trang60 — bằng chứng thực tế

**FACT_CONFIRMED**: tìm thấy đúng lỗi gần timestamp người dùng cung cấp:

- Diagnostic: `logs/diagnostics/e8ddd939ee7a790e5a0ca026fe99ab0a05e7a505a636d259e1da63862d0d8543/errors.jsonl`, dòng1.
- Timestamp `2026-11-09T05:01:21.057963+00:00`; diagnostic transport bên trong
  `2026-11-09T05:01:20.816834+00:00`.
- Job `e8ddd939ee7a790e5a0ca026fe99ab0a05e7a505a636d259e1da63862d0d8543`;
  chapter **276880**, page60. Đây là job khớp sự cố được mô tả là chương5;
  không suy ra title từ thứ tự GUI.
- Provider `AGY Gemini`, mode `AI Gemini AGY`: **Batch**, không phải Whole.
  Model của journal `gemini-3.8-flash-medium`, CLI diagnostic1.5.3,
  timeout90s, budget64. Lỗi `TIMEOUT`, `parser_reason=TRANSPORT`,
  `guard_decision=STOP`, classification `UNKNOWN_PROTOCOL_SHAPE`.
- `request_number=2` là ordinal generation của provider instance, không phải
  retry count hoặc số request backend. Record có `retry=false`,
  `pending_preserved=true`, `translation_cached=false`.
- Reader đã ghi nhận stdout4096byte, stderr0byte, một newline;
  `exit_code=null`, không stream overflow. Không có raw stdout/terminal JSON,
  PID, attempt UUID, start timestamp hoặc HTTP status trong diagnostic này.
  Counter là dữ liệu reader quan sát, không chứng minh đã thu toàn bộ output.
- Batch ID `27478f2744cd062f554f43dca08714d623981597a7d5d944185352b70e5d2872`:
  24 trang có chữ,39vùng,226ký tự nguồn. Tái dựng ID từ OCR cache bằng SQLite
  immutable/read-only **khớp toàn bộ hash**; không chạy planner hoặc OCR/MT.
- Trang có chữ: 60,61,63,64,65,68,70,71,72,73,75,76,78,79,81,82,85,88,89,
  91,92,96,98,102. Batch trải khoảng60–102; trang không có vùng cần dịch
  không tính page cap của planner hiện có. Trang103 đã OCR làm lookahead.

Journal khớp: `cache/online_comics/pipeline-resume-v1/bc961120200340a4b4abfd08e40aeeb7.json`.
State `paused_provider`, updated `05:01:21.059971+00:00`. Có109trang,
59done1–59,50pending60–109; tương ứng54,13%. OCR ready1–103, còn104–109.
44 region receipts đã validated được giữ. Manifest chapter276880 cũng
`paused_provider`, needs_retry60–109. Đối chiếu109 source hash,59 pipeline
output,59 published output và59 SQLite done/output receipts khớp. Điều này
không có nghĩa mọi trang done đều có chữ đã dịch, hoặc đã decode lại bitmap.

## 4. Timeout thuộc lớp nào? Điều gì chưa chứng minh?

Đường lỗi trong source:

`MultiPageAGY.translate_batch → AGYProvider.translate_batch →
_run_translation → run_bounded → OnlineProviderError(TIMEOUT) →
ProviderSuspended(TIMEOUT) → ProcessingManager paused_provider →
diagnostic/checkpoint/signal → thông báo UI`.

Vị trí rà mã: `providers/agy.py:111` (runner), `:146–154` (đồng hồ/lỗi),
`:419` (generation/budget/runner/error wrap); `core/multipage.py:31` (planner),
`:113` (pacing), `:136` (batch/diagnostic); `core/pipeline.py:603–630`
(diagnostic/pause). Các dòng có thể dịch chuyển ở Stage sau.

| Nhận định | Phân loại và bằng chứng |
|---|---|
| CLI đã khởi động | FACT_CONFIRMED theo nhánh TRANSPORT/TIMEOUT: Popen đã trả process; loop còn poll=None tại deadline. Có stdout reader. |
| Timeout subprocess90s | FACT_CONFIRMED: options journal90, runner phát TIMEOUT khi monotonic vượt deadline; không phải timer GUI hay numeric guard. |
| Terminal đã được nhận hợp lệ | NOT_PROVEN: runner chưa trả output cho parser; không có terminal/schema validation. Không thể khẳng định terminal không tồn tại trong pipe/bytes bị mất. |
| Batch flush do page cap24 | INFERENCE từ planner và tái dựng batch khớp: số trang có chữ24;39vùng/226ký tự rất thấp. Không có event runtime ghi riêng lý do flush. |
| Pacing gây timeout | Không có bằng chứng. Source chờ trước khi vào provider/khởi động đồng hồ subprocess;5–10s không được cộng vào90s. Thời gian chờ thật không lưu nên chưa xác minh được. |
| Request budget hết | Không được hỗ trợ: ordinal2, budget64; mã lỗi TIMEOUT, không REQUEST_LIMIT. |
| Quota/rate/auth | NOT_PROVEN. Không có response reason tương ứng. TIMEOUT không phải bằng chứng quota. |
| Output overflow/JSON/ID/numeric | Không phải lỗi trực tiếp được ghi: transport timeout trước parser; overflow=false. Không có nội dung để đánh giá terminal nếu có. |
| Retry/fallback tự động | Không có nhánh tự retry/fallback trong đường lỗi đã đọc; record retry=false. Không quan sát được retry nội bộ AGY/backend hoặc toàn bộ các phiên khác. |
| Lý do CLI chưa kết thúc | NOT_PROVEN: không có raw terminal/exit/duration từng chặng; không đoán mạng, model, quota hoặc tool-use. |

Không sửa timeout, prompt, model, parser, pacing, guard hoặc journal để che
lỗi. Thông báo quyền nội dung UNKNOWN không tạo TRANSPORT/TIMEOUT này.

## 5. Giữ dữ liệu và khả năng resume

Codex không resume hoặc retry trang60/chương5/trang111. 59 output đã publish,
59 output pipeline,44 region receipts và109 nguồn đang khớp dữ liệu đã lưu;
50 trang pending không bị sửa. Batch lỗi không có bản dịch được cache theo
diagnostic. Các OCR cache sẵn có được giữ nguyên.

Có cơ sở để giữ checkpoint và đề nghị người dùng **chủ động** chọn Batch /
Tiếp tục từ cache sau khi kiểm tra thông tin lưu. Không bảo đảm AGY sẽ hoàn
tất lần sau, không bảo đảm timeout không tiêu thụ quota và chưa chạy nghiệm
thu resume Stage3H. Whole là đường mới riêng; không dùng nó để đổi done/pending
hoặc nhập59 output cũ vào journal Whole. Không tự thực hiện thao tác đó.

Bảo toàn:

- Metadata7349file cache/config/output/logs-diagnostics được snapshot trước
  chỉnh source; cuối lượt không đổi size/mtime, không mất file.
- SHA256 của **28.941/28.941file** được snapshot trong lượt forensic và đối
  chiếu sau triển khai,0đổi/0mất; gồm toàn bộ các cây trên cộng models/dist,
  BAT/spec gốc, đủ4EXE ImageTranslatorVN. Hash snapshot không chạy/import app.
- Không hash toàn bộ .venv; không có cài package hoặc sửa môi trường.
- SQLite chỉ mở URI `mode=ro&immutable=1` sau khi kiểm tra WAL không có dữ
  liệu; không gọi connection production ở chế độ ghi. Dữ liệu QA phát sinh
  trong lượt Codex chỉ là evidence dưới logs/stage3h-20261109T050706Z/.
- Không sửa/xóa artifact Stage3F hoặc dữ liệu production để làm Git sạch.

## 6. File Stage3H và kiểm tra đã thực hiện

Source Stage3H:

- `providers/agy.py`: thêm WHOLE_MODE, không đổi runner/timeout/guard.
- `sources/whole_input.py` (mới): context/input receipt, đọc cache và đường
  download tương lai qua adapter vào cache riêng.
- `sources/service.py`: fail closed nếu nhầm truyền Whole vào LocalComicJob;
  không ngầm đổi Whole thành Offline.
- `core/whole_chapter.py`: danh sách input_paths rõ ràng, optional journal
  marker và lọc renderer theo danh sách đó. Không migration journal production.
- `ui/main_window.py`: dropdown/itemData, routing nguồn, chặn đồng thời,
  menu Công cụ, nút mở kết quả Whole, không đổi Batch/Auto Fallback identity.
- `ui/comic_sources.py`: emit chương đã chọn, nhãn/điều kiện nút Whole,
  không chuyển Batch retry journal sang Whole.
- `ui/whole_chapter.py`: nhận nguồn/provider cố định, chuẩn bị ảnh trong
  worker, tìm lượt Whole lưu, nút thân thiện và xác nhận riêng giữ nguyên.

Tài liệu: báo cáo này, PROJECT_STATUS.md, README.md, docs/USER_GUIDE.md,
docs/TROUBLESHOOTING.md, docs/WEBSITE_ADAPTER_AI_GUIDE.md. Giữ lịch sử Stage3G.

Chỉ parse AST, đọc diff và `git diff --check`. **NOT_TESTED** cho mọi pytest/
unittest/mock/integration/GUI/layout/OCR/MT/cancel/resume/live/batch regression.
Không dùng497PASS/10SKIPPED Stage3F làm kết quả mới. AST không chứng minh API
Qt, signal, downloader, receipt hoặc GUI chạy đúng. Người dùng tự nghiệm thu.

## 7. Người dùng tự nghiệm thu và giới hạn còn lại

Trước hết mở source, kiểm tra đủ sáu lựa chọn, chọn Whole và xác minh không
AGY chỉ vì chọn. Dùng ảnh QA/chương đã cache, chọn một chương, bấm Chuẩn bị:
nguồn phải được nạp sẵn, không hỏi lại provider/thư mục. Kiểm tra số liệu và
output riêng, thử Hủy trước xác nhận; không được gọi dịch. Khi muốn live AGY,
người dùng tự đọc/xác nhận phạm vi và quota trong hộp xác nhận.

Kiểm tra đóng/mở lại: chỉ nạp lượt lưu, chờ Tiếp tục; xác nhận mới chỉ bật sau
khi worker xác minh số liệu/hash. Thử Hủy khi chuẩn bị; dữ liệu đã lưu cần được
giữ. Không dùng job production đang paused để nghiệm thu lần đầu. Không xóa
receipt để gọi lại AGY. Kết quả thiếu/sai ID/numeric phải chặn render, không
retry tự động. Các hành vi này là tiêu chí tự nghiệm thu, chưa được Codex chạy.

Các giới hạn: chưa nghiệm thu GUI/runtime; chưa đánh giá chương lớn thực tế;
chưa ghép publisher/tổng kết Batch và Whole; không migration OCR/translation
cache production; cache partial không tự sửa; chưa chứng minh nguyên nhân sâu
hơn của TIMEOUT. Không chuyển Stage tiếp theo hoặc build EXE.

## 8. Git & Fork Handoff

Root `D:/TransTool`, branch `main`, HEAD
`a0ea3bbc0479b0215645c83df0593571e167c4e7`. Baseline có12tracked modified và
1untracked Stage3G report, không staged/conflict. **Chưa commit Stage3G**;
không giả định người dùng đã commit. Giữ nguyên thay đổi đó.

Status cuối14tracked modified và3untracked (report Stage3G, report
Stage3H, sources/whole_input.py); kết quả máy lưu trong git-after.json. Không
sửa .gitignore; cache/output/logs/model/.venv/dist bị ignore đúng, source mới/
test/docs/spec/BAT/config mẫu vẫn hiển thị; không có runtime đã tracked cần
untrack. Không có binary hoặc credential mới trong danh sách review. Regex
rà secret chỉ hỗ trợ review, không thay thế người dùng xem diff.

Nên review/commit: bảy source Stage3H và sáu tài liệu liệt kê ở mục6. Working
tree còn thay đổi Stage3G có sẵn ở core/multipage.py, core/pipeline.py,
ui/settings_dialog.py, report Stage3G và các file source/docs dùng chung. Review
cả phần nền Stage3G vì Stage3H phụ thuộc nó; không commit thiếu dependency.
Không tự stage hoặc chia hunk thay người dùng.

Không commit: logs/evidence/hash snapshot/diff QA, cache/SQLite/journal,
output ảnh/receipt, model/weights, .venv, EXE, config cá nhân/credential AGY.
Không có yêu cầu xóa hoặc untrack dữ liệu.

`git diff --check` không báo lỗi ở lần rà cuối. Evidence:
`logs/stage3h-20261109T050706Z/` gồm git-before.json, diff-before.patch,
stage3h-only-review.patch (delta so với nền Stage3G chưa commit), static-review.json,
timeout-matches.json, timeout-forensic-summary.json, timeout-batch-reconstruction.json,
runtime-stat-before.json, protected-sha256-before.json, preservation.json và
git-after.json. Không cần đưa evidence runtime vào Git.

Fork: mở repo → Local Changes → review từng file và delta Stage3G/3H → tự
stage source/docs cần thiết → kiểm tra staged diff → tự nhập message/commit.
Gợi ý sau khi review: `feat(ui): expose whole-chapter AGY and document batch timeout`.
Message không nói đã chạy test hoặc sửa được nguyên nhân timeout.

**NO_COMMIT — NO_PUSH — NO_TAG — NO_DESTRUCTIVE_GIT.**

**STAGE_3H_IMPLEMENTED_NOT_TESTED** — dừng để người dùng tự nghiệm thu GUI.
