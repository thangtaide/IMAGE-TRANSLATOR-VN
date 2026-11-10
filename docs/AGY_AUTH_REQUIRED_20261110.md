# AGY: xác thực hết thời gian chờ — 10/11/2026

## Nguyên nhân đã xác định

Attempt `b9a0f3df379d4c019e44445fee05aece`, provider AGY Gemini,
model gemini-3.8-flash-medium. Metadata ghi process_started=true, exit_code=1,
elapsed_seconds=60.5, configured_timeout=300, watchdog=315; outcome paused_provider.

Người dùng cho phép riêng giải mã stdout/stderr cục bộ trong RAM. Terminal
result: status ERROR, error `authentication failed or timed out`, finished_reason
error. Stderr yêu cầu đăng nhập OAuth, chờ60s rồi báo `authentication timed out`.
Đây là lỗi xác thực CLI, không phải timeout300s của batch hoặc bằng chứng quota.
Backend nhận OCR hay chưa vẫn UNKNOWN; không gọi API để xác minh.

Chỉ giải mã đúng hai artifact của attempt được cho phép bằng DPAPI CurrentUser;
không ghi plaintext, token hoặc URL OAuth đầy đủ. Ciphertext gốc giữ nguyên.
Diagnostic hỗ trợ nằm trong logs/inspect_authorized_agy_attempt.py, không phải
công cụ replay sản phẩm; không gửi lại payload hoặc tạo invocation dịch.

CLI hiện tại `agy --version`:1.5.4; --help đọc được. Đây chỉ là capability
metadata, không chứng minh xác thực. Không đọc token profile hoặc đổi cấu hình.

## Sửa code

- providers/agy.py: nhận các thông báo authentication required/failed/timed out
  trong trường error của terminal thất bại, trả AUTH_REQUIRED. Giữ xử lý quota,
  rate limit, guard/tools/schema/ID/numeric và chặn retry như cũ.
- ui/provider_notice.py: AGY AUTH_REQUIRED có tiêu đề và chỉ dẫn đăng nhập
  thủ công bằng agy; không đề xuất đổi key/model hoặc bật provider khác.
- Không đổi journal, state paused_provider, input/output, model hay auth files.

Kiểm tra cú pháp AST thành công. Theo yêu cầu không chạy test của người dùng,
không chạy unittest/pytest/GUI/E2E hoặc gửi dịch. Build chỉ đóng gói; kết quả
binary thực tế và SHA256 ghi trong BUILD_REPORT.md. Đăng nhập/resume thật còn
do người dùng thực hiện, chưa nghiệm thu dịch thành công trên máy này.

## Cách xử lý trên máy này

1. Mở PowerShell dưới đúng tài khoản Windows đang chạy ứng dụng.
2. Chạy `agy`, hoàn tất đăng nhập theo hướng dẫn trong CLI/trình duyệt.
3. Khi đã vào giao diện AGY, thoát CLI; không cần gửi prompt dịch để đăng nhập.
4. Mở binary mới hoặc run_source.bat, rồi chủ động Tiếp tục công việc đã dừng.

Phiên đăng nhập được quản lý bởi AGY. Không chuyển token bằng tay, không xóa
auth profile hoặc thay API key. Xem
[Authenticate chính thức](https://antigravity.google/docs/install) và
[CLI getting started](https://antigravity.google/docs/cli/tutorial).

## Git & Fork Handoff

Root D:/WebLocal/IMAGE-TRANSLATOR-VN-main; baseline đã có các sửa setup/build/
export trước lượt này. Không có .git: GIT_REPOSITORY_NOT_INITIALIZED, branch/
HEAD/index không có; không thể báo git diff/check/stat/check-ignore PASS.
Người dùng review/tạo repo bằng Fork. Không stage, commit hoặc đổi lịch sử.

Review source: providers/agy.py, ui/provider_notice.py; docs: PROJECT_STATUS.md,
BUILD_REPORT.md, docs/TROUBLESHOOTING.md và báo cáo này. .gitignore không đổi.
Không commit logs/DPAPI/private config/token, models, venv, build/dist/output.
Không thêm secret vào source/docs. Evidence gốc:
logs/diagnostics/agy_errors/b9a0f3df379d4c019e44445fee05aece/.
Message đề xuất: `fix: classify AGY authentication timeouts and explain login`.
NO_COMMIT, NO_PUSH, NO_TAG, NO_DESTRUCTIVE_GIT.
