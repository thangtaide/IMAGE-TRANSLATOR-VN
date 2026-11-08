# Stage 3A — Online Free Machine Translation

Ngày kiểm tra: **08/11/2026 (+07)**.
Trạng thái: **STAGE_3A_COMPLETED_WITH_WARNINGS**.
API MyMemory đã chạy thật với phạm vi người dùng duyệt; GUI/quota/resume đã kiểm
thử riêng bằng HTTP mock và OCR/Argos thật. Không đánh đồng hai phép thử đó với
một E2E ảnh→HTTP thật→ảnh được nghiệm thu đầy đủ. Không chuyển Stage3B/3C/4/5.

## 1. Baseline và phạm vi

Đã đọc AGENTS, PROJECT_STATUS, README, USER_GUIDE, TROUBLESHOOTING, báo cáo
Stage1/2/3, pipeline/diagnostics/storage/providers, worker GUI và LocalComicJob.
Git trước sửa sạch, branch main, không staged/xung đột. Baseline Stage3 từ artifact:
261 PASS/10 SKIPPED mỗi runner; dataset150,99dev/51holdout,0 verified reference.
Manifest chương274872: completed_with_warnings,120 output,119 pipeline-complete,
1 FALLBACK_ORIGINAL, needs_retry=[111]. Không gọi119 là119 trang đều đã dịch chữ.

Trước sửa lưu hash595 file runtime/resource cần bảo vệ và snapshot manifest trong
`logs/stage3a-online-free-20261108T014648Z/`. Khác688 Stage3 vì lần này source/test
được phép sửa, tập bảo vệ tập trung model/config/ảnh/cache/DB/output/BAT/spec/EXE.
Không sửa .venv, native guard, models, default Argos, numeric validator hoặc recipe
Offline; không tải ảnh/model, không retry111, không build EXE.

## 2. Nghiên cứu provider chính thức

Chỉ chọn **MyMemory GET ẩn danh**. VERIFIED dưới đây là điều kiện tích hợp/miễn
phí trong phạm vi này, không bảo đảm SLA hoặc đúng ngữ nghĩa mọi câu. Không có
đăng ký tài khoản, email, key, billing, set/import TM hoặc nâng quota bằng danh tính.

