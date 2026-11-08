# Hướng dẫn sử dụng Image Translator VN

## Online Free — Stage3A (bản source)

1. Chạy run_source.bat; chọn nguồn ảnh, output và OCR như trước.
2. Chọn **Online Free**, provider **MyMemory** ở khu vực OCR/dịch chung3tab.
   Đây là thao tác cho phép gửi text OCR của job tới MyMemory; ảnh ở trên máy.
   Dịch vụ có thể lưu/chia sẻ text với đối tácMT. Không dùng cho text bí mật.
3. Bấm Bắt đầu/Tải và dịch sau khi chọn đúng ảnh/chương. Dán URL hay phân tích
   chương không tự gửi OCR. Chỉ chương được chọn mới xử lý; không tự tải model.
4. MyMemory ẩn danh miễn phí5.000ký tự/ngày; app chia nhỏ theo giới hạn byte,
   giãn request. Không hiện số lượt còn lại vì không có số liệu đáng tin.
5. Khi QUOTA_EXCEEDED/RATE_LIMITED/AUTH_REQUIRED: công việc dừng an toàn, giữ
   ảnh/output/checkpoint. × chỉ đóng notice, không resume hoặc đổi phương thức.
6. Trong cùng phiên, có thể chọn Offline hoặc giữ Online Free rồi bấm Tiếp tục.
   Chỉ phần chưa hoàn tất chạy; đổi phương thức tạo recipe mới, kết quả trước đó
   giữ receipt riêng. URL nhiều chương: resume chương đang dở từ cache; những
   chương chưa bắt đầu phải chọn/bắt đầu sau, không tự tải tiếp.

Sau khi đóng app, pending UI cho thao tác đổi provider chưa được khôi phục tự
động. Cùng recipe có thể khôi phục/bỏ qua thành công theo checkpoint/hash;
**không đổi provider rồi chạy cảfolder nếu chỉ muốn retry pending**. Giữ cache và
manifest để bổ sung cross-restart resume ở Stage3C. Không sửa checkpoint bằng tay.

Numeric guard giữ nguyên: bản dịch ngày hợp nghĩa có thể đổi thứ tự token số
và bị reject. Đọc diagnostic/Trang cần xem lại; fallback không được gọi là dịch
thành công. Stage3A không tự retry trang111 hoặc dùng handler ngày QA.

LibreTranslate custom cũ chỉ dùng khi bạn có endpoint tựhost/miễn phí được phép;
không coi libretranslate.com hoặc mọi mirror là miễn phí. Không có Gemini ở Stage3A.
Chi tiết: STAGE3A_ONLINE_FREE_TRANSLATION_REPORT.md. Chưa build EXE mới.

## Stage3 — kết quả nghiên cứu, chưa đổi cách dịch

Benchmark150 mẫu có0 bản dịch tham chiếu được người rà soát độc lập. Những
thử nghiệm ở `qa/` **chưa có trong GUI**, không đổi Argos/default/numeric guard
và không tự cài/tải model. App/source/EXE chạy như Stage2; chương274872 vẫn có
120 output,119 hoàn tất pipeline và1 ảnh gốc dự phòng111 cần xem lại.

Không đổi length_penalty sang1.0 theo hai ví dụ Name đẹp hơn: thử nghiệm có
thêm số ngoài nguồn ở holdout. Handler ngày QA tạo được `Từ ngày20/5 đến ngày30/5`
nhưng chưa đủ điều kiện dùng production. Không sửa cache/checkpoint hoặc bấm
Retry lặp lại để ép ảnh111 thành công; model/input hiện tại vẫn có thể sai như cũ.

Muốn hỗ trợ đánh giá ngữ nghĩa, mở
`logs/stage3-translation-quality-20261107T204426Z/human-reference-template.csv`:
xem source và ảnh, điền bản dịch/biến thể chấp nhận,người/ngày xác minh trước
khi xem `outputs-for-review.csv`. Bản dịch tham chiếu đang trống; output Argos
hoặc ứng viên không tự trở thành đáp án chuẩn. Chưa có form review online hay
quy trình tải dữ liệu lên dịch vụ bên ngoài.

