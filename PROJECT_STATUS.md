# Trạng thái Image Translator VN

## Mới nhất — Stage3C multi-page AGY và persistent resume, 08/11/2026

**STAGE_3C_COMPLETED_WITH_WARNINGS**. Đã thêm planner OCR nhiều trang dùng engine/
cache/renderer cũ, batch ID job/chapter/page/region/reading order; mặc định3.000
ký tự/60vùng, tối đa16trang có chữ,6.000ký tự/vùng,12.000ký tự cứng,128KB input/
1MB stdout. Trang còn vừa được giữ nguyên; oversized page chỉ chia tại vùng.
Context tùy chọn tối đa8vùng đã validated/1.600ký tự JSON; cache có version/context.
Numeric guard literal-numbers-v2-signed không đổi, không dùng date handler QA.

Journal JSON version1 cạnh DB không migration SQLite, lưu OCR/region receipt và
publication intent. Resume xác minh source/output/hash/recipe, giữ receipt cũ,
chỉ dịch phần pending; hỗ trợ đổi AGY→Argos/MyMemory, restart và crash lúc publish.
UI không tự gửi online khi mở. Source resume ưu tiên cache; chương chưa tải được
kiểm tra access/policy lại, chỉ trong lệnh tiếp tục chủ động. Không nới downloader.

Người dùng duyệt đúng1liveQA:3trang tổng hợp/3vùng OCR thật/17ký tự,1AGY CLI,
3ảnh export/0fallback/0retry. Không có request bổ sung.60vùng/3.000ký tự và carryover
nhiều batch mới được test local/mock; chưa nghiệm thu cả chương/độ chính xác nghĩa.
Pytest349PASS/10SKIPPED/0FAIL; unittest349PASS/10SKIPPED/0FAIL (359ca), thêm31test.
Windows GUI restart/source batch mock PASS; Windows ảnhđơn/folder/OCR+Argos thật
PASS;595/595file bảo vệ giữ hash,120output/119normal+fallback111 nguyên vẹn.
Không build/cài/tải model/ảnh hoặc chạy jobproduction. Journals áp dụng từ lượt
chạy mới, không tự migration job lịch sử. Xem
`docs/STAGE3C_MULTIPAGE_BATCH_RESUME_REPORT.md`, logs/stage3c-20261108T052551Z.

## Mới nhất — điều tra IMAGE_LIST_READY, 08/11/2026

**DIAGNOSIS_COMPLETE / LIVE_CASE_NOT_VERIFIED**. Chương 第8话 驯马 là277859,
thứ tự10 trong topic DOM đã lưu; snapshot có PUBLIC/free/not-locked/not-VIP.
Chưa tìm thấy reader response/log của lượt107 URL, nên không khẳng định quyền
hiện tại hoặc HTTP/JavaScript PASS. Không gửi request website/ảnh/provider.

Source chứng minh IMAGE_LIST_READY chỉ hoàn tất discovery, không gọi process;
cần giữ chương chọn rồi bấm Tải và dịch khi decision.allowed. Câu "quyền nội
dung vẫn UNKNOWN" thuộc ALLOWED_BY_USER_POLICY, không phải gate DOWNLOAD_UNKNOWN.
Nhánh images_ready giữ nguyên từ Stage2, adapter/transport/policy không đổi bởi
Stage3A/3B. Chưa chứng minh bug điều kiện/worker nên **không sửa production
source, không thêm auto-download hoặc nới access/policy**.

Thêm9 test local/mock: discovery không tải, phân biệt UNKNOWN, VIP/verified_only,
3phương thức, QThread→download bitmap/cache/progress, lỗi worker và controls.
Pytest318PASS/10SKIPPED/0FAIL; unittest318PASS/10SKIPPED/0FAIL (328ca).
Xem `docs/IMAGE_LIST_DOWNLOAD_FLOW_REPORT.md` và
`logs/hotfix-image-list-20261108T045247Z`. Không build/commit hoặc chạy jobproduction.

## Mới nhất — Stage3B AGY, 08/11/2026

**STAGE_3B_COMPLETED_WITH_WARNINGS**. AGY1.5.3 tìm thấy trong
LocalAppData/agy/bin dù PATH tiến trình cũ thiếu; version/help/models thật PASS,
không cần restart/cài/đăng nhập lại. Official headless/stdin JSON/schema/settings
session-only có sẵn. Đã thêm provider/UI3phương thức, pinGemini3.8FlashMedium,
denytools/không thêmcredits/APIkey, cache riêng, batchID/numeric guard cũ và
timeout/cancel/quota/protocol stop. FieldAGY không đổi recipeOffline cũ.

Người dùng duyệt1batch3mẫu development17ký tự quaOCR thật trênfixture tổng hợp;
CLI attempt1 bị INVALID_RESPONSE,0target chấp nhận,0ảnh dịch,1QA fallback.
Người dùng duyệt thêm1lượt cùng3mẫu: terminalSUCCESS,3target/numericPASS,ảnhPNG
1600x1000export thật/0fallback. Không córawprotocol lần1 nên không khẳng định
rootcause hoặc sửa dứt điểm; metadata an toàn đã thêm, không nới parser/guard.
Tổng2attempts/17ký tựOCR mỗi lượt/0auto retry, không request3. GUI Windows còn
render1ảnh từ cache live có lineage,0generation mới. Không đổi AGY globalconfig.

Full pytest/unittest mỗi runner309PASS/10SKIPPED/0FAIL. GUI Windows3phương thức+
notice× PASS; ảnhđơn/thưmục/OCR+ArgosOffline thật PASS. Data595file giữhash,
chương274872 vẫn120output/119normal+fallback111/needs_retry=[111],4EXE nguyên.
Live E2E làfixture tổng hợp,không nghiệmthu truyệnthực hoặc benchmark ngữ nghĩa.
Không tải/cài/bậtAPI riêng/build hoặcStage3C. Xem
`docs/STAGE3B_AGY_TRANSLATION_REPORT.md` và evidence logs/stage3b-agy-20261108T023844Z.

## Mới nhất — Stage3A Online Free, 08/11/2026

**STAGE_3A_COMPLETED_WITH_WARNINGS**. MyMemory API chính thức,ẩn danh5.000ký tự/ngày,
không key/billing. Người dùng duyệt QA6 mẫu development/1.000ký tự/tối đa8request;
thực tế6request/37ký tự/0retry,5numeric pass/1date reject; không đo accuracy hoặc
nới guard. Tách identity cacheOnline mới, giữ Argos/default/signed guard/nguồn111.
GUI chọn Online Free chung3tab, privacy note, notice ×, quota/rate/auth pause an toàn,
không tự đổi provider. Tiếp tục có thể đổi phương thức cho phần pending với recipe
mới, giữ receipt/output cũ; chapter resume chỉ chương đang dở từ cache. Khôi phục
pending UI đổi provider sau restart chưa triển khai, không chạy cảfolder dưới
provider mới để giả resume. Xem giới hạn trong báo cáo Stage3A.

Pytest281PASS/10SKIPPED/0FAIL và unittest281PASS/10SKIPPED/0FAIL. Windows3tab+
Offline E2E thật PASS; GUIquota realOCR/mockHTTP→realArgos resume PASS,279heartbeat.
Không gọi GUIquota mock là liveAPI E2E ảnh. 595file runtime/resource bảo vệ giữhash,
120output/119normal+fallback111, needs_retry=[111],models/config/DB/4EXE nguyênvẹn.
Không tải model/ảnh, cài dependency/buildEXE/Stage3B. Hướng dẫn/test/evidence và
Git & Fork Handoff: `docs/STAGE3A_ONLINE_FREE_TRANSLATION_REPORT.md`.

## Bổ sung quy trình Git/Fork — 08/11/2026

Áp dụng yêu cầu từ Stage 3A trở đi: baseline Git trước sửa, kiểm tra ignore/diff/
file review sau Stage; Codex không stage/commit/push/tag hoặc quản lý lịch sử.
Đã cập nhật AGENTS.md và .gitignore; xem `docs/GIT_FORK_WORKFLOW.md` cho bàn giao,
phân loại file, evidence và cách tự commit trong Fork. Chỉ thay quy trình/tài liệu,
không triển khai Stage 3A/provider mới hoặc Stage 4/5. Repository main có thay đổi
nhiều Stage chưa commit; giữ nguyên và yêu cầu review theo file/hunk.

