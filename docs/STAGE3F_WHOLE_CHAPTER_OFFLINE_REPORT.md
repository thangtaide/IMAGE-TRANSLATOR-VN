# Stage3F — Whole Chapter Translation, offline-first

Ngày09/11/2026. Phạm vi nghiệm thu: chương tổng hợp, mock translator và
PaddleOCR/Argos đã cài. Không gọi dịch mạng hoặc chạy chương production.

**STAGE_3F_COMPLETED_WITH_WARNINGS**: luồng offline/mock đạt; giữ cảnh báo về
artifact test ban đầu ở mục7. AGY thật chưa triển khai/nghiệm thu trong whole mode.

## 1. Baseline và kế hoạch

Đã đọc AGENTS, PROJECT_STATUS, báo cáo Stage3C/batching/resume, source OCR,
TranslationService, cache, receipt, source downloader và GUI. HEAD thực tế
`9e20d094e70b2de78762e15b5e7bec7157a0527b`, branch main. Stage3D.2 ghi lịch sử
454PASS/10SKIPPED mỗi runner; không nhận đó là kết quả chạy mới của Stage3F.

Baseline chưa commit gồm PROJECT_STATUS.md, docs/TROUBLESHOOTING.md modified và
hai báo cáo forensic/live-smoke Stage3D.3 untracked. Giữ nguyên các thay đổi này.
Chưa có Stage3E/provider Groq/DeepSeek được xác minh trong source; không giả định
chúng tồn tại hoặc gọi bất kỳ dịch vụ nào để kiểm tra.

Kế hoạch đã thông báo trước sửa: thêm coordinator whole-chapter QA độc lập;
dùng OCR/guard/render hiện có, không thêm field Options làm đổi identity batch.
Snapshot runtime/resource trước kiểm thử tại
`logs/stage3f-20261109T024010Z/protected-before.json`: **24.067 file, bốn EXE**.
Phạm vi rộng hơn snapshot forensic trước, gồm cả các file trong dist hiện có.

## 2. Kiến trúc trước và sau

Trước: ProcessingManager xử lý tuần tự; AGY/API có MultiPageAGY planner giới
hạn3.000ký tự/60vùng/16trang. OCR cache độc lập provider; ResumeStore version1
lưu trang/region/output receipt và publication intent.

Luồng thử nghiệm mới:

```text
Danh sách ảnh local (natural order, cố định)
  → OCR tuần tự một worker → SQLite QA + receipt OCR từng trang
  → Chapter OCR Manifest hoàn chỉnh, SHA256
  → whole-chapter translator interface (Argos hoặc manual mock)
  → strict ID mapping + numeric/glossary guard từng vùng
  → durable validated-translations.json
  → ProcessingManager với PreparedChapter → render tuần tự/atomic publish
  → ResumeStore/receipt render QA hiện có
```

Không thêm downloader hoặc gọi source adapter trong coordinator. Đọc ảnh local
đã có; không tích hợp chế độ này vào tải chương production. Toàn bộ artifact,
SQLite/WAL, journal/diagnostic/output mới phải ở `output/stage3f-…`; từ chối
workspace ngoài QA hoặc có symlink. Không reuse SQLite/cache production để thử.

ProcessingManager chỉ thêm hook `prepared_chapter` mặc địnhNone. Khi có hook,
identity render chứa hash manifest/kết quả đã xác nhận và for_page đối chiếu OCR
trước khi trả target. Không có hook thì batch/Argos/MyMemory/AGY/API chạy nhánh
cũ. TranslationService và numeric/glossary code không đổi. Không sửa Options,
ResumeStore schema, provider mặc định hoặc namespace translation cache cũ.

`sources/service.py` tách đường dẫn staging sẵn có thành hằng
PIPELINE_STAGING_ROOT. Giá trị mặc định vẫn đúng `ROOT/output/online_comics_work`,
không đổi namespace, download/access gate hoặc hành vi batch. Harness test có
thể đổi riêng hằng này sang QA mà không đổi ROOT dùng kiểm tra đường dẫn an toàn.

## 3. Chapter OCR Manifest

- schema_version1, recipe whole-chapter-local-v1; chapter identity và OCR identity.
- Trang có index theo danh sách đầu vào, đường dẫn tương đối, hash ảnh và ID.
- Vùng có ID ổn định theo page ID/region slot, reading_order/group_id, text gốc,
  polygon, confidence/language. Đủ thông tin để đối chiếu tọa độ khi render.