OPUS-MT zh-vi,M2M100,NLLB chỉ được tra cứu nguồn/metadata; chưa tải trọng số,
chưa đo chất lượng trên máy. Việc thử model mới cần chấp thuận riêng. Báo cáo:
[STAGE3_TRANSLATION_QUALITY_REPORT.md](STAGE3_TRANSLATION_QUALITY_REPORT.md).

## Cập nhật Stage 2 — 08/11/2026

Chương274872 đã phục hồi đúng hai trang từ cache: **120/120 file**,119 ảnh hoàn
tất pipeline bình thường,1 ảnh gốc dự phòng,1 trang cần xem lại. Trang74 giữ
nguyên byte ảnh sau khi bỏ vùng OCR giả theo bằng chứng; **không có văn bản
cần dịch**, không gọi provider, không phải fallback. Trang111 vẫn sai bản dịch
ngày tháng, dùng `original/0111.jpg`, nằm trong needs_retry. Lần Retry tiếp theo
chỉ chọn trang111; không tự tải CDN. Bản dịch đúng cho trang111 chưa có.

Override OCR nằm ở `overrides/ocr_regions.json` cạnh source/data root, không ở
cache OCR. Mỗi mục có id/version, hash ảnh, text/polygon chính xác, action,
reason/evidence và `enabled`. Profile hiện chỉ có vùng hoa văn đã xác minh.
Tắt/thu hồi bằng `enabled=false`; đổi phiên bản khi sửa bằng chứng. Không dùng
profile để bỏ chữ khó dịch. Không có editor vùng OCR trong GUI ở Stage2.

Hash/polygon không khớp gây diagnostic/fallback, không chọn vùng gần giống.
Locator tương đối chỉ định đúng ảnh để phát hiện hash bị đổi; không hardcode
tên0074 trong engine. Cùng hash vẫn phải khớp text/polygon. Cache OCR gốc không
sửa. Override được ghi receipt trong metadata, thay fingerprint riêng ảnh đó,
không đổi job ID hoặc fingerprint118 ảnh cũ. Thu hồi có hiệu lực ở lần xử lý
ảnh đó tiếp theo; không tự xóa output đã xuất hoặc tự đưa ảnh thành công vào
needs_retry. Nếu cần đánh giá lại ảnh đã xong sau khi sửa profile, dùng công cụ
phục hồi có phạm vi rõ hoặc job/thư mục mới; không ghi đè output cũ.

Khi không còn vùng cần dịch và giữ định dạng gốc, pipeline sao chép nguyên byte
nguồn vào **output hoàn tất bình thường**. Metadata `no_text_to_translate=true`
và cảnh báo nói rõ; khác với sao chép do lỗi `FALLBACK_ORIGINAL`. Tổng số hoàn
tất pipeline có thể gồm ảnh không có chữ, không phải số ảnh đã dịch văn bản.

Numeric guard hiện `literal-numbers-v2-signed`: giữ chặt dấu số, không tự chuẩn
hóa ngày hoặc thập phân. Dữ liệu signed legacy không được tin mù quáng; cache
có dấu dùng namespace v4. Không xóa cache v3 unsigned và không xử lý lại118
output cũ. Lỗi trang111 mới đã xác nhận pivot dịch sai, không phải lý do để tắt
validator. Xem [báo cáo Stage2](STAGE2_NUMERIC_OCR_RECOVERY_REPORT.md).

Stage2 chỉ có ở source hiện tại, dùng **run_source.bat**. EXE cũ và hướng dẫn
Stage1 dưới đây giữ nguyên; chưa có bản build mới, portable management hoặc
benchmark chất lượng Stage3.

## Chạy ứng dụng

Chạy **run_source.bat** để dùng source mới nhất trong môi trường đã cài.
Các launcher và bốn EXE cũ được giữ nguyên. EXE cũ chưa có diagnostic/fallback
Stage 1; chưa build EXE mới cho thay đổi này. Hướng dẫn setup máy phát triển
trong README và các báo cáo cài đặt vẫn áp dụng.

