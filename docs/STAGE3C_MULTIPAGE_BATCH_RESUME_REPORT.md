# Stage3C — Multi-page OCR batching & persistent resume

Ngày08/11/2026. **STAGE_3C_COMPLETED_WITH_WARNINGS**.
Đã triển khai, local/mock regression, Windows GUI, OCR/Argos thật và một lượt
AGY thật giới hạn đã được duyệt. Không build hoặc chuyển Stage4.

## 1. Baseline và phạm vi bảo vệ

Đọc AGENTS/PROJECT_STATUS, storage/types/pipeline/diagnostics/overrides/providers,
source job/worker/UI/settings, báo cáo Stage3B và luồng tải. Baseline thực tế là
318PASS/10SKIPPED mỗi runner, không phải chỉ309/10 của Stage3B. Git main/HEAD1a47b15,
không staged. Có sẵn4tài liệu sửa và2file chưa track của lượt IMAGE_LIST_READY;
không hoàn nguyên, không nhận là file mới do Stage3C tạo. Hai file untracked ấy
giữ nguyên hash; bổ sung Stage3C vào tài liệu chung, giữ nội dung lịch sử.

Trước sửa snapshot595file runtime/resource tại
`logs/stage3c-20261108T052551Z/protected-before.json`; cuối giữ595/595hash.
Gồm source/cache/output chương274872, DB/checkpoint/manifest, model/config/BAT/
spec và4EXE. Chương vẫn120output/119pipeline-normal+fallback111/needs_retry111.
119 không đồng nghĩa119trang đều có chữ đã dịch. Không chạy job này hoặc retry111.

## 2. Luồng mới và giới hạn

Downloaded/local ImageCollection → ProcessingManager.load_ocr_page → OCR cache
nguyên bản → áp override/filter hiện có → MultiPageAGY planner → AGY → guard
từng vùng → region receipt/cache → render từng trang đầy đủ → atomic publish
→ output checkpoint → LocalComicJob publisher/manifest.

Không tạo engine OCR/MT thứ2, không đổi model, không sửa core/runtime.py,
core/ocr.py, providers/offline.py hoặc providers/online.py. Numeric/glossary
comparison giữ nguyên byte so với HEAD, VALIDATOR_VERSION vẫn literal-numbers-v2-signed.

| Giới hạn | Giá trị và hành vi |
|---|---|
| Mục tiêu ký tự | 3.000, cấu hình100–12.000; đếm ký tự Unicode nguồn |
| Vùng/batch | 60, cấu hình1–60 |
| Trang có chữ/batch | Tối đa16, giới hạn bổ sung cho lookahead |
| Vùng riêng | Tối đa6.000ký tự; quá dài fail closed, không cắt chữ |
| Tổng request | Tối đa12.000ký tự sau bảo vệ glossary, input128KB |
| Output | stdout1MB/stderr64KB, JSON từng target1–4.000ký tự |
| Context | Tối đa8vùng/1.600ký tự JSON, có thể tắt |
| Timeout/request budget | Giữ cấu hình AGY, mặc định90giây/64lượt mỗi lần chạy |

Trang còn vừa batch được giữ nguyên. Thêm trang vượt char/region/ngôn ngữ hoặc
lookahead limit thì flush batch trước. Trang oversized chia theo region, không
cắt text. Một vùng lớn hơn ngưỡng mục tiêu có thể đi riêng tới6.000ký tự; vẫn
chịu hard limit/target limit. Cuối chương flush batch cuối. Empty OCR không gửi
AGY, giữ pixels gốc và ghi no_text_to_translate. Không gọi đó là dịch văn bản.

AGY legacy translate_batch vẫn chia12 khi không có item_ids; planner mới gọi
nhánh ID rõ ràng, tối đa60, với kiểm tra kích thước và schema. Không chỉ đổi12→60.
MyMemory không nhận batch3.000ký tự: vẫn chunk450byte, giới hạn API500byte như cũ.
Argos tiếp tục tuần tự; Offline vẫn mặc định, không gọi AGY hay tự đổi provider.

## 3. ID, validation và context/cache

ID chứa prefix job/chapter hash, page index, image hash, region index và reading
order. Parser đòi đủ ID duy nhất, không ID lạ; trả lại thứ tự input dù JSON bị
đảo. JSON hợp lệ không chứng minh ngữ nghĩa đúng. Mỗi target qua guard cũ riêng;
numeric mismatch không được cache hợp lệ hoặc dùng làm context. Các vùng khác
được commit riêng, các trang hợp lệ khác vẫn có thể xuất. Trang thiếu/sai một
vùng không render/inpaint dở; dùng cơ chế fallback Stage1 đúng trạng thái.

Context là đoạn source/target trước đã qua validation, có ID/dedup, reference_only
và chỉ dẫn không xem là lời thoại mới/lệnh. Không suy danh tính/quan hệ hoặc tự
tạo tóm tắt. Đây không phải human-verified truth, có thể chứa lỗi nghĩa chưa
phát hiện. Không truyền toàn chương. Chỉ các vùng accepted được carryover.

