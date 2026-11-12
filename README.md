# IMAGE TRANSLATOR VN

## GroqCloud API — 12/11/2026

Vào **Cài đặt → AI dịch thuật → GroqCloud**, chọn Qwen 3.8 27B (mặc định),
GPT-OSS 120B hoặc GPT-OSS 20B, Lưu rồi dùng **AI — Batch/Toàn chương**.
Key đọc từ `GROQ_API_KEY`, không lưu vào config. Không tự đổi provider/model.

**ĐẠT kiểm thử cơ bản:** 201 test liên quan PASS; API Qwen thật và OCR/dịch/
render một ảnh từ EXE PASS. Đã dùng 3/3 request (lượt đầu 429, hai lượt sau
200). Whole Chapter và hai GPT-OSS kiểm bằng fixture, không benchmark/live thêm.
EXE mới đã chạy GUI, Save/Cancel, mở lại và pipeline HTTP fixture sau sửa nhãn;
pipeline live đã PASS trên bản trước sửa nhãn với cùng bytecode provider/OCR/render:
`dist/ImageTranslatorVN-20261111T230840399194Z/ImageTranslatorVN-20261111T230840399194Z.exe`.
Giữ `_internal`. [Hướng dẫn](docs/GROQCLOUD_SETUP.md) · [Báo cáo](docs/GROQCLOUD_REPORT.md).

## Sửa Sonnet tự trở về Gemini khi Bắt đầu — 12/11/2026

**Bắt đầu dịch** dùng model đã Lưu trong Cài đặt và tạo journal mới; **Tiếp
tục/Thử lại ảnh lỗi** giữ model của run cũ mà không đổi preference cho lượt mới.
Đã kiểm tra source và EXE bằng thao tác Settings/Start/Continue thật, worker
fixture không gọi AGY. Bản mới đã build/chạy/mở lại:
`dist/ImageTranslatorVN-20261111T192625787431Z/ImageTranslatorVN-20261111T192625787431Z.exe`.
Giữ `_internal`, đóng bản EXE cũ trước khi mở bản này.
[Nguyên nhân, kiểm thử và ảnh bằng chứng](docs/SONNET_START_FIX.md).

## Renderer offline: box OCR giao nhẹ ở góc — 12/11/2026

Source đã sửa LAYOUT_UNFIT do gộp vùng thưa từ các box giao nhẹ ở góc.
Chỉ thu hẹp vùng đặt chữ trong giới hạn an toàn, giữ đủ nội dung và kiểm tra
va chạm. Không thay engine OCR/mask; mask rỗng vẫn báo lỗi. 174 test liên
quan PASS; OCR + Argos + render offline thật PASS trên fixture trung tính.
Chưa build lại EXE. [Chi tiết, ảnh minh họa và giới hạn](docs/OFFLINE_LAYOUT_FIX.md).

## Chọn model AI trong Cài đặt — 11/11/2026

Vào **Cài đặt → AI dịch thuật (AGY)** để chọn Gemini Flash Low/Medium/High,
Claude Sonnet 4.6, Claude Opus 4.6 Thinking hoặc GPT-OSS 120B Medium. Lưu mới
áp dụng; Hủy giữ nguyên. Màn hình chính chỉ có trạng thái ngắn. Run tiếp tục
giữ model/effort đã lưu của run; Settings mới áp dụng cho run mới.

EXE mới đã chạy GUI, lưu/mở lại, DPI 100/125/150% và Opus Whole Chapter thật:
`dist/ImageTranslatorVN-20261111T165120860976Z/ImageTranslatorVN-20261111T165120860976Z.exe`.
Giữ `_internal`. Gemini Low, Sonnet và Opus live PASS; **GPT-OSS live FAIL
INVALID_RESPONSE/AGENT_TURNS**, nên **CHƯA ĐẠT toàn bộ model**. Đã dùng đủ
4/4 lượt AGY CLI, không tự retry/fallback. Regression liên quan 211 PASS;
smoke model/ToonCN 40 PASS (hai bộ trùng chín test), không phải full suite.

[Hướng dẫn, model ID/effort](docs/AI_MODEL_SETTINGS.md) ·
[Báo cáo, ảnh GUI và giới hạn nghiệm thu](docs/AI_MODEL_SETTINGS_REPORT.md).

## AGY: lỗi kết nối/bộ lọc và model Low — 11/11/2026

AGY báo rõ NETWORK_ERROR khi stream HTTP/2 bị máy chủ đóng; RESPONSE_BLOCKED
khi nhà cung cấp chặn phản hồi bằng bộ lọc nội dung, kể cả CLI exit 0. Không
tự retry hoặc nhận terminal ERROR làm thành công. Model mặc định Low và cửa
sổ cũ không ghi đè lựa chọn model mới trên đĩa khi lưu/đóng.

EXE mới đã build, chạy GUI và offline E2E:
`dist/ImageTranslatorVN-20261111T144631162670Z/ImageTranslatorVN-20261111T144631162670Z.exe`.
Giữ `_internal`, đóng bản EXE cũ. Source AGY Low thật 3 fixture PASS; regression
liên quan 201 PASS. Batch trang 112 vẫn bị provider chặn, không tuyên bố đã gỡ
bộ lọc. [Báo cáo và bằng chứng](docs/AGY_RECURRING_20261111.md).

## Bản dịch online và Flash Low — 11/11/2026

Bản dịch AGY/AI/API và mọi provider online được nhận mà không kiểm tra lại
nội dung số hoặc marker thuật ngữ; offline vẫn giữ validator. Lỗi giao thức,
provider, mask/xóa chữ và layout vẫn được báo đúng. Cấu hình hiện tại dùng
`gemini-3.8-flash-low`, effort low; mở lại app để nạp nếu app đang chạy.

