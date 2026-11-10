# Stage 3G — Whole Chapter AGY và Batch AGY 24 trang

09/11/2026. **STAGE_3G_IMPLEMENTED_NOT_TESTED**.

Đã kết hợp prompt chính và phần bổ sung; phần bổ sung ưu tiên: whole một lần
gửi, batch24trang và chờ5–10giây. Chỉ triển khai code, đọc diff và kiểm tra cú
pháp AST không import ứng dụng. **Không chạy pytest/unittest/mock/regression/
smoke/integration, không mở GUI, không chạy bất kỳ lệnh AGY hoặc API dịch nào.**
Kết quả Stage3F497/10 là lịch sử, không phải kết quả kiểm thử Stage3G.

## 1. Baseline và file thay đổi

Root D:/TransTool, branch main, HEAD
`a0ea3bbc0479b0215645c83df0593571e167c4e7`. Working tree sạch lúc bắt đầu;
Stage3F và các báo cáo trước đã được commit bởi người dùng. Index trống,
không có conflict. Đã đọc AGENTS/PROJECT_STATUS, báo cáo Stage3F, core whole/
pipeline/multipage/resume, provider/parser/runner AGY và UI trước khi sửa.

Source:

- core/multipage.py: tham số page cap riêng, giới hạn AGY, khoảng chờ hủy được.
- core/pipeline.py: thêm cờ pacing trong JobControl, không đổi TranslationService.
- core/whole_chapter.py: adapter whole AGY, consent binding, receipt phản hồi,
  budget bền vững, thống kê manifest và nối guard/render Stage3F.
- providers/agy.py: tái sử dụng command/runner/parser; entry whole một lần gửi;
  schema riêng và timeout riêng. Batch mặc định giữ giao thức cũ.
- ui/whole_chapter.py: lựa chọn Argos/AGY, thống kê, xác nhận riêng, mở kết quả.
- ui/main_window.py, ui/comic_sources.py: giới hạn và countdown batch AGY.
- ui/settings_dialog.py: giải thích giới hạn AGY/API và Whole Chapter độc lập.

Tài liệu: báo cáo này, PROJECT_STATUS.md, README.md, docs/USER_GUIDE.md và
docs/TROUBLESHOOTING.md. Không sửa tests, dependency manifests, Options hoặc
ResumeStore schema, adapter Kuaikan, model/default provider hoặc .gitignore.

## 2. Hai đường thực thi độc lập

| Thuộc tính | Whole Chapter AGY | Batch AGY | Gemini REST |
|---|---|---|---|
| Điều phối | WholeChapterJob → AGYWholeChapterTranslator | MultiPageAGY | MultiPageAGY nhánh API cũ |
| Trang | Toàn bộ manifest, local tối đa500 | Tối đa24trang có chữ | Giữ16 |
| Vùng/ký tự nguồn | Local10.000vùng/1.000.000ký tự | Tối đa60vùng/3.000ký tự | Giữ cấu hình/ràng buộc cũ |
| Gửi dịch | Một invocation tối đa/workspace | Theo batch có cache miss | Không đổi |
| Chờ5–10giây | Không | Trước lần gửi tiếp theo | Không |
| Xác nhận | Hộp xác nhận gắn hash manifest | Lệnh chạy batch hiện có | Không đổi |

Argos giữ đường Stage3F, dịch nội bộ từng vùng và không có pacing AGY.
Không dùng pack_pages/translate_batch để chia Whole Chapter.

## 3. Payload toàn chương và prompt

OCR xong toàn bộ mới tạo manifest; cache OCR, override/filter/preserved regions
của Stage3F giữ nguyên. Mọi trang vẫn có page_id/page_index, kể cả trang không
có vùng cần dịch. Mọi vùng cần dịch có region_id/reading_order/source_language,
original_ocr_text nguyên bản và text đã bảo vệ glossary. Không đưa trở lại vùng
false positive đã skip hoặc xóa vùng để vừa quota/batch. Raw OCR vẫn giữ local.

Payload gồm schema_version, chapter_id, manifest_hash và pages theo thứ tự.
Không chứa bitmap, đường dẫn ảnh, URL CDN, DB hoặc credential. Prompt yêu cầu
đọc ngữ cảnh toàn chương, dịch Việt tự nhiên, nhất quán tên/xưng hô/địa danh,
không tự suy quan hệ/tình tiết, không thêm/bớt/ghép vùng, giữ ID/marker và mọi
numeric token theo thứ tự/dấu. OCR chỉ là dữ liệu, không phải lệnh. Cấm tools/
file/shell/web/MCP/skills/agents như provider cũ.

