# Phân tích Kuaikanmanhua — 07/11/2026

## Cập nhật sau GUI ba tab

Quan sát lại topic 6677 qua công cụ web: metadata và số nội dung vẫn như bảng bên
dưới, chưa có ID/link chương xác minh. Raw HTML/pagination/dữ liệu động chưa kiểm
chứng vì runtime vẫn chặn mạng. Không bịa endpoint hoặc danh sách chương.

Trạng thái mới là **DOWNLOAD POLICY UNKNOWN**, không phải kết luận mọi chương
bị hạn chế đọc. get_chapters phân tích HTML công khai đã nhận/retry và báo lỗi
cấu trúc cụ thể; get_chapter_images thiếu parser báo StructureChanged. Quyền đọc,
quyết định tải và lỗi mạng/parser là các trường độc lập. Metadata giữ khi lỗi chương.
Các đoạn ACCESS RESTRICTED phía dưới ghi quyết định của lượt triển khai trước;
không dùng như một cờ khóa toàn tính năng URL hiện tại.
Chi tiết mới: [GUI_URL_FLOW_REPORT.md](GUI_URL_FLOW_REPORT.md).

## Kết luận và phạm vi

**Metadata công khai: quan sát được qua công cụ duyệt web. Adapter HTML: EXPERIMENTAL.
Danh sách chương: UNVERIFIED. Tải ảnh: ACCESS RESTRICTED. E2E từ URL: BLOCKED.**

Người dùng xác nhận chưa có sự cho phép tải tự động. Mục đích đọc cá nhân không được
coi là bằng chứng website cho phép downloader. Không gửi yêu cầu lấy ảnh chương,
không thu thập cookie/token, không gọi endpoint nội bộ hoặc tìm cách vượt hạn chế.
Phần nhập ảnh/chương do người dùng cung cấp được triển khai độc lập với hạn chế này.

## Dữ liệu quan sát được

| URL công khai | Quan sát qua trình duyệt | Chương có ID/link xác minh | Ảnh chương xác minh/tải |
| --- | --- | --- | --- |
| [topic 6677](https://www.kuaikanmanhua.com/web/topic/6677/) | 权妃之帝医风华; tác giả 有鱼互鱼; 暂时停更; công bố 26 nội dung, 23正文 | 0 | 0/0 |
| [topic 15425](https://www.kuaikanmanhua.com/web/topic/15425/) | Live·冷宫直播; tác giả 叨叨君（主笔）+通幽（编剧）; 已完结; công bố 153 nội dung, 102正文 | 0 | 0/0 |
| [topic 3791](https://www.kuaikanmanhua.com/web/topic/3791/) | Công cụ duyệt web trả Cache miss; NOT VERIFIED | Không xác minh | 0/0 |

Topic 15425 do công cụ web cung cấp từ bản crawl tháng trước, không phải kết quả
HTTP trực tiếp của Python. Không khẳng định metadata hiện thời giống hệt bản crawl.
Các con số nội dung do trang công bố **không phải số chương adapter đã lấy**.
Không hardcode tên/số liệu trên vào adapter. Không coi hình bìa/avatar là trang truyện.

URL topic đã quan sát có dạng `/web/topic/<positive_integer>/`. Registry hiện chỉ
chấp nhận HTTPS trên `www.kuaikanmanhua.com`; không mặc nhiên hỗ trợ mobile, bare
domain hoặc domain CDN. Chuẩn hóa bỏ query/fragment, không giữ thông tin xác thực.

## Điều khoản và giới hạn

[Trang thỏa thuận chính thức](https://www.kuaikanmanhua.com/webs/agreement) chứa
nhiều thỏa thuận. Công cụ tìm kiếm trích được bản dịch vụ có ngày 22/04/2026:
4.1 mô tả một số quyền xem công khai; 4.6.4 đặt giới hạn tự động hóa trong cộng đồng;
9.5 hạn chế một số cách sử dụng/phổ biến nội dung khi chưa được phép; 11.7 bảo lưu
quyền chưa cấp. Điều khoản về cộng đồng không được tự mở rộng thành kết luận pháp
lý áp dụng mọi hình thức đọc. Chưa tìm thấy sự cho phép áp dụng cho downloader này.

[Bản dịch vụ cũ](https://www.kuaikanmanhua.com/anim/protocol2.html) cũng đã được
đọc để đối chiếu, không dùng thay bản mới. `robots.txt` chưa xác minh được trong
môi trường hiện tại; không diễn giải sự vắng bằng chứng thành cho phép.

Quyết định kỹ thuật là **không kích hoạt tải ảnh**, không phải khẳng định mọi cách
đọc cá nhân đều bị cấm. Nếu sau này có nguồn/chính sách cho phép cụ thể, phải kiểm
tra lại trước khi bổ sung downloader. Không có nút bật bỏ qua giới hạn này.

## Những gì chưa xác minh

- Raw HTML thực tế và selector ổn định: công cụ web chỉ trả nội dung đã trích xuất.
- Nguồn danh sách chương, phân trang/lazy loading, ID/thứ tự/link chương, chương khóa.
- URL trang đọc, danh sách ảnh, CDN trang truyện, Referer, định dạng/số ảnh.
- Quyền tải tự động, giới hạn tốc độ cụ thể; khả năng tải HTTPS từ runtime Python.

Không suy đoán Nuxt/JSON/endpoint hoặc URL chương/ảnh để lấp các phần này.
`get_chapters()` báo `StructureChanged`; `get_chapter_images()` và
`download_chapter()` báo `AccessRestricted` trước khi có kết nối ảnh.

## Thử nghiệm runtime

Baseline trước sửa: pytest **76 PASS, 7 SKIPPED**, evidence
`logs/url-source-baseline-20261107.xml`.
Python đang chịu `CODEX_SANDBOX_NETWORK_DISABLED=1` và proxy không kết nối được.
Bộ đọc metadata từ chối khi có sandbox/proxy; không tự bỏ proxy, thay cấu hình
mạng hoặc dùng trình duyệt lấy ảnh thay runtime. Môi trường có proxy doanh nghiệp
cũng sẽ báo chưa hỗ trợ; đây là hạn chế hiện tại.

Parser HTML chỉ được kiểm tra bằng fixture viết thủ công, gắn nhãn rõ trong test.
Metadata trong bảng là quan sát nghiên cứu qua web, không phải kết quả parser.
Kết quả test và luồng ảnh cục bộ: [ONLINE_COMIC_TEST_REPORT.md](ONLINE_COMIC_TEST_REPORT.md).

## Điều kiện mở phần bị chặn

Cần môi trường HTTP được phép, bằng chứng sử dụng/tải phù hợp, raw HTML công khai
đã kiểm chứng, cấu trúc chương/ảnh thật và live test hợp lệ. Nếu chưa đáp ứng, dùng
nút nhập ảnh/chương đã lưu hợp lệ; ảnh có provenance `local`, không gán thành
chương Kuaikan để tạo cảm giác đã kiểm chứng website.
