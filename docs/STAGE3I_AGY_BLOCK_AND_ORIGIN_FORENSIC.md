# Stage3I — AGY extension block và Batch toàn Origin

09/11/2026 — **STAGE_3I_FORENSIC_COMPLETE**.

Đã hoàn tất điều tra bằng source và dữ liệu local thực. Không sửa source hoặc
cấu hình, không chạy test/GUI/AGY/API hoặc resume production. Không có tuyên bố
đã sửa cấu hình hay nghiệm thu dịch thành công. Source Stage3G/3H chưa commit
được giữ nguyên. Evidence: `logs/stage3i-20261109T074547Z/`.

## 1. Kết luận ngắn

Hai hiện tượng cùng chapter276880 nhưng **khác job/workspace**:

- Whole109trang/93vùng/536ký tự bị guard cấu hình chặn **trước khi tạo
  subprocess dịch**. `agy_attempt_used=true` là ngân sách được chốt trước
  constructor, không chứng minh đã gọi CLI/tiêu thụ quota. Không render ảnh.
- Batch109Origin là lượt mới, có109diagnostic `AGY_AUTOMATIC_EXTENSIONS` do
  **một lỗi khởi tạo provider local được tái phát trong vòng xử lý ảnh**.
  Generic fallback của Stage1 áp dụng cho mỗi trang. Không phải109request
  AGY, không phải numeric rejection hoặc bản dịch bị biến thành Origin.
- Job timeout cũ vẫn có59done/50pending,44region receipts;59output pipeline,
  59published output và44target cache còn khớp hash. Không bị ghi đè bởi109
  fallback mới. Manifest chương dùng chung đã được lượt mới cập nhật sang
  journal mới nên GUI không cộng59output cũ vào lượt109Origin.

## 2. Guard cấu hình nào đã chặn?

`providers/agy.py:72`, `check_automatic_extensions()`:

1. Đọc `%USERPROFILE%\.gemini\config\hooks.json`, rồi `mcp_config.json`.
   Đây là cấu hình **cấp người dùng**, không phải project/source hoặc session
   settings do Image Translator tạo cho invocation.
2. File thiếu/rỗng được bỏ qua. File lớn hơn128.000byte, JSON không xác minh
   được hoặc effective object không rỗng thì phát `AGY_AUTOMATIC_EXTENSIONS`.
3. Với JSON object: `active = data.get(key, data)`, key lần lượt là `hooks`
   và `mcpServers`. Không có key mong đợi thì xét cả root, không giả định an toàn.
4. `if active` tạo ValueError và chuyển thành **OnlineProviderError** với
   mã trên. Không tạo tool invocation, không mở quyền hoặc sửa file.

Quan sát hiện tại (chỉ lưu field/type/count; không ghi command hoặc giá trị
metadata bất kỳ):

| File | Dữ kiện đọc được | Nhánh guard |
|---|---|---|
| `%USERPROFILE%\.gemini\config\hooks.json` | Có,1084byte, JSON hợp lệ; root object1field không có key `hooks` cấp đầu; chứa map5sự kiện và5trường command không rỗng | Root object không rỗng → chặn |
| `%USERPROFILE%\.gemini\config\mcp_config.json` | Có,0byte | Bỏ qua nếu tới bước này |

Trong cấu trúc có Stop,PreToolUse,PostToolUse; hai tên sự kiện và tên field
không nằm allowlist diagnostic đã được ẩn. Các trường command chỉ được đếm,
không đọc ra báo cáo, không thực thi. Không thấy cờ disabled=true hoặc
enabled=false trong cấu trúc đã kiểm tra; điều này cũng không chứng minh
enable/runtime behavior của AGY.

Vì vậy: **có khai báo hook chứa command**, không đủ cơ sở coi là metadata vô
hại. Nhánh guard trực tiếp là cấu hình khác key cấp đầu mong đợi nhưng không
rỗng, không phải lỗi JSON hoặc vượt dung lượng. Chưa xác minh AGY có chạy các
hook đó hoặc chính xác schema/version nào quản lý chúng. Đây không phải bằng
chứng false positive cần nới guard. MCP không phải nguồn chặn hiện tại; vòng
lặp constructor dừng ở hooks trước khi tới MCP.