## Mới nhất — Stage3 đánh giá chất lượng, 08/11/2026 (+07)

**STAGE_3_RESEARCH_ONLY**, không promotion hoặc phục hồi111. Từ183 vùng OCR thật
của chương274872 +ImgTest, chọn150 mẫu source-only sau khử trùng,99development/
51holdout theo family gần trùng.146 cần MT,4 preserve control. **0 independent
human references**;1 kỳ vọng ngày từ task ghi riêng, không tính accuracy/BLEU/COMET.

Argos baseline thật hai chặng giữ decode0.2:145/146 qua literal numeric guard,
1 reject ngày111; Name2 tái hiện tại en→vi.158 historical cache occurrences
khớp output mới, không phải bằng chứng dịch đúng. Lỗi còn ở zh→en (tên riêng,
Rule13/birthday) và OCR/clipping/hoa văn cần rà soát; không quy toàn bộ cho pivot.

Thử4 ứng viên QA riêng, freeze trước holdout: NFC0 output đổi; split6; LP1.0
đổi61 và bỏ Name2 nhưng **thêm1 lỗi số holdout** (`分镜：墨墨子`→`Lỗi:% 1`), loại
khỏi production. QA typed date tạo đúng `Từ ngày20/5 đến ngày30/5` cho source
có delimiter;128 fixture/192 mutation qua,20 date inference bổ sung không được
gọi là20 lỗi model. Natural date chỉ1 ở dev, holdout0; early-year0001 roundtrip
proof chưa đạt. Handler chưa nối với production guard/cache; không coi QA pass
là production pass, không nới guard hoặc dò lại LP theo holdout.

Đọc nguồn/model card và3 GET metadata HF200 (~19KB), **không gửi OCR**,không
Kuaikan/ảnh/weights. Xác minh OPUS zh-vi312MB Apache2.0,M2M1001.94GB MIT,
NLLB600M2.46GB CC-BY-NC4.0; đều **chưa inference cục bộ**. Chưa Transformers,
không cài/convert/tải. Máy chỉ có Argos2model pivot; không đổi default provider.

**Pytest261 PASS,10 SKIPPED,0 FAIL; unittest261 PASS,10 SKIPPED,0 FAIL**.
Thêm9 test QA. GUI Qt Windows/E2E pipeline cũ thật PASS,149heartbeat,2 vùng OCR/
2 MT ở ảnh đơn; không phải candidate đã vào GUI.688/688 file bảo vệ giữ hash,
DB/cache/manifest/checkpoint/120 output và4EXE nguyên vẹn.119 normal +1fallback,
needs_retry=[111] không đổi. Production fingerprint bằng Stage2, không sửa core/
providers/sources/ui/config, không đổi cache version/recipe hoặc build EXE.

Code mới chỉ `qa/` và `tests/test_stage3_quality.py`; evidence
`logs/stage3-translation-quality-20261107T204426Z/`: dataset-manifest.json,
development/,holdout/,baseline.json,candidate-results.json,benchmark-metrics.json,
human-reference-template.csv,outputs-for-review.csv,model-comparison.md,
promotion-decision.json,regression-results.json,preservation.json,summary.json.
Xem `docs/STAGE3_TRANSLATION_QUALITY_REPORT.md`; docs người dùng/model cập nhật.
Dừng trước Stage4/5. Cần human review và chấp thuận thử model/integration trước
khi nâng production; các lệnh chạy source/EXE hiện tại không đổi.

## Mới nhất — Stage 2 phục hồi hai trang, 08/11/2026 (+07)

**STAGE_2_COMPLETED_WITH_WARNINGS; dừng trước Stage3.** Đúng job
`e82b4eb8abed1050602c5d01b62322bd021684c54cebb1715d62b206fd9feca8`, chương274872.
Qua nút Retry/QThread Qt Windows thật, chỉ xử lý0074/0111 từ cache:
**120/120 output hợp lệ,119 hoàn tất bình thường,1 FALLBACK_ORIGINAL,0 thiếu
output; needs_retry=[111]**. 119 là hoàn tất pipeline, không phải119 ảnh có văn
bản đã dịch. Trang74 không có vùng cần MT sau override; output giống nguyên
byte nguồn, không fallback. Hash118 output và118 checkpoint cũ giữ nguyên.

Override mới `core/ocr_overrides.py`, profile `overrides/ocr_regions.json`:
hash+text+polygon chính xác, evidence/version/enabled; không hardcode filename
trong OCR core, không sửa raw OCR cache. Hash/polygon mismatch giữ fallback và
diagnostic; có thể thu hồi. Job ID không đổi; chỉ fingerprint trang74 thêm
revision override. Cache OCR gốc của mọi job giữ nguyên.

Raw target **mới Stage2** trang111: `20 giờ 30 tháng 5`; zh→en: `20-30 May`,
en→vi sai nghĩa khoảng ngày thành thời gian. Source cache thật có dấu gạch:
`5月20日—5月30日`. **PROVIDER_NUMERIC_ERROR ở kết quả pivot cuối**, guard từ
chối phù hợp; không nới kiểm tra ngày, không sửa số bằng thay chuỗi. Raw target
lịch sử vẫn không có. Trang111 giữ nguồn nguyên byte tại `original/0111.jpg`.

Test C2 phát hiện riêng guard cũ bỏ qua dấu đầu số. Siết thành
`literal-numbers-v2-signed`; có3 test đỏ trước sửa, sau sửa PASS. Cache có dấu
dùng namespace v4, không tin legacy signed cache; unsigned cache v3 giữ nguyên.
Giữ pipeline identity cũ để resume;118 output cũ không được gọi là đã revalidate
v2. Không đổi model, provider, tokenizer/beam/Online hoặc native import guard.

**Pytest252 PASS,10 SKIPPED,0 FAIL; unittest252 PASS,10 SKIPPED,0 FAIL**.
Thêm21 test. Qt Windows recovery GUI/review dialog PASS, heartbeat71; E2E
fixture tổng hợp OCR/MT/CV/Pillow thật PASS, không mock. Phục hồi dùng OCR cache
thật, không inference OCR lại. **0 network attempts/0 download/0 build**.

Evidence `logs/stage2-recovery-20261107T200532Z/`: preflight.json,
snapshot/, before-commit/, after-commit/, probe-results.json, recovery-result.json,
pytest-final.xml, unittest-final.json, synthetic-e2e-result.json, preservation.json.
Chỉ job row mục tiêu,2 item checkpoint và2 page manifest được cập nhật; thêm
3 cache row output-hash/metadata. Mọi cache row có sẵn,118 page entry, checkpoint
thành công và job khác giữ nguyên. Model/config/BAT/spec/DOM/4 EXE giữ hash.

Chạy run_source.bat; EXE cũ chưa có Stage2. Xem
`docs/STAGE2_NUMERIC_OCR_RECOVERY_REPORT.md`; USER_GUIDE, TROUBLESHOOTING,
README và adapter guide đã cập nhật. Trang111 vẫn cần sửa chất lượng dịch ở
stage sau; chưa Stage3/4/5, chưa portable/new model/benchmark chất lượng.

## Mới nhất — Stage 1 diagnostic/fallback/retry, 08/11/2026 (+07)

**Stage 1 hoàn thành và kiểm thử source; dừng trước Stage 2 theo yêu cầu.**
Ảnh lỗi được thử xuất bản sao nguyên byte đã kiểm tra ở đường dẫn riêng,
không dùng ảnh inpaint dở. `FALLBACK_ORIGINAL` không phải dịch thành công, item
checkpoint `fallback_original`, vẫn needs_retry; ảnh hỏng/không ghi được là
`FAILED_NO_OUTPUT`. Chưa bật xuất dịch một phần. Đủ file còn fallback là
`completed_with_warnings` / GUI COMPLETED_WITH_WARNINGS, đếm riêng dịch hoàn
chỉnh, gốc, thiếu output, bỏ qua và xem lại. Output thành công có hash/checkpoint
hợp lệ luôn giữ nguyên, kể cả config cũ skip_success=false.

