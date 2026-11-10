# Stage 1 — diagnostic, ảnh dự phòng và retry

Ngày hoàn tất: **08/11/2026 (+07)**. Evidence bắt đầu 17:49 UTC ngày 07/11.
Phạm vi: **chỉ Stage 1**, dừng trước Stage 2–5 theo yêu cầu.

## Chức năng đã thực hiện

- Giữ nguyên regex, thứ tự so sánh và cache key kiểm tra số. Lỗi số dùng mã
  `NUMERIC_MISMATCH`, thông báo trung tính, không tự quy lỗi provider/OCR.
  Diagnostic ghi raw target của **lỗi mới**, source/tokens/provider nếu biết.
- Lỗi OCR, model preflight, MT/validation, inpaint, render, export được ghi nhận
  riêng từng ảnh. Khi không hoàn tất an toàn, kiểm tra bitmap/hash rồi sao chép
  **nguyên byte nguồn** vào file fallback riêng. Không dùng ảnh xóa chữ dở.
- File mới được atomic publish, không replace output đã có. Nếu nguồn hỏng/mất
  hoặc không ghi được fallback, báo `FAILED_NO_OUTPUT`, không tạo file giả.
- `TRANSLATED_SUCCESS` và `FALLBACK_ORIGINAL` đếm riêng. Có định nghĩa
  `PARTIAL_TRANSLATION` nhưng **chưa bật xuất từng phần**: khi một vùng lỗi,
  Stage 1 bảo toàn toàn bộ ảnh gốc. Kiểm thử xác nhận không inpaint vùng lỗi.
- Fallback checkpoint `fallback_original`, không `done`; giữ `needs_retry`.
  Đủ file còn fallback là `completed_with_warnings`; tổng kết có
  `chapters_with_warnings`, không tính vào chương dịch sạch.
- Fallback truyện ở `run_<job>/original/<page>.<ext>`. Retry thành công tạo bản
  dịch riêng, giữ fallback cũ. Nếu đích dịch xung đột, giữ file đó và thử bản
  gốc riêng. Nếu cả hai không ghi được, báo thiếu output thực sự.
- `LocalComicJob(retry_only=True)` xác minh ChapterCache/manifest/hash/output,
  chỉ gửi trang lỗi/fallback/thiếu output vào ProcessingManager. Không gọi
  adapter/discovery/HTTP/CDN. Mapping theo đường dẫn, không theo chỉ số trong
  tập retry. Cache thiếu/hỏng dừng rõ ràng, không tải lại để lấp lỗi.
- Không đổi schema SQLite. Manifest v1 thêm field tương thích. Trạng thái mới
  dùng cột TEXT có sẵn. Không sửa database/checkpoint chương thật.
  `diagnostic_text` không tham gia identity; **tính lại job ID274872 khớp ID cũ**.
  Preflight model thiếu dùng identity unavailable riêng, không giả làm model
  cũ đã sẵn sàng.
- GUI folder/ảnh đơn/URL có **Trang cần xem lại / log**: số trang, filename,
  stage/provider/code/output/log; thông báo rõ file và loại dự phòng. Tổng kết
  tách dịch, một phần (hiện0), bản gốc, thiếu output, skipped, cần xem lại.
- Output đã thành công có checkpoint/hash hợp lệ luôn được giữ nguyên, kể cả
  config cũ skip_success=false. Ô skip được khóa bật để biểu thị quy tắc này.

## Diagnostic

Vị trí `logs/diagnostics/<job_id>/errors.jsonl`. Lỗi acquisition trước pipeline
có transfer ID riêng. Trường chưa biết để null; không bịa filename/target/model.

Record gồm UTC timestamp, job/chapter/image, stage/code/exception/message,
provider/mode/model identity nếu có, region/confidence/source/raw target,
numeric tokens, validator version, retry count, action/output/checkpoint.
`retry_count=0` là không thêm retry suy luận tự động ở cấp pipeline; không phải
số lần bấm Retry hoặc số lần HTTP transport retry nội bộ.

Giới hạn1.000 record/4 MB/job; text2.048 ký tự/trường, token list100×80 ký tự.
`truncated_fields` cho biết phần bị cắt. URL/credential được ẩn; không ghi base64
ảnh. Append/flush/fsync; nếu dòng cuối dở do mất điện thì giữ file cũ, record
mới sang file errors khác. Không auto xóa lịch sử. Quota/I/O/serialization lỗi
không ngăn việc thử xuất fallback; có diagnostic_error khi có thông tin.

Tắt source/target/token capture trong Cài đặt chỉ ảnh hưởng record mới, không
xóa log cũ hoặc gửi log ra Internet. Không tái tạo raw target của lỗi lịch sử.

## Kiểm thử

