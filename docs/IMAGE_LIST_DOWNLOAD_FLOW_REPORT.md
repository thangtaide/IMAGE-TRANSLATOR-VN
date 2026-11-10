# IMAGE_LIST_READY: điều tra luồng tải Kuaikan

Ngày08/11/2026. Workspace D:\TransTool, Python .venv, Windows.
**DIAGNOSIS_COMPLETE / LIVE_CASE_NOT_VERIFIED**. Không thay đổi production source.

## 1. Bằng chứng và nguyên nhân đã xác nhận

Người dùng báo 第8话 驯马/thứ tự10,107 URL từ comic_info.comic_images,
IMAGE_LIST_READY/"Đã tìm thấy URL ảnh (chưa tải)"/0%/quyền nội dung UNKNOWN.
107 là số người dùng quan sát, **chưa tái kiểm chứng reader response của lượt đó**.

Topic DOM gốc `output/kuaikan-capture/topic-6677.dom.html` xác định ID277859,
order_index9, is_free=true/locked=false/need_vip=false/is_pay_comic=false,
AccessStatus.PUBLIC tại thời điểm capture. Không dùng snapshot này để cấp quyền
hiện tại. Cache thật hiện chỉ có chapter274872; app.log có trước Stage3A/3B,
không có trace tương ứng click/download107 URL. Không có căn cứ kết luận lỗi
HTTP, JavaScript, chữ ký CDN hoặc worker của chính lượt báo lỗi.

Luồng source thực tế:

1. Checkbox chọn chương chỉ đổi selection/button state.
2. Nút Phân tích ảnh chương gọi `discover_selected_images` → `launch('images')`.
3. `ComicSourceWorker.run` lấy ảnh từ adapter, emit images_ready; không download.
4. `ComicSourcesPanel.handle_event(images_ready)` lưu URL/số ảnh, tính lại
   download_decision, gọi refresh_start. **Không gọi begin/launch('process')**.
5. **Tải và dịch** gọi begin; nếu không busy và nút được phép, launch process.
6. Worker gọi LocalComicJob; job kiểm tra decision từng chương, nối progress,
   adapter.download_chapter → downloader → cache → pipeline OCR/MT cũ.

Vì vậy **chỉ kết thúc discovery không tạo yêu cầu tải**; 0%/chưa tải ở thời điểm
này đúng với code. Chưa có bằng chứng rằng người dùng đã bấm nút Tải và dịch
được bật mà worker không chạy. Không giả định thao tác ấy đã xảy ra.

## 2. Ba UNKNOWN cần phân biệt

| Trường | Ý nghĩa và tác động |
|---|---|
| ContentPermission.UNKNOWN | Chưa có bằng chứng cấp quyền chính thức. Không tự chặn default_allow_public. |
| AccessStatus.UNKNOWN | Chưa xác minh PUBLIC/free/unlocked. Policy trả UNKNOWN; không tải. |
| DownloadState.UNKNOWN | Quyết định tải chưa đủ điều kiện; nút tắt, lý do dưới bảng/tooltip. |

Chuỗi chính xác **"Cho phép theo cấu hình chủ ứng dụng; quyền nội dung vẫn UNKNOWN."**
được tạo tại `sources/download_policy.py:decide_download` khi quyết định là
ALLOWED_BY_USER_POLICY, **allowed=True**. Nó không phải thông báo từ chối quyền.
Điều kiện ready còn gồm chapter list ready, có chương được chọn, adapter có
downloader, tất cả chương đã chọn đều allowed, và worker không busy.
Một chương UNKNOWN trong lựa chọn nhiều chương vẫn làm nút tải tắt.
Không đổi evidence UNKNOWN thành OFFICIAL_PERMISSION; không nới access guard.

## 3. Có liên quan Stage3A/3B không?

Đối chiếu Git commit a9c1e5e(Stage2),894e6c4(Stage3A),1a47b15(Stage3B):
nhánh images_ready byte-identical qua cả3phiên bản. Các file kuaikan.py,
download_policy.py và kuaikan_download.py không đổi từ Stage2 đến HEAD.
Stage3A/3B thêm phương thức dịch/provider pause nhưng không thêm/bỏ lệnh tải
trong discovery. **Không có bằng chứng regression do Stage3A/3B.**
`analysis.json` lưu so sánh và cờ snapshot, không lưu signed URL.

## 4. Quyết định sửa

Theo điều kiện cuối nhiệm vụ: chưa chứng minh quyền/reader hiện tại của lượt107
hoặc điều kiện sai, nên chỉ chẩn đoán, thêm test local/mock và hướng dẫn.
**Không sửa production source, không khởi động tải từ IMAGE_LIST_READY,
không thay policy/access status, không tải live.** Đây không phải hotfix khôi
phục tính năng đã chứng minh hỏng; không tuyên bố đã sửa nguyên nhân live.