`multipage-ids-context-v1`, provider/model identity, glossary, cấu hình batch,
batch members/source và context digest tham gia namespace/cache. Raw OCR cache
key không đổi và không có provider. Cache Argos/MyMemory không đổi, không dùng
lẫn cache AGY. Region journal lưu context hash và target hash, không sửa DB schema.
Resume cùng AGY dùng receipt đã validated; đổi provider giữ receipt/cache cũ,
phần pending dùng namespace mới. Không lấy Argos cache giả làm AGY hoặc ngược lại.

## 4. Checkpoint, restart và publication

- `core/resume.py:ResumeStore`: journal version1 cạnh database, thư mục
  `<database-stem>-resume-v1`; atomic fsync/rename, file đọc tối đa16MB. Không
  ghi vào models/_internal hoặc hardcode D trong runtime.
- Pipeline journal lưu options/work recipe, source hashes/page states,
  validated-region receipts, context và original output/job/fingerprint receipt.
  Không đánh dấu done khi batch trả lời; done chỉ sau output hợp lệ.
- Trước publish, file tạm đã decode được gắn hash/publication intent. Nếu crash
  sau publish nhưng trước checkpoint, worker xác minh bitmap/hash/metadata rồi
  hoàn tất receipt gốc. Không đổi output cũ sang recipe mới.
- Source journal giữ danh sách chương đã chọn, thứ tự và cached_chapters count.
  Restore xác minh toàn bộ cache đã ghi nhận/output thành công trước inference.
  Cache hỏng/thiếu không bị âm thầm tải lại. Chương chưa được tải từ đầu chỉ
  được discovery/access/policy lại trong lệnh tiếp tục chủ động rồi mới download.
  Không tự tải khi mở app. Không thay download policy/allowlist/DNS/CDN safeguards.
- Khi source publish xong nhưng manifest chưa lưu, replay receipt_job_id gốc;
  publisher nhận cùng bitmap/hash, không ghi đè hoặc dịch lại trang cũ.
- Không migration hàng loạt database hoặc job lịch sử; job cũ không journal
  chưa tự có resume đa-provider sau restart. Cache/checkpoint cũ vẫn nguyên.

Tab thư mục: Khôi phục công việc còn dở chỉ nạp trạng thái → chọn phương thức →
Tiếp tục. Tab ảnh/URL: chọn phương thức chung rồi bấm Tiếp tục công việc đã lưu
(ưu tiên cache). Nút có tooltip về chương chưa tải; restore chạy trong QThread.
Folder/source scope đổi thì bỏ intent trong UI nhưng giữ journal cũ. Work recipe
OCR/font/glossary/render đổi trong resume bị từ chối; dùng job/output mới.

Quota/rate/auth/protocol/timeout/request budget dừng gửi, giữ pending. × chỉ ẩn.
Không retry AGY tự động, không reset quota giả, không mua credits/API key khác.
Cancel giữ OCR/validated regions; numeric reject là review/fallback, không PASS.

## 5. Test và QA thật

**Full pytest349PASS/10SKIPPED/0FAIL; unittest349PASS/10SKIPPED/0FAIL
(359ca mỗi runner).** Artifact cuối `pytest-verified.xml/txt`,
`unittest-verified.json/txt`. Các artifact initial/final/gate/release/acceptance
giữ lịch sử; không dùng count cũ thay kết quả cuối.

31test mới `tests/test_multipage_resume.py` kiểm tra packing (dưới/đạt/vượt,
oversized/empty/60vùng/negative limits), ID đảo/thiếu/lạ/trùng/NDJSON, numeric
page-local, context exclusion/cache identity, payload/schema/output max,
quota/timeout, cache/recipe/output/source integrity, cancel sau OCR/sau MT,
crash atomic publication và source publication, MyMemory/Offline pending-only,
source cached-first/uncached-selected access check, Qt restart/tab scope/batch
events và prompt injection. Hai tiến trình Python mới riêng biệt xác minh
restart không dựa vào import cache: receipt/output1giữ nguyên,2pending tiếp tục,
0OCR mới/0AGY khi Offline. Các ca này dùng fake CLI/HTTP/MT, không gọi live.

Test quota Stage3B cũ được cấu hình agy_batch_regions=1 để giữ ca lỗi ở request2
dưới batching mới; không giảm assertion hoặc đổi SKIPPED thành PASS. Các lỗi
phát hiện khi triển khai (quota fixture không còn chạm request2, cache retry
nhầm restage) được sửa và giữ artifact, không che lỗi. Native/number tests cũ PASS.

Windows Qt thật:

- `output/stage3c-windows-gui/20261108T070034081810Z/report.json`: GUI đóng/mở,
  quota notice× không resume, user đổi AGY→Offline/pending, output/receipt cũ
  nguyên, source panel3trang qua batch event/export PASS,20heartbeat. OCR/CLI/MT
  ở bài này **mock**,0live requests; screenshots lưu cùng thư mục.
- `output/source-tabs-validation/20261108T070036Z-1e102b/report.json`: ảnh đơn/
  thư mục/pause-resume/gui responsive với OCR/Paddle và Argos thật PASS, config/
  nguồn không đổi, không network. InvalidURL stack trace là ca âm tính cố ý.