mtime hooks là `2026-11-09T06:53:28.539356+00:00`, MCP
`2026-11-08T02:32:28.477992+00:00`. hooks có mtime sau job timeout05:01 nhưng
trước hai lượt lỗi07:21/07:30. Không có audit lịch sử nội dung nên không khẳng
định byte cấu hình tại hai thời điểm quá khứ giống hiện tại, ai đã sửa file,
hoặc thao tác nào tạo các hook. Runtime code lỗi và cấu hình hiện tại tương
ứng cùng guard, không có raw historical config để phân biệt nhánh cũ hơn.

## 3. Whole bị chặn trước hay sau invocation?

Workspace khớp GUI:
`output/stage3g-20261109T072406Z-9cf0024a/`.

- Source: `cache/online_comics/kuaikanmanhua/6677/chapter_276880`.
- Chapter identity Whole:
  `2f19423368963c5706f536bd7488f674610e4bdf933aa32e9adf049bd0562224`.
- Model `gemini-3.8-flash-medium`, translator kind `agy`.
- Manifest109trang,93vùng,536ký tự;109OCR records đã lưu.
- Manifest hash:
  `7ad606af4d9365f7c9e5e56c41992d3a057cdde2705eb5bdfb478ff8ef9e0236`.
- Recipe `eefd6dd9c45a13b68831477eba350a369b664abbf10162e9fa6d4fc89b048ca3`.
- `state=blocked`, `error_code=AGY_AUTOMATIC_EXTENSIONS`, journal mtime
  `2026-11-09T07:30:41.274303+00:00` (mtime, không phải request timestamp).
- `agy_attempt_used=true`; không agy-response.json, không accepted hash,
  không render_resume_id,0rendered file. Journal/manifest/context/input seal
  được kiểm tra bằng digest read-only, đều khớp.

Đường mã:

`WholeChapterJob._run → kiểm tra consent/hash → save agy_attempt_used=True
→ AGYWholeChapterTranslator.translate_manifest → AGYProvider.__init__
→ check_automatic_extensions → exception → WholeChapterJob blocked`.

Vị trí: `core/whole_chapter.py:397` chốt cờ; `:162` tạo provider;
`providers/agy.py:328` kiểm tra extension. Guard nằm trước root/init counters,
trước mọi help/version probe và trước `_run_translation`/Popen. Whole vốn
`probe_cli=False`. Không có đường generation được chạy trước constructor này.

**FACT_CONFIRMED trong phạm vi lượt này:** không tạo subprocess dịch AGY.
Không có bằng chứng quota tiêu thụ qua lượt bị chặn đó. Không suy rộng thành
không có AGY/backend request nào khác trên máy/tài khoản. Cờ đã chốt không
được reset; chính sách Stage3G cố ý bảo thủ cho lỗi local/crash. Tiếp tục cùng
workspace không cho phép một lượt gửi mới nếu không có response receipt.

Batch và Whole dùng **cùng check_automatic_extensions**, không có bypass cho
Whole. Khác biệt là Whole chốt ngân sách rồi constructor; Batch khởi tạo qua
`TranslationService.identity()` và dùng đường fallback của ProcessingManager.
Đây là guard cấu hình local, không phải parser NDJSON báo Unexpected tool use;
không có phản hồi model/tool invocation nào được quan sát ở hai lượt này.

## 4. Batch109Origin và job cũ

| Thuộc tính | Batch timeout cũ | Batch toàn Origin |
|---|---|---|
| Pipeline job ID | `e8ddd939ee7a790e5a0ca026fe99ab0a05e7a505a636d259e1da63862d0d8543` | `9646fde09e2225cb98ba2ccf395e757f258639e1e0f7c9b40a5f2d5c1a5a156a` |
| Chapter journal ID | `bc961120200340a4b4abfd08e40aeeb7` | `bef9d2d92ef14ea2b3a681d640b8105c` |
| Source journal ID | `89b4535915c340f3b5a09cbad88cfc6c` | `29cc3fac88b74ae29f9d4e367c64afad` |
| Provider được chọn | AI Gemini AGY | AI Gemini AGY |
| Provider identity | `agy-account-headless-v1:23c9ea76a563e088ab707b37d3e6c863466f320b86b6fdce0b8a8af3ce504aca` | Constructor thất bại, service identity `unavailable:OnlineProviderError` |
| Trạng thái | paused_provider | completed_with_warnings |
| Pages |109:59done,50pending |109fallback_original |
| Region receipts |44 |0 |
| Thời điểm cuối journal |05:01:21.059971Z |07:21:38.667296Z |