EXE mới đã build/chạy GUI và contract smoke:
`dist/ImageTranslatorVN-20261110T191355235181Z/ImageTranslatorVN-20261110T191355235181Z.exe`.
Giữ `_internal` bên cạnh EXE. 283 test liên quan PASS; không gọi dịch thêm.
[Chi tiết, ảnh 0020 đã khôi phục và hai lỗi mask còn lại](docs/ONLINE_TRANSLATION_TRUST.md).

## Giao diện mới, cache an toàn và dịch lại từ đầu — 10/11/2026

**ĐẠT:** nút **Dịch lại từ đầu** trực tiếp trong tab Thư mục ảnh tạo run/DB/
output riêng, OCR và dịch mới, không dùng checkpoint/cache cũ. Có xác nhận,
mở/quản lý cache, backup trước khi dọn và khôi phục đúng DB sau mở lại app.
Menu Thêm và popup đã dùng dark theme thống nhất; DPI 100/125/150% PASS.

EXE đã chạy kiểm thử thực tế:
`dist/ImageTranslatorVN-20261110T152147487436Z/ImageTranslatorVN-20261110T152147487436Z.exe`.
Giữ `_internal` và models tại project/models. Full regression 607 PASS,
0 FAIL, 12 SKIP. AGY thật 3 request hoàn tất sau khi được cấp thêm 1 lượt;
gate GUI sớm của QA được sửa và kiểm lại bằng cache, không gọi AGY thêm.
EXE cuối kiểm Offline thật, cache/fresh/resume và cache AGY đúng trạng thái idle.
Không cần di chuyển SQLite DB thủ công. Dọn DB chung/Whole/ToonCN chưa hỗ trợ.

[Cách sử dụng](docs/CACHE_UI_GUIDE.md) · [Ảnh và báo cáo nghiệm thu](docs/CACHE_UI_REPORT.md).
Các mục tiếp theo giữ lịch sử các bản trước.

## Bản sửa khả năng đọc đã có EXE kiểm thử — 10/11/2026

**ĐẠT** 0002/0003/0004 thật: xóa nét Trung gây nhiễu, Việt không chồng/cắt,
giữ đủ target. Source và frozen EXE đã chạy AGY Batch/Whole thật (4/6 request),
GUI Windows PASS. Regression 582 PASS/0 FAIL/12 SKIP. Nền còn vệt inpaint ở
dải chữ; không yêu cầu phục chế hoàn hảo. Xem [ảnh và báo cáo](docs/READABILITY_ACCEPTANCE_20261110.md).

Mở EXE mới: `dist/ImageTranslatorVN-20261110T115939410209Z/ImageTranslatorVN-20261110T115939410209Z.exe`.
Giữ cả thư mục cùng `_internal`, models ở project/models; font dùng Windows.
Chưa nghiệm thu máy sạch. EXE/output cũ được giữ nguyên và không tự cập nhật;
tạo lượt xử lý mới để dùng bản sửa. Source mở bằng `run_source.bat`.
PROJECT_ROOT suy ra từ workspace/module, không cố định ổ đĩa.

## Lịch sử setup: chạy source, xuất ra thư mục ngoài và build EXE

Project dùng ROOT từ workspace; Python 3.10.9,
`.venv`, dependencies và 5 model Trung giản thể→Việt đã cài. Mở
`run_source.bat`. Đầu ra batch có thể ở thư mục ngoài project, ví dụ
`D:\MangaTranslated` hoặc ổ đĩa khác; vẫn cần tách khỏi nguồn và vùng ứng dụng.
Chưa chạy test/GUI/E2E theo yêu cầu người dùng; đã build onedir thành công tại
`dist\ImageTranslatorVN\ImageTranslatorVN.exe`, chưa mở binary để kiểm chứng.
Xem [hướng dẫn xuất và build](docs/EXPORT_AND_BUILD.md) để biết lệnh build,
đường dẫn EXE. `build.bat` mặc định đóng gói không chạy test; dùng
`build.bat --validated` nếu cần gate GUI/E2E và pytest. Workspace Whole Chapter thử nghiệm vẫn được
quản lý riêng trong `output/stage3g-*`, không đổi bởi bản sửa batch này.

## ToonCN qua Chrome đã cấp quyền

Trong Link truyện online, bật **ToonCN**, dán URL truyện/chương rồi phân tích
và tải/dịch theo luồng hiện có. Extension0.3 nhận yêu cầu tự động, không cần
Gửi trang từng lần. Live QA có32chương,316URLảnh và3ảnh mẫu hợp lệ; chưa tải
đủ chương hoặc chạy dịch ToonCN thật. Xem [cách dùng/cập nhật extension](extensions/tooncn_bridge/README.md).

## Stage3H — chọn Whole Chapter tại cửa sổ chính (chưa kiểm thử)

Mở bản source bằng `run_source.bat`. Chọn **AI Gemini AGY — Toàn chương
(1 lần)** trong ô Dịch, chọn một chương/ảnh hoặc thư mục theo luồng hiện có,
rồi bấm **Chuẩn bị toàn chương**. Chương/ảnh được đưa sang cửa sổ chuẩn bị,
không cần tìm lại thư mục hay chọn provider lần nữa. Xem số trang/vùng/ký tự
rồi bấm **Xác nhận dịch bằng AGY…** nếu muốn gửi. Chọn provider/OCR/tiếp tục
dữ liệu đã lưu không tự gửi AGY. Output Whole riêng, không ghi đè output Batch.
Menu thủ công cũ nằm trong **Công cụ → Whole Chapter Translation (nâng cao)…**.

**STAGE_3H_IMPLEMENTED_NOT_TESTED**: chỉ triển khai/kiểm tra tĩnh, không chạy
GUI/test/dịch thật. Timeout trang60 đã khớp diagnostic Batch90s; chưa chứng minh
nguyên nhân AGY chưa kết thúc, không kết luận quota. Xem [báo cáo Stage3H](docs/STAGE3H_MAIN_UI_AND_TIMEOUT_FORENSIC.md).

