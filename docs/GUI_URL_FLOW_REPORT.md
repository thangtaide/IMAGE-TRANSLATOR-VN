# GUI và luồng URL — 07/11/2026

Lượt tiếp theo đã bổ sung router chương và fallback image discovery ở source,
không đổi thiết kế GUI chính. Xem **KUAIKAN_CHAPTER_281106_ANALYSIS.md** để biết
trạng thái mới; EXE GUI tab trong báo cáo này giữ nguyên và chưa chứa sửa adapter
chương. Các số 0 live discovery dưới đây vẫn chưa được thay bằng fixture PASS.

## Phạm vi và trạng thái

Ba nguồn đã tích hợp trực tiếp vào MainWindow, dùng lại toàn bộ OCR/Offline/render
hiện có. Kuaikan vẫn chưa có chapter parser/downloader được kiểm chứng đầy đủ.
Giới hạn đó không khóa ô URL, phân tích, chọn chương UNKNOWN hoặc retry.

## File thay đổi

- `ui/main_window.py`: QScrollArea, 3 tab, cấu hình chung, chống nhiều job đồng thời,
  hủy an toàn khi đóng; tùy chọn persist_settings=False cho QA.
- `ui/comic_sources.py`: tách ComicSourcesPanel nhúng và compatibility dialog;
  metadata/chapters retry, state/error riêng, nút tải theo từng chương, giao diện
  ảnh đơn gọn, giữ worker/cache/pause/resume/retry.
- `sources/states.py` mới: analysis/access/download/processing states, DownloadDecision.
- `sources/contracts.py`, `metadata_http.py`: quyết định tải của adapter; HTTP 429
  tách thành usage_limit, không retry; thiếu downloader không bị gọi là thiếu quyền.
- `sources/kuaikan.py`: reuse HTML metadata, thử lại HTML công khai cho chapter
  analysis, lỗi cấu trúc rõ; get_chapter_images chưa có parser báo StructureChanged;
  policy UNKNOWN, tách biệt với chapter access và metadata.
- `sources/service.py`, `cache.py`: nhận adapter tùy chọn, kiểm tra lại quyết định
  mỗi chương, ImageCollection trong vùng cache được cấp → pipeline cũ; giữ site_id
  và provenance web. Không có downloader Kuaikan thực được kích hoạt.
- `main.py`: thêm entry QA `--validate-source-tabs`; không đổi native import order.
- `scripts/validate_source_tabs.py`, `tests/test_source_tabs.py` mới; cập nhật QA cũ
  và tests/test_integration.py để kiểm tra tab và không lưu cấu hình thật.
- Cập nhật README/PROJECT_STATUS/BUILD_REPORT, hướng dẫn adapter và phân tích website.

Không thêm dependency, không đổi .venv/model/DLL/PATH/BAT/spec. Backup trước sửa:
`backups/gui-tabs-20261107T044038Z` (82 file). EXE cũ không bị ghi đè.

## Luồng và phân loại lỗi

- URL nhập và phân tích độc lập với quyết định tải.
- metadata_state vẫn METADATA_READY khi chapter_state chuyển CHAPTER_LIST_ERROR.
- Retry chương dùng lại ComicInfo, không bắt người dùng xác nhận quyền lặp lại.
- Chapter UNKNOWN có thể chọn; LOCKED/RESTRICTED không chọn. HTTP 200 không tự
  chứng minh quyền tải, kể cả đọc cá nhân.
- Tải chỉ bật khi mọi chương chọn có DownloadDecision.ALLOWED và có implementation
  downloader. Worker kiểm tra lại trước tải; không dựa vào cờ download_enabled cũ.
- Lỗi URL/website/parser/network/access/usage_limit/download_policy/cache/technical
  phân biệt bằng phase + category. Chỉ trạng thái tải chưa sẵn sàng không cản phân tích.

## Kuaikan: quan sát lại