Diagnostic giới hạn 4 MB/1.000 record/job, văn bản2.048 ký tự/trường, numeric
tokens có giới hạn; fsync/giữ dòng dở cũ, ẩn URL/credential, tắt ghi nội dung
trong Cài đặt. Raw target chỉ có cho lỗi **mới**. Thêm danh sách Trang cần xem
lại / mở log. Download error trước pipeline dùng transfer job riêng. Retry
URL/ảnh đơn từ ChapterCache xác minh hash, không HTTP/CDN, chỉ gửi trang cần
xem lại vào pipeline, ánh xạ theo đường dẫn giữ đúng trang. Schema SQLite không
đổi; manifest v1 thêm field tương thích. diagnostic_text không tham gia recipe.
Tính lại ID job chương274872 khớp chính xác ID cũ; không chạy job đó.

**Pytest231 PASS,10 SKIPPED,0 FAIL; unittest231 PASS,10 SKIPPED,0 FAIL**.
Thêm24 test; một test cũ đổi kỳ vọng theo hành vi fallback mới. Test lỗi dùng
mock OCR/MT có phân loại riêng. OCR zh / MT en→vi và zh→en→vi thật PASS.
GUI **Qt Windows** và ProcessingManager thật: ảnh đơn/thư mục,2 vùng OCR/MT
trong ảnh đơn, pause/resume, heartbeat155, nguồn/config không đổi,0 request mạng.
Captured DOM/cache/output/native guard còn PASS. Live web/download và EXE mới
NOT_TESTED trong stage này. Không build, không cài dependency/model.

Evidence `logs/stage1-errors-20261107T174933Z/`: pytest-final.xml,
unittest-final.json, existing-job-identity.json, preservation.json. GUI/E2E:
`output/source-tabs-validation/20261107T181015Z-d76439/report.json`.
556 file đã theo dõi: chỉ9 file source/test dự kiến đổi hash, không có thay
đổi dữ liệu bảo vệ; database/checkpoint/manifest chương274872,120 nguồn/cache,
118 output, config/DOM/BAT/model receipt và4 EXE giữ hash.

**Chưa retry hai trang thật 0074/0111, chưa sửa validator/OCR override**, chưa
benchmark chất lượng, chưa làm portable dependency management, chưa build EXE,
chưa sửa .gitignore (Stage5). Các stage sau chờ xác nhận. Dùng run_source.bat.
Xem `docs/STAGE1_ERROR_HANDLING_REPORT.md`, `docs/USER_GUIDE.md`,
`docs/TROUBLESHOOTING.md`; AGENTS và website adapter guide đã cập nhật.

## Mới nhất — DEFAULT_ALLOW_PUBLIC và downloader, 07/11/2026 từ 10:19 UTC

Theo chỉ dẫn chủ ứng dụng, cấu hình mới `config/download_policy.json` mặc định
`default_allow_public`. Quyền nội dung vẫn UNKNOWN; kết quả app là
**ALLOWED_BY_USER_POLICY / USER_POLICY_DEFAULT_ALLOW**, không OFFICIAL_PERMISSION.
Evidence/source/verified/applicability, owner policy, technical access và quyết
định cuối tách riêng. Verified restriction luôn chặn; PUBLIC cần URL manifest
an toàn; locked/VIP/paywall/login/DRM/CAPTCHA/unsafe redirect/401/403/429 dừng.

Downloader Kuaikan mới: TLS/DNS pin/allowlist, redirect validation, tuần tự,
200 ảnh/chương,32MB/ảnh,512MB/chương,2GB cache, deadline/retry hữu hạn, MIME/magic/
Pillow verify+decode, hash/atomic receipt, resume/cancel. Không sửa signature,
cookie/Referer/UA/proxy. Không tự tải khi nhập/phân tích URL; chọn chương và
bấm Tải và dịch mới chạy, worker kiểm tra policy lại. GUI tái dùng progress/
QThread, cache manifest ghi provenance user policy. Không đổi core OCR/MT.

**LIVE_IMAGE_DOWNLOAD_PASS:2 ảnh đầu chương281106,2 GET CDN200,689114 byte,
JPEG1280×1000**, bitmap/cache/hash PASS, không401/403/429. Cache hit và GUI QA
không tải lại ảnh. **KUAIKAN_URL_TO_TRANSLATION_E2E_PASS (2-image sample)**:
2 vùng OCR/2 bản dịch thật,2 output, nguồn không đổi. GUI button/QThread/
LocalComicJob sample PASS, pause/resume và responsive. Chưa thử toàn116 ảnh.

**Pytest/unittest207 PASS,10 SKIPPED,0 FAIL**; thêm27 ca. Captured DOM, local
single/folder/Offline E2E/Windows Qt smoke/cache/output/native guard còn PASS.
2 lỗi diagnostic QA được giữ bằng chứng và kiểm tra độc lập lại; app/core không
sửa để né lỗi QA. Không cài package/model, không đổi .venv/BAT/spec/DOM/settings
hoặc4 EXE. 93 file bảo vệ giữ hash,5 model integrity PASS. Không build EXE.

Evidence `logs/kuaikan-default-allow-20261107T101940Z/`:
`live-sample-audit.json`, `gui-sample.json`, `pytest-final.xml`, `unittest-final/`,
`preservation.json`. Output mẫu dưới `output/kuaikan-user-policy-validation/`.
Chi tiết source/config/giới hạn/test và lịch sử Stage A giữ nguyên tại
`docs/KUAIKAN_IMAGE_DOWNLOAD_VALIDATION.md`; guide cập nhật policy mới.
Chạy `run_source.bat` để dùng source mới; EXE cũ chưa chứa thay đổi. Bước tiếp:
nghiệm thu lựa chọn lớn hơn/chương thực tế, giữ mọi chặn kỹ thuật và evidence
UNKNOWN tách riêng. Không gọi user default allow là website cấp phép.

## Mới nhất — Kuaikan download policy gate, 07/11/2026 từ 09:58 UTC

Giai đoạn A hoàn thành: đọc nguồn chính thức, đối chiếu đúng serviceData và
policyData trong `/webs/agreement`, không dựa riêng search snippet/upload terms.
Chưa có grant đủ phạm vi cho tải tự động CDN/cache/OCR/MT/export qua app ngoài.
**DOWNLOAD_UNKNOWN, case C; Stage B BLOCKED_BY_POLICY** do thiếu bằng chứng,
không phải FAIL kỹ thuật hoặc kết luận mọi cách đọc cá nhân bị cấm.

Live metadata/parser vẫn PASS: topic26/23main, chương281106 PUBLIC/unlocked,
116 URL ảnh manifest có sign/t, đúng tn1.kkmh.com. **0 HEAD/GET ảnh,0 ảnh/0 byte**;
TTL/CDN connectivity/bitmap/cache ảnh web NOT_TESTED. Không triển khai downloader
hoặc Kuaikan E2E, không sửa production/pipeline/native guard, không build EXE.

Thêm `tests/test_kuaikan_download_policy.py`8 ca. **Pytest/unittest180 PASS,
10 SKIPPED,0 FAIL**. Captured DOM/SSR/HTTP fixture, Windows Qt local single/folder,
OCR/MT/cache/output, GUI smoke và LOCAL_OFFLINE_E2E_PASS. Không dùng mocked
permission/HTTP hoặc local E2E thay cho live download. 102 file trước nhiệm vụ
giữ hash,5 model integrity PASS; config/DOM/BAT/spec/4 EXE bảo toàn.

Báo cáo: `docs/KUAIKAN_IMAGE_DOWNLOAD_VALIDATION.md`; evidence
`logs/kuaikan-download-policy-20261107T095823Z/`. Cập nhật guide về gate và phạm
vi giấy phép. Bước tiếp: nguồn/chấp thuận đủ quyền tải và xử lý dự kiến; giữ
metadata/discovery và nhập ảnh đã lưu hợp lệ trong lúc chờ. Không cần DOM mới.

## Mới nhất — Kuaikan LIVE_HTTP_PASS, 07/11/2026 từ 09:33 UTC

Phiên mới có mạng, không network-disabled flag/proxy. Đúng transport
`fetch_public_html` trả **HTTP200 HTML UTF-8 cho cả topic6677 và chapter281106**.
Đã xác minh qua MainWindow tab URL/QThread thật, không mock, không preload DOM:
topic **26 mục / 23 main / 3 phụ**, chương15 ID281106; reader **116 URL ảnh từ
public manifest trong response thật**, chỉ2 URL trong thẻ img SSR. Thứ tự ID
chương và116 URL path khớp captured DOM. GUI responsive, không tự chọn/crawl.

