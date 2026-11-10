# Image Translator VN

- Tự xác định PROJECT_ROOT từ workspace chứa project; code/script dùng ROOT suy ra từ vị trí module, tài liệu/output/test dùng đường dẫn tương đối. Không dùng đường dẫn project của máy cũ.
- Không tạo lại dự án từ đầu. Luôn đọc `PROJECT_STATUS.md` trước khi sửa code.
- Không dùng API trả phí hoặc dịch vụ tự phát sinh chi phí.
- Offline không được gửi dữ liệu lên Internet; không tự tải model trong job.
- Không xóa, sửa hoặc ghi đè ảnh gốc.
- Không giả lập kết quả test. Phân biệt test mock và integration thực tế.
- Luôn cập nhật tài liệu khi thay đổi kiến trúc.
- Sau mỗi nhiệm vụ hoàn thành, cập nhật `PROJECT_STATUS.md` và tài liệu tính năng
  tương ứng theo thay đổi thực tế. Cập nhật hướng dẫn chạy source/EXE nếu cách
  chạy đổi, troubleshooting khi thêm mã lỗi, và AI adapter guide khi đổi nguồn
  truyện. Giữ lịch sử; không ghi test PASS hoặc tính năng hoàn tất khi chưa kiểm chứng.

## Git và checkpoint sau mỗi Stage (từ Stage 3A)

- Trước khi sửa: đọc Git status/branch/root/ls-files và `.gitignore`; lưu baseline
  gồm thay đổi có sẵn, staged files và xung đột. Không hoàn nguyên thay đổi người dùng.
- Sau mỗi Stage: hoàn thành triển khai; chạy test/regression phù hợp; kiểm tra
  bảo toàn dữ liệu; cập nhật PROJECT_STATUS và tài liệu; rà `.gitignore`; kiểm tra
  status, diff/check/stat, untracked files và check-ignore trên runtime mẫu.
- Không ignore source/test/docs/spec/BAT/config mẫu hoặc manifest/checksum cần
  phân phối. Dùng ignore theo đường dẫn runtime; kiểm tra file lớn và secret,
  không in giá trị secret. File runtime đã track chỉ liệt kê, không tự untrack.
- Báo cáo Stage phải có `Git & Fork Handoff`: root/branch, baseline và status cuối,
  thay đổi ignore, kiểm tra ignore, file nên/không nên commit, file cần review,
  diff --check, commit message đề xuất và đường dẫn evidence. Xem
  `docs/GIT_FORK_WORKFLOW.md` để thực hiện đầy đủ.
- Codex chỉ chuẩn bị review: không git add/stage, commit, push, tag/release,
  init, checkout/switch branch, merge/rebase/reset/restore, rm --cached hoặc clean;
  không sửa lịch sử hoặc xóa file để làm sạch status. Nếu repo chưa khởi tạo,
  báo GIT_REPOSITORY_NOT_INITIALIZED và hướng dẫn khởi tạo bằng Fork.
- Dừng thao tác Git có nguy cơ khi repo bất thường hoặc ownership thay đổi chưa rõ.
  Người dùng tự review/stage/commit trong Fork. Commit không phải điều kiện để
  Stage hoàn thành về kỹ thuật. Kết thúc bằng NO_COMMIT, NO_PUSH, NO_TAG,
  NO_DESTRUCTIVE_GIT; không triển khai Stage tiếp theo nếu chưa được yêu cầu.
