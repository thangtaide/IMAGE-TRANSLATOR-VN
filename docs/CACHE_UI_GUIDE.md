# Dịch lại từ đầu và quản lý cache

Áp dụng cho source và EXE mới có nút **Dịch lại từ đầu** trong tab **Thư mục ảnh**.
Không cần đổi tên hoặc di chuyển SQLite DB thủ công.

## Chọn thao tác

**Bắt đầu dịch** dùng cache hợp lệ. Bật **Bỏ qua ảnh đã xử lý thành công** để
bỏ qua output có receipt và checksum đúng. Tắt tùy chọn này để tạo bản xử lý
mới với tên riêng, giữ output/receipt cũ; OCR/bản dịch vẫn có thể dùng cache
khi key khớp. Đây không phải yêu cầu OCR và dịch mới hoàn toàn.

**Dịch lại từ đầu** tạo run ID mới, DB riêng và thư mục kết quả mới. Lượt này
không đọc OCR, bản dịch, checkpoint hoặc receipt render của lượt cũ, bất kể
checkbox bỏ qua đang bật hay tắt. Dữ liệu mới ghi vào run riêng; nếu bị dừng,
run có thể tiếp tục từ chính cache/checkpoint của nó.

## Chạy một lượt mới

1. Chọn nguồn ảnh, thư mục xuất và phương thức dịch.
2. Bấm **Dịch lại từ đầu** ở khu vực **Thao tác chính**.
3. Kiểm tra số ảnh, phương thức/model, nguồn, đích mới và trạng thái cache bypass.
   Có thể chọn thư mục cha khác cho kết quả Batch.
4. Bấm **Xác nhận dịch lại**. Với Batch, worker bắt đầu OCR rồi dịch. Chọn **Hủy**
   để thoát mà không tạo run hoặc gọi AGY.

Đích mặc định là một thư mục `run-<thời gian>-<ID>` trong thư mục xuất đã chọn.
Các lần dịch lại tiếp theo tạo thư mục ngang cấp, không lồng thêm nhiều lớp run.
Đích đã tồn tại sẽ bị từ chối; chọn vị trí khác. Không ghi đè output cũ mặc định.

Với **AGY Toàn chương**, lượt mới có workspace riêng trong `output/stage3g-restart-<ID>`.
Sau OCR vẫn cần nút xác nhận gửi manifest tới AGY của Whole Chapter. Không dùng
checkpoint hoặc bản dịch của workspace Whole cũ.

## Tạm dừng, hủy và tiếp tục

**Tạm dừng** chờ checkpoint an toàn; **Tiếp tục** dùng lại worker đang dừng.
**Hủy** giữ các kết quả và checkpoint đã ghi. Native OCR hoặc request đang chạy
cần kết thúc theo cơ chế hủy hiện có; không cưỡng bức xóa file đang dùng.

Sau khi mở lại ứng dụng, nguồn/đích đã lưu khớp run đang chọn sẽ nhận đúng DB
riêng, chưa tự xử lý. Dùng **Thêm → Khôi phục công việc đã lưu**, rồi **Tiếp tục**.
Hoặc mở **Quản lý cache**, chọn run và bấm **Mở / khôi phục lượt đã chọn**.
Khôi phục chỉ nạp cấu hình/checkpoint, không tự gọi AGY. Các lượt cũ vẫn nằm
trong danh sách. Checkpoint chung còn dở không bị lượt riêng đã hoàn tất che mất.

## Mở và quản lý cache

**Mở thư mục cache** mở thư mục chứa DB thực sự của lượt đang dùng. Với Whole
đã chuẩn bị, nút mở workspace chứa `qa.sqlite3`. Không giả định AppData hay
một ổ đĩa cố định; nếu thư mục không tồn tại, ứng dụng báo rõ và không tự tạo.

**Quản lý cache** thống kê trong thread nền. Hiển thị vị trí thực, dung lượng,
job/run, loại dữ liệu và thời điểm cập nhật. Cache lớn có thể chỉ thống kê
được dung lượng tối thiểu/danh sách giới hạn trong thời gian cho phép; GUI vẫn
hoạt động. Các ô bảng bị thu gọn có tooltip để xem đủ giá trị.

Để dọn, chọn một **run riêng đã hoàn tất**, chọn **OCR** và/hoặc **Bản dịch**,
rồi bấm **Dọn OCR / bản dịch đã chọn…** và xác nhận. Ứng dụng sao lưu DB bằng
SQLite backup API, sao lưu journal, sau đó dọn đúng các hàng cache trong transaction.
Backup nằm cạnh DB chung, dưới `cache-backups/<run>/<thời gian>/`. Nút **Sao lưu
lượt đã chọn** cho phép tạo backup riêng mà không dọn.

Không dọn run đang chạy, run còn dở, DB chung chưa xác định ownership, hoặc
cache Whole/ToonCN. Không xóa DB, WAL/SHM thủ công, checkpoint, receipt render,
output, ảnh nguồn, models, config hay đăng nhập. Các nút không hỗ trợ được vô
hiệu hóa và có giải thích. Backup lỗi hoặc không lấy được khóa thì không dọn.

Dọn hàng cache có thể chưa làm file SQLite nhỏ đi ngay; ứng dụng không tự
VACUUM hay xóa database. Các bản backup được giữ nguyên.

Menu **Thêm**, menu **Công cụ**, popup chọn phương thức và dialog dùng chung
dark palette; hover và disabled có màu riêng, không còn popup nền trắng.

Xem [báo cáo kỹ thuật và bằng chứng](CACHE_UI_REPORT.md).