Root cause: initial HTTP HTML chưa có `.title-item` và chỉ render2 img-box,
trong khi Nuxt state công khai có đủ chapter records/manifest. Chỉ sửa
`sources/kuaikan_dom.py` để dùng state được kiểm chứng theo topic/chapter ID,
title/order/domain khi DOM chưa đủ; giữ DOM path cũ và warnings/provenance rõ.
`sources/kuaikan.py` cập nhật mô tả/support status. Transport/GUI/OCR/MT/native
guard/models/dependencies không đổi. Không thêm endpoint/browser automation.

**Pytest/unittest172 PASS,10 SKIPPED,0 FAIL**; thêm10 ca SSR. Captured DOM và14
mocked HTTP cũ vẫn PASS; dedicated live GUI PASS độc lập. Local single/folder,
OCR/Argos thật, cache/output, GUI smoke Windows Qt và E2E Offline PASS.
99 file bảo vệ giữ hash ngoài2 source sửa có chủ đích,5 model integrity PASS;
config, DOM gốc, .venv/BAT/spec và4 EXE cũ bảo toàn. Không tải ảnh hoặc build.

Evidence: `logs/kuaikan-http-20261107T093330Z/gui-live-verified.json`, pytest/
unittest/preservation cùng thư mục. Initial parser FAIL và lỗi script QA đầu
giữ nguyên bằng chứng, giải thích tại `docs/KUAIKAN_CHAPTER_281106_ANALYSIS.md`.
Guide cập nhật live state fallback và registry. Fixture mới là public HTTP state
đã lọc + DOM skeleton viết tay, không gọi là raw HTTP hoặc live test.

**DOWNLOAD_UNKNOWN / downloader NOT IMPLEMENTED**; URL → ảnh → dịch chưa hoàn
thành. Source hiện phân tích URL được; không cần DOM thủ công mỗi chương, không
cần browser automation cho hai mẫu. Bước tiếp: xác minh điều kiện tải trước khi
triển khai downloader; dùng ảnh đã lưu hợp lệ trong lúc chờ. EXE cũ chưa chứa
sửa parser SSR, không build trong nhiệm vụ này. Mục ENVIRONMENT_BLOCKED dưới là
lịch sử phiên cũ.

## Mới nhất — LIVE HTTP runtime Kuaikan, 07/11/2026 09:05 UTC

**ENVIRONMENT_BLOCKED.** Đã gọi transport thật `fetch_public_html` cho đúng hai
URL topic6677 và chapter281106. Phiên Windows/Python `.venv` 3.10.9 x64 đang có
`CODEX_SANDBOX_NETWORK_DISABLED=1` và HTTP/HTTPS/ALL proxy loopback port9;
transport từ chối trước DNS/TCP/HTTP send (đều0). Không nhận response, status/type/
charset/Nuxt/parser trên live response đều chưa xác minh. Không kết luận website
chặn, không bỏ proxy/guard, không sửa parser theo lỗi mạng.

Không sửa production source/GUI/core/providers/native guard/transport; chỉ thêm
`tests/test_kuaikan_http_runtime.py`: **14 ca MOCKED_HTTP_PASS** (11 transport/
adapter và3 GUI/QThread thật với simulated responses). Kiểm tra200/redirect/
timeout/DNS/proxy/401/403/429/nonHTML/missing state, reuse page, direct reader,
metadata giữ khi lỗi chương, GUI responsive. Không gọi mock là LIVE_HTTP_PASS.

**Pytest/unittest 162 PASS, 10 SKIPPED, 0 FAIL**, captured DOM vẫn26/23/3 và116
URL. GUI Windows Qt ảnh đơn/folder/OCR/MT thật + cache/output/pause-resume,
E2E Offline và GUI smoke PASS. Không tải ảnh, DOWNLOAD_UNKNOWN, downloader chưa
triển khai. Không build hoặc kiểm thử EXE mới; 4 EXE cũ bảo toàn hash. 100 file
chụp hash giữ nguyên và5 model integrity PASS, config/DOM/ảnh nguồn không đổi.

Evidence: `logs/kuaikan-http-20261107T090510Z/` (environment, runtime-probe,
pytest, unittest, preservation). Báo cáo/đường dẫn GUI/E2E và việc còn lại tại
`docs/KUAIKAN_CHAPTER_281106_ANALYSIS.md` (mục LIVE HTTP RUNTIME VALIDATION);
guide có mục LIVE HTTP ACQUISITION VALIDATION. Bước tiếp là phiên có mạng hợp lệ
để kiểm chứng response bằng cùng adapter; không cần gửi DOM mỗi lần đọc chương.

## Mới nhất — parser Kuaikan kiểm chứng bằng DOM người dùng, 07/11/2026

Hai file thật dưới `output/kuaikan-capture/` đọc UTF-8 được, giữ nguyên SHA.
Parser topic hiện ánh xạ **26 mục / 23 main / 3 supplementary** từ DOM title
và ID thật trong public Nuxt state; **0 href literal nhưng 26 canonical URL**
theo route reader đã xác minh. Chương 15 khớp ID281106 và URL từ dữ liệu nhúng.
Reader có **122 img nội dung / 116 URL duy nhất / 6 bản trùng**, khớp 116 mục
manifest snapshot; image_list_complete vẫn None, chưa kiểm tra bitmap hoặc mạng.

Đã thêm literal/alias reader không JS execution, sửa parser scope/lazy/signed
URL discovery, thêm provenance/thống kê và redaction report. PUBLIC chỉ là đọc
theo snapshot; DownloadDecision vẫn UNKNOWN, downloader Kuaikan chưa có.
Không đổi GUI, core OCR/MT, native guard, transport HTTP, service/cache,
dependencies, model, .venv, BAT/spec hoặc EXE. Không build trong nhiệm vụ này.

**Pytest/unittest: 148 PASS, 10 SKIPPED, 0 FAIL** (thêm 14 ca, trong đó 2 ca
chạy toàn bộ DOM gốc). Hai CLI rendered_dom PASS, zero network/download.
GUI Windows Qt ba tab với ảnh đơn/folder/OCR/MT thật, E2E Offline và GUI smoke
PASS; config/ảnh nguồn không đổi. Physical desktop nghiệm thu thủ công chưa làm.
**Live HTTP, image download và EXE mới: NOT TESTED trong nhiệm vụ DOM**, không
coi parser PASS là daily URL → ảnh → dịch PASS hoặc tái kết luận mạng BLOCKED.

Evidence/tests/bảo toàn: `logs/captured-dom-20261107/`; CLI báo cáo tại
`output/kuaikan-html-analysis/20261107T082007Z-14ec3b/` (topic) và
`20261107T082007Z-f9cb99/` (reader). Chi tiết/đường dẫn GUI/E2E trong
`docs/KUAIKAN_CHAPTER_281106_ANALYSIS.md`. Hai DOM nguyên bản không commit;
fixture capture đã lọc riêng tư và thay query chữ ký bằng dummy, có provenance.

`docs/WEBSITE_ADAPTER_AI_GUIDE.md` cập nhật ứng dụng cá nhân, USER-PROVIDED DOM
WORKFLOW, prompt thêm domain, API và checklist nghiên cứu/runtime riêng.
Bước tiếp: kiểm chứng HTTP acquisition khi được yêu cầu/phép; chỉ thêm tải khi
điều kiện tải được xác minh. Không cần thêm DOM cho parser snapshot hiện tại.
Các trạng thái chưa nhận DOM/fixture-only ở mục cũ phía dưới là lịch sử.

## Mới nhất — adapter URL chương Kuaikan, 07/11/2026

Đã bổ sung router `/webs/comic-next/<id>`, parser HTML/DOM topic/reader/ảnh tách khỏi
download, partial lists/warnings, parent comic ID nullable và IMAGE_LIST_READY.
GUI chính/pipeline không viết lại; worker phân tích URL chương độc lập topic list,
thêm thao tác nhỏ phân tích ảnh chương đã chọn. Chưa tải ảnh hoặc bật downloader.