## Chọn nguồn

- **Ảnh đơn**: chọn ảnh, đọc danh sách, chọn thư mục kết quả rồi dịch ảnh đã có.
- **Thư mục ảnh**: chọn nguồn và đích riêng biệt, cấu hình quét thư mục con,
  OCR và Offline, rồi Bắt đầu dịch.
- **Link truyện online**: nhập URL topic/chương Kuaikan, Phân tích link, chọn
  chương cần xử lý rồi Tải và dịch. Dán/phân tích URL không tự tải ảnh.
  Chính sách hiện tại `default_allow_public` là lựa chọn của chủ ứng dụng,
  không phải website cấp phép. Nội dung khóa/hạn chế và chặn kỹ thuật vẫn dừng.

Pipeline truyện và ảnh đơn sử dụng Offline. Chế độ Online của tab thư mục
chỉ dùng khi bạn chủ động chọn; không tự bật Online để xử lý lỗi số.

## Model

Dùng **Quản lý mô hình AI** để xem model đã cài, kiểm tra hoặc chủ động tải
model được ứng dụng liệt kê. Không có model M2M100 cục bộ thì không coi engine
đó đã sẵn sàng. Không tải lại model đang hợp lệ. Job Offline không tự tải model.
Thiếu model hoặc runtime có thông báo rõ; Stage 4 về first-run/portable dependency
management **chưa thực hiện trong lượt Stage 1**.

## Tiến độ và trạng thái ảnh

Progress lấy từ tác vụ thật. Tạm dừng có hiệu lực tại checkpoint; hủy chờ tác vụ
đang chạy về checkpoint và giữ file đã hoàn thành.

| Trạng thái | Ý nghĩa |
|---|---|
| `TRANSLATED_SUCCESS` | Hoàn tất pipeline với các vùng chữ cần dịch đã qua kiểm tra; ảnh không có chữ cần dịch cũng có thể hoàn tất |
| `PARTIAL_TRANSLATION` | Dự phòng cho bản dịch một phần; Stage 1 chưa tự xuất dạng này |
| `FALLBACK_ORIGINAL` | Bản sao nguyên byte của ảnh nguồn hợp lệ, chưa phải bản dịch hoàn chỉnh |
| `FAILED_NO_OUTPUT` | Chưa có output hợp lệ, ví dụ ảnh hỏng/mất hoặc không ghi được file |

Stage 1 chọn cách bảo toàn toàn ảnh: nếu một vùng lỗi, không inpaint/chèn bản
dịch chưa hợp lệ vào ảnh xuất. Nếu render sau đó lỗi, bản dự phòng vẫn lấy từ
**nguồn**, không lấy ảnh đã xóa chữ dở. Không có thao tác sửa số tự động.

Chương đủ file nhưng còn ảnh dự phòng có trạng thái **COMPLETED_WITH_WARNINGS**,
không phải dịch thành công toàn chương. Tổng kết tách dịch hoàn chỉnh, dịch một
phần (hiện bằng 0), ảnh gốc, không output, bỏ qua checkpoint và cần xem lại.

Trong tab thư mục, file dự phòng có `.fallback-original` trong tên và giữ định
dạng nguồn. Trong output truyện, chúng ở `run_<job>/original/0001.jpg`…; ảnh dịch
ở `run_<job>/0001.jpg`… Thứ tự trang vẫn theo số trong manifest. Chưa có chế độ
gộp hai thư mục thành một trình đọc truyện. Sau retry, bản dự phòng cũ vẫn giữ
lại; manifest trỏ tới bản mới nếu dịch thành công. Không đếm số file trong cả
cây thư mục để suy ra số trang hiện hành: dùng manifest/tổng kết ứng dụng.

Ảnh thành công có checkpoint/hash hợp lệ luôn được giữ nguyên, kể cả config
cũ có `skip_success=false`. Ô bỏ qua thành công được khóa bật để biểu thị việc
bảo toàn này. Muốn tạo phiên bản khác, đổi thư mục xuất hoặc cấu hình ảnh/model;
không sửa/xóa file kết quả cũ để ép retry.