- Giữ riêng raw_ocr nguyên bản, effective regions sau override/filter hiện có,
  preserved regions, override receipt, warnings và kích thước ảnh.
- SHA256 content_hash bao toàn manifest. ID duy nhất trong manifest; response
  phải gắn đúng manifest_hash. Không dùng thứ tự worker hoàn thành làm thứ tự trang.

Giới hạn local:500trang,10.000vùng,1.000.000ký tự nguồn, JSON đọc tối đa16MB;
target mock tối đa12.000ký tự/vùng. Đây là giới hạn QA local, **không phải** hạn
mức AGY/API đã được xác minh. Argos vẫn có token/decode limit của provider cũ.
Manifest vượt giới hạn bị chặn, không cắt hoặc bỏ vùng để tạo PASS.

Không giữ danh sách bitmap cả chương: metadata/text được gom, từng bitmap được
đọc, OCR hoặc render rồi giải phóng theo scope. Render có các ảnh trung gian
của một trang theo pipeline cũ. Chưa tăng worker ngoài mức1.

## 4. Translator, validation và cache

ArgosWholeChapterTranslator sử dụng model Argos/CTranslate2 CPU int8 đã cài,
route zh→en→vi hiện có. Giao diện đầu vào là một manifest chương nhưng suy luận
**từng vùng** nội bộ. Không tương đương một request AGY toàn chương hoặc model
hiểu ngữ cảnh toàn chương. Thiếu model trả blocked/MISSING_MODEL, không tải model.

MockWholeChapterTranslator nhận packet có manifest_hash và region ID/text;
manual response contract là JSON translations[id,text]. Đây là fixture thiết
kế cho QA, không phải bằng chứng về giao thức AGY thật. Cho phép đảo thứ tự
response nhưng phải có đúng tập ID, không thiếu/trùng/lạ/rỗng hoặc duplicate
JSON keys. JSON lỗi/bị cắt hoặc hash sai bị từ chối trước render.

Guard dùng nguyên TranslationService._translate_using qua cache validation
không trả cache hit, vì phải thực sự kiểm tra raw target nhận được. Numeric
version vẫn **literal-numbers-v2-signed**. Glossary dùng marker/restoration cũ,
không sửa số, không thêm date handler. Guard không tự chứng minh đúng ngữ nghĩa.

Translation progress và accepted file là cache/receipt riêng của whole mode:
namespace có version, manifest hash, provider identity, glossary và validator.
Giữ raw/validated target trong artifact QA cục bộ để revalidate khi resume;
không ghi vào cache Argos/MyMemory/AGY/API production. Không dùng provider cache
hit để bỏ qua kiểm tra một response mới. Không cache một vùng bị guard từ chối
như bản dịch hợp lệ; các vùng hợp lệ trước đó có thể giữ trong progress QA.

## 5. Resume, integrity và GUI

- chapter-journal.json/receipt OCR/translation đều atomic. Mỗi trang OCR xong
  được lưu trước khi chuyển sang trang tiếp; raw OCR vẫn ở SQLite QA.
- Resume đối chiếu danh sách nguồn/hash/recipe/OCR identity. Nguồn thiếu/hỏng/
  đổi hoặc manifest bị sửa thì chặn. Không sửa hash/journal bằng tay để ép chạy.
- run(allow_translation=False) không gọi translator cho phần thiếu. Người dùng
  phải chủ động cho phép mỗi lượt cần dịch; không replay sau timeout/cancel.
- Toàn bộ target phải hợp lệ và accepted file durable trước event RENDER.
  Có thể phục hồi accepted đã atomic publish nhưng crash trước commit journal,
  sau khi kiểm tra namespace/manifest/guard. Không cần gọi translator lại.
- Render dùng ResumeStore/atomic publication hiện có. Trang done phải có hash/
  receipt hợp lệ mới skip; không ghi đè output user sửa hoặc output khác recipe.