**Chưa nghiệm thu live Kuaikan.** Trang chương không truy cập được qua công cụ web;
runtime bị sandbox/proxy guard chặn mạng. Chưa xác minh HTTP status/DOM/prev-next/
link 15 từ topic/URL ảnh thật. Đã yêu cầu HTML/DOM đã lưu; fixture hiện tại viết tay,
không thay bằng chứng website. Chi tiết `docs/KUAIKAN_CHAPTER_281106_ANALYSIS.md`.
Regression source: **pytest/unittest 134 PASS, 10 SKIPPED (144 ca)**; GUI Windows
ảnh đơn/folder/OCR/MT thật, E2E Offline và GUI smoke PASS. 18 ca parser/worker mới
chỉ dùng fixture; 3 ca live Kuaikan SKIPPED. Chưa build mới khi chưa có DOM thật.
EXE GUI tab đã nghiệm thu ở các mục dưới được giữ nguyên, chưa chứa sửa adapter này.

## Mới nhất — GUI ba tab và luồng URL độc lập, 07/11/2026

MainWindow nhúng **Ảnh đơn / Thư mục ảnh / Link truyện online**, có cuộn, không mở
dialog nguồn lớn. ComicSourcesPanel dùng lại worker và pipeline; folder cũ giữ nguyên.
Phân tích URL không phụ thuộc cờ quyền tải toàn website. Metadata giữ khi lỗi chương;
chương UNKNOWN chọn được; tải xét DownloadDecision từng chương và worker kiểm tra lại.
Lỗi parser/network/access/usage_limit/download_policy/kỹ thuật tách riêng.

Kuaikan: metadata browser quan sát được, raw chapter/parser/image list chưa xác minh;
policy UNKNOWN, downloader chưa triển khai. Không bịa chương hoặc endpoint. Chưa có
live URL → ảnh PASS. Ảnh người dùng cung cấp vẫn dịch Offline bình thường.

Pytest/unittest **116 PASS, 7 SKIPPED (123 ca)**; tab GUI Windows với ảnh truyện/
OCR/MT thật PASS, folder workflow cũ/E2E/GUI smoke PASS. Build mới PASS qua build.bat;
chính EXE đã PASS tab workflow, GUI Windows smoke và E2E Offline ảnh truyện thật.
Binary `dist/ImageTranslatorVN-20261107T045417969128Z/ImageTranslatorVN-20261107T045417969128Z.exe`,
SHA-256 `99baadc76bc0836781ac7db43674f1a4e7b93be3e5344d6d47c0b5357bbe517c`.
Không ghi đè bản cũ; không đổi dependencies/model/core pipeline/native guard/BAT/spec.
QA đã được tách khỏi lưu config thật; xem lỗi đã khắc phục và evidence đầy đủ tại
`docs/GUI_URL_FLOW_REPORT.md`. Các trạng thái lịch sử phía dưới không phải trạng thái mới nhất.

## Mới nhất — nguồn ảnh/chương/URL, 07/11/2026

**Phần ảnh cục bộ đã tích hợp; Kuaikan URL đầy đủ vẫn BLOCKED.** Không tạo lại
dự án/.venv, không cài/nâng package, không tải/đổi model, không sửa core pipeline,
provider, native import guard, BAT/spec hoặc EXE cũ.

- `sources/`: contract/registry/Kuaikan metadata thử nghiệm, HTTPS/DNS validation,
  ImageCollection, cache manifest kiểm tra ảnh/hash/quota, LocalComicJob dùng
  ProcessingManager gốc và publisher xuất theo chương không ghi đè.
- `ui/comic_sources.py`: ảnh đơn/thư mục chương/link; QThread, chọn chương chủ động,
  pause/resume/cancel/retry, output riêng. MainWindow chỉ thêm nút mở dialog.
- `scripts/qa_common.py` đưa `sources/*.py` vào source fingerprint để gate build
  không tái dùng bằng chứng của adapter cũ. Không nới các điều kiện build khác.
- Mở source mới bằng **`run_source.bat`**, rồi **Ảnh đơn / chương ảnh / link truyện
  online**. BAT cũ vẫn trỏ luồng cũ; EXE cũ chưa có UI nguồn mới.
- Kuaikan: quan sát metadata topic 6677 và 15425 qua công cụ web; topic 3791 chưa
  đọc được. Chưa có raw HTML/chapter IDs/image list được xác minh, chưa có quyền
  tải tự động. Không triển khai downloader ảnh HTTP. Runtime metadata báo mạng bị
  sandbox/proxy giới hạn; không bỏ proxy hoặc vượt kiểm soát truy cập.
- Thay thế hợp lệ đã chạy: nhập ảnh người dùng cung cấp, 2 chương/2 ảnh truyện thật,
  3 vùng OCR + 3 bản dịch, xuất PNG, nguồn nguyên vẹn; GUI Qt Windows và offscreen
  đã có evidence. Không coi ảnh này có provenance Kuaikan hoặc chất lượng dịch đạt.
- Audit `.venv`: 16/16 imports, 18/18 pins, Ready True; 5 model còn hợp lệ.
  **Pytest/unittest cuối: 106 PASS, 7 SKIPPED (113 ca)**. GUI smoke, workflow thư
  mục cũ và E2E Offline chuẩn PASS; GUI chương ảnh Windows/offscreen PASS.
  Test/đường dẫn evidence cuối xem `docs/ONLINE_COMIC_TEST_REPORT.md`.
- EXE mới chưa build/NOT TESTED: luồng URL chưa đủ điều kiện nghiệm thu. Không ghi
  đè bản EXE cũ. Các phần lịch sử bên dưới không thay thế trạng thái mới này.

Tài liệu: `docs/KUAIKANMANHUA_ANALYSIS_REPORT.md`,
`docs/ONLINE_COMIC_TEST_REPORT.md`, **`docs/WEBSITE_ADAPTER_AI_GUIDE.md`**.
Bước tiếp: xác minh cấu trúc HTML/chương thật trong môi trường mạng được phép;
chỉ thêm downloader khi quyền tải và các giới hạn đã được xác minh. Tiếp tục cải
thiện chất lượng MT/mask theo báo cáo cũ; không thay model trong tác vụ URL này.

## Quản lý Git — 06/11/2026

Đã `git init -b main`; chưa có commit và chưa thêm được remote vì sandbox chặn ghi `.git/config`/index. Remote dự kiến `https://github.com/thangtaide/IMAGE-TRANSLATOR-VN.git`. `.gitignore` loại model, môi trường Python, EXE/build, backup, cache, log, output/evidence, ảnh ImgTest và cấu hình riêng. Giữ mã nguồn/test/script, cấu hình mẫu và các báo cáo Markdown. Không xóa dữ liệu cục bộ. Truy cập GitHub cũng lỗi proxy `127.0.0.1:9`. Yêu cầu nâng quyền ghi Git metadata đã bị chính sách `sandbox_approval=false` từ chối. Cần môi trường cho phép ghi `.git` và HTTPS tới GitHub để commit/push; không đổi quyền ACL hoặc bỏ proxy để vượt giới hạn. Xem `GIT_PUBLISH_REPORT.md`.

## Kết quả cuối lượt khôi phục — 06/11/2026, sau 10:26 UTC

**MVP đã khôi phục và mở rộng, chưa nghiệm thu chất lượng dịch.** Audit cuối `logs/install-audit-20261106T102603Z`: **16/16 imports, 18/18 pin, Ready True**; 5 model vẫn hợp lệ. Không cài package, đổi model/.venv/setuptools/CT2 hoặc DLL hệ thống.