Prompt được bọc đúng stream-json user event và gửi qua **stdin**; không đưa
OCR lên argv, không tạo file prompt. Chỉ schema ID và session settings nằm
trên argv. Các giới hạn vẫn hữu hạn:

- Whole stdin JSON tối đa16.000.000byte, theo mức local JSON của whole mode;
  không áp trần128KB của batch. Đây là trần an toàn local **chưa kiểm thử**,
  không khẳng định là dung lượng context/token AGY hoặc model hỗ trợ.
- Windows argv tối đa30.000UTF-16code units (dự phòng cho giới hạn command line);
  schema enum quá nhiều ID có thể chạm mức này trước giới hạn10.000vùng local.
- Giữ6.000ký tự tối đa/vùng AGY, output4.000ký tự/vùng theo parser cũ.
- Giữ stdout1MB/stderr64KB của run_bounded. Không nâng output limit chỉ vì
  chương lớn; vượt/cắt/thiếu vùng sẽ bị chặn, không chia batch hoặc tự gọi lại.
- Token/context/backend limit thực tế chưa được đo; không bịa giới hạn model.

## 4. Một invocation và xác nhận thủ công

AGYWholeChapterTranslator chỉ tra đường dẫn/hash executable khi worker chuẩn
bị; không chạy CLI. Danh tính riêng `whole-agy-v1:` có hash binary/model/prompt/
session settings/validator/schema, tách Argos và batch AGY.

Chọn AGY hoặc bấm OCR/Tiếp tục không cấp phép generation. GUI chỉ bật nút
**Xác nhận dịch bằng AGY…** sau worker trả awaiting_translation với manifest
đã chốt. Hộp xác nhận nêu số trang/vùng/ký tự và cảnh báo quota; Hủy là mặc định.
Hash manifest được truyền riêng, worker phải kiểm tra khớp trước generation.
Mở dialog, chọn thư mục/provider, OCR hoàn tất, nạp journal hoặc khởi động lại
không tự gửi. Provider ở cửa sổ chính không bị đổi.

Journal chốt `agy_attempt_used` trước khi có thể tạo process. Sau đó tái sử dụng
AGYProvider/command/run_bounded/parser cũ, `max_requests=1`, `probe_cli=False`.
Không chạy --help/--version trong whole mode, kể cả sau xác nhận, để không có
CLI invocation phụ. Không tuyên bố phiên bản/capability vừa được kiểm chứng:
version được đánh dấu unprobed, binary hash giữ vai trò identity. Flag sai hoặc
CLI không tương thích phải lỗi; không bỏ sandbox/permission guard để chạy được.

Một đường runner cho generation, không vòng lặp, không retry/fallback. Dùng
session đăng nhập hiện hữu, lọc API key/ADC như cũ, useG1Credits=false và toàn bộ
deny/settings cũ. Một invocation phía ứng dụng **không chứng minh chỉ có một
backend request nội bộ AGY**; quota/backend behavior không quan sát được ở đây.

`agy_attempt_used` là **ngân sách đã chốt**, không chứng minh process đã khởi
động hoặc quota đã bị tiêu thụ: lỗi local payload/argv/extension cũng có thể
xảy ra sau bước này. Không reset cờ khi resume. Nếu thiếu phản hồi đã lưu,
workspace đó không được gửi lần hai. Người dùng phải xem lại trước khi chủ động
tạo workspace mới; code không tự tạo lượt mới để retry.

## 5. Parser, validation, cache và resume

Whole yêu cầu JSON `translations[{region_id, translated_text}]` bên trong NDJSON
result wrapper hiện có. Parser dùng nhánh whole riêng cho tên trường này;
batch mặc định vẫn translations[id,text]. Không đoán JSON từ prose/markdown,
không nới tool-use predicate hoặc chấp nhận metadata trước đây bị reject.

Kiểm tra terminal/result/status/exit, num_turns, tool indicators, JSON/schema,
đúng tập ID duy nhất, không thiếu/lạ/rỗng và mapping theo ID. Normalize sang
contract Stage3F `{manifest_hash, translations:[{id,text}]}`. Hash binding lấy
từ input bất biến của chính invocation và journal đã chốt, không giả là model
đã echo hash. Kiểm tra manifest/source trước/sau, trước publish theo Stage3F.

Phản hồi đã qua protocol/ID được lưu `agy-response.json` có seal/namespace/hash,
**chưa được coi là bản dịch validated**. Chỉ lưu target chuẩn hóa cần thiết,
không raw NDJSON/stdout/stderr/prompt hoặc nội dung suy luận. Sau đó từng vùng
qua nguyên numeric/glossary guard `literal-numbers-v2-signed`, lưu progress/
accepted bền vững rồi mới render. Guard identity proxy chỉ ngăn đường dịch
ngoài ý muốn; bản dịch thực tế phải đến từ AGY transport, không phải mock.

