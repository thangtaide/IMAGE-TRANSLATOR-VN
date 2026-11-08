# Tra cứu lỗi ảnh — Stage 1–2

## Stage3: phân biệt lỗi chất lượng với lỗi chương trình

- `Name` hoặc `Lỗi` có thể là **chuỗi model thật trả về**, không phải exception
  ứng dụng. Benchmark mới tái hiện chúng qua native decoder. Không xóa cache
  để giả định sẽ sửa được nghĩa;158 cached occurrences khớp output mới.
- Name của `活动时间` bắt đầu sai tại en→vi; tên riêng/chương13 có thể đã sai
  ở zh→en. Nếu source bị cắt/OCR sai, không tự đoán câu gốc hoặc quy hết cho MT.
- Numeric guard PASS không chứng minh giữ nghĩa, tên hoặc danh xưng. Ví dụ
  `第13话`→`Nguyên tắc13` giữ số nhưng cần xem lại nghĩa.
- Không áp dụng LP1.0 vào production: holdout sinh `Lỗi:% 1` ngoài nguồn. Không
  nới validator để chấp nhận dạng này. Các ứng viên chỉ có trong QA.
- Date QA dùng cấu trúc endpoint, không phải Argos mới dịch đúng. Chưa có
  production typed guard/cache policy, nên không dùng output QA để đánh dấu111
  done. Năm0001 có probe roundtrip chưa đạt, được giữ trong evidence.

Xem [báo cáo Stage3](STAGE3_TRANSLATION_QUALITY_REPORT.md) để biết dữ liệu đã
kiểm chứng và giới hạn. Những hướng dẫn Stage1/2 dưới đây vẫn áp dụng.

## Stage 2: OCR override và số có dấu

- `OCR_OVERRIDE_HASH_MISMATCH`: ảnh ở locator đã khác hash bằng chứng. Không
  bỏ qua vùng OCR; giữ nguồn/fallback. Kiểm tra đúng ảnh và profile trước retry.
- `OCR_OVERRIDE_REGION_MISMATCH`: text/polygon không khớp duy nhất. Không dùng
  tọa độ gần đúng hoặc tăng ngưỡng OCR toàn cục; cần bằng chứng mới/thu hồi rule.
- `OCR_OVERRIDE_INVALID`: schema/evidence/profile không đọc được. Giữ file
  profile và log để xem lại, không tự xóa OCR cache. Profile ở
  `overrides/ocr_regions.json`; tắt mục bằng `enabled=false`.
- Numeric version `literal-numbers-v2-signed` ngăn mất/thêm dấu đầu số; ký tự
  fullwidth không tự chuẩn hóa. Cache signed dùng v4; legacy unsigned giữ v3.
  Không đổi list thành set/multiset và không tự sửa số bằng nguồn.

Trang111 của chương274872: **lượt Stage2 mới** có source thật
`5月20日—5月30日`, zh→en `20-30 May`, en→vi `20 giờ 30 tháng 5`. Chặng cuối
sai nghĩa khoảng ngày. Giữ fallback và needs_retry; không lặp Retry vô hạn
với model/input y hệt. Raw target lỗi lịch sử vẫn không có; không gán kết quả
này cho lần lỗi cũ. Trang74 đã hoàn tất không cần MT theo override có evidence.
Chi tiết: [STAGE2_NUMERIC_OCR_RECOVERY_REPORT.md](STAGE2_NUMERIC_OCR_RECOVERY_REPORT.md).

Trước tiên mở **Trang cần xem lại / log**, xác định file, trang, stage và job.
`FALLBACK_ORIGINAL` có file nhưng chưa dịch hoàn chỉnh; `FAILED_NO_OUTPUT`
không có output hợp lệ. Không xóa receipt/cache để ép job chạy lại.

| Mã lỗi | Kiểm tra tiếp |
|---|---|
| `NUMERIC_MISMATCH` | So OCR nguồn, raw target mới và hai danh sách numeric tokens trong diagnostic. Không kết luận provider sai chỉ từ mã này; validator hiện so chuỗi theo thứ tự, chưa chuẩn hóa ngày tháng/số chữ. |
| `OCR_ERROR` | Kiểm tra nguồn, model OCR, bộ nhớ và giai đoạn lỗi. Confidence thấp không tự chứng minh OCR sai. |
| `TRANSLATION_ERROR` | Xem provider/mode/model identity/exception; thiếu model không tự bật Online. |
| `INPAINT_ERROR` | Kiểm tra giới hạn ảnh/mask; nguồn gốc vẫn được dùng làm dự phòng nếu xác minh được. |
| `RENDER_ERROR` | Xem font, kích thước vùng, độ dài bản dịch; không cắt chữ để giả thành công. |
| `EXPORT_ERROR` | Kiểm tra quyền ghi, dung lượng, file đích có sẵn. File khác nội dung được giữ nguyên; app thử bản gốc ở đường dẫn riêng. |
| `DOWNLOAD_ERROR` | Xem lỗi nguồn/mạng/quyền truy cập, trang cuối được progress xác nhận nếu có. Không retry vượt 401/403/429, CAPTCHA hoặc paywall. |

`retry_count=0` hiện là số retry tự động bổ sung ở cấp pipeline cho lỗi này,
không phải lịch sử số lần người dùng bấm Retry hay số lần HTTP transport retry.
Stage 1 không thêm retry suy luận MT. Lịch sử các lần lỗi là các record riêng.

Nếu `diagnostic_path` trống, xem `diagnostic_error`: hết quota, không có quyền
ghi hoặc I/O lỗi có thể làm log không ghi được. Bản dự phòng vẫn được thử xuất.
Log giới hạn 4 MB/1.000 record/job; không tự xóa log cũ để né giới hạn. Nếu dòng
cuối hỏng do mất điện, giữ file đó để điều tra; ứng dụng ghi record mới sang file
khác. Không gửi URL ảnh có chữ ký, cookie, token hoặc toàn bộ cache lên mạng.

Hai lỗi cũ của chương 274872 đã điều tra ở
[NUMERIC_INTEGRITY_INVESTIGATION.md](NUMERIC_INTEGRITY_INVESTIGATION.md). Không
gán raw target của lần retry tương lai cho hai lần lỗi lịch sử. Chưa phục hồi
hai trang thật trong Stage 1.