- Unittest **83 ca: 76 PASS, 7 SKIPPED**, `logs/real-image-fix-unittest-20261106/`. Pytest cuối **76 PASS, 7 SKIPPED**, trong `logs/build-ImageTranslatorVN-20261106T101857052219Z.log`.
- Corpus người dùng `D:\TransTool\ImgTest`: **61/61 ảnh xuất, 0 lỗi**, nguồn giữ hash và kích thước; **75 vùng chữ dịch thật**, 2 vùng số/ký hiệu bảo toàn. 24 ảnh raw OCR không tìm thấy chữ; không gọi mọi ảnh là bản dịch đạt. Evidence `output/real-image-validation-20261106-numeric-fix/`.
- Lượt trước có 3 lỗi marker số, đã sửa bằng giữ nguyên vùng chỉ có số/ký hiệu và kiểm tra số nguyên dạng sau dịch; mất/đổi/thêm số vẫn bị chặn. Các output/cache/job có revision mới, không ghi đè kết quả cũ. Backup trước sửa `backups/pre-numeric-fix-20261106T101537Z`.
- GUI với 61 ảnh thật: PASS, 494 heartbeat, 61 hàng, progress 100%. Chính EXE cuối: GUI smoke, workflow nút và E2E ảnh truyện thật PASS kỹ thuật. Ảnh dài ghép panel 1280×3385 cũng PASS kỹ thuật; ghi rõ là fixture ghép, chưa chấm accuracy.
- Mở bản mới bằng **`run_updated.bat`**. EXE `dist/ImageTranslatorVN-20261106T101857052219Z/ImageTranslatorVN-20261106T101857052219Z.exe`, SHA-256 `bc3227317d216e32ed34831402df159f8aad8b21540d5670a93887a7376db1b0`. Bản gốc và bản build trung gian đều giữ nguyên; `run.bat` vẫn mở bản gốc.
- **Còn hạn chế:** Argos sai nghĩa/tên riêng trên truyện, còn nét màu/dấu câu ở một số mask. M2M100 chỉ tích hợp adapter, chưa có trọng số/Transformers; so sánh thật SKIPPED do sandbox mạng tắt. Không tuyên bố bản dịch đã tốt hoặc M2M100 đã chạy được.

Đọc **RECOVERY_REPORT.md, REAL_IMAGE_REPORT.md, BUILD_REPORT.md, M2M100_SETUP.md** trước khi tiếp tục. Bước tiếp theo: cung cấp môi trường thực thi có HTTPS hợp lệ/model M2M100 chính thức để chuyển đổi và so sánh; đánh giá corpus có bản chép chuẩn và mask trên nền phức tạp. Các phần dưới ghi lịch sử từng giai đoạn, không thay thế trạng thái này.

## Khôi phục sau mất điện — trạng thái mới 06/11/2026, sau 10:00 UTC

Đã xác minh lại MVP trước khi sửa: fingerprint nguồn và SHA-256 EXE khớp, SQLite quick_check ok, 5 model hợp lệ, audit 16/16 imports và 18/18 pins, Ready True. Baseline unittest/pytest 63 PASS, 6 SKIPPED; GUI và E2E Offline chính EXE cũ PASS. Không tạo lại dự án/.venv, không cài package hoặc đổi model. Backup 70 file tại `backups/recovery-20261106T095010Z`.

Sau sửa: **unittest và pytest 73 PASS, 7 SKIPPED**; GUI smoke và E2E chuẩn không mock PASS. Mask thích ứng giảm pixel tối còn sót **600 → 0**, viền màu thay đổi **0** trên fixture đã kiểm tra. GUI nút thật + QThread/OCR/MT thật PASS cả pause/resume/cancel/retry/skip/error/preview/zoom/settings/verify model; có cache QA riêng và khôi phục cấu hình.

Provider M2M100 CPU riêng đã tích hợp, không thay Argos mặc định. **Chưa có model M2M100; suy luận/so sánh thực tế SKIPPED**, không có bản dịch giả. Sandbox vẫn tắt mạng, không tải lớn hoặc cài Transformers. Chi tiết `M2M100_SETUP.md`, `RECOVERY_REPORT.md`. Chưa có corpus truyện thực tế được cung cấp; chưa nghiệm thu ngữ nghĩa/nền phức tạp/chữ dọc.

`build.bat` giữ gate và ghi build mới vào tên timestamp để bảo vệ bản EXE cũ. Log hiện tại `logs/build-ImageTranslatorVN-20261106T100146952450Z.log`: pip check PASS, pytest 73 PASS/7 SKIPPED; PyInstaller đang chạy. Xem BUILD_REPORT để biết kết quả kiểm chứng binary sau đó.

Kiến trúc chỉ mở rộng factory/provider local M2M100, mask và injection đường dẫn SQLite QA cho MainWindow; native runtime guard vẫn giữ nguyên. Cache/job identity bổ sung `adaptive-mask-v2` để không tái sử dụng ảnh xuất mask cũ.

Ưu tiên tiếp: có quyền mạng thực thi hợp lệ và model M2M100 chính thức → chuyển đổi/kiểm thử CPU → so sánh 24 câu; nhận đường dẫn corpus truyện thực tế để nghiệm thu. Giữ nguyên model/EXE cũ hợp lệ. Các trạng thái phía dưới là lịch sử trước lượt khôi phục này.

**Hiện trạng mới nhất 06/11/2026:** audit `.venv` **16/16 imports, 18/18 pin, Ready: True**. Đã sửa WinError 127 trong luồng chuẩn, **E2E kỹ thuật không mock PASS**. GUI offscreen và native Windows platform PASS, screenshot hiển thị chữ Việt. Unittest và pytest đều **63 PASS, 6 SKIPPED**. **Build onedir PASS, chính EXE đã chạy GUI smoke và E2E Offline thành công**. Chất lượng model pivot còn lỗi ngữ nghĩa và mask còn sót nét; không coi sản phẩm đã nghiệm thu chất lượng. Dữ liệu/model/bằng chứng cũ được giữ nguyên.

## Kết quả binary và công việc tiếp theo hiện tại

- Chạy bằng `run.bat` hoặc `D:\TransTool\dist\ImageTranslatorVN\ImageTranslatorVN.exe`. Giữ nguyên thư mục onedir và model ngoài tại `D:\TransTool\models`.
- EXE GUI: `logs/gui-smoke-20261106T085536Z-fb0e84/report.json` PASS, Windows Qt platform; đã xem screenshot tiếng Việt. Desktop vật lý/native Windows picker chưa xác minh.
- EXE E2E: `output/e2e-validation/20261106T085546Z-e14cdf/report.json` PASS kỹ thuật, OCR/dịch thật, đủ artifact, kích thước giữ nguyên và nguồn không đổi. Đây là fixture tổng hợp.
- Build: `logs/build.log`, binary SHA-256 và ma trận nghiệm thu trong `BUILD_REPORT.md`; không có model/dependency nào bị thay trong lượt sửa DLL.
- Sau kiểm thử EXE, chạy lại E2E chuẩn `.venv` PASS tại `output/e2e-validation/20261106T085912Z-51c063/` và build prerequisite check PASS. Đây là evidence Python mới nhất; evidence EXE riêng vẫn giữ nguyên.
- Việc tiếp theo: đánh giá và tích hợp model trực tiếp zh→vi sau khi quyết định dung lượng/RAM; sửa mask còn sót nét dựa trên ảnh thật; kiểm thử corpus truyện/photo, OCR chữ dọc và các ngôn ngữ thiếu model; kiểm thử workflow thao tác đầy đủ trên desktop người dùng và máy sạch. Chưa thực hiện các mục này.
- Mục “Công việc tiếp theo” trong lịch sử phía dưới mô tả thời điểm môi trường còn thiếu thư viện; **không chạy lại install hoặc tải lại model đã hợp lệ**.