## Stage3G — AGY Whole Chapter và batch24 (chưa kiểm thử)

Trong menu Whole Chapter Translation, chọn **AGY CLI**, OCR/tạo manifest trước,
sau đó kiểm tra số liệu và bấm **Xác nhận dịch bằng AGY…**. Whole gửi toàn chương
một lần, không chia batch/chờ5–10giây; Argos vẫn có lựa chọn riêng. Batch AGY
thông thường tối đa24trang/60vùng/3.000ký tự, chờ5–10giây giữa các lần dịch thật.
Gemini API không đổi. Không tự retry/fallback hoặc gửi lại khi mở journal.
**STAGE_3G_IMPLEMENTED_NOT_TESTED**: người dùng tự mở source để nghiệm thu;
không có test/AGY/API thật hoặc EXE mới trong Stage này. Xem
[báo cáo và hướng dẫn](docs/STAGE3G_AGY_WHOLE_CHAPTER_IMPLEMENTATION.md).

## Stage3F — Whole Chapter Translation thử nghiệm, chỉ offline

Mở **Whole Chapter Translation (thử nghiệm)…** trên thanh menu của bản source.
Chọn thư mục ảnh chương đã có; OCR toàn chương và lưu manifest trước khi dịch.
Tích cho phép Argos rồi chủ động chạy. Output/cache/journal riêng trong
`output/stage3f-…`; không dùng database hoặc output của chương production.
Mở journal QA không tự dịch/resume. Batch mode và bốn provider hiện có giữ nguyên.
Whole-chapter hiện chỉ nối Argos offline; phản hồi AGY toàn chương mới được
kiểm tra bằng mock, không có lệnh gửi AGY/API thật ở chế độ này.
Xem [hướng dẫn](docs/USER_GUIDE.md) và [báo cáo Stage3F](docs/STAGE3F_WHOLE_CHAPTER_OFFLINE_REPORT.md).

## Stage3D.2 — phân tích chương trực tiếp và diagnostic API

Tab Link truyện theo luồng: **URL → Phân tích link → chọn chương → Phân tích
chương đã chọn → Tải và dịch**. Nút phân tích chương luôn ở trên bảng, không
cần mở cache/nâng cao. Giới hạn phân tích cũ1–10chương/lượt được giải thích ngay
ở nút. Phân tích chỉ discovery, không tải ảnh/dịch; chỉ Tải và dịch bắt đầu job.

Thông báo lỗi mặc định gọn, có Chi tiết mở rộng. Lỗi API phân biệt chưa attempt,
đã attempt, đã nhận response và chưa biết. `READY_UNVERIFIED` chỉ là cấu hình
cục bộ, không chứng minh generateContent được phép. HTTP403 lịch sử chưa có đủ
metadata để xác nhận độc lập nguyên nhân quyền; không yêu cầu bật billing/đổi
key/model. Chưa gọi API thật trong Stage này, không build EXE. Xem
[báo cáo Stage3D.2](docs/STAGE3D2_ACCESS_DIAGNOSTICS_CHAPTER_UI_REPORT.md).

## Stage3D.1 — thiết lập Gemini API và giao diện gọn

Thanh cấu hình chung còn OCR, phương thức dịch, model/provider và Cài đặt.
Provider phụ/Auto Fallback consent ở Cài đặt; không tự đổi lựa chọn đã lưu.
Bảng chương mặc định4cột; bật Tùy chọn nguồn/cache để xem thêm. Thư mục xuất
thu gọn, các thao tác ít dùng ở menu Thêm. Ở cửa sổ nhỏ/high DPI, cuộn để xem
đủ nội dung; các nút tải/dịch nằm trước bảng chương.

`FREE_TIER_UNCONFIRMED` là thiếu xác nhận cấu hình, không phải Gemini đã dịch
thất bại. Bấm **Mở Cài đặt Gemini API**, tự kiểm tra project ở Google AI Studio,
chỉ xác nhận Free tier/không billing khi đúng. Sau đó chủ động Bắt đầu/Tiếp tục
từ cache; không tự gửi request hoặc tiếp tục khi đóng thông báo/đổi cài đặt.
Đủ cấu hình chỉ là `READY_UNVERIFIED`, chưa xác minh key/model/quota trên mạng.
Không build EXE; xem [báo cáo Stage3D.1](docs/STAGE3D1_API_PREFLIGHT_COMPACT_UI_REPORT.md).

## Stage3D — Gemini API chính thức (bản source)

Bổ sung **AI Gemini API**, giữ nguyên Offline Argos (mặc định), Online Free
MyMemory và AI Gemini AGY. Provider mới dùng REST `generateContent`, không phụ
thuộc AGY/NDJSON, không cần cài SDK. Chỉ gửi OCR/context khi chủ động chạy.

Đặt `GEMINI_API_KEY` trong môi trường Windows rồi mở lại ứng dụng; không lưu key
trong config/Git. Trong Cài đặt, chỉ xác nhận Free tier sau khi kiểm tra project
của key ở AI Studio **không gắn billing**. Chọn AI Gemini API rồi Bắt đầu/Tiếp tục.
Model cố định `gemini-2.5-flash`; Google đang giới hạn truy cập 2.5 theo dự án.
Không tự đổi model/provider khi bị từ chối. Checkbox là xác nhận của người dùng,
không phải xác minh billing từ Google; key dự án Paid có thể phát sinh phí.

**Chưa gọi Gemini API thật trong Stage3D.** Chỉ có kiểm thử mock/local; quyền
truy cập model, quota dự án và chất lượng dịch thật còn chờ QA được duyệt riêng.
Không build EXE. Xem [báo cáo Stage3D](docs/STAGE3D_GEMINI_API_REPORT.md) và
[hướng dẫn](docs/USER_GUIDE.md). Các mục dưới giữ lịch sử Stage trước.

## Stage3B — AI Gemini AGY trong bản source