Chapter journal ở `cache/online_comics/pipeline-resume-v1/<id>.json`.
Hai lượt có cùng109source paths/hashes, **không khác field Options nào**, cùng
recipe `489f1dea5488b75731d041b66bc1543d92c4ea68a7ca7663c8e0e0210b34d6ac`.
Recipe không bao gồm provider fields nên bằng nhau không chứng minh cùng job.

Tái dựng digest từ dữ liệu thật, không instantiate provider:

- Identity hợp lệ lịch sử → job ID e8ddd939… khớp.
- `unavailable:OnlineProviderError` → job ID9646fde0… khớp.

Không phải OCR/render recipe mismatch. Đây là journal mới; không thể kết luận
chính xác người dùng bấm nút nào vì không có UI action audit. Nếu đã tiếp cùng
chapter journal cũ thành công thì59done phải được giữ/skip; thực tế journal cũ
không đổi byte, còn journal mới có109fallback, nên không phải tiếp journal cũ.

## 5. Vì sao toàn Origin, không pause một lần?

Diagnostic thực tế:
`logs/diagnostics/9646fde09e2225cb98ba2ccf395e757f258639e1e0f7c9b40a5f2d5c1a5a156a/errors.jsonl`.
Có109record, page1–109, **đều** TRANSLATION / AGY_AUTOMATIC_EXTENSIONS /
OnlineProviderError / FALLBACK_ORIGINAL. Từ `07:21:28.479389Z` đến
`07:21:38.614122Z`. Provider/model identity null vì constructor chưa xong,
không có raw target; mode vẫn AGY. Không chứng minh đã gọi MyMemory/Argos.

Đường xử lý tại `core/pipeline.py`:

1. `:454–460` gọi service.identity; lỗi guard được giữ trong preflight_error,
   service_identity thành unavailable. Không tạo MultiPageAGY khi có lỗi.
2. `:533–535` tái raise lỗi đó trên mỗi trang chưa done, trước load OCR/inpaint.
3. Lỗi là **OnlineProviderError**, không phải subclass **ProviderSuspended**;
   do đó không vào nhánh pause ở `:602`, mà vào `except Exception` ở `:645`.
4. `fallback_original` sao chép ảnh nguồn, ghi checkpoint fallback_original,
   needs_retry và diagnostic. Không dịch, không inpaint rồi bỏ trống.
5. Cuối lượt có109fallback/0failed_no_output → completed_with_warnings.
   `sources/service.py` tính109xuất/0dịch/109cần xem lại theo trạng thái này.

Đây là chính sách fallback đang có, không phải109lần thử constructor hoặc109
invocation. Ngăn chạy provider vẫn có hiệu lực. Không có dấu hiệu quota,
parser, JSON, numeric/glossary, timeout hoặc publication error là nguyên nhân
trực tiếp của lượt này. Không biến completed_with_warnings thành MT success.

## 6. Bảo toàn59output /44receipts và manifest hiện tại

Đối chiếu với snapshot Stage3H:

- Journal bc961120… giữ nguyên SHA256,59done/50pending/44receipts.
- 109ảnh nguồn và59published output lịch sử:168/168hash khớp.
- 59pipeline output và59SQLite done/output-hash/fingerprint receipts khớp.
- 44/44region receipt khớp target hash trong translation cache đúng provider,
  context và namespace; batch context_provider identity cũng khớp. Chỉ kiểm
  tra hash/ánh xạ, không chạy numeric validator/MT hoặc đánh giá lại ngữ nghĩa.
- 109fallback mới đều có byte/hash bằng ảnh nguồn;109pipeline fallback và
 109published output/hash receipts khớp. SQLite có109fallback_original cho
  job mới. Không có ảnh giả hoặc bản render dở được coi là dịch thành công.