Để sử dụng luồng hiện có: giữ chương chọn → xem Điều kiện tải → bấm Tải và dịch
khi nút bật. Nếu sau click vẫn đứng: cần thông báo sau click, ID/giờ chạy,
trạng thái nút và decision/tooltip, source hay EXE nào; không cần cookie/token,
signed URL, toàn bộ DOM hoặc tải lại chương. EXE cũ không được cập nhật lượt này.

## 5. Kiểm thử

Thêm `tests/test_image_list_download_flow.py`: **9PASS**, tất cả local/mock:

- Discovery allowed vẫn không tự tải; progress0%, nút tải được bật.
- PUBLIC + content UNKNOWN vẫn allowed theo user policy.
- Access UNKNOWN hoặc verified_only thiếu evidence: không launch, có lý do.
- VIP/locked/restricted không chọn/tải được.
- Click tải dispatch process với Offline,MyMemory,AGY; không gọi provider thật.
- **QThread thật → downloader thật → mocked HTTP → PNG decode/cache/progress**.
  Job shell được thay fixture (không gọi đây là OCR/MT E2E). Lượt thứ2 dùng
  receipt, **0HTTP**, hash bitmap không đổi.
- Lỗi khởi tạo worker được đưa vào last_result/error và thông báo GUI.
- Pause/resume/cancel được nối đến JobControl; các test downloader/cache hiện
  có còn kiểm chứng cancel giữa tải, giữ file dở, resume/cache hit/không ghi đè.

Lượt targeted đầu8PASS/1FAIL vì fixture QA đặt ngoài cache, guard từ chối đúng;
chỉ sửa đường dẫn fixture vào cache QA, không đổi guard. Lượt cuối9PASS.

**Full pytest318PASS/10SKIPPED/0FAIL; full unittest318PASS/10SKIPPED/0FAIL
(328ca).** Baseline309PASS/10SKIPPED giữ nguyên, thêm9test. Chạy bằng .venv,
native import guard trước Qt, tắt opt-in live và chặn socket trong runner;
database mặc định GUI/test evidence được chuyển sang QA, không dùng DB production.
Các test real OCR/Argos/native import/worker restart vẫn PASS; GUI Qt offscreen
PASS. Không chạy lại E2E chương production, không tuyên bố desktop thủ công
hoặc AGY/MyMemory live PASS mới. Live Kuaikan/download: **NOT_TESTED**.

Evidence: `logs/hotfix-image-list-20261108T045247Z/` gồm analysis.json,
targeted.xml/targeted-final.xml, pytest-final.xml/txt, unittest-final.json/txt,
git-initial-observation.json/git-before.json/git-final.json,
protected-before.json/preservation.json.

## 6. Bảo toàn và Git & Fork Handoff

Baseline repository D:\TransTool, branch main, HEAD1a47b15, clean, không staged.
595file runtime/resource trọng yếu khớp baseline Stage3B khi kiểm tra đầu và cuối.
Snapshot mở rộng22.145file model/config/cache/DOM/dist/resource cũng giữ nguyên
hash ở kiểm tra cuối; xem preservation.json. Scan mở rộng hoàn tất trong lúc QA,
nên git-before.json của scan có test mới do nhiệm vụ này tạo. Baseline clean ban
đầu được quan sát trực tiếp trước khi viết test, ghi rõ nguồn tại
git-initial-observation.json; không coi status chụp muộn là thay đổi của người dùng.
Không sửa model/.venv/config/BAT/spec/SQLite/checkpoint/manifest/120output,
không retry111 hoặc tải ảnh/model. Bốn EXE giữ nguyên. Production source và
provider Argos/MyMemory/AGY giữ nguyên; không build.

File nên review/commit (6file):

- Test mới: tests/test_image_list_download_flow.py.
- Báo cáo mới: docs/IMAGE_LIST_DOWNLOAD_FLOW_REPORT.md.
- Tài liệu sửa: PROJECT_STATUS.md, docs/USER_GUIDE.md,
  docs/TROUBLESHOOTING.md, docs/WEBSITE_ADAPTER_AI_GUIDE.md.

.gitignore hiện đủ; không sửa. Evidence/log/output/cache/model/.venv/config riêng/
EXE bị ignore; source/test/docs/spec/config mẫu vẫn hiển thị. Không thêm secret,
ảnh hoặc binary trong thay đổi dự kiến. Không có thay đổi sẵn của người dùng
ở baseline; git-final.json lưu status/diffcheck/stat/ignorechecks cuối.

Mở Fork → Local Changes → review6file trên → tự stage/test/docs phù hợp → xem
staged diff → tự commit. Không commit evidence/cache/output/model/EXE.
Do không sửa production, đề xuất message đúng phạm vi:
`test(sources): verify chapter download intent and permission states`.
Message hotfix người dùng gợi ý chưa phù hợp vì không có thay đổi khôi phục tải.

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT**.
