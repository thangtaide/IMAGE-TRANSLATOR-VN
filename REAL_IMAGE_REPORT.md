# Kiểm thử corpus ImgTest — 06/11/2026

## Nguồn và phạm vi

Người dùng cung cấp **D:\TransTool\ImgTest**, 61 file JPG chứa panel truyện Trung, bong bóng thoại, bảng tên, chữ nhỏ/chữ dọc và nền màu. Đã lưu kích thước/hash trước chạy tại `output/real-image-validation-20261106/input-inventory.json`, contact sheet cùng thư mục. Ảnh cao nhất 1000 px; không coi đây là corpus ảnh dài gốc.

Không mock OCR/dịch, không nhập bản dịch hoặc output OCR thủ công. Dùng ProcessingManager chuẩn, PaddleOCR CPU, Argos zh→en→vi, OpenCV và Pillow. Audit subclass chỉ ghi lại output/lỗi từ `super().translate`, không thay kết quả. SQLite riêng cho QA.

## Kết quả batch và lỗi kỹ thuật đã sửa

| Lượt | Hoàn thành | Lỗi | Nguồn giữ hash | Bằng chứng |
| --- | --- | --- | --- | --- |
| Trước sửa số | 58/61 | 3 | 61/61 | `output/real-image-validation-20261106/report.json` |
| Sau sửa số | **61/61** | **0** | **61/61** | `output/real-image-validation-20261106-numeric-fix/report.json` |

Lượt đầu lỗi ở `312zUOpDm`, `dOhv69PdQ`, `FzJJO98a9`: Argos biến đổi marker bảo vệ số. Hai vùng OCR chỉ chứa `2` và `$3333` (có thể là false positive trên nét vẽ); việc dịch rồi vẽ lại chúng không cần thiết. Pipeline hiện giữ nguyên pixel vùng chỉ có số/ký hiệu. Số trong câu giữ nguyên dạng khi gửi model, sau dịch kiểm tra chuỗi số gồm thứ tự/số lượng/định dạng; mất/đổi/thêm số vẫn bị chặn. Marker thuật ngữ/tên riêng giữ nguyên. Cache/provider/job revision thay đổi để không dùng lại kết quả theo quy tắc cũ. Không hardcode bản dịch chương hoặc số cụ thể.

Lượt sau xử lý 94.923 giây, peak process working set 2,283,753,472 byte (~2.13 GiB). Mọi ảnh xuất giữ kích thước. Có **75 vùng chữ được dịch**, 2 vùng chỉ có số/ký hiệu giữ nguyên; 24 ảnh raw OCR không phát hiện chữ, thêm một ảnh chỉ có vùng số nên tổng 25 ảnh không cần vẽ bản dịch. Không gọi 61 ảnh là 61 bản dịch ngữ nghĩa đạt.

Mỗi ảnh có thư mục `image-001` … `image-061` chứa source/OCR JSON/translation JSON/mask/erased/final/report. `translated/` chứa ảnh xuất trực tiếp từ pipeline. Mask và erased của lượt sau được tạo từ đúng vùng chỉnh sửa trong metadata; các vùng số bảo toàn không bị đưa vào mask. Evidence lượt FAIL cũ giữ nguyên.

## GUI và EXE

- GUI nút Bắt đầu thật với 61 ảnh gốc, QThread/OCR/MT thật: **61 hoàn thành, 0 lỗi, 61 hàng bảng, progress 100%, 494 heartbeat**, `output/real-image-validation-20261106-numeric-fix/gui-batch/report.json`, screenshot `window.png`. Đây là Python MainWindow dùng đúng mã nguồn build, cache riêng.
- Chính EXE cuối chạy E2E trên `0H9l8tBjR.webp-t.w1280.jpg`: **PASS kỹ thuật**, `output/e2e-validation/20261106T102347Z-9dbcba/report.json`; giữ 1280×1000 và hash nguồn. Không chỉ kiểm tra exit code build.
- Chính EXE cuối chạy workflow nút pause/resume/cancel/retry/skip/error/preview/zoom/settings/verify model: **PASS**, `output/gui-workflow/20261106T102357Z-67edd2/report.json`. Input của bài điều khiển này là fixture tổng hợp và ảnh hỏng cố ý; không gán nhãn ảnh truyện cho nó.
- Stress ảnh dài **1280×3385** ghép bốn panel thật: E2E **PASS kỹ thuật**, `output/e2e-validation/20261106T102242Z-5024d1/`. `output/real-image-validation-20261106-numeric-fix/long-derived/provenance.json` ghi rõ ảnh ghép thử chia tile, không phải strip dài nguyên bản của người dùng. Tọa độ/confidence/kích thước và reuse model được runner kiểm tra; chưa có ground truth để chấm accuracy/dedup toàn bộ chữ.

## Chưa nghiệm thu chất lượng

Đã xem trực tiếp ảnh cuối của bong bóng nhọn, bảng địa danh dọc và credit/chương. Có các hạn chế rõ:

- `第13话` → `Rule 13` → **“Nguyên tắc 13”**: số giữ đúng nhưng nghĩa “chương/tập” sai. `numeric-literal-probe.json` lưu suy luận thực nghiệm.
- Credit/tên riêng bị lược hoặc dịch thành `Name`, `Lỗi`, `I wassa`; không đạt yêu cầu dịch đầy đủ/nhất quán.
- Một số nét màu và dấu câu ngoài polygon OCR vẫn còn. Kết quả mask **600→0 trên fixture trắng** không chứng minh xóa sạch trên truyện thật.
- Có OCR false positive/nhận nhầm, chưa có bản chép chuẩn để đo recall; 24 ảnh không có OCR chưa được chấm từng ảnh để khẳng định không sót chữ.
- Bố cục Việt có thể khác bố cục chữ dọc, chưa đánh giá đầy đủ mọi panel. Metadata nhãn PASS chỉ xác nhận công đoạn chạy/xuất/giữ nguồn, không chấm bản dịch hay thẩm mỹ.

**Kết luận: PASS kỹ thuật batch và bảo toàn dữ liệu; chất lượng ngữ nghĩa/OCR/mask truyện chưa đạt nghiệm thu.** M2M100 vẫn thiếu trọng số và mạng thực thi hợp lệ. Cần kiểm thử model trực tiếp và corpus có ground truth trước khi công bố chất lượng sản phẩm.