Output mới nằm tại thư mục chương
`output/test_download-orc/权妃之帝医风华__6677/0007_第5话 水下的亲密接触__276880/run_9646fde09e2225cb/original/`.
Output cũ ở nhánh `run_e8ddd939ee7a790e/`, không cùng destination. Các file
pipeline đã dịch ở staging cũng còn nguyên. Không phát hiện ghi đè các output
cũ đã xác minh; không khẳng định về file ngoài phạm vi snapshot/receipt này.

**Metadata dùng chung đã đổi trước Stage3I:** manifest chapter276880 giờ trỏ
`pipeline_resume_id=bef9d2d9…`,109page đều FALLBACK_ORIGINAL, needs_retry1–109.
Nó mô tả lượt mới, không tự cộng59output của run cũ. GUI0dịch là đúng với
latest manifest. Đây là thay pointer/trạng thái theo lượt mới, không phải mất
59file hoặc xoá44cache.

Vì source resume hiện đọc manifest chung và lấy pipeline_resume_id từ đó,
**không hướng dẫn bấm Tiếp tục mù để khôi phục59trang cũ**. Lượt hiện tại có
109fallback pending; phục hồi chỉ50pending cũ cần phương án chọn journal/
receipt lịch sử có kiểm soát, được người dùng yêu cầu riêng. Không sửa JSON
hoặc ghép database bằng tay trong điều tra này.

## 7. Timeline và giới hạn kết luận

| UTC | Bằng chứng |
|---|---|
|05:01:21 | Job cũ TIMEOUT page60,59done/44receipts; Stage3H đã kiểm chứng |
|06:53:28 | mtime hooks.json hiện tại, không có audit người sửa/nội dung lịch sử |
|07:21:28–07:21:38 | Lượt Batch mới109lỗi extension và109fallback |
|07:24:06 | Timestamp trong tên workspace Whole mới, không phải timestamp gọi mạng |
|07:30:41 | mtime journal Whole blocked,109OCR/93vùng/536ký tự |
|Stage3I | Đọc/hash/đối chiếu; không thực thi lại |

FACT_CONFIRMED: guard local, hai journal/job khác nhau, cấu hình hiện tại có
khai báo command, không CLI generation trên đường lỗi, flag true,109fallback
bằng nguồn,59output/44target cache cũ khớp hash.

INFERENCE: file hooks hiện tại giải thích các lỗi runtime cùng guard và có
mtime trước lỗi; không có bản sao config lịch sử để xác nhận byte lúc lỗi.

NOT_PROVEN: ai thêm hooks, AGY thực sự enable/thực thi chúng hay chưa, schema
chính thức của toàn cấu hình hiện tại, quota tài khoản, thao tác UI chính xác,
hoặc liệu live AGY sẽ hoạt động sau cấu hình lại. Không có test/live evidence mới.

## 8. Hướng xử lý an toàn và quyết định source

1. Giữ **BLOCKED** với cấu hình hiện tại; đây không phải lý do đổi model/key,
   billing, tăng timeout/budget hoặc nới guard. Chưa có bằng chứng guard nhầm
   metadata vô hại. Không tự sửa/xóa hooks/MCP.
2. Người dùng sao lưu riêng hooks.json/mcp_config.json, xem các khai báo hook
   trong công cụ cấu hình chính thức đã dùng với AGY. Kiểm tra Stop,
   PreToolUse,PostToolUse và hai sự kiện còn lại; không gửi command/credential
   ra ngoài. Không công bố file thô để xin hỗ trợ.
3. Chỉ khi người dùng đồng ý và AGY có cơ chế hỗ trợ đã được xác minh, tắt
   các hook/MCP tự động thực sự hoặc dùng profile cách ly chính thức. Nhiệm
   vụ này chưa xác minh UI/CLI cụ thể để tắt chúng, nên không bịa lệnh/cờ.
   Không thêm key hooks rỗng cạnh các hook đang có, không làm rỗng/đổi tên file
   chỉ để né kiểm tra. Nếu không thể xác minh an toàn thì giữ blocked; có thể
   chọn Offline cho lượt QA riêng, không tự fallback.
4. Không reset agy_attempt_used hoặc sửa receipt của Whole đã chốt. Sau khi
   cấu hình an toàn, nếu muốn thử AGY thì người dùng chủ động tạo workspace
   mới và xác nhận mới. Không tự chạy từ workspace bị chặn.
