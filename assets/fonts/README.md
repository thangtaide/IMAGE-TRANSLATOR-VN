# Font

Font mục tiêu: **Noto Sans Regular**, SIL OFL 1.1, hỗ trợ tiếng Việt.

Script `scripts/download_assets.py` tải font và giấy phép trực tiếp từ kho Noto trong một thao tác cài đặt riêng. Tải trong phiên hiện tại thất bại vì mạng bị chặn; chưa có font Noto để phân phối.

Runtime hiện dùng Arial/Segoe UI của Windows nếu chưa có Noto, hoặc font TTF/OTF người dùng chọn trong Cài đặt. Không sao chép font Windows vào dự án hay EXE. Kiểm thử Unicode CV hiện dùng font có sẵn trong Windows.