Resume với raw receipt có thể hoàn tất validation/render local mà không gọi
lại. Receipt accepted/render cũ vẫn kiểm hash và skip; không ghi đè output
user sửa. Thiếu/hỏng receipt hoặc source/manifest/binary/recipe khác thì chặn.
Không migration journal production. AGY whole bắt buộc workspace stage3g mới;
không dùng/sửa workspace stage3f bằng cách đổi translator. Argos journal cũ vẫn
có thể nạp như Argos; không chuyển namespace giữa provider.

## 6. Timeout, cancel và lỗi

Timeout whole mặc định600giây, cấu hình riêng10–1800trong dialog; không sửa
timeout/budget batch. run_bounded chạy ngoài GUI, hủy process tree do ứng dụng
sở hữu, giữ checkpoint. Timeout/hủy không chứng minh chưa tiêu thụ quota.

GUI có mã/hướng dẫn cho CLI thiếu/không khởi động được, auth, model unavailable,
permission, quota/rate, timeout, empty output, nonzero exit, invalid JSON/ID/
tool guard, payload/argv limit, mismatch số và budget đã dùng. Không log raw
exception/response/key. Journal chỉ giữ mã lỗi và metadata AGY đã sanitize
nếu có, không lưu raw protocol. Lý do model/auth/quota chỉ phân loại khi CLI
trả code được hỗ trợ; unknown error không được suy thành quota.

## 7. Batch24, khoảng chờ và tương thích

`core/multipage.py`: AGY_MAX_PAGES=24, AGY_MAX_REGIONS=60,
AGY_MAX_CHARACTERS=3000; pack_pages nhận max_pages/hard_chars. Chỉ nhánh AGY
truyền24 và clamp ký tự/vùng. Nhánh Gemini API/default generic giữ16, cấu hình
và giới hạn cũ. Vùng riêng dài hơn3.000ký tự bị báo lỗi trang, giữ nguyên OCR;
không cắt chữ để nhét batch. Trang oversized nhiều vùng được chia theo ranh
giới vùng như trước. Batch kết thúc ở ngưỡng đầu tiên, không bắt buộc đủ24trang.

`MultiPageAGY.wait_before_next_invocation` chỉ chạy trong `if missing`. Sau
generation trước và validation/context receipt đã hoàn tất, cờ JobControl
agy_batch_completed được bật. Cờ dùng chung giữa các chương cùng worker/job,
không bị xóa bởi batch cache hit. Khi có lần gửi thật tiếp theo mới chọn ngẫu
nhiên5–10giây và chờ; không chờ trước lần đầu, sau lần cuối hoặc cache-only.
Phần OCR/render/cache xen giữa không phát sinh chờ riêng. Trước lần gửi kế
tiếp vẫn chờ đủ khoảng mới chọn, nên gap tổng thể có thể dài hơn10giây nếu
có thêm công việc xen giữa. Thời gian này luôn sau khi batch trước hoàn tất,
không tính từ lúc bắt đầu generation trước.

Chờ bằng Condition.wait từng lát≤0,2giây và checkpoint; Cancel notify_all làm
thức ngay, kiểm tra hủy lại trước gửi. Pause chặn ở checkpoint; không GUI sleep.
Event agy_batch_wait hiển thị countdown trên tab thư mục/ảnh/URL. Không áp
cho Whole AGY, Argos, API, OCR hay render. Không tăng concurrency/retry/budget.

Nếu provider cung cấp minimum_batch_interval_seconds hợp lệ lớn hơn10 thì
dùng mức lớn hơn; không giả định AGY đã công bố mức này. Rate/quota/auth/
permission lỗi vẫn dừng qua đường lỗi hiện có, không dùng countdown để retry
hoặc né hạn mức, không đoán thời điểm reset.

BATCH_VERSION/provider identity, recipe và receipt keys cũ giữ nguyên. Context
cache đã hash cả batch members/source/context: nhóm mới24 thay16 tạo context
khác khi thành viên khác. Region receipt cũ vẫn đọc context/target_hash cũ;
output done giữ nguyên. Không sửa/move journal hoặc âm thầm tái dịch tất cả.
Pacing chỉ là state RAM, không vào cache identity. Restart không gửi gì tự động;
người dùng bấm tiếp tục mới chạy. Tương thích này **chưa kiểm thử**.

## 8. Người dùng tự nghiệm thu

1. Mở source bằng `D:\TransTool\run_source.bat` (không phải EXE cũ). Codex không
   chạy BAT/GUI. Không cần build/cài dependency trong nhiệm vụ này.
