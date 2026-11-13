# Qoder CLI — nguồn dịch OCR Trung → Việt

Chọn **Cài đặt → AI dịch thuật → Qoder CLI**, chọn model rồi Lưu. Không cần
đổi model ở màn hình dịch chính. AGY/Groq và cấu hình của chúng được giữ nguyên.
Qoder chỉ nhận OCR text/ID đã có, không nhận ảnh hoặc đường dẫn ảnh.

## Cài đặt và đăng nhập

Theo [hướng dẫn chính thức](https://docs.qoder.com/cli/installation), trên
PowerShell Windows:

```powershell
irm https://qoder.com/install.ps1 | iex
```

Mở terminal mới, kiểm tra `qoder --version`, `qodercli --version` và `--help`.
Ứng dụng gọi trực tiếp `.exe`, không gọi wrapper `.cmd` bằng shell. Ưu tiên
`qodercli.exe` trên PATH; có hỗ trợ vị trí cài native dưới thư mục người dùng
và PATH User Windows mới khi process cha chưa nhận PATH cập nhật.
Có thể chọn đường dẫn `.exe` trong Cài đặt; không tải/cài/đăng nhập tự động.

Chạy CLI, nhập `/login`, chọn trình duyệt. Xác minh bằng `status -o json` và
`--list-models`. Không gửi token/cookie cho ứng dụng hoặc đưa chúng vào EXE.
PAT chính thức qua environment vẫn được CLI hỗ trợ, nhưng không lưu trong
settings/snapshot của Image Translator VN.

## Model và effort

CLI 1.1.89 đã xác nhận hai giá trị tên dùng cho `--model`: `Ultimate`, `Sonus`.
Fixture gốc đã làm sạch: `tests/fixtures/qoder_models_1_1_89.txt`.
`Ultimate` đã chạy headless và batch thật. `Sonus` đã chạy một batch thử thật;
CLI trả modelUsage bằng tên nội bộ `smodel`, khác tên `Sonus` truyền qua
`--model`. Bản sửa nhận đúng ánh xạ này, vẫn từ chối metadata model khác.
Xem [sửa lỗi Sonus MODEL_UNAVAILABLE](QODER_SONUS_FIX.md).
Không có Qwen3.7-Plus/MiniMax-M3/DeepSeek-V4-Flash/Qwen3.8-Max/Efficient trong
output tài khoản được kiểm tra, nên không đưa các ID suy đoán vào catalog.

CLI không trả capability effort trong catalog này. Ứng dụng chưa cung cấp mức
effort tùy chỉnh và không truyền `--reasoning-effort`; đây không phải kết luận
model không có khả năng suy luận. Thinking Off không được ánh xạ thành Low.
Model/effort không hợp lệ bị chặn; không tự đổi sang giá trị khác. Không thay
đổi cấu hình model/effort Qoder toàn cục.

Nút **Kiểm tra kết nối** chỉ chạy version/help/status/catalog/plugin metadata;
không gửi prompt, không dịch thử. Mở Settings/startup không tự kiểm tra mạng.
Model được kiểm tra lại với catalog trước khi gửi batch đầu của provider.

## Batch, Whole Chapter và resume

Một batch gom nhiều ảnh vào một invocation, một JSON dịch. Trần cục bộ:
20 ảnh, 60 vùng, 3.000 ký tự OCR, prompt UTF-8 24.000 byte (gồm system prompt),
output cap 4.096 token. Có ước lượng bảo thủ cho độ dài tiếng Việt, escape và
ID lặp lại: `3 × ký tự nguồn + tổng độ dài ID + overhead` tối đa 3.072 đơn vị.
Đây là ngân sách ứng dụng; CLI chưa cung cấp giới hạn context/output của model
trong catalog/metadata (các giá trị quan sát là 0), không coi 0 là vô hạn.
Output vượt/cắt bị từ chối, không retry để "sửa JSON".

20 là số ảnh tối đa, không phải số ảnh bắt buộc trong mỗi invocation. Prompt,
số vùng, ID và output dự kiến có thể làm batch nhỏ hơn. Qoder có hạn mức riêng
`qoder_max_requests`, mặc định 128 invocation/lần chạy, chỉnh trong nhóm Qoder
ở Cài đặt AI. Hạn mức AGY/Groq giữ nguyên. Chạm trần cục bộ báo REQUEST_BUDGET,
không phải PROVIDER_ERROR/quota; batch tiếp theo chưa gửi. Người dùng chủ động
Continue từ checkpoint, không tự retry hoặc đổi nguồn.

Lượt mới mặc định chữ trắng, viền đen 1 px bằng renderer hiện có. Continue
Qoder giữ foreground/stroke của snapshot cũ; thay preference không làm đổi
ảnh đã xuất hoặc recipe của lượt đang dở. Muốn áp dụng kiểu chữ mới cho cả
chương, tạo lượt mới với output riêng. Xem [báo cáo cập nhật](QODER_BATCH_STYLE_FIX.md).

Whole Chapter Qoder tự chia nhiều batch nếu cần, lưu tiến độ/receipt sau mỗi
batch, rồi dùng renderer hiện có. Không chuyển thủ công sang Batch. Một ảnh
quá lớn có thể được chia tại ranh giới vùng; một vùng vượt ngân sách bị chặn,
không cắt chữ. AGY/Groq Whole Chapter giữ quy tắc cũ.

Mapping kiểm tra batch ID, ảnh và vùng thuộc ảnh; không dùng vị trí trả lời.
Receipt chỉ có trạng thái done sau khi toàn response qua validation. Receipt
lưu trước cache từng vùng để khôi phục được sau crash giữa các bước commit.
Một tập vùng pending khác vẫn tái sử dụng được response đã lưu hợp lệ.

Start dùng Settings hiện tại. Continue dùng snapshot provider/model/effort/
contract; identity binary cũng được pin. Không chia sẻ namespace với AGY/Groq.
Ảnh done được kiểm tra receipt/hash rồi bỏ qua, không dịch lại. CLI đổi binary
giữa run bị chặn cho phần pending; tạo run mới chủ động nếu cần đổi CLI.

Nếu timeout/cancel/crash sau intent nhưng chưa có receipt, batch thành unknown.
Continue yêu cầu người dùng xác nhận gửi lại; mặc định Không. Xác nhận chỉ có
hiệu lực cho lần thử tiếp theo, không tạo vòng retry. Với luồng nguồn truyện,
nếu mới mở ứng dụng, lần Continue đầu có thể chỉ phát hiện unknown; lần tiếp
theo mới đưa ra lựa chọn gửi lại cho đúng receipt của chương đang dừng.

## Cô lập và mã lỗi

Mỗi invocation dùng workspace tạm ngoài repository, explicit `--cwd`, system
prompt riêng; input qua stdin UTF-8. Tools rỗng, strict MCP rỗng, setting sources
rỗng, permission `dont_ask`, không persist session, không retry model/network,
không auto update; loại environment Qoder có thể ghi đè model/session/prompt.
Chỉ giữ biến auth/config chính thức cần thiết. Kiểm tra public settings và
plugin metadata; active plugin, hook hoặc status command toàn cục làm preflight
bị chặn thay vì tự sửa cấu hình của người dùng. Không đọc auth/token files.

Windows Job Object chứa đúng cây subprocess đã tạo. Cancel/timeout kết thúc
cây này, không kill tiến trình Qoder Desktop/CLI khác theo tên. stdout/stderr
được drain đồng thời và giới hạn 1 MB mỗi luồng; stderr không là bản dịch.

| Mã | Cách xử lý |
|---|---|
| CLI_NOT_FOUND | Kiểm tra CLI đã cài hoặc chọn `.exe` trong Settings |
| AUTH_REQUIRED | Đăng nhập CLI bằng trình duyệt rồi chủ động Continue |
| MODEL_UNAVAILABLE | Kiểm tra catalog/model/identity; không tự đổi model |
| QUOTA_OR_CREDITS_EXCEEDED | Chờ quota/kiểm tra Credits, giữ checkpoint |
| TIMEOUT / CANCELLED | Kết quả có thể chưa rõ; không tự gửi lại |
| INVALID_RESPONSE | Giữ receipt/input; không nhận JSON/ID sai hoặc bị cắt |
| REQUEST_BUDGET | Chạm giới hạn lệnh cục bộ; chủ động Continue hoặc chỉnh hạn mức Qoder |
| PROVIDER_ERROR | Xem diagnostic, kiểm tra cấu hình/kết nối rồi quyết định |
| BLOCKED_BY_ISOLATION | Kiểm tra hooks/plugins; ứng dụng không tự cấp quyền |
| QODER_RESULT_UNKNOWN | Xác nhận rõ trước khi gửi lại và tiêu Credits lần nữa |

Không tự mua Credits, bật billing, đổi provider hoặc retry toàn chương.
Credits không được suy ra từ số invocation. Timeout/hủy có thể vẫn bị tính phí.

Nếu bản EXE đầu báo MODEL_UNAVAILABLE khi chọn Sonus dù đăng nhập/catalog hợp
lệ, dùng EXE sửa lỗi trong `QODER_SONUS_FIX.md`. Đóng bản cũ, mở bản mới và
chủ động Continue run đã lưu. Không xóa cache/journal hoặc đổi sang Ultimate
để né lỗi. Batch bị bản cũ loại sau khi CLI trả thành công không có response
để replay; Continue phải gửi lại phần pending, có thể tiêu Credits thêm.

Tài liệu Qoder có [headless automation](https://docs.qoder.com/cli/run-in-scripts).
[Terms of Service](https://qoder.com/product-service) mục 3.2.10 có giới hạn rộng
về scrape/mine/distil output; đã báo điểm chưa rõ về phạm vi desktop translator
trước triển khai. Việc chạy kỹ thuật thành công không xác nhận cách diễn giải
điều khoản; dùng tài khoản cá nhân qua CLI chính thức, không cung cấp endpoint
nội bộ, cookie, cơ chế né quota hoặc chia sẻ credential.

## Chạy và build

Chạy source như trước: `run_source.bat`. Build theo `build.bat`; không cần đổi
spec, PyInstaller tìm module qua import tĩnh. Qoder CLI/credential không nằm
trong gói; máy chạy EXE phải có CLI và phiên đăng nhập riêng.

Smoke có thể chạy từ source hoặc EXE bằng `--qoder-check --run <output/QA-run>
--phase <tên-mới> --action gui|fixture`. `fixture` không gọi Qoder/model thật;
`live` chỉ dành cho test có ledger giới hạn và sự cho phép rõ ràng. Không gọi
live như regression mặc định. Xem `QODER_CLI_REPORT.md` cho kết quả và EXE cuối.
