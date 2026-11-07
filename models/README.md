# Model AI bên ngoài chương trình

`ocr/` và `translation/` là thư mục cục bộ được quản lý bởi `core/models.py`.

Hiện **0/12 model đã cài**. Đã thử tải model OCR và Anh → Việt nhưng bị proxy chặn. Không đặt file giả vào các thư mục này.

Tải riêng qua GUI khi môi trường có kết nối hợp lệ; không tải model trong job Offline. Mỗi model cần receipt `integrity.json` do bộ cài tạo sau khi kiểm tra archive. Danh mục và đường dịch cần thiết được mô tả trong README gốc. Model manager chỉ hỗ trợ gói chính thức có định dạng được xác minh; không tự tìm/tải mô hình khác hoặc API trả phí.