Bản source có lựa chọn **AI Gemini AGY** và cài đặt executable/model/giới hạn.
AGY1.5.3 headless chính thức đã xác minh; lượt QA đầu bị INVALID_RESPONSE, lượt
bổ sung được duyệt riêng đã **OCR→AGY→ảnh PASS thật trên fixture tổng hợp**.
Chọn AI Gemini AGY rồi Bắt đầu để dùng phiên account đã có, không API key riêng
hoặc tự dùng thêm credits. Offline/Online Free vẫn như Stage3A; Offline default.
Chưa nghiệmthu wholechapter/truyện phức tạp; không có EXE mới.
Xem [báo cáo Stage3B](docs/STAGE3B_AGY_TRANSLATION_REPORT.md) để tiếp tục đúng
phạm vi QA được duyệt; không tự cài/đăng nhập lại hay đổi sang Gemini API.

## Stage3A — Online Free trong bản source

Chạy `run_source.bat`, chọn **Online Free** và **MyMemory** tại cửa sổ chính
(dùng chung3tab). Chỉ text OCR gửi tới API, không gửi ảnh. API ẩn danh miễn phí
5.000ký tự/ngày, có retention/chia sẻ với đối tácMT; không dùng cho dữ liệu bí mật.
Quota/rate/auth dừng an toàn với thông báo ×; không tự đổi provider. Người dùng
có thể đổi phương thức rồi Tiếp tục phần pending trong cùng phiên. Offline vẫn
mặc định; bốnEXE cũ chưa chứa thay đổi này. Không buildEXE hoặc tích hợp Gemini.
Đọc [báo cáo Stage3A](docs/STAGE3A_ONLINE_FREE_TRANSLATION_REPORT.md) và
[hướng dẫn sử dụng](docs/USER_GUIDE.md) về date rejection, resume và giới hạn.

## Hiện tại — Stage3 chỉ nghiên cứu QA, 08/11/2026

Đã đánh giá150 vùng OCR thật, tách99development/51holdout; chưa có reference
dịch được người rà soát độc lập. Không thay engine/default/decode/numeric guard
của ứng dụng. LP1.0 có regression số nên không áp dụng; date handler chỉ ở QA,
chưa nối production. Trang111 vẫn fallback, chương274872 giữ120 output/119
hoàn tất pipeline/1 cần xem lại; không tự retry hoặc ghi đè output.

Chạy app vẫn **run_source.bat**, EXE cũ giữ nguyên. Benchmark/dataset/model
research và mẫu điền tham chiếu tại
[STAGE3_TRANSLATION_QUALITY_REPORT.md](docs/STAGE3_TRANSLATION_QUALITY_REPORT.md).
Thư mục `qa/` là công cụ nghiên cứu, không phải provider mới trong GUI. Chưa tải
model direct, cài dependency, làm Stage4/5 hoặc build EXE. Các mục dưới là lịch sử.

## Hiện tại — Stage 2 phục hồi hai trang, 08/11/2026

Chương274872 hiện có **120/120 output**,119 ảnh hoàn tất pipeline và1 bản gốc
dự phòng cần xem lại. Trang74 bỏ đúng OCR hoa văn theo hash/polygon, không cần
MT, giữ nguyên byte ảnh. Trang111 có raw target mới `20 giờ 30 tháng 5`, sai
nghĩa khoảng ngày; guard vẫn từ chối và giữ `original/0111.jpg`. Không gọi119
ảnh hoàn tất là119 ảnh đều đã dịch văn bản. Không đổi model hoặc nới guard ngày.

Source hỗ trợ override có evidence/version ở `overrides/ocr_regions.json`,
cache OCR gốc giữ nguyên; chi tiết tại [USER_GUIDE.md](docs/USER_GUIDE.md).
Guard dấu số đã siết có version/cache policy riêng. Dùng **run_source.bat**;
không build EXE mới. Stage3 chưa thực hiện. Báo cáo:
[STAGE2_NUMERIC_OCR_RECOVERY_REPORT.md](docs/STAGE2_NUMERIC_OCR_RECOVERY_REPORT.md).
Các mục Stage1/adapter cũ dưới đây giữ lịch sử, không phải trạng thái mới nhất.

## Hiện tại — Stage 1 diagnostic và ảnh dự phòng, 08/11/2026