- Rà soát phát hiện khe kiểm tra giữa dịch và publish: chỉ xác minh nguồn trước
  render chưa đủ nếu ảnh/manifest/accepted bị đổi ngay sau đó. Whole plan kiểm
  lại hash nguồn của từng trang và hai artifact lúc lấy target, ngay trước
  atomic publish và khi render kết thúc. Ba test mới đổi nguồn ở ranh giới
  render, đổi manifest/accepted trước publish: bị chặn, không publish bản dịch
  sai; fallback nguyên bản theo Stage1 nếu đã vào xử lý trang. Không sửa guard.
- Một whole job trong app tại một thời điểm; workspace có OS file lock, giải
  phóng khi process chết, không cần xóa stale lock để resume. Không có migration
  các job cũ hoặc tự chuyển provider khi mở lại.

Menu **Whole Chapter Translation (thử nghiệm)…** mở dialog riêng, chỉ Argos.
Không đổi lựa chọn/provider/config của cửa sổ chính. QThread chạy OCR/MT/render;
GUI có tiến độ theo giai đoạn, Hủy và Mở journal/Tiếp tục QA. Mở journal không
tự chạy; checkbox cho phép dịch mặc địnhfalse và được bỏ tích sau lượt chạy.
Không mở dialog khi worker ảnh/URL/thư mục đang chạy. Xem USER_GUIDE.

## 6. Kiểm thử và đo lường

Unit/fixture bao gồm1/16/100/120trang, trang0OCR, nhiều vùng, thứ tự OCR đảo,
ID/schema/target/JSON sai hoặc bị cắt, mismatch số/glossary, timeout/cancel,
source/manifest/accepted bị sửa, thiếu model, chỉ một job, không dịch ngầm,
resume sau OCR/sau MT/render dở, crash giữa accepted publication và commit,
output/receipt cũ bất biến và fresh Python process resume không OCR/MT lại.
Qt thật offscreen, worker/mock OCR/MT, kiểm tra heartbeat GUI và progress cuối.

Lượt focused đầu:33PASS/1FAIL (workspace không an toàn trả ValueError chung).
Đã sửa mã lỗi thành ChapterError/WHOLE_QA_WORKSPACE_REQUIRED, không nới ranh giới
QA. Focused sau sửa:73PASS/0FAIL/0SKIPPED, gồm whole/multipage/numeric tests.
Các ca GUI bổ sung nằm trong full regression cuối.

Full regression dùng harness riêng chuyển CACHE/CONFIG mặc định sang QA, chặn
socket, bảo vệ file production đã snapshot, không dùng credential thật trong
process kiểm thử. Các subprocess kiểm tra runtime là Python local, không AGY.
Harness cho phép lệnh version/CPU read-only và taskkill của test timeout/cancel
cho process Python fixture; không chạy CLI dịch. Các lượt harness lỗi ban đầu
(UTF8, nhận diện executable/PID cleanup quá chặt) giữ evidence; không sửa test
cũ/guard ứng dụng hoặc bỏ test lỗi để tạo PASS. Kết quả cuối được ghi bên dưới.

| Runner cuối | PASS | FAIL / ERROR | SKIPPED | Thời gian |
|---|---:|---:|---:|---:|
| Full pytest acceptance |497|0 /0|10|92,42giây|
| Full unittest acceptance |497|0 /0|10|92,131giây|

507ca mỗi runner, thêm43test so với baseline lịch sử454PASS/10SKIPPED. Hai test
Qt mới dùng QApplication/QThread thật offscreen; mock OCR/MT, có heartbeat,
progress100% khi xong và không tự start khi mở dialog. Full suite cũng chạy
native import guard, OCR/Argos integration và workflow provider/batch/resume cũ.
Không đồng nhất Qt offscreen với nghiệm thu tương tác trên màn hình Windows thật.
10skip giữ nguyên: thiếu model OCR/MT ngôn ngữ phụ, M2M100, hoặc live opt-in.
Không ép skip thành pass và không gọi các live test đó.

Lượt đạt trước khi cô lập thêm staging: `pytest-run6/results.xml`,
`unittest-verified/summary.json` và console tương ứng trong evidence. Chạy lại
hai runner sau thay đổi staging, artifact cuối có nhãn `final`.
Lượt `final` trước hardening publish đạt494PASS/10SKIPPED mỗi runner. Sau thêm
3test và kiểm tra hash sát publish, kết quả cuối nằm ở
`pytest-acceptance/results.xml`/console.txt và
`unittest-acceptance/summary.json`/console.txt. Không có test bị bỏ để qua gate.
Các lượt pytest-run4 (15FAIL do harness chặn nhầm subprocess), pytest-run5
(3FAIL/2ERROR do harness chặn taskkill của Python fixture) giữ lại; không dùng
kết quả cuối để xóa lịch sử lỗi harness. Kết quả XML thực tế có thẩm quyền khi
cần xem riêng phân loại failure/error của từng lượt.