| Nhóm | Kết quả thực tế |
|---|---|
| Pytest toàn bộ, source cuối | **231 PASS,10 SKIPPED,0 FAIL**, 241 ca,59,05 giây |
| Unittest toàn bộ, source cuối | **231 PASS,10 SKIPPED,0 FAIL**, 241 ca |
| Stage1 mới | 24 test; OCR/MT lỗi dùng mock, bitmap/cache/Qt thật |
| Numeric/captured DOM/cache/native guard | PASS trong suite, không gọi fixture là live |
| OCR thật | Trung giản thể PASS; ngôn ngữ thiếu model SKIPPED |
| MT thật | Anh→Việt và Trung→Anh→Việt PASS; không đổi model/provider |
| Windows Qt GUI / source E2E | **PASS**: ảnh đơn/thư mục qua ProcessingManager thật, ảnh đơn2 vùng OCR/2 bản dịch, pause/resume, heartbeat155, resize/scroll, nguồn/config không đổi,0 network attempts |
| Live Kuaikan / download | **NOT_TESTED** trong stage này |
| Phục hồi trang74/111 thật | **NOT_TESTED**, chưa chạy lại |
| EXE / portable / Windows sạch | **NOT_TESTED**, không build |

24 test mới bao phủ numeric diagnostic/raw target, lỗi ở vùng sau không erase,
OCR/model/inpaint/render/export, source hỏng, permission, output bất biến,
retry cache, publisher conflict, download diagnostic, quota/dòng dở/redaction,
tắt text capture và GUI. Một test cũ “translation failure exports nothing” đổi
kỳ vọng sang fallback đúng hành vi sản phẩm; test từ chối số sai vẫn giữ.

10 SKIPPED: 3 OCR thiếu model (en/ko/zt),2 MT thiếu route (ko/zt),1 Online opt-in,
3 live Kuaikan opt-in,1 M2M100 chưa có model. Skip reason lịch sử của test live
có nhắc sandbox; stage này không kiểm tra mạng, không kết luận mạng hiện bị chặn.

Runner regression chặn socket và chuyển evidence của integration/default GUI DB
sang thư mục QA mới; không ghi đè log integration cũ/cache người dùng. GUI dùng
ảnh đã có tại ImgTest, không phải hai trang lỗi, không tải ảnh. Không gọi test
mock lỗi là Kuaikan URL-to-translation thật.

Evidence: `logs/stage1-errors-20261107T174933Z/`:

- `pytest-final.xml`, `pytest-final.txt`, `unittest-final.json`, `unittest-final.txt`.
- `existing-job-identity.json`, `protected-before.json`, `preservation.json`.
- `source-before/`: backup code/tài liệu trước thay đổi, giữ backup cũ.
- `windows-gui-final.txt`; report/screenshot source cuối:
  `output/source-tabs-validation/20261107T181015Z-d76439/`.
- Giữ lượt trung gian229/10 và targeted test riêng; không thay kết quả cuối231/10.

## Bảo toàn

556 file theo dõi trước/sau: chỉ9 source/test dự kiến đổi hash, không thay đổi
ngoài dự kiến trên dữ liệu bảo vệ. **120 ảnh incoming,120 staging,118 output
người dùng và118 output nội bộ**, manifest/download receipt, database/checkpoint
chương274872, config, DOM, BAT/spec và4 EXE giữ hash. Model integrity receipts
giữ hash; không cài package/model, không sửa .venv/native guard. Không gọi đây
là full hash audit toàn bộ trọng số model hoặc .venv.

Source sửa: `core/pipeline.py`, `core/imaging.py`, `core/types.py`,
`sources/service.py`, `sources/states.py`, `ui/main_window.py`,
`ui/comic_sources.py`, `ui/settings_dialog.py`.

Source tạo: `core/diagnostics.py`, `ui/review_dialog.py`.
Test: tạo `tests/test_error_fallback.py`, cập nhật một ca `tests/test_core.py`.
Docs: cập nhật AGENTS.md, PROJECT_STATUS.md, README.md, WEBSITE_ADAPTER_AI_GUIDE.md;
tạo báo cáo này, USER_GUIDE.md và TROUBLESHOOTING.md. Không đổi launcher/spec,
EXE, provider/model, native guard hoặc .gitignore.

## Chưa thực hiện / bước tiếp

**Stage2 chờ xác nhận**: override vùng hoa văn OCR của trang74 theo image hash/
polygon; thu raw target mới của trang111 (giữ đúng OCR cache có dấu gạch ngày),
quyết định sửa validator theo bằng chứng; chỉ phục hồi hai ảnh và kiểm tra hash
118 output. Stage1 chưa chạy hai trang, chưa có raw target mới để chốt nguyên
nhân MT/validator, không sửa cache OCR gốc hoặc giả trạng thái thành công.

Stage3 benchmark chất lượng, Stage4 portable runtime/model download/máy sạch,
Stage5 .gitignore chưa triển khai. Tài liệu Stage1 đã cập nhật theo quy tắc
workflow mới, không tuyên bố các stage khác hoàn tất. Chưa có trình sửa vùng
OCR/bản dịch, chưa có trình đọc gộp thư mục translated/original. Không bảo đảm
output khi nguồn mất/hỏng hoặc quyền ghi/dung lượng không cho phép.

**STAGE_1_SOURCE_VALIDATED — dừng trước Stage2.**