5. Không resume chapter276880 qua latest manifest để ép dùng lại59trang.
   Giữ cả run cũ/mới và yêu cầu nhiệm vụ phục hồi riêng nếu cần nối50pending.

**Không sửa source trong Stage3I.** Guard chặn đúng điều kiện an toàn hiện có;
109Origin phù hợp policy generic fallback và được gắn trạng thái chính xác,
không phải mất ảnh/false success. Thay lỗi preflight toàn-provider thành pause
một lần thay vì109fallback là cải tiến hành vi có thể đề xuất riêng:
phân loại extension denial vào typed suspension, diagnostic trước CLI và kiểm
tra pending/receipt. Cần test fake/local cho59done/50pending,0invocation,
0fallback mới, không đổi guard predicate/namespace hoặc tự reset budget.
**Chưa triển khai hoặc kiểm thử đề xuất này.**

## 9. Preservation, test và Git & Fork Handoff

Baseline root D:/TransTool, branch main, HEAD
`a0ea3bbc0479b0215645c83df0593571e167c4e7`. Có14tracked modified và3untracked
Stage3G/3H, không staged/conflict. Đã đọc status/branch/HEAD/root/ls-files và
.gitignore. Không hoàn nguyên, sửa hoặc commit source đang dở.

Snapshot trước/sau gồm cache/config/models/output/dist/logs-diagnostics,
BAT/spec và hai config AGY được phép đọc. Kết quả hash ghi trong
`preservation.json`: **29.279/29.279file giữ SHA256/size/mtime**,0mất/0đổi,
gồm4EXE và2config AGY ngoài repo;130snapshot source/báo cáo Stage3G-H tham
chiếu cũng không đổi. Không hash toàn bộ .venv, không cài dependency. Đọc SQLite
chỉ bằng URI mode=ro&immutable=1 khi WAL0byte, không import app/ResumeStore
hoặc mở DB để ghi. Forensic dùng Python stdlib, không chạy test.

Stage3I chỉ thay tài liệu: báo cáo này, PROJECT_STATUS.md,
docs/TROUBLESHOOTING.md và docs/USER_GUIDE.md. Không có source/config/test
thay đổi của Stage3I. Source/docs Stage3G/3H đã snapshot riêng để đối chiếu.
Mọi pytest/unittest/mock/GUI/regression/smoke/OCR/MT runtime: **NOT_TESTED**.
Không có AGY/API/network translation, production retry/resume/download,
DB/journal/output/config modifications, build hoặc billing changes từ Codex.

Git status cuối gồm14tracked modified và4untracked, do thêm report Stage3I.
.gitignore không đổi; kiểm tra cache/log/output/model/EXE/config AGY/runtime
không lọt vào review. Source/test/docs/spec/config mẫu vẫn được hiển thị.
`git diff --check` cuối lượt exit0, không báo lỗi; không stage để kiểm tra.

Nên commit riêng cho điều tra: bốn tài liệu Stage3I trên. File cùng chỉnh với
Stage3G/3H cần tự review hunk trong Fork; không chọn commit toàn bộ mù. Source
và hai báo cáo Stage3G/3H cùng sources/whole_input.py là thay đổi có sẵn, giữ
nguyên để người dùng quyết định commit. Không commit logs/evidence/hash,
ảnh/cache/SQLite/journal/output/models/EXE/.venv/config cá nhân/credential.

Evidence chính: git-before/after.json, diff-before.patch, source-before.json,
extension-config-summary.json, hooks-schema-summary.json, whole-workspaces.json,
chapter-diagnostics-summary.json, chapter-manifest-summary.json,
historical-comparison.json, integrity-and-source-runs.json,
job-id-reconstruction.json, protected-stat-before.json, protected-hash-before.json,
preservation.json. Chỉ dữ liệu đã lọc; không raw hooks command/OCR/target/prompt.

Fork → Local Changes → xem bốn tài liệu/hunk Stage3I và thay đổi có sẵn → tự
stage cần thiết → review staged diff → tự commit. Gợi ý:
`docs(stage3i): explain AGY extension block and origin-only run`.

**NO_COMMIT — NO_PUSH — NO_TAG — NO_DESTRUCTIVE_GIT.**

**STAGE_3I_FORENSIC_COMPLETE** — không tuyên bố đã khắc phục cấu hình AGY.