## Lượt sửa WinError 127 và hoàn thành E2E
- Root cause đã xác minh bằng PE imports/exports và loaded-module path: Paddle nạp `paddle/libs/libiomp5md.dll`, bản này thiếu `__kmpc_masked` và `__kmpc_end_masked` mà `torch/lib/torch_cpu.dll` yêu cầu. Torch bị import gián tiếp tại `ctranslate2/specs/model_spec.py:18`; loader báo WinError 127 tại shm.dll/dependency.
- Bằng chứng chính xác: `output/runtime-validation/20261106T084730Z-ca8bd9/report.json` (negative control `REPRODUCED`, không phải pipeline thành công).
- Thêm `core/runtime.py`: khóa và cache khởi tạo CT2/Torch trước Paddle. Entry point và package UI cũng gọi trước Qt để tránh lỗi typing.Self phát hiện ở worker Python 3.10/PySide6. Hai adapter OCR/Offline tự bảo vệ đường gọi trực tiếp. Model vẫn lazy/reuse, suy luận ở QThread.
- Không đổi dependencies/setuptools, không sửa site-packages/PATH/DLL hệ thống; không xóa/tải lại model. Chưa cần kiến trúc subprocess suy luận: thứ tự nạp ổn định qua các ca fresh-process.
- Worker hỗ trợ SQLite state riêng qua tham số tùy chọn; validation dùng DB mới để đảm bảo OCR/MT thực sự chạy thay vì cache. Hủy trước/sau khởi tạo runtime được xử lý an toàn.
- `tests/test_runtime_integration.py` chạy 7 ca tiến trình mới: tái hiện raw legacy order; CT trước Paddle; chuẩn bị runtime rồi import Paddle; OCR adapter trước dịch; 4 lần OCR/MT cùng model; restart QThread worker hai lần; cancel job thật. Các đường được guard PASS; raw legacy order vẫn tái hiện lỗi đúng như negative control.
- `logs/runtime-final-unittest-20261106/test-results.json`: 69 ca, **63 PASS, 6 SKIPPED**, không lỗi. `logs/runtime-final-pytest.log` và XML: **63 PASS, 6 SKIPPED**, không lỗi. Các skip: OCR en/ko/zt, MT ko/zt thiếu model; Online opt-in.
- Full suite đầu phát hiện một test dùng literal `.venv/python.exe` làm ví dụ “Python khác”; khi chạy bằng chính `.venv` giả định này sai. Đã sửa test tạo đường dẫn khác interpreter thực tế; không thay logic build gate hay sửa output test.
- E2E chuẩn mới nhất `output/e2e-validation/20261106T084804Z-4a9386/`: PASS toàn bộ, đủ source/OCR/translation/mask/erased/final/report, input fixture Trung tổng hợp, không hardcode OCR/MT. Đã xem ảnh cuối; còn vết nhỏ ở rìa mask và bản dịch câu thứ hai sai nghĩa.
- Font: Qt offscreen không có font directory/family mặc định. `ui/fonts.py` đăng ký font đã cài tại Windows qua đường dẫn, kiểm tra glyph bằng Unicode codepoint; không sao chép/phân phối font Windows. Screenshot đã đọc được tiếng Việt, native Windows platform cũng PASS trong desktop của sandbox, chưa xác minh desktop vật lý của người dùng.
- GUI bằng chứng mới nhất `logs/gui-smoke-20261106T084804Z-d4ffe4/`. Khởi tạo, picker Qt, bảng ảnh, model dialog, preview, heartbeat, glyph và screenshot PASS.
- Corpus 24 câu và từng chặng: `output/translation-quality/20261106T083515Z-bdb3f5/`. Tokenizer khớp Argos; pivot khớp hai chặng riêng, direction đúng, không lỗi giới hạn token. Câu mục tiêu zh→en đã lệch cách diễn đạt, en→vi làm mất nghĩa hoàn toàn. Xem `TRANSLATION_QUALITY_REPORT.md`.
- Đã nghiên cứu `facebook/m2m100_418M` MIT, hỗ trợ zh/vi, trọng số chính thức 1.94 GB; CT2 4.6 hỗ trợ chuyển đổi CPU/int8. Chưa tải hoặc kiểm thử model lớn này.
- `build.bat` đã hoàn tất sau khi gate PASS và full tests đạt; binary đã PASS GUI smoke và E2E thật. Xem BUILD_REPORT để biết phạm vi kiểm chứng và giới hạn.

Các phần lịch sử bên dưới mô tả những trạng thái FAIL cũ, không thay thế bằng chứng hiện tại.

## Lượt sửa import CTranslate2 (sau evidence 20261106T080950Z)
- Import duy nhất FAIL: `ctranslate2` 4.6.0, `ModuleNotFoundError: No module named 'pkg_resources'` tại `ctranslate2/__init__.py:8`.
- Nguyên nhân: setuptools 84.2.1 đã bỏ pkg_resources; không phải thiếu model hay DLL trong lỗi import ban đầu.
- Đã hạ riêng setuptools xuống 80.9.0 từ wheel cache, SHA-256 khớp PyPI. Inventory trước/sau xác nhận **chỉ setuptools thay đổi**. Không tạo lại `.venv`, không cài lại requirements, không đổi CTranslate2/Torch/Paddle và không sửa mã runtime chính.
- Chạy lại check_installation.py: **Imports PASS 16/16, Required packages satisfied 18/18, Ready: True**, pip check PASS. Evidence `logs/install-audit-20261106T081441Z/installation.json`.
- Bằng chứng sửa và traceback: `logs/ctranslate2-repair-20261106T081432Z-3ca7ce/`.
- GUI smoke **PASS Qt offscreen**, process exit 0; picker/model manager/preview/list ảnh/heartbeat đạt. Screenshot vẫn hiện ô vuông thay chữ ở offscreen, chưa xác minh font và desktop/native dialog. Evidence `logs/gui-smoke-20261106T081510Z-263830/`.
- Model có và verify OK: det-ch/rec-zh/cls + translate-zh_en-1_9/translate-en_vi-1_9. Không tải lại/xóa model nào.
- Model còn thiếu: OCR det-en/rec-en/det-ml/rec-ko/rec-zt; dịch translate-zt_en-1_9/translate-ko_en-1_1. Không tải tự động.
- OCR Trung thật trên fixture tổng hợp: `你好，世界！` confidence 0.993094; `欢迎使用图像翻译。` confidence 0.982723, tọa độ hợp lệ. Evidence `output/e2e-validation/20261106T081543Z-83d0a4/ocr.json`.
- Offline en→vi độc lập PASS suy luận; cùng tiến trình Paddle trước CT FAIL WinError 127 ở torch/lib/shm.dll; CT trước Paddle rồi dịch zh→en→vi PASS suy luận. Xác nhận vấn đề thứ tự nạp, chưa chỉ rõ symbol/DLL phụ thuộc bị xung đột. Evidence `logs/engine-interop-20261106T081715Z-e403eb/`.
- Bản dịch câu thứ hai là `Không có gì.`, sai nghĩa so với nguồn. Không coi suy luận thành công là đạt chất lượng.
- Luồng E2E chuẩn hiện FAIL tại translation; mask/inpaint/render/export SKIPPED. Không build EXE.
- Thêm hai script chẩn đoán phạm vi hẹp: `repair_ctranslate2_import.py`, `probe_engine_interop.py`. Đã cập nhật INSTALL_REPORT, giữ nguyên bằng chứng các lượt trước.
- Việc tiếp theo: xử lý khởi tạo CT trước Paddle trong worker, kiểm thử lại E2E và chất lượng; xác minh font/desktop. Yêu cầu hiện tại về sửa import đã hoàn tất; chưa thay đổi mã xử lý chính để mở rộng sang lỗi runtime mới.

Các phần bên dưới lưu **lịch sử lượt triển khai/chẩn đoán trước**, bao gồm trạng thái từng thiếu thư viện/model; xem phần hiện trạng mới nhất trước khi tiếp tục.