[Trang 6677](https://www.kuaikanmanhua.com/web/topic/6677/) qua công cụ web vẫn cho
thấy 权妃之帝医风华, tác giả 有鱼互鱼, tạm ngừng; công bố 26 nội dung và 23正文.
Đó không phải 26 chương đã được parser lấy. Trong dữ liệu công cụ trả về không có
ID/link chương đủ kiểm chứng. Không thu được raw DOM, pagination hoặc phương thức
dữ liệu động từ runtime bị sandbox/proxy giới hạn; không suy đoán endpoint.

Chương đã lấy có ID/link: **0**. Ảnh chương xác minh/tải: **0/0**. Quyền tải tự
động vẫn UNKNOWN, không khẳng định toàn bộ quyền đọc bị cấm. URL → ảnh dịch Kuaikan
chưa PASS; dùng ảnh người dùng lưu hợp lệ trong tab ảnh đơn/thư mục.
Tham chiếu [thỏa thuận chính thức](https://www.kuaikanmanhua.com/webs/agreement)
không được coi là đã cấp quyền cho downloader này. Chi tiết lịch sử nghiên cứu tại
KUAIKANMANHUA_ANALYSIS_REPORT.md.

## Kiểm thử thật và mock

- Pytest: **116 PASS, 7 SKIPPED**; logs/gui-tabs-20261107/pytest.xml; build.bat
  cũng chạy lại toàn bộ pytest trên fingerprint cuối và PASS cùng số lượng.
- Unittest: **123 ca, 116 PASS, 7 SKIPPED**, 0 failure/error;
  logs/gui-tabs-20261107/unittest/test-results.json.
  Các fixture web/mock policy được ghi nhãn, không gọi là live download PASS.
- Kiểm thử MainWindow mới Qt Windows không mock:
  `output/source-tabs-validation/20261107T045339Z-dc5103/report.json`.
  3 tab độc lập, không dialog nguồn; ảnh truyện ImgTest OCR thật 2 vùng và dịch
  Offline thật 2 bản dịch, ảnh đơn + thư mục đều xuất; pause/resume, cuộn cửa sổ
  nhỏ, URL sai, mạng bị giới hạn nhưng không bị gọi là lỗi quyền; 169 heartbeat,
  0 kết nối mạng. preferences_unchanged=True.
- Workflow thư mục cũ: PASS tại `output/gui-workflow/20261107T045346Z-04252d/`,
  gồm cancel/retry, ảnh lỗi, preview và suy luận thật.
- E2E Offline chuẩn: PASS tại `output/e2e-validation/20261107T045351Z-fd62c9/`
  (fixture ảnh tổng hợp, OCR/MT thật, không nhập tay output).
- GUI smoke: PASS tại `logs/gui-smoke-20261107T045358Z-4fee82/report.json`.
- 10 ca mới trong tests/test_source_tabs.py kiểm tra state/policy/partial metadata,
  nhóm lỗi, retry không lấy lại metadata, gate worker, provenance và config QA.
  Approved downloader trong unit test chỉ copy fixture cục bộ, không phải Kuaikan.

Fingerprint code cuối: `a7e5b4f70ca01a409f00ab02205a12bfd164c5ad498ba8ac781e47226ffa87ea`.
7 SKIPPED giữ nguyên do model OCR/MT ngôn ngữ khác và M2M100 thiếu, Online không opt-in.

## Cấu hình QA

Một test mới ban đầu ghi đường dẫn `tabs-unit-*` vào trường source khi đóng
MainWindow. Đã sửa QA dùng persist_settings=False, thêm assertion file preferences
không đổi và khôi phục riêng source từ checkpoint duy nhất khớp thư mục output.
Các tùy chọn khác giữ nguyên. Evidence:
`logs/gui-tabs-20261107/settings-source-recovery.json`. Không tuyên bố có snapshot
nguyên vẹn trước lỗi QA; các lượt kiểm tra sau khôi phục xác nhận config không đổi.

## Build

**PASS build và kiểm thử chính EXE.** Đã chạy nguyên build.bat qua gate GUI/E2E,
pip check, pytest và PyInstaller spec hiện có. Không sửa hoặc bỏ qua gate.

Binary: `dist/ImageTranslatorVN-20261107T045417969128Z/ImageTranslatorVN-20261107T045417969128Z.exe`.
19,799,672 byte; SHA-256 `99baadc76bc0836781ac7db43674f1a4e7b93be3e5344d6d47c0b5357bbe517c`.
Log: `logs/build-ImageTranslatorVN-20261107T045417969128Z.log`; exit code 0.

| Kiểm tra binary | Kết quả và evidence |
| --- | --- |
| `--validate-source-tabs` | PASS, frozen=True, Qt Windows, 427 heartbeat, 0 network attempts; output/source-tabs-validation/20261107T045845Z-6f3417/report.json |
| GUI smoke Windows | PASS; logs/gui-smoke-20261107T045856Z-bf49d7/report.json |
| E2E Offline ảnh truyện thật | PASS; output/e2e-validation/20261107T045858Z-42bf8c/report.json |

Binary mở ba tab, đọc model/font, OCR/MT/inpaint/render/export thật; không lỗi DLL
hoặc import trong các workflow đã chạy. URL sai và lỗi kết nối được thử trên chính
EXE; không suy diễn đó là Kuaikan chapter/download PASS. Cấu hình không đổi sau QA.
Đã xem screenshot binary: tiếng Việt hiển thị. Mọi EXE/BAT/spec cũ còn nguyên hash.
Mở binary mới trực tiếp hoặc run_source.bat cho source; BAT cũ giữ nguyên hành vi.

## Giới hạn

Live chapter list/downloader và URL → ảnh Kuaikan NOT TESTED/BLOCKED do chưa xác
minh raw cấu trúc/quyền và runtime thiếu mạng. Các test giả lập không thay chúng.
Chất lượng MT qua tiếng Anh và mask nền phức tạp giữ hạn chế cũ. Không thay model.
Chưa test mọi DPI/màn hình/website/proxy; HTTP metadata transport chưa hỗ trợ proxy.
