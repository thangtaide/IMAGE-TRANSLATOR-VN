# ToonCN Bridge — kết nối theo yêu cầu của Image Translator VN

Bản **0.3.0** dùng Chrome cá nhân đã truy cập hợp lệ. Đã kiểm tra live trang
truyện/chương mẫu, 32 chương, 316 URL ảnh, tải mẫu 3 ảnh JPEG hợp lệ. Chưa tải
đủ 316 ảnh và chưa chạy OCR/dịch/render ToonCN thật trong QA này.

## Sử dụng khi đã cài cầu nối

1. Tại `chrome://extensions`, **Reload ToonCN Bridge** để nạp mã cuối cùng.
   Không cần đăng ký host lại hoặc cấp thêm quyền website. Chrome vẫn giữ mở.
2. Mở lại Image Translator VN từ `run_source.bat`. Trong Link truyện online,
   bấm **ToonCN: TẮT** để chuyển sang **BẬT**. Mặc định mỗi lần mở ứng dụng là TẮT.
3. Dán `https://tooncn.net/webtoon/5701569/` → Phân tích link → chọn chương →
   Phân tích chương đã chọn → Tải và dịch. Chọn phương thức dịch như trước.
   Hoặc dán thẳng URL chương, phân tích link rồi chọn chương và Tải và dịch.
4. Không bấm Gửi trang theo từng chương nữa. Popup extension chỉ báo trạng thái.
   Tắt nút ToonCN để ngừng yêu cầu đọc/tải qua trình duyệt.

Chỉ phân tích link/chương không tải toàn bộ ảnh hoặc dịch. Bật kết nối cũng
không tự tải truyện. Website yêu cầu xác minh thì bạn tự thao tác trong Chrome;
ứng dụng dừng ở challenge, không tự click CAPTCHA hoặc cố vượt chặn.

Nếu cần trang chưa mở, extension mở/reuse một tab ToonCN riêng trong chính
Chrome đó, không tạo profile mới, không điều hướng tab website khác hoặc đóng
Chrome. Không tự retry sau lỗi nguồn. Các tab do người dùng điều hướng sang
website khác không bị ứng dụng lấy lại hoặc đọc nội dung.

## Cài lần đầu trên máy chưa đăng ký

Chỉ khi chưa cài: tự chạy `register_host.bat`, rồi Chrome → Developer mode →
Load unpacked → chọn `D:\TransTool\extensions\tooncn_bridge`. Installer ghi đúng
một HKCU NativeMessagingHosts và launcher/manifest riêng ở config/tooncn_bridge;
không cài extension hoặc sửa profile. ID giữ nguyên:
`jhcbfanogbihlfaklgcnkppcmcbeblgl`. Key trong manifest là public key định danh,
không phải API key hay bí mật. `unregister_host.bat` chỉ gỡ đăng ký host đó;
Chrome → Remove/Tắt extension để gỡ/tắt tiện ích. Không xóa dữ liệu cũ.

## Phạm vi và quyền

- Chỉ `https://tooncn.net/*`, với `scripting` và `nativeMessaging`. Không có
  cookies, debugger, history, tabs, downloads, webRequest hoặc `<all_urls>`.
  Chưa có bằng chứng site dùng www.tooncn.net nên không tự thêm quyền www.
- Mọi trang công khai trên hostname được capture khi ứng dụng yêu cầu; không
  hardcode ID truyện. Adapter nhận cấu trúc `/webtoon/<id>/` và `/<id>-Ep-<số>/`.
  Không đọc trang đăng nhập/quản trị, form/input/script/iframe, cookie, storage,
  token hoặc header xác thực. Query/fragment không xuất khỏi trình duyệt.
- Service worker giữ Native Messaging port để nhận yêu cầu local. Khi TẮT chỉ
  có IPC cục bộ, không query tab hoặc đọc DOM. Không ghi lịch sử duyệt web và
  không liên tục chụp mọi trang người dùng xem. Trang tải động được đọc lại
  theo yêu cầu, đợi load và hai projection ổn định, tối đa90giây.
- Lease ứng dụng hết sau20giây nếu ứng dụng chết; heartbeat5giây. Tắt hủy công
  việc đang chờ, chặn kết quả đến muộn và gửi abort cho fetch ảnh đang chạy.
- Dữ liệu truyền tạm ở `cache/tooncn_browser/runtime-v2/`: metadata tối đa16MB,
  ảnh tối đa64MiB, TTL10phút, giới hạn128request. Chỉ dọn file UUID của runtime-v2,
  không xóa inbox v1, cache nguồn, journal, DB, output hoặc dữ liệu lịch sử.
  Ảnh đã tải theo lệnh người dùng được giữ trong ChapterCache như nguồn cũ.
- Capture tối đa4.000node/20.000element và900KB JSON. Không tự cắt thiếu.
  Tải ảnh tối đa8MiB/ảnh, 500ảnh/chương; quá hạn/quota thì báo lỗi.
- Ảnh chỉ được lấy từ `#readerarea img.ts-main-image`, ưu tiên data-src thật,
  không dùng SVG placeholder/thumbnail. Fetch same-origin trong Chrome, cookie
  chỉ được Chrome sử dụng nội bộ. Binary gửi theo chunk có ACK/hash, host không
  xuất cookie/token. Python kiểm MIME/bitmap/hash/thứ tự và publish bằng cơ chế
  downloader/receipt sẵn có. Không gửi ảnh/text tới dịch vụ dịch khi chỉ tải.
- Mặc định vẫn Offline; không đổi model, prompt, numeric/glossary hoặc AGY.

## Lỗi ngắn gọn

`TOONCN_CONNECTION_OFF`: bật nút ToonCN. `WAITING_EXTENSION` hoặc timeout:
Reload đúng extension, kiểm tra popup trạng thái. `NATIVE_HOST_UNAVAILABLE`:
kiểm tra đăng ký host bằng BAT; không cần bật CDP hoặc lấy cookie.
`CHALLENGE_PENDING`/`ACCESS_DENIED`/`RATE_LIMITED`: dừng, tự kiểm tra Chrome,
không retry để vượt chặn. `TOONCN_*_MISSING/CHANGED/SEQUENCE_*`: cấu trúc hoặc
thứ tự nguồn không hợp lệ, giữ cache để xem lại, không báo thành công giả.

[Native Messaging chính thức](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging).
Không có web server, telemetry hoặc dịch vụ giải CAPTCHA.