## Lượt tiếp tục: chẩn đoán WinError 10061 và kiểm thử thật
- Đã chẩn đoán chỉ đọc: `CODEX_SANDBOX_NETWORK_DISABLED=1`, HTTP_PROXY/HTTPS_PROXY/ALL_PROXY cùng là `http://127.0.0.1:9`, PIP_NO_INDEX=1. Cổng proxy trả 10061.
- Proxy Windows HKCU tắt; WinHTTP Direct; DNS của các nguồn chính thức PASS. HTTPS theo môi trường FAIL; không bỏ proxy để vượt sandbox.
- Người dùng **đã đồng ý cấp môi trường thực thi có mạng**. Kiểm tra lại vẫn thấy hạn chế như cũ. Yêu cầu thực thi có quyền mạng bị auto-review từ chối vì `sandbox_approval=false`. Không cần hỏi lại quyền đã được đồng ý; cần host áp dụng quyền có hiệu lực.
- Không sửa proxy hệ thống/VPN/firewall/Codex config và không lặp lại pip/model downloads khi biết chắc bị chặn.
- `.venv` được tái sử dụng, pip 22.3.1; audit import từng module: 0/16 đạt, 0/18 pin được đáp ứng. Cài đặt đầy đủ SKIPPED vì mạng chưa hợp lệ.
- Thêm `scripts/diagnose_network.py`, `check_installation.py`, `validate_e2e.py`, `smoke_gui.py`, `gui_smoke_actions.py`, `qa_common.py`, `check_build_ready.py`; không viết lại core/providers/UI.
- Thêm nhánh QA tùy chọn `main.py --smoke-test --smoke-report ...`; chạy bình thường giữ nguyên entry point.
- Đã thực hiện E2E **không dùng mock**: ảnh Trung tổng hợp 1200×430 được tạo và kiểm tra trực quan; OCR FAIL vì thiếu Paddle/PaddleOCR, các bước dịch/mask/inpaint/render/export SKIPPED. Không tạo ảnh dịch giả.
- Bằng chứng E2E: `output/e2e-validation/20261106T070513Z-a4c481/report.json`; nguồn, OCR/translation JSON lỗi và traceback nằm cùng thư mục. Các lần trước được giữ lại.
- GUI smoke SKIPPED vì thiếu PySide6; chưa mở GUI/desktop thật. `logs/gui-smoke-20261106T070512Z-5fe844/report.json`.
- `build.bat` có gate mới: yêu cầu GUI/E2E PASS thật, đúng fingerprint và interpreter. Gate thực tế trả SKIPPED; không gọi PyInstaller ở lượt này, không có EXE.
- Regression hiện tại **49 PASS**, 0 fail/error, bằng unittest; 5 ca gate mới đều là unit fixtures, không phải AI PASS. Log riêng `logs/qa-followup-unit-20261106/`, không ghi đè 44 ca ban đầu.
- Đã tạo `INSTALL_REPORT.md`, `E2E_REPORT.md`, `BUILD_REPORT.md`. Xem các báo cáo này trước khi tiếp tục; báo cáo 44 ca dưới đây là lịch sử lượt đầu.

## Môi trường
Windows, Python 3.10.9 x64. CMD hoạt động; PowerShell runner báo Access denied.

## Kiến trúc
PySide6 GUI → QThread batch → OCR PaddleOCR 2.x cục bộ → provider dịch độc lập → OpenCV mask/inpaint → Pillow render → atomic save. SQLite lưu cache và checkpoint. Model manager tải theo thao tác riêng.

## Module đã tạo
- `core/paths.py`, `types.py`, `storage.py`: đường dẫn, cấu hình, logging, SQLite.
- `core/ocr.py`, `models.py`: PaddleOCR CPU, tile/dedup/grouping, danh mục model, tải riêng, xác minh hash, cài đặt an toàn.
- `providers/base.py`, `online.py`, `offline.py`: MyMemory/LibreTranslate miễn phí, Argos/CTranslate2 cục bộ, đường dịch pivot có kiểm soát.
- `core/imaging.py`, `pipeline.py`: mask glyph/inpaint, Unicode renderer, atomic export, batch, checkpoint, retry, pause/resume/cancel.
- `ui/`: PySide6, bảng tiến trình thực, preview hai ảnh, quản lý model và settings.
- `scripts/`, `tests/`, các batch script và PyInstaller spec.

## Theo giai đoạn yêu cầu
| Giai đoạn | Kết quả |
| --- | --- |
| 1: môi trường/GUI/config/log | Mã nguồn và .venv đã tạo; GUI chưa mở được do thiếu PySide6 |
| 2: OCR | Adapter/model manager đã viết; test adapter đạt, OCR thật chưa có dependencies/model |
| 3: Online | Provider/cache/retry đã viết, mock đạt; MyMemory live thất bại kết nối |
| 4: Offline | Argos tokenizer/CT2/pivot/model manager đã viết; model thật chưa tải/cài, chưa suy luận |
| 5: inpaint/render/preview | CV/export chạy thật và xem artifact; Qt preview chưa chạy |
| 6: batch/progress/điều khiển | Core workflow fixture đạt; GUI/QThread integration chờ Qt |
| 7: QA/build | Lượt đầu 44 ca đạt; lượt tiếp tục 49 ca đạt. GUI/E2E chưa PASS, build được gate chặn; chưa nghiệm thu |

## Kết quả giai đoạn kiểm thử
- 44 ca unit/CV/workflow khả dụng PASS bằng unittest; tests tương thích pytest.
- 9 method integration và 1 class GUI SKIP do thiếu model/thư viện hoặc Online opt-in.
- Lỗi alpha khi vẽ chữ đã sửa và regression test đạt.
- Cache theo hash font/mask/model/cấu hình, ảnh gốc giữ nguyên, lỗi dịch không xuất ảnh tẩy trắng đã được test.
- `compileall` đạt ở mã nguồn hiện tại.
- Đã xuất/xem artifact OpenCV/Pillow 960×520 trong `output/cv-validation`; alpha giữ nguyên. Đây là fixture CV, không phải OCR/MT thật.
- MyMemory live probe đã thực hiện và thất bại sau 3 lần kết nối; log `logs/online-probe.json`.
- PyInstaller đã được gọi thật nhưng không có module; **không có EXE**.
- README tiếng Việt, TEST_REPORT, THIRD_PARTY_NOTICES và config mẫu đã có.

## Trở ngại môi trường
- Pip có PIP_NO_INDEX và proxy không kết nối được (WinError 10061). Đã thử cài dependencies nhưng thất bại.
- Không có PySide6, PaddleOCR/PaddlePaddle, Argos/CTranslate2, SentencePiece, pytest, PyInstaller trong môi trường dự án.
- Model OCR, model dịch Anh → Việt và font Noto tải thất bại vì mạng. Không có model AI được cài.
- GUI thật, OCR thật, dịch Offline thật, EXE **chưa được xác minh**. MyMemory/LibreTranslate trong unit tests là mock.
- requirements là bộ phiên bản khóa đề xuất dựa trên metadata, chưa được kiểm chứng cài đủ.
- Danh mục model Hàn → Anh dùng bản 1.1 theo index chính thức; chưa tải hoặc kiểm thử tương thích binary.
- Font Noto chưa tải được; test CV dùng font Windows đã cài, không sao chép font Windows vào dự án.

## Giới hạn còn tồn tại
- Chưa đánh giá chất lượng OCR/dịch trên ảnh thật, chữ dọc, giản/phồn thể và truyện tranh.
- Gom dòng/thứ tự đọc là heuristic; chưa có segmentation bong bóng; chưa có chỉnh bản dịch/polygon thủ công trong preview.
- Metadata ảnh không được bảo toàn đầy đủ; ảnh động không hỗ trợ; giới hạn 65 triệu pixel.
- Marker bảo vệ thuật ngữ/số có thể bị MT biến đổi và sẽ khiến ảnh báo lỗi an toàn.
- Inpainting trên nền phức tạp cần kiểm tra thủ công; không hứa khôi phục hoàn hảo.
- Hook đóng gói Paddle/CT2/Qt cần chạy kiểm chứng thực tế.

## Công việc tiếp theo
1. Áp dụng quyền mạng ở host/profile (đã được người dùng đồng ý), mở lại phiên tại D:\TransTool; chạy script chẩn đoán trước. Khi có mạng hợp lệ hoặc wheelhouse đầy đủ: `install.bat`; chạy resolver/pip check/import audit.
2. Ưu tiên Trung giản thể theo yêu cầu mới: tải riêng det-ch/rec-zh/cls, sau đó en→vi và zh→en; xác minh đủ hai chặng. Không tải cả 12 model một lúc, không tải lại model hợp lệ.
3. Chạy pytest và integration thật; ghi kết quả rõ ràng, không đổi SKIP thành PASS.
4. Kiểm tra GUI/nút điều khiển, ảnh dài, RAM, câu dịch/tên riêng trên tập ảnh thật.
5. Chạy smoke_gui.py và validate_e2e.py bằng cùng `.venv`; chỉ khi gate đạt mới build onedir. Mở EXE thật để smoke-test, giữ model bên ngoài; cập nhật trạng thái.
Đọc TEST_REPORT và source manifest trước khi tiếp tục, không tạo lại dự án.

## Lệnh
- Người dùng cuối: `install.bat`, sau đó `run.bat`; build bằng `build.bat`.
- Kiểm tra hiện tại: `python scripts\run_tests.py` (unittest, không thay tên thành pytest).
- Sau khi cài: `.venv\Scripts\python.exe -m pytest -q`.