### Lượt AGY thật được duyệt

Người dùng chấp thuận riêng1lượt,3trang QA tổng hợp/3vùng/17ký tự, model
gemini-3.8-flash-medium,0retry. Prepare chạy PaddleOCR thật và lưu OCR cache QA;
không gửi ảnh/path/DB. Source: 活动时间; 活动时间和活动内容; 第13话.

**PASS: 1CLI invocation,3target validated,3PNG1600×400,0fallback/0failed**.
Ở đây `cli_invocations` của QA đếm lượt **sinh có OCR payload**, không phải mọi
process metadata: constructor provider còn chạy --help/--version (2lệnh chỉ đọc,
không OCR). Vì vậy cold job này có1lượt dịch và2preflight metadata. Không có
lượt sinh thứ2; không trình bày là tổng cộng chỉ1process AGY.
Targets: “Thời gian hoạt động”; “Thời gian hoạt động và nội dung hoạt động”;
“Chương 13”. Numeric guard giữ13; sources không đổi. Không gọi lượt thứ2.
Không dùng API key/billing/extra credits; dùng phiên AGY hiện có.

`output/stage3c-qa-20261108T052551Z/`: plan.json, live-attempt.json (ghi trước
invocation), report.json với protocol shapes/byte counts, QA DB/journal/source/
export. stdout4.480byte, không lưu raw stderr/OAuth/chain-of-thought. Bộ31test
không gọi mock là live; lượt thật chỉ xác minh batch3trang nhỏ, chưa xác minh
60vùng/3.000ký tự hoặc carryover nhiều request trên tài khoản thật.

## 6. File và bảo toàn

Source sửa: core/types.py, core/storage.py, core/imaging.py, core/pipeline.py,
providers/agy.py, sources/service.py, ui/workers.py, ui/main_window.py,
ui/comic_sources.py, ui/settings_dialog.py. Source mới: core/resume.py,
core/multipage.py, sources/resume.py. Test sửa: tests/test_agy.py; test mới:
tests/test_multipage_resume.py. QA mới: qa/validate_multipage_agy.py,
qa/validate_multipage_gui.py. Tài liệu: báo cáo này, PROJECT_STATUS, README,
USER_GUIDE, TROUBLESHOOTING, WEBSITE_ADAPTER_AI_GUIDE. AGENTS/.gitignore đủ,
không sửa. Không dependency mới/model download/build.

`logs/stage3c-20261108T052551Z/preservation.json`:595/595hash nguyên; nguồn/cache/
120output/DB/manifest/checkpoint/config/BAT/spec/models/4EXE production không đổi.
core/runtime,core/ocr,core/diagnostics,Argos/MyMemory source nguyên; numeric
comparison block byte-identical với HEAD. Không chạy chươngproduction hoặc111.
Các journal/SQLite/output mới chỉ là QA riêng. Không xóa dữ liệu hoặc cache cũ.

## 7. Git & Fork Handoff

Repository D:\TransTool, branch main, HEAD1a47b15 giữ nguyên, staged0. Baseline
6file thay đổi từ hotfix:4docs tracked sửa và2untracked test/report. Giữ nguyên
hai file untracked; docs chung có thêm phần Stage3C, không bỏ lịch sử.

Review source/test/QA/docs liệt kê mục6. Hai file từ nhiệm vụ trước cần review
riêng: docs/IMAGE_LIST_DOWNLOAD_FLOW_REPORT.md và tests/test_image_list_download_flow.py.
Không commit .venv/models/cache/journals/SQLite/logs/output/ảnh/EXE hoặc credential.
.gitignore không đổi; kiểm tra ignore/visible paths, secret/large-file scan và
git diff --check **PASS**, lưu trong git-final.json. Cuối lượt16tracked sửa,
9untracked (gồm2file từ hotfix trước), staged0; không có runtime/binary/secret
mới trong danh sách review, không file runtime đã track cần untrack.
Không tự stage hoặc untrack file.

Fork → Local Changes → review từng file/hunk (có docs từ hotfix trước) → tự stage
phần cần lưu → xem staged diff → tự commit. Gợi ý:
`stage(3c): add multi-page AGY batching and persistent resume`.

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT**.

## 8. Giới hạn còn lại

Batch defaults là thử nghiệm. 60vùng/3.000ký tự chỉ local/mock; batch live nhỏ
không chứng minh latency/quota/chất lượng của cả chương. Carryover còn có thể
mang lỗi nghĩa đã qua numeric guard;0human ground truth/không đo accuracy.
Không live MyMemory/Kuaikan mới trong stage này. Không cắt điện máy thật; dùng
fresh process và fault fixtures. Không migration tự động job lịch sử. Không
đổi provider mặc định/model/date handler hoặc buildEXE;4EXE cũ chưa có Stage3C.
Sau nghiệm thu, có thể đề xuất một QA live lớn hơn với ngân sách dữ liệu/lượt
cụ thể; phải xin phép riêng, không dùng lại consent1lượt đã hết.

**STAGE_3C_COMPLETED_WITH_WARNINGS**.