QA bổ sung `partial-progress-resume.json`:3trang/3vùng, hủy sau1vùng đã validated;
gọi lại không cho phép dịch → awaiting_translation, mock call vẫn1; cho phép
tiếp có chủ đích → chỉ2ID pending được gửi mock,3output, không OCR lại. Đây là
QA local riêng, không cộng thêm vào số test494 hoặc gọi là AGY thật.

| QA riêng | Mock120 | OCR + Argos thật |
|---|---:|---:|
| Ảnh / vùng |120 /240|3 /6|
| Ký tự nguồn |1.224|45|
| Output bitmap hợp lệ |120|3|
| Invocation whole mock |1 (240vùng)|0; Argos suy luận6vùng local|
| Thời gian pipeline |25,937giây|10,797giây|
| Peak Python allocations (tracemalloc) |4.961.721byte|126.733.524byte|
| Peak process working set Windows |254.529.536byte|999.112.704byte|
| Network attempts bị chặn |0|0|
| Hash nguồn QA giữ nguyên |Có|Có|

Mock dùng ảnh800×400 và hai vùng/trang; OCR/MT là fixture. Ca thật dùng3ảnh
Trung tổng hợp1200×430, PaddleOCR/Argos thật, không OCR/cache production.
Peak working set tính cả runtime/model của process, không phải riêng metadata
chương; tracemalloc không đo toàn bộ native RAM. Không suy hiệu năng của mọi
chương thực từ ảnh tổng hợp này. Chưa chạy100–120trang qua OCR/Argos thật.

Evidence QA:
`output/stage3f-qa-mock120-20261109T032505Z-508cc5/report.json`,
`output/stage3f-qa-offline-20261109T032534Z-f171a5/report.json`.
Đây là lượt đo lại sau hardening publish. Hai lượt đầu22,625/18,125giây và
artifact tương ứng vẫn giữ nguyên; không suy tăng/giảm tốc độ từ một lần đo
khác trạng thái cache hệ điều hành. Không benchmark provider khác.
Evidence test/Git/preservation: `logs/stage3f-20261109T024010Z/`.

## 7. Bảo toàn và phát hiện về vị trí artifact test

Đối chiếu lần đầu sau hai runner đạt: **24.067/24.067 file có sẵn giữ nguyên
SHA256**,0thiếu/0đổi, gồm4EXE, model/config/BAT/spec và ảnh/cache/SQLite/journal/
receipt/output production trong snapshot. Không chạy job production, không retry
trang111 hoặc resume chương đã dừng. Nguồn QA tổng hợp cũng giữ nguyên hash.

Kiểm tra inventory bổ sung phát hiện **60 file PNG fixture mới,23namespace**
dưới `output/online_comics_work` do nguồn staging global của regression cũ.
Các lần chạy đó đã cô lập SQLite/settings nhưng chưa cô lập đường staging này.
Không có file cũ bị ghi đè, nhưng **không thể gọi các lượt đó là mọi ghi mới đều
nằm trong workspace Stage3F**. Đây là thiếu sót của harness; giữ nguyên60file,
không xóa chúng để làm inventory trông sạch. Danh sách/hash lưu riêng trong
`test-staging-spill.json` ở evidence để review và đối chiếu lần cuối.

Đã tách hằng staging mặc định như mục2 và đổi riêng trong harness sang
`output/stage3f-regression-…/source-staging`; chạy lại full regression. Không
thay đổi vị trí stage mặc định của ứng dụng người dùng hoặc sửa DB/receipt để
đổi đường dẫn job cũ. Không nên commit60artifact hoặc evidence runtime.