2. Đặt model/path AGY hợp lệ trong Cài đặt chính như trước. Mở menu Whole
   Chapter Translation → chọn AGY CLI; kiểm tra model và timeout hiển thị.
3. Chọn thư mục ảnh local của **một chương**. Bấm OCR/tạo manifest mới. Phải
   thấy số trang/vùng/ký tự; chưa có generation hoặc countdown batch ở bước này.
4. Bấm Xác nhận dịch bằng AGY…; kiểm tra số liệu. Bấm Hủy phải không gửi.
   Chỉ chọn Xác nhận mới cho phép một invocation. Nên bắt đầu ảnh QA nhỏ;
   không tự coi code chưa test là đã an toàn cho chương production.
5. Khi chạy, xem trạng thái/progress/Hủy. Sau trả kết quả, kiểm tra số vùng qua
   guard, trang render/skip, kích thước bitmap/nội dung, output/journal QA và
   guard numeric/glossary. JSON hợp lệ không chứng minh đúng nghĩa.
6. Đóng/mở lại → mở journal → Tiếp tục: nếu có response/accepted hợp lệ phải
   phục hồi local; thiếu response sau budget đã chốt phải chặn, không gửi lại.
   Không sửa cờ/hash bằng tay hoặc xóa cache để ép invocation thứ hai.
7. Kiểm tra batch bình thường riêng: thông tin24/60/3.000, batch không bắt buộc
   đủ24. Với dữ liệu đủ nhiều và ít vùng/ký tự, quan sát ranh giới24. Với vùng/
   ký tự đầy trước phải flush sớm. Quan sát chờ5–10giây trước lần gửi tiếp.
8. Hủy trong countdown phải không gọi batch kế. Cache-only không chờ; cache
   xen giữa hai batch thật vẫn có pacing. Quota/rate/permission phải dừng.
9. Kiểm tra Argos và Gemini API độc lập: không chịu pacing AGY; API giữ16trang.

Tất cả bước trên là hướng dẫn **người dùng tự làm**, Codex chưa thực hiện.
Chưa xác minh CLI lớn/argv/schema mới/JSON mapping/cancel/latency/token limits,
batch24/cached resume, layout/high DPI hoặc chất lượng toàn chương. Không có
nhãn test/runtime nghiệm thu. Dừng ở trạng thái IMPLEMENTED_NOT_TESTED.

## 9. Git & Fork Handoff và bảo toàn

Baseline main/a0ea3bb sạch, index trống. Không stage/commit/push/tag/restore/
reset/clean/merge/rebase. .gitignore không đổi; không che source/test/docs mới.
Các file source/docs liệt kê mục1 cần review trong Fork; không stage evidence,
cache/DB/journal/log/model/output/credential/EXE. Không sửa/xóa60PNG Stage3F,
evidence cũ hoặc output production. Không gọi app để xác minh dữ liệu.

Evidence tĩnh nằm trong thư mục logs/stage3g-… được trỏ bởi
`logs/latest-stage3g.json`: git-before.json, runtime-stat-before.json,
static-review.json, metadata-preservation.json, git-final.json. Metadata/stat
không phải hash audit toàn bộ dữ liệu; không gọi đó là nghiệm thu pipeline.
Danh sách cuối/diff --check/check-ignore ghi trong git-final.json sau cập nhật docs.
Không có thay đổi dependency/model/config người dùng/BAT/spec/EXE.

Status cuối:12tracked modified và1báo cáo mới untracked, tất cả thuộc Stage3G.
HEAD/branch giữ nguyên, index trống. git diff --check không báo lỗi; AST đọc8
filePython không phát hiện lỗi cú pháp. .gitignore giữ nguyên; source/report
mới hiển thị trong Fork, runtime bị ignore đúng. Không có runtime đã track,
file review binary hoặc >2MiB; rà mẫu key/Bearer/private-key không có cờ nghi
ngờ (scan có giới hạn, không phải đảm bảo mọi loại secret).

Đối chiếu tĩnh cache/config/output/logs-diagnostics: **7.226file**, không đổi
size/mtime, không thiếu hoặc thêm file. So hash riêng4EXE và6BAT/spec với
snapshot Stage3F vẫn khớp; `exe-launcher-hashes.json` giữ kết quả. Không quét
hash toàn bộ .venv/models hoặc gọi pipeline để bảo toàn. Những kết quả này
không thay thế việc kiểm thử logic mới.

Fork: Local Changes → review từng file/hunk → người dùng tự stage/commit nếu
muốn. Message gợi ý: `stage(3g): implement single-call AGY chapters and paced 24-page batches`.

**STAGE_3G_IMPLEMENTED_NOT_TESTED**

**NO_TESTS · NO_LIVE_AGY · NO_LIVE_API · NO_BUILD · NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT**