| Provider / nguồn chính thức | zh→vi / xác thực | Miễn phí, billing | Request / batch / tốc độ | Privacy, tích hợp và kết luận |
|---|---|---|---|---|
| [MyMemory API](https://mymemory.translated.net/doc/spec.php), [limits](https://mymemory.translated.net/doc/usagelimits.php), [terms/privacy](https://mymemory.translated.net/terms-and-conditions) | zh-CN\|vi trực tiếp; GET q/langpair, mt=1, không key | 5.000 ký tự/ngày anonymous; không billing. Email50.000/whitelist không dùng | Max500 byte UTF8/query; một đoạn/request, không batch nhiều bong bóng. Không công bố RPM cố định ở nguồn đã đọc; app tự giãn1,1s | API automation được phép theo điều kiện; cấm crawl, lách quota và ghép nhiều đoạn. Có lưu segment dài hạn, logging và đối tác MT; không dùng cho dữ liệu bí mật. **VERIFIED**, chọn opt-in |
| [LibreTranslate API](https://docs.libretranslate.com/guides/api_usage/), [portal](https://portal.libretranslate.com/) | Tùy model instance; hosted cần key | Hosted portal Pro29USD/tháng; không phải free default | API có q dạng mảng; quota/model phụ thuộc instance | AGPL engine không chứng minh hosted miễn phí. Hosted **NOT_ELIGIBLE** cho stage này |
| [Mirrors chính thức](https://docs.libretranslate.com/community/mirrors/): translate.cutie.dating, translate.fedilab.app | Danh sách ghi không cần key; zh/vi thực tế chưa xác minh | Chưa xác minh quota/điều kiện riêng | Qua web reader lần lượt timeout/403; không thử né hoặc gửi OCR | Chưa xác minh retention/privacy/SLA từng mirror: **UNVERIFIED**, không chọn |
| [DeepL developer](https://www.deepl.com/en/developers), [limits](https://developers.deepl.com/docs/resources/usage-limits), [languages](https://developers.deepl.com/docs/getting-started/supported-languages) | API key/account; cặp zh/vi và engine non-LLM phù hợp chưa xác minh bằng account | Trang hiện quảng bá free/no credit card; hạn mức/account thực tế chưa xác minh, không đăng ký | Docs body128KiB; batch text có API; RPM gói cụ thể chưa xác minh | Không suy chính sách retention cho gói chưa chọn. **UNVERIFIED**, không tích hợp, không nói bắt buộc credit card dựa tài liệu cũ |
| [Google pricing](https://cloud.google.com/products/translate/pricing), [setup](https://docs.cloud.google.com/translate/docs/setup) | Cloud credentials/project, NMT có API; không thử cặp live | 500.000 ký tự/tháng dạng credit10USD; setup bắt buộc enable billing, có phí vượt mức | Có batch; chưa nghiên cứu limit từng method vì đã loại ở cổng billing | Không gửi OCR/đăng ký. **NOT_ELIGIBLE**, web Translate miễn phí không phải Cloud API |
| [Azure pricing](https://azure.microsoft.com/en-us/pricing/details/translator/), [limits](https://learn.microsoft.com/en-us/azure/ai-services/translator/service-limits) | Subscription/key/region; route live chưa thử | F0 công bố2triệu ký tự/tháng; chưa xác minh signup không billing/card trong môi trường người dùng | Có batch; giới hạn từng method/gói phải xác minh khi chọn | Không tạo resource/account; retention và điều kiện account chưa xác minh. **UNVERIFIED**, không tích hợp |

Không ghi quota không biết thành unlimited. Không dò endpoint, Google web,
reverse-engineered API hoặc dịch vụ LLM. Research chỉ truy cập tài liệu công khai.

## 3. Kiến trúc triển khai

- Tái sử dụng TranslationProvider, TranslationService và ProcessingManager; không
  tạo OCR/MT pipeline thứ hai. Online Free dùng MyMemory chính thức hiện có đã
  nâng cấp transport; LibreTranslate custom/self-host cũ giữ tương thích nhưng
  không được chứng nhận là dịch vụ hosted miễn phí mới của Stage3A.
- GUI chung chọn Offline hoặc Online Free ở cả3tab. Offline vẫn mặc định như
  trước, provider thực tế hiển thị riêng; legacy Online config được hiển thị thành
  Online Free khi mở GUI. Auto Fallback cũ vẫn cần opt-in riêng, không đổi quy tắc.
  Source job cũ vẫn ép Offline; **Online Free mới phải được chọn rõ** mới cho gửi
  text. LocalComicJob luôn tắt automatic fallback. Gemini chưa triển khai/không có nút giả.
- Chỉ gửi q, langpair và mt=1; ảnh/đường dẫn/SQLite không gửi. Privacy note thông
  báo lưu/chia sẻ text. Không lưu key/credential hoặc trả exception URL chứa q.
- HTTPS/TLS verify, fixed MyMemory URL, không follow redirect, timeout8/25s,
  stream JSON tối đa1MB; kiểm MIME/shape/target. Retry tối đa3 với backoff1/2s
  cho lỗi mạng/5xx, có checkpoint cancel/pause. Không retry 401/403/429.
- Mỗi OCR region dịch riêng; split UTF8 tối đa450byte/chunk, tách newline/paragraph,
  không ghép các bong bóng. Chunks kết hợp rồi qua guard nguyên trạng; không tự
  sửa số hoặc đưa QA date handler vào production. Chunking có thể giảm ngữ cảnh.
- Structured codes: QUOTA_EXCEEDED, RATE_LIMITED, AUTH_REQUIRED, NETWORK_ERROR,
  TIMEOUT, PROVIDER_UNAVAILABLE, INVALID_RESPONSE; numeric rejection vẫn
  NUMERIC_MISMATCH (thuộc TRANSLATION_VALIDATION_ERROR); cancel dùng CancelledError
  và state cancelled. Không đổi mọi429 thành quota ngày hoặc đoán reset.
- Identity MyMemory mới `mymemory-official-anonymous-v2:mt1:utf8-480:literal-numbers-v2-signed`
  tách cache cũ/Argos. Source/target lang/text/context/glossary và version unsigned3/
  signed4 giữ trong key. Không đổi cache version/guard/default Offline. API không
  công bố weights/model version nên không bịa model ID hoặc hứa output ổn định.
  Numeric/glossary reject không được ghi cache hợp lệ.

## 4. Quota, checkpoint và resume

Provider latch sau quota/rate/auth, không dispatch thêm. Manager ghi diagnostic
và checkpoint paused_provider, giữ pending_paths từ trang đang làm; không xóa
chữ, không tạo fallback mới hoặc đếm quota như một trang dịch hoàn tất. Những
fallback đã tồn tại giữ nguyên. Worker kết thúc an toàn để GUI tiếp tục tương tác.

Thông báo đóng bằng × chỉ ẩn notice. Nó không đổi provider hoặc tiếp tục job.
Không biết reset thì ghi “Chưa xác định thời điểm khôi phục”; Retry-After nếu có
chỉ là thời gian đợi do provider trả về, không phải số quota còn lại.

Trong phiên GUI hiện tại: người dùng có thể chọn lại phương thức rồi Tiếp tục.
Folder chỉ truyền pending_paths, giữ output/receipt đã hoàn tất. Recipe/provider
đổi tạo job identity mới cho phần còn lại, không gán receipt cũ sang provider mới.
Chương ảnh/URL resume current chapter từ ChapterCache, chỉ trang needs_retry/
chưa có output; xác minh SHA output thành công trước skip, giữ receipt mỗi trang.
Manifest có thể chứa kết quả từ nhiều recipe được người dùng chọn rõ, không
gộp chúng thành một provider. Không gọi CDN khi retry_only.

**Giới hạn:** URL nhiều chương chỉ resume chương đang dở; chương chưa bắt đầu cần
chọn/bắt đầu sau, không tự tải tiếp. Pending-path UI đổi provider được kiểm thử
trong cùng phiên; chưa triển khai khôi phục danh sách pending đó vào GUI sau khi
đóng app. Sau restart, checkpoint còn nguyên; cùng recipe có thể bỏ qua thành
công theo hash, nhưng **không đổi provider rồi chạy lại cả folder** nếu muốn chỉ
tiếp tục các trang chưa xong. Resume đổi provider qua restart là Stage3C cần bổ
sung; không sửa checkpoint bằng tay hoặc nhận là đã PASS.

## 5. Local/mock và regression mới

20 tests mới trong tests/test_online_free.py: official request, UTF8/chunking,
200, malformed/missing/oversized JSON, MIME, redirect, timeout/DNS/5xx/backoff,
429≠quota ngày, quotaFinished, auth, latch, cancel trước/sau response, cache
isolation, numeric reject+raw target, Offline không construct Online, recipe mới
chỉ pending, giữ receipt/output và chapter retry cache không network.

Test cũ test_source_tabs đổi một assertion visibility: method selector nay phải
hiện trên tab ảnh đơn theo yêu cầu mới; không bỏ test lỗi hoặc đổi skip thành pass.

**Pytest281 PASS/10 SKIPPED/0 FAIL; unittest281 PASS/10 SKIPPED/0 FAIL.**
291 tests tổng. Skip giữ nguyên10: model/lang thiếu, online/live opt-in, M2M100
chưa cài. Một số reason lịch sử có chữ sandbox: không dùng chúng để kết luận
phiên hiện tại chặn mạng. Test thật có OCR zh và dịch en/zh Offline, native
interop/cancel/reuse; full runners chặn socket/DNS và chuyển test DB/evidence
sang QA, không dùng DB production.

Windows nguồn ảnh/thư mục + Offline E2E thật:
`output/source-tabs-validation/20261108T015631Z-1820d8/report.json`: PASS.
GUI quota riêng: `windows-online-quota-location.json` dẫn đến report/screenshot
trong output/online-free-validation: Windows Qt, **real PaddleOCR**, HTTP mock2
request, người dùng đổi Offline, **real Argos** chỉ trang còn lại;279heartbeats,
0socket/DNS, output trướcquota giữ hash, settings không đổi, × không tự resume.
Đây là MOCKED_HTTP_PASS + LOCAL_OFFLINE_E2E_PASS, không phải live HTTP E2E ảnh.

Các thử QA GUI đầu có lỗi đường dẫn logs và các vòng pump Python chậm khi import
Paddle; không gọi PASS. Chỉ dừng tiến trình QA sở hữu, giữ artifacts/trace. Dùng
QEventLoop theo script hiện có thì pass~8s; không sửa native guard. Xem
qa-attempts.json. Pytest-final là revision trước phần diagnostic cuối; dùng
pytest-verified.xml/unittest-verified.json cho kết quả chính thức.

## 6. Real Online QA được duyệt

Người dùng đã chấp thuận MyMemory, tối đa6 mẫu development/1.000 ký tự, tối đa8
request kể cả retry; không ảnh/holdout/toàn bộ dataset/chương. Thực tế **6 request,
37 ký tự nguồn,0retry;6 mẫu có phản hồi;5 qua guard,1 NUMERIC_MISMATCH**. Mỗi phản
hồi được parse qua request path yêu cầu HTTP200; không log URL query đầy đủ.
Độ trễ trung bình~1,211s/mẫu trong lượt nhỏ (gồm giãn request, không phải SLA).
Quota/rate/auth thật chưa gặp; các nhánh đó chỉ mock. Không biết quota còn lại/reset.

| Nguồn development | MyMemory thực tế | So với Argos đã đo / guard |
|---|---|---|
| 5月20日—5月30日 | Ngày 20 tháng 5 - ngày 30 tháng 5 | Argos:20 giờ30 tháng5. Online có cách diễn đạt ngày nhưng literal token5,20,5,30 đổi20,5,30,5 → REJECT, không cache valid |
| 活动时间 | Thời gian event: | Argos Name; quan sát khác biệt, còn lẫn tiếng Anh |
| 活动时间和活动内容 | Thời gian hoạt động và nội dung hoạt động | Argos Name; nội dung quan sát cụ thể hơn, chưa có human reference |
| 回去！ | trở về | So với Argos Quay lại!; không gán điểm ngữ nghĩa |
| 父亲大人， | Thưa Cha, | Cách xưng hô cần người rà soát |
| 上线大礼包 | Gói khởi chạy | Cụm thông báo thiếu ngữ cảnh; không tự nhận tốt hơn |

0 independently verified reference, không accuracy/BLEU/COMET hoặc tuyên bố Online
đúng hơn Argos. Mẫu ít, chọn từ dev đã biết, không benchmark holdout độc lập.
Không yêu cầu dịch lại trang111 và không sửa output user. API/test HTTP thật PASS
không đồng nghĩa cả6 dịch đúng hoặc full comic Online E2E PASS.

## 7. Bảo toàn, evidence và source

Evidence: `logs/stage3a-online-free-20261108T014648Z/`: protected-before.json,
chapter-manifest-before.json, git-before.json, live-online/approved-plan.json,
results.json và online-qa.sqlite3 riêng; regression-results.json,
pytest-verified.xml/txt, unittest-verified.json/txt, preservation.json, qa-attempts.json,
windows-online-quota-location.json, git-final.json và summary.json.

595/595 hash bảo vệ không đổi:120 source/cache,120 output (119normal+fallback111),
DB/cache/manifest/checkpoint,models,config,BAT/spec,bốnEXE. 120 bitmap output và
120 source được mở/xác minh lại riêng, không thay nội dung. Không tải ảnh/model,
không cài package, không nâng môi trường, không chạy chương user/retry111.

Sửa production: providers/online.py, core/pipeline.py (chỉ routing/operational
pause/diagnostic, không sửa numeric comparison), sources/service.py,
ui/main_window.py, ui/comic_sources.py, ui/settings_dialog.py.
Thêm ui/provider_notice.py, tests/test_online_free.py, qa/validate_online_free.py,
qa/validate_online_free_gui.py; sửa visibility test_source_tabs.py.
Docs: báo cáo này, PROJECT_STATUS, README, USER_GUIDE, TROUBLESHOOTING và adapter guide.
Không thêm dependency/config field bắt buộc, không đổi .gitignore/AGENTS ở Stage3A.

## 8. Giới hạn và Stage3B

- MyMemory có quota nhỏ, retention/privacy không phù hợp nội dung bí mật; mặc định
  vẫn Offline. Không có remaining quota đáng tin, không tự tăng quota/trả phí.
- Bộ6chưa có reference; date hợp cách biểu diễn vẫn reject. Không promotion
  date handler hoặc phục hồi111 trong Stage3A.
- Full image+live API E2E/wholechapter Online, quota thật và cross-restart
  provider-switch resume: **NOT_TESTED / chưa triển khai đầy đủ như mục4**.
- Gemini CLI Stage3B chưa làm; có thể thêm provider độc lập theo interface sau
  yêu cầu mới, không sửa numeric guard hoặc bỏ chính sách explicit selection.
- Source mới chưa có trong bốn EXE cũ; **không build**. Chạy run_source.bat để
  thử source, không gọi EXE cũ là đã chứa Online Free mới.

## Git & Fork Handoff

Root D:/TransTool, branch main; baseline sạch, không staged/xung đột. .gitignore
giữ nguyên. git-final.json lưu status/diff/stat/check-ignore và danh sách file.
Status cuối:12 tracked modified +5 untracked files (17 file review),0 staged;
30 kiểm tra ignore/visibility đạt. Không có thay đổi có sẵn trước Stage3A.
Source/test/qa/docs vẫn hiện; runtime/models/logs/output/dist bị ignore. Không
có runtime đã track cần untrack; không thay HEAD/index. git diff --check PASS.

Nên review/commit:6 production files nêu trên, ui/provider_notice.py,20test mới,
visibility assertion,2QA scripts và6tài liệu. Không commit weights/venv/cache/
DB/ảnh/logs/evidence/runtime/EXE/secret. Không phát hiện file review >2MiB; scan
diff và file mới không thấy key thật. Fixtures cũ không sửa trong Stage3A.
Danh sách chính xác trong git-final.json; Fork Local Changes → review từng
file/hunk → tự stage → xem staged diff → tự commit. Không stage toàn bộ runtime.

Message đề xuất: `stage(3a): add official MyMemory online free translation and quota pause`.
**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT**.

**STAGE_3A_COMPLETED_WITH_WARNINGS**