Source mới có diagnostic theo ảnh, xuất nguyên ảnh gốc khi OCR/MT/render lỗi
và phân biệt `FALLBACK_ORIGINAL` với dịch hoàn chỉnh. Chương đủ file còn fallback
hiển thị `COMPLETED_WITH_WARNINGS`; retry dùng cache chỉ cho trang cần xem lại.
Dùng **run_source.bat**. Chưa build EXE chứa Stage 1, chưa phục hồi hai trang
0074/0111 thật. Xem [USER_GUIDE.md](docs/USER_GUIDE.md) và
[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

Các mục cũ bên dưới giữ lịch sử; trạng thái Kuaikan hiện tại xem
`PROJECT_STATUS.md`: live discovery/downloader mẫu đã kiểm thử theo user policy,
không còn trạng thái chỉ fixture/chưa có downloader như báo cáo đầu tiên.

## Adapter URL chương — thay đổi source sau bản EXE GUI tab

Source hiện nhận cả URL topic và `/webs/comic-next/<chapter_id>`. URL chương có
thể được phân tích độc lập danh sách truyện; image discovery không tải ảnh và
không tự bật quyền download. Có nút **Phân tích ảnh chương** cho chương đã chọn.

Parser HTML/DOM mới hiện chỉ PASS fixture viết tay, **chưa được xác minh với DOM
Kuaikan thật** do giới hạn mạng. Cần DOM lưu từ trình duyệt; không dùng con số
ảnh/chương trong fixture như kết quả website. Chưa build EXE chứa thay đổi này;
dùng run_source.bat để chạy source hiện tại. Chi tiết:
[KUAIKAN_CHAPTER_281106_ANALYSIS.md](docs/KUAIKAN_CHAPTER_281106_ANALYSIS.md).

## Giao diện mới — ba tab nguồn

EXE đã kiểm thử của giao diện này:
`dist/ImageTranslatorVN-20261107T045417969128Z/ImageTranslatorVN-20261107T045417969128Z.exe`.
Mở trực tiếp file đó; run.bat/run_updated.bat được giữ nguyên nên vẫn có thể mở bản cũ.

Mở source bằng **run_source.bat**. Chọn trực tiếp **Ảnh đơn / Thư mục ảnh / Link
truyện online** trên cửa sổ chính; không cần mở cửa sổ nguồn lớn. Tab ảnh đơn chọn
file rồi Bắt đầu dịch. Tab thư mục giữ các tùy chọn/quy trình cũ. Tab URL có phân
tích, thông tin truyện, chọn chương, retry danh sách, điều kiện tải theo chương.
Các lỗi kết nối/phân tích được báo riêng, metadata giữ khi bước chương lỗi.

Kuaikan chưa lấy được danh sách chương đủ kiểm chứng; điều kiện tải UNKNOWN và
chưa có downloader. Vẫn nhập/phân tích URL được; dùng tab ảnh/thư mục cho ảnh đã
lưu hợp lệ. Không mặc định public = được tải tự động.

Xem **docs/GUI_URL_FLOW_REPORT.md** và **docs/WEBSITE_ADAPTER_AI_GUIDE.md** cho
kiến trúc/trạng thái/test mới. Phần mô tả nút mở dialog bên dưới là lịch sử lượt đầu.

## Nguồn ảnh và chương truyện — 07/11/2026

Source Python bổ sung nút **Ảnh đơn / chương ảnh / link truyện online**. Mở source
mới bằng **`run_source.bat`** (dùng `.venv` đã cài), hoặc
`.venv\Scripts\python.exe main.py`. Các EXE và launcher cũ được giữ nguyên, chưa có
tính năng này; không dùng EXE cũ để đánh giá giao diện URL mới.

Trong cửa sổ nguồn, chọn ảnh đơn hoặc thư mục. Nếu thư mục gốc có ảnh, đó là một
chương; nếu không, mỗi thư mục con chứa ảnh là một chương. Chọn nguồn → đọc danh
sách → tự chọn chương → chọn nơi xuất → **Dịch ảnh đã có**. Luồng chương dùng
Offline và cấu hình OCR/provider/font của cửa sổ chính; nguồn không bị sửa. Có
pause/resume/cancel/retry, manifest, cache kiểm tra hash và xuất theo chương.
Để tiếp tục sau khi đóng ứng dụng, chọn lại cùng nguồn/cấu hình/output rồi xử lý;
checkpoint hợp lệ sẽ bỏ qua ảnh thành công. Cache mặc định được giữ lại.

Kuaikan hiện **EXPERIMENTAL metadata / CHAPTERS UNVERIFIED / DOWNLOAD ACCESS
RESTRICTED**: chưa xác minh quyền tải tự động và cấu trúc chương. Nút tải bị vô
hiệu hóa. Phân tích link không tải ảnh; nếu mạng/HTML không phù hợp sẽ báo lỗi rõ.
Sử dụng **Nhập chương từ ảnh đã lưu hợp lệ** để tiếp tục với ảnh người dùng cung cấp.
Không coi việc hiển thị ảnh trên website là quyền tải tự động.

Chi tiết: [phân tích Kuaikan](docs/KUAIKANMANHUA_ANALYSIS_REPORT.md),
[kiểm thử tích hợp](docs/ONLINE_COMIC_TEST_REPORT.md),
[hướng dẫn AI thêm website](docs/WEBSITE_ADAPTER_AI_GUIDE.md).

Kho Git chỉ lưu mã nguồn, kiểm thử, script chạy/build, cấu hình mẫu và báo cáo: `https://github.com/thangtaide/IMAGE-TRANSLATOR-VN`. Không đưa `.venv`, model AI, EXE/build, backup, cache, log/evidence, ảnh `ImgTest` hoặc cấu hình cá nhân lên Git. Các đường dẫn artifact trong báo cáo là bằng chứng cục bộ của máy đã kiểm thử, không phải file kèm repository. Khi clone sang máy khác cần cài dependencies/model và build riêng; `run_updated.bat` dành cho binary đã xác minh tại máy hiện tại, `run.bat` hỗ trợ chạy mã Python khi chưa có EXE.

Ứng dụng Windows OCR, dịch sang tiếng Việt, xóa chữ gốc và chèn bản dịch theo vùng OCR. Mã nguồn nằm trực tiếp tại **D:\TransTool**.

**Đã khôi phục và xác minh lại sau mất điện 06/11/2026:** nguồn/EXE cũ khớp fingerprint/hash, 5 model hợp lệ, Imports 16/16, dependencies 18/18, Ready: True. Sau cải tiến: unittest/pytest **76 PASS, 7 SKIPPED**, GUI và E2E Offline không mock PASS. Corpus `ImgTest` **61/61 ảnh xử lý, 0 lỗi, nguồn không đổi**, có 75 vùng chữ dịch thật; ảnh không có chữ hoặc chỉ có số/ký hiệu được bảo toàn. **Chưa nghiệm thu chất lượng:** Argos còn sai nghĩa/tên riêng và mask truyện có thể còn nét; M2M100 đã có adapter nhưng thiếu trọng số nên chưa suy luận thật. Xem [RECOVERY_REPORT.md](RECOVERY_REPORT.md), [REAL_IMAGE_REPORT.md](REAL_IMAGE_REPORT.md), [PROJECT_STATUS.md](PROJECT_STATUS.md), [M2M100_SETUP.md](M2M100_SETUP.md).

Chạy ngay bằng **`run.bat`** hoặc nhấp đúp **`dist\ImageTranslatorVN\ImageTranslatorVN.exe`**. Giữ toàn bộ thư mục onedir và `models` tại vị trí hiện có. Không cần cài lại môi trường hoặc tải lại năm model đã hợp lệ. GUI dùng font Windows đã cài tại chỗ, không sao chép font Windows để phân phối. Desktop vật lý người dùng/máy Windows sạch chưa kiểm thử.

**Mở bản cải tiến bằng `run_updated.bat`**. Bản này đã được kiểm thử GUI, các nút điều khiển và E2E trên ảnh truyện thật. `run.bat` vẫn mở bản MVP cũ, được bảo vệ nguyên vẹn. Build mới nằm cạnh bản cũ với timestamp `20261106T101857052219Z`; xem [BUILD_REPORT.md](BUILD_REPORT.md). Không sao chép riêng một file EXE ra khỏi thư mục onedir. Provider M2M100 cần model cài riêng; chọn khi chưa có model sẽ báo thiếu và không tự tải hoặc chuyển Online.

Các đoạn dưới đây về lỗi proxy/dependencies/build ban đầu là **lịch sử**, không phải hiện trạng. Các lệnh cài đặt chỉ dùng khi thiết lập máy mới; không nâng setuptools quá 80.9.0 trong môi trường CT2 4.6 hiện tại.

Lượt tiếp tục đã xác định proxy `127.0.0.1:9` và cờ tắt mạng do sandbox Codex; proxy Windows tắt, WinHTTP Direct, DNS hoạt động. Người dùng đã đồng ý cấp mạng nhưng profile thực thi chưa đổi. Xem [INSTALL_REPORT.md](INSTALL_REPORT.md) để áp dụng quyền đúng tại host, không xóa proxy quản lý. Regression hiện **49 ca PASS bằng unittest**, log riêng `logs/qa-followup-unit-20261106`. E2E thật không dùng mock đã được chạy và **FAIL tại OCR thiếu engine**, xem [E2E_REPORT.md](E2E_REPORT.md). Build hiện có gate chặn nếu GUI/E2E thật chưa PASS, xem [BUILD_REPORT.md](BUILD_REPORT.md).

## Sử dụng khi đã cài đủ thư viện

1. Nhấp đúp `install.bat` để tạo `.venv`, cài bộ phiên bản trong `requirements.txt` và tải font Noto Sans. Cần Python 3.10 hoặc 3.11 **64 bit** đã có Python Launcher. Máy hiện tại có Python 3.10.9. Script báo lỗi và lưu log nếu cài không thành công; không bỏ qua hạn chế mạng/proxy của máy.
2. Nhấp đúp `run.bat`. Sau khi cài thành công, người sử dụng không cần terminal. Khi đã có bản build, script ưu tiên EXE trong `dist\ImageTranslatorVN`.
3. Mở **Quản lý mô hình AI**. Chọn từng model cần thiết và bấm **Tải**, sau đó **Kiểm tra model**. Đây là thao tác riêng có truy cập Internet, không gửi ảnh hoặc văn bản OCR. Kiểm tra model hiện xác minh cấu trúc và SHA-256; kiểm thử suy luận thật là bước riêng.
4. Chọn thư mục ảnh nguồn, thư mục xuất riêng (có thể ngoài project hoặc khác ổ đĩa; mặc định `output`), ngôn ngữ OCR và chế độ dịch.
5. Chọn **Cài đặt** nếu cần đổi font/cỡ chữ/màu/viền/căn lề, thứ tự đọc, inpaint/nền trắng/mask tùy chỉnh, định dạng và chất lượng ảnh, thuật ngữ/tên riêng.
6. Bấm **Bắt đầu dịch**. Theo dõi tên file, công đoạn, số ảnh đã hoàn thành/lỗi/bỏ qua và tiến trình phát sinh từ worker thật. Nhấp đúp hàng kết quả để xem trước/sau và cảnh báo.
7. **Tạm dừng**, **Tiếp tục**, **Hủy** có hiệu lực ở checkpoint an toàn. OCR hoặc một yêu cầu mạng đang thực hiện cần kết thúc trước khi dừng. **Thử lại ảnh lỗi / chưa xong** chỉ xử lý danh sách đó. Các kết quả đã hoàn tất được giữ lại.
8. Dùng **Mở kết quả** để mở Explorer. Ảnh nguồn luôn được giữ nguyên; tên ảnh xuất có hậu tố `.vi-<mã công việc>`.

Khi khởi động lại, nút **Khôi phục cấu hình công việc chưa hoàn thành** nạp công việc trước. Bấm Bắt đầu dịch; các ảnh thành công có fingerprint và checksum đầu ra đúng sẽ được bỏ qua. Công đoạn OCR/dịch bị gián đoạn giữa một ảnh sẽ được thực hiện lại qua cache; checkpoint hoàn tất ghi sau mỗi ảnh.

## Model cần tải

| OCR | Model phát hiện | Model nhận diện | Model hướng |
| --- | --- | --- | --- |
| Trung giản thể | `det-ch` | `rec-zh` | `cls` |
| Trung phồn thể | `det-ch` | `rec-zt` | `cls` |
| Hàn | `det-ml` | `rec-ko` | `cls` |
| Anh | `det-en` | `rec-en` | `cls` |
| Tự động | Cả ba model phát hiện | Cả bốn model nhận diện | `cls` |

Tự động thử bốn bộ model tuần tự và cảnh báo nếu điểm gần nhau; chưa có bộ phân loại ngôn ngữ đã hiệu chỉnh. Nên chọn rõ ngôn ngữ, đặc biệt với giản thể/phồn thể hoặc ảnh nhiều ngôn ngữ.

| Nguồn dịch Offline | Gói cần có | Đường dịch dự kiến |
| --- | --- | --- |
| Anh | `translate-en_vi-1_9` | en → vi |
| Trung giản thể | `translate-zh_en-1_9`, `translate-en_vi-1_9` | zh → en → vi |
| Trung phồn thể | `translate-zt_en-1_9`, `translate-en_vi-1_9` | zt → en → vi |
| Hàn | `translate-ko_en-1_1`, `translate-en_vi-1_9` | ko → en → vi |

Danh mục dựa trên [index chính thức Argos](https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json). Đây là model được chọn để tích hợp; **chưa có model nào được tải/cài hoặc kiểm thử suy luận trong phiên này**. Bộ cài từ chối model thiếu file, sai cặp ngôn ngữ hoặc không có cấu trúc SentencePiece/CTranslate2 được hỗ trợ. Không tuyên bố mọi gói Argos/BPE khác đều tương thích.

Model OCR nằm trong `models\ocr`, model dịch trong `models\translation`. Model được tải qua HTTPS từ PaddlePaddle và Argos. Sau tải, phần mềm kiểm tra archive, chống đường dẫn thoát thư mục, kiểm tra file bắt buộc và lưu SHA-256 cho từng file. Hash cục bộ giúp phát hiện hỏng/thay đổi về sau; danh mục chưa có checksum được nhà phát hành ký, nên không coi receipt cục bộ là chữ ký nguồn phát hành. Không tải lại model đã cài hợp lệ. Model hỏng cần xóa qua GUI rồi tải lại.

## Online miễn phí và quyền riêng tư

- **MyMemory** dùng GET API anonymous được công bố, không có API key/thẻ/credit. Hạn mức anonymous khoảng 5.000 ký tự/ngày/IP; mỗi truy vấn tối đa 500 byte. Phần mềm giới hạn truy vấn, dùng cache, giãn cách yêu cầu, timeout và tối đa 3 lần thử với backoff cho lỗi mạng/server. HTTP 429 dừng ngay; không né hạn mức. Tham khảo [đặc tả](https://mymemory.translated.net/doc/spec.php), [hạn mức](https://mymemory.translated.net/doc/usagelimits.php), [điều khoản](https://mymemory.translated.net/doc/en/tos.php). Thử gọi thật trong môi trường hiện tại thất bại kết nối; chưa xác minh dịch Online thành công.
- **LibreTranslate** chỉ dành cho endpoint tự host hoặc endpoint miễn phí người dùng có quyền sử dụng. Mặc định `http://127.0.0.1:5000`; ứng dụng không tự cài server. Không hardcode dịch vụ công cộng không được phép, không nhập API key. Endpoint bên ngoài phải dùng HTTPS. Provider đã được test bằng HTTP mock, chưa có instance thật được kiểm thử.
- **Offline** chỉ dùng OCR/model cục bộ, không gọi Online, không tự tải model, kể cả khi checkbox fallback đã được bật ở chế độ khác. Thiếu model sẽ báo lỗi. Argos provider dùng tokenizer của Argos và engine CTranslate2; tránh đường gọi Stanza có khả năng tải tài nguyên tự động.
- **Auto Fallback** thử Offline trước; chỉ gửi văn bản OCR tới Online khi ô đồng ý riêng được bật. Cả ảnh và xử lý phục hồi nền ở máy. GUI mô tả rõ chế độ hiện tại.
- Cache SQLite lưu văn bản OCR/bản dịch trên máy theo yêu cầu tính năng. Log không chủ động ghi nội dung OCR/bản dịch hoặc thông tin xác thực. Không có provider API tính phí trong chương trình.

## Chất lượng và giới hạn hiện tại

- PNG/JPG/JPEG/WEBP/BMP tĩnh, tên Unicode, quét thư mục con, sắp xếp tự nhiên. Ảnh động bị từ chối. Giới hạn 65 triệu pixel/ảnh để tránh cấp phát RAM không kiểm soát; ảnh dài được OCR bằng tile có overlap và dedup hình học. Một worker xử lý ảnh, OCR giữ một engine đang dùng, dịch giữ tối đa hai model CT2.
- Output giữ kích thước pixel được mã hóa trong file; không tự xoay theo EXIF. Giữ alpha khi định dạng hỗ trợ. JPEG/BMP được ghép nền trắng kèm cảnh báo; PNG/WEBP giữ alpha. Metadata/ICC/EXIF chưa được bảo toàn đầy đủ.
- Mask ước lượng nét chữ trong polygon OCR, nới mask có giới hạn; hỗ trợ Telea inpainting, nền trắng và mask từ ảnh PNG/BMP cùng kích thước. Mask tùy chỉnh hiện dùng chung cho batch, nên chỉ dùng khi các ảnh có cùng bố cục/kích thước hoặc xử lý từng ảnh.
- Chữ Việt tự xuống dòng và giảm font, tính cả dấu/viền. Nếu không vừa vùng OCR ở cỡ tối thiểu, ảnh được báo lỗi và không xuất ảnh đã tẩy chữ. Chưa có công cụ sửa polygon/bản dịch tương tác.
- Gom dòng bằng heuristic căn chỉnh/gap/viền tối. Chưa có segmentation bong bóng thoại hoặc bố cục truyện tranh đã được đánh giá. Thứ tự đọc phải chọn phù hợp; chữ dọc dựa trên xử lý crop của PaddleOCR, chưa được kiểm chứng bằng dữ liệu thật. Model sai/ngôn ngữ trộn có thể bỏ sót chữ: cần xem preview.
- Từ điển và số được bảo vệ bằng marker. Nếu provider làm thay đổi marker, ảnh báo lỗi thay vì mất tên/số. Cơ chế này có thể từ chối bản dịch model thật; cần đánh giá khi có model.
- Mặc định tải Noto Sans (SIL OFL 1.1). Tải font hiện bị chặn; runtime có fallback font Arial/Segoe UI đã cài trong Windows, không sao chép/phân phối font Windows. Noto chưa được đóng gói.

## Kiến trúc và thư mục

```text
D:\TransTool
  main.py                    Điểm vào GUI
  core\
    paths.py                 Root Python/EXE, thư mục model/cache
    types.py                 Options, OCRResult, lỗi nghiệp vụ
    storage.py               SQLite/cache/checkpoint/config/logging
    models.py                Danh mục, tải, kiểm tra và xóa model
    ocr.py                   PaddleOCR CPU, tile, dedup, thứ tự/gom dòng
    imaging.py               Mask, inpaint, renderer, atomic export
    pipeline.py              Providers/cache, batch và JobControl
  providers\                 Base, Online, Offline Argos/CTranslate2
  ui\                        MainWindow, QThread, settings, model manager, preview
  config\                    Cấu hình người dùng
  models\ocr\                Model OCR bên ngoài EXE
  models\translation\        Model dịch bên ngoài EXE
  assets\fonts\              Font và giấy phép khi tải được
  assets\icons\
  cache\                     SQLite, cache dependencies/framework
  logs\                      Log ứng dụng, kiểm thử và bằng chứng
  tests\                     Unit và real integration tách biệt
  scripts\                   CLI/QA, tải model/font chủ động, báo cáo môi trường
  output\cv-validation\      Artifact kiểm tra CV, không phải bằng chứng OCR/MT
  dist\                      Hiện chưa có EXE
  requirements.txt           Bộ pin đầy đủ đề xuất, chưa cài kiểm chứng
  requirements-core-tested.txt  Bộ CV đã chạy thật trong Python hệ thống
  install.bat / run.bat / build.bat
  ImageTranslatorVN.spec
  AGENTS.md / PROJECT_STATUS.md / TEST_REPORT.md
```

Đường dẫn framework được cấu hình về dự án khi có thể (Argos/XDG/Paddle/Torch/Hugging Face). PaddleOCR dùng đường dẫn model explicit và thay downloader bằng kiểm tra model cục bộ. Không sửa cache hay môi trường Python của dự án khác.

## Kiểm thử và build cho người phát triển

```bat
cd /d D:\TransTool
.venv\Scripts\python.exe -m pytest -q
set ITVN_TEST_ONLINE=1
.venv\Scripts\python.exe -m pytest tests\test_integration.py -v
```

Online test opt-in gửi chuỗi mẫu `Hello world`. Tests AI thật skip rõ lý do nếu thiếu engine/model; test GUI chạy nền với Qt offscreen và cần thêm kiểm tra trực tiếp trên Windows.

Môi trường hiện tại không có pytest; đã chạy cùng các test unittest bằng Python hệ thống có OpenCV/Pillow/NumPy/requests:

```bat
python scripts\run_tests.py
python -m compileall -q main.py core providers ui scripts tests
python scripts\runtime_probe.py
```

Các unit test workflow dùng OCR/MT fixture riêng trong `tests/test_core.py`; không có fake provider trong runtime ứng dụng. File `logs/test-results.json` lưu danh sách PASS/SKIP/error; log `tests-unittest.log` có chi tiết. `output/cv-validation/evidence.json` ghi rõ tọa độ và bản dịch nhập thủ công, chỉ xác minh CV và xuất ảnh.

`build.bat` chạy pip check, pytest rồi PyInstaller onedir. Đích là `dist\ImageTranslatorVN\ImageTranslatorVN.exe`, model bên ngoài. Giữ cấu trúc thư mục tại D:\TransTool để EXE tìm đúng root. **Build đã được thử nhưng thất bại vì chưa có PyInstaller; chưa có EXE để smoke-test.** Hooks Paddle/CT2 và đóng gói Qt còn phải kiểm tra trên môi trường có đủ dependencies. Không coi spec là bằng chứng build thành công.

## Xử lý lỗi cài đặt hiện tại

Xem `logs/install.log`: pip không kết nối được proxy (WinError 10061). `logs/pytest-attempt.log` và `logs/build-attempt.log` ghi thiếu module. `logs/online-probe.json` ghi thử provider thật không thành công. Cần kết nối hợp lệ được môi trường cho phép, hoặc wheelhouse đầy đủ đã được chuẩn bị cho Python/Windows tương ứng. `install.bat` hỗ trợ wheelhouse cục bộ và không tự tắt proxy/chính sách mạng.

Khi điều kiện này được giải quyết, đọc PROJECT_STATUS, cài đủ requirements, chạy pip check, tải các model trong bảng qua thao tác riêng, chạy integration thật, sửa lỗi tương thích phát hiện được, rồi mới build và nghiệm thu GUI/EXE. Chưa có kết quả cho các bước đó để tuyên bố hoàn tất.

## Stage 3C: batch AGY nhiều trang và resume bền vững

Bản source: AGY gom theo thứ tự trang, mục tiêu3.000ký tự/60vùng, giữ trang
còn vừa batch; trang quá lớn chỉ chia tại ranh giới vùng. Có giới hạn bổ sung
16trang có chữ/batch,6.000ký tự/vùng,12.000ký tự cứng và128KB payload; output
CLI tối đa1MB. Cấu hình AGY trong Cài đặt; Offline vẫn mặc định.

Journal riêng cạnh database (`<tên-db>-resume-v1/`) lưu công việc chưa xong.
Mở app không tự gửi mạng: ở tab thư mục bấm Khôi phục công việc, chọn phương
thức rồi Tiếp tục. Tab ảnh/URL có Tiếp tục công việc đã lưu (ưu tiên cache).
Ảnh cache hợp lệ không tải lại; chương đã chọn nhưng chưa tải được kiểm tra
access/policy lại trước khi tải, chỉ sau lệnh tiếp tục của người dùng.

Không thay numeric guard/date handler hoặc model; không build EXE. Journal
được tạo cho lượt chạy mới; không tự migration/chạy lại job production cũ.
Xem `docs/STAGE3C_MULTIPAGE_BATCH_RESUME_REPORT.md` về bằng chứng và giới hạn.