## Xem lỗi và diagnostic

Bấm **Trang cần xem lại / log** sau khi job xong. Danh sách có số trang, file,
giai đoạn, provider nếu biết, mã lỗi, loại output và đường dẫn diagnostic.
Chọn một dòng rồi **Mở thư mục log của dòng chọn**. Nút Mở kết quả mở thư mục
đích. Tab thư mục vẫn có xem trước bằng nhấp đúp hàng.

Diagnostic nằm ở `logs/diagnostics/<job_id>/errors.jsonl`. Lỗi download trước
khi có pipeline job dùng transfer job ID riêng; trường chưa xác định để trống,
không tự tạo tên ảnh hay raw target. Mã lỗi tham khảo
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).

Mỗi job giới hạn 1.000 record/4 MB, văn bản tối đa 2.048 ký tự/trường, tối đa
100 numeric tokens. `truncated_fields` cho biết trường bị cắt. Nếu không ghi
được log, ảnh dự phòng vẫn được thử xuất, giao diện báo vấn đề diagnostic.
Record được flush/fsync; nếu mất điện để lại dòng cuối dở, file cũ giữ nguyên,
record mới sang file `errors-<id>.jsonl`. Không sửa dữ liệu lỗi cũ.

Trong **Cài đặt**, bỏ chọn “Lưu văn bản OCR/bản dịch bị lỗi…” để không ghi mới
source/target/numeric tokens vào diagnostic. Việc này không xóa log đã có,
không đổi job identity và không gửi log ra Internet. Hãy kiểm tra nội dung riêng
tư trước khi chia sẻ diagnostic. Lượt lỗi cũ không có raw target thì không thể
khôi phục lịch sử bằng cách giả định bản dịch của lượt mới là bản dịch cũ.

## Retry ảnh cần xem lại

- Tab thư mục: **Thử lại ảnh lỗi / chưa xong** chỉ gửi danh sách ảnh cần retry.
- Tab ảnh đơn/URL: **Thử lại…** dùng manifest và ảnh cache đã xác minh, chỉ gửi
  trang thiếu output/lỗi/fallback vào ProcessingManager. Không gọi HTTP hoặc
  tải CDN trong nhánh retry này. Trang thành công giữ nguyên.
- Cache thiếu/hỏng hoặc output bị sửa thì retry dừng rõ ràng, không tải lại,
  không ghi đè. Chương chưa từng tải/cache chưa thể dùng retry này; bắt đầu
  job nguồn tương ứng để lấy nguồn hợp lệ trước.
- Chỉ retry khi đã có cách khắc phục. Dịch lại cùng input/model có thể lặp lại
  lỗi cũ. Chưa có trình sửa OCR/bản dịch theo vùng trong Stage 1.

Hai trang thực tế `0074.jpg` và `0111.jpg` của chương 274872 **chưa chạy phục
hồi** trong Stage 1. Cơ chế override OCR và phân tích raw target thuộc Stage 2.

## EXE trên máy khác, sao lưu và giới hạn

Onedir phải được sao chép **cả thư mục**, không chỉ file EXE. Bản cũ có thể cần
model/tài nguyên và thư mục dữ liệu đi kèm đúng bố cục hiện tại; chưa nghiệm thu
Windows sạch hoặc đường dẫn dữ liệu `%LOCALAPPDATA%` mới. Không có
`PORTABLE_EXE_PASS`, không tự pip install hoặc tải DLL vào EXE.

Khi sao lưu, đóng job an toàn rồi giữ source, model, config, toàn bộ cache/SQLite
(cả WAL/SHM nếu có), manifest, output và log. Không chỉ chép hai ảnh lỗi: để
resume cần receipt và database đúng job. Không xóa ảnh nguồn hoặc cache của
chương còn fallback. Bản dịch Argos pivot vẫn có hạn chế ngữ nghĩa; kiểm tra
preview, đặc biệt tên riêng/ngày tháng. Công việc chất lượng dịch và portable
EXE là các stage sau, chưa thay model/provider mặc định ở Stage 1.