Đối chiếu **sau bản acceptance và hai QA đo lại**:
`preservation-acceptance.json` xác nhận24.067/24.067file gốc giữ SHA256,
0đổi/0thiếu;60artifact test cũ cũng giữ hash, **không có file thêm khác** trong
các vùng production đã kiểm kê. Không xóa hoặc chuyển60file này. Đây là lý do
giữ trạng thái WITH_WARNINGS, không báo toàn bộ các lượt QA đều không ghi vào
đường staging chung. Các job production, DB/journal/receipt/output cũ không đổi.

## 8. Giới hạn và nghiệm thu AGY sau này

- Không live AGY/Gemini/Groq/DeepSeek/MyMemory; không request dịch hoặc chi phí.
- Whole mode chưa có adapter AGY thật. Không tăng giới hạn60 của provider AGY
  cũ thành toàn chương; không đổi prompt/CLI/security hoặc request budget cũ.
- Chưa biết một response AGY chứa240vùng có nằm trong payload/output/token/
  timeout limit hay không. JSON mock đúng không chứng minh AGY thật sẽ trả đúng.
- Muốn thử sau này: giữ nguồn/output production, dùng workspace QA mới; kiểm
  tra schema envelope AGY riêng, giới hạn request/bytes và ID/manifest binding;
  chỉ chọn manifest QA tổng hợp nhỏ trước. Cần adapter fail-closed và phạm vi
  live được phê duyệt riêng trước khi nối nút chạy. Không dán manifest truyện
  production vào CLI như bước mặc định của hướng dẫn này.
- Chưa benchmark chất lượng ngữ nghĩa hoặc thêm context hiểu toàn chương cho
  Argos. Không nâng model/provider hoặc tự phục hồi trang111/production khác.
- Hủy tại checkpoint; một lần suy luận Argos đang chạy không bị cưỡng bức ngắt
  giữa chừng. Test crash là fixture/process restart, không nghiệm thu mất điện thật.
- Manifest hoàn chỉnh so với danh sách file local đã chốt, không chứng minh đủ
  trang trên website. Chưa tự đối chiếu downloader manifest để phát hiện file
  vốn đã thiếu trước lượt đầu; thiếu/thay đổi so với danh sách đã lưu bị chặn.

## 9. Git & Fork Handoff

Root D:/TransTool, main/9e20d094e70b2de78762e15b5e7bec7157a0527b. Baseline cũ
được giữ, không stage hoặc hoàn nguyên. .gitignore không cần sửa:
output/log/cache/model/EXE ignore, source/test/docs/QA script hiển thị để review.

Git status cuối:7tracked modified và8untracked, trong đó có2báo cáo Stage3D.3
untracked đã tồn tại.13file thuộc Stage3F (hai docs chung có cả hunk trước).
Index trống, HEAD/branch không đổi. `git diff --check` đạt; rà cả untracked
text không có trailing whitespace. check-ignore xác nhận runtime bị ignore,
source/test/docs/spec/BAT/config mẫu không bị che. Không có runtime đã track,
binary hoặc file review lớn hơn2MiB. Rà mẫu key/Bearer/private-key trong15file
review không có cờ nghi ngờ; đây là scan có giới hạn, không phải audit mọi secret.
Evidence Git tại git-before.json, git-review.json, git-final.json/review-scan.json
trong thư mục logs Stage3F; runtime evidence được ignore.

File Stage3F cần review:

- Source: core/whole_chapter.py, core/pipeline.py, ui/whole_chapter.py,
  ui/main_window.py, sources/service.py (chỉ tách hằng staging như trên).
- Test/QA source: tests/test_whole_chapter.py, qa/validate_whole_chapter.py,
  qa/run_whole_chapter_regression.py.
- Docs: README.md, PROJECT_STATUS.md, docs/USER_GUIDE.md,
  docs/TROUBLESHOOTING.md, báo cáo này.

PROJECT_STATUS/TROUBLESHOOTING có cả hunk cũ. Hai báo cáo Stage3D.3 untracked
đã có trước, không nhận là Stage3F; review riêng. Không commit ảnh/output,
SQLite/WAL/journal/manifest OCR runtime, model, credential, logs hoặc EXE.

Trong Fork: Local Changes → review từng file/hunk → chỉ stage source/test/docs
phù hợp → xem staged diff → tự commit. Commit không phải điều kiện chạy QA.
Message đề xuất sau khi regression đạt:
`stage(3f): add offline whole-chapter manifests and resumable rendering`.

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT**
