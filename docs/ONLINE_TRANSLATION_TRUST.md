# Tin cậy bản dịch online và AGY Flash Low — 11/11/2026

Theo yêu cầu người dùng, **tất cả provider có `online=True` không bị validate
lại nội dung bản dịch**: AGY Batch/Whole, Gemini API, MyMemory, LibreTranslate
và các adapter online cùng giao diện. Offline giữ validator hiện có.

## Hành vi hiện tại

- Không phát NUMERIC_MISMATCH vì số, dấu, thứ tự số hoặc cách viết số trong
  phản hồi online khác OCR. Không từ chối bản dịch online vì thiếu/đổi marker
  thuật ngữ. Marker đã biết vẫn được khôi phục theo glossary nếu có.
- Giữ kiểm tra giao thức/schema/ID/số vùng, phản hồi rỗng, lỗi provider, quota,
  tool guard và tính toàn vẹn cache/checkpoint. Đây là hợp đồng dữ liệu để
  nhận/render phản hồi, không phải đối chiếu lại nội dung dịch với OCR.
- Bước xóa chữ và layout vẫn báo lỗi khi không thể tạo ảnh hợp lệ. Không thay
  thuật toán OCR, mask/inpaint/renderer để che lỗi ảnh.
- Cache hợp lệ đã được tạo trước đây vẫn dùng được; không đổi provider
  identity, cache key, work recipe hoặc namespace Whole chỉ vì giảm kiểm tra
  nội dung. Không xóa DB/journal/receipt hay tự chạy lại các ảnh thành công.
  Nhánh legacy kiểm tra dấu của cached target chỉ còn áp dụng offline; online
  không gọi lại provider chỉ vì target được tin cậy có dấu khác nguồn.
- `last_attempt.content_validation_applied` và metadata ảnh
  `translation_content_validation_applied` ghi nhận chính sách khi có lần dịch.
  Validator version cũ vẫn nhận diện implementation offline. Prepared Whole
  render có thể ghi null vì bản dịch đã nhận ở bước trước, không có lần dịch
  tại ProcessingManager render.

Điều kiện dựa vào cờ provider thật, không chỉ tên mode: provider offline trong
Auto Fallback vẫn được kiểm tra; provider online trong Whole với chế độ render
Offline vẫn được tin cậy.

## Model đang lưu

`config/settings.json` đã đổi **duy nhất** `agy_model` từ
`gemini-3.8-flash-medium` sang **`gemini-3.8-flash-low`**. Source và EXE cùng
đọc cấu hình tại root suy ra từ module/executable. Không thay tài khoản/token.

Lệnh danh mục `agy models` trả exit 0 và có slug Low. Kiểm tra command trong
source và EXE xác nhận cả `--model gemini-3.8-flash-low` và `--effort low`.
Ở lượt thay đổi ban đầu chỉ lưu Low trong cấu hình hiện tại. Lượt điều tra
tiếp theo đã đặt Low làm default source/provider và chặn snapshot cửa sổ cũ
ghi đè model mới; xem [báo cáo cập nhật](AGY_RECURRING_20261111.md).
Đóng/mở lại bản EXE mới để nạp lựa chọn.

## Diagnostic job 66f9042a…

File người dùng yêu cầu là `errors.jsonl`, không tồn tại `errors.json`. Hai
đường dẫn người dùng gửi trùng nhau. Có 6 record: một lỗi số ảnh 0020, ba lần
quota lịch sử ở 0067, hai lỗi inpaint ở 0076/0111. Khi điều tra lần này job đã
`completed_with_warnings`: **141 done / 3 fallback_original**, không còn dừng
ở Trang 67. Không suy ra tình trạng quota mọi request tương lai từ trạng thái này.

**0020:** người dùng cho phép giải mã riêng attempt
`cacaa9444c8e42b69766db564392484b` bằng CurrentUser DPAPI trong RAM. Hash/length
khớp capture, parser ACCEPT 58 vùng; ID vùng 1 khớp source hash/OCR thực tế.
Nguồn `生命值归零…24H` chứa “归零” nghĩa là “về 0”. Guard cũ so `['24']` với
`['0','24']`, báo sai dù AGY diễn đạt đúng. Không lưu raw stdout hoặc target
plaintext bị che; chỉ giữ tóm tắt số và ảnh render được yêu cầu.

Sau chính sách mới, năm target của riêng ảnh 0020 từ phản hồi cũ được nhận
nguyên nội dung, xóa chữ/render thật bằng code hiện có. JPEG đã xem ở 1280×720:
chữ Việt đọc được, dòng có “về 0…24H”, không chồng/cắt. Không ghi production DB
hoặc thay ảnh đã thành công.

[Ảnh 0020 render lại](../output/ai-numeric-policy-20261110T185605Z/recovered-0020/final.jpg)

**0076:** mask rỗng tại OCR region 3, email watermark, box
`(1109,32)–(1277,65)`. **0111:** mask rỗng tại region 2, nhãn Latin
`REALTUME4WD`, box `(977,541)–(1200,663)`. Xem crop ảnh nguồn, tái hiện
`erase_text` trong RAM và đối chiếu cache: cả hai target giống hệt nguồn,
nhưng pipeline vẫn yêu cầu xóa nên guard TEXT_REMOVAL_FAILED chặn. Đây là lỗi
xử lý ảnh/vùng giữ nguyên, không phải validator bản dịch hoặc AGY dịch lỗi.
**Hai lỗi này chưa sửa**, không bỏ qua guard xóa chữ trong yêu cầu hiện tại.
Crop chẩn đoán: `output/diagnostic-check-20261110T185127Z/`.

## Kiểm thử

- **209 PASS**: AGY/diagnostic, Gemini API, Online Free, multipage/resume,
  numeric offline, Stage2, selective recovery và Whole Chapter.
- **6 PASS** bổ sung: các engine online tin cậy số/chữ số 0 được viết bằng
  chữ, glossary paraphrase/marker, offline vẫn chặn, phản hồi rỗng và guard
  của AGY Whole thật (chỉ constructor lookup/hash, không chạy CLI).
- Test bổ sung tái hiện một cache miss không cần thiết với target online có
  dấu số: trước sửa 1 FAIL, sau sửa PASS. Chạy lại **119 test liên quan PASS**
  sau thay đổi này, không cộng trùng vào tổng 283 test khác nhau.
- **68 PASS**: core và error/fallback/offline.
- Tổng **283 PASS / 0 FAIL / 0 SKIP** trong các suite đã chạy. Không phải full
  regression toàn project. Các test được đổi kỳ vọng vì người dùng chủ động
  thay chính sách; các test offline vẫn kiểm tra từ chối số/marker sai.
- Source GUI smoke PASS, không gọi model. Source đọc Low/effort low đúng; source-gui-final kiểm tra cache dấu số.
- EXE mới thực sự khởi động GUI trên Windows, smoke PASS và exit 0. Giao diện
  hiện Low; dialog/menu/combo hoạt động, không cắt nhãn nút. Chính code đóng
  gói nhận target fixture có số khác OCR mà không chạy content validator,
  trong khi fixture offline vẫn bị chặn.
- Không gọi AGY dịch/API thêm trong lượt đổi chính sách này. Danh mục model
  là lệnh lookup, không phải một lượt sinh bản dịch. Smoke policy dùng target
  fixture rõ ràng, không giả là dịch vụ AGY thật hoặc OCR/inference thật.
- Không tuyên bố đã nghiệm thu chất lượng dịch của Low bằng request mới,
  hoặc đã sửa hai lỗi mask chỉ vì các test chính sách PASS.

Log/XML: `logs/online-trust-regression.*`, `logs/online-trust-policy.*`,
`logs/online-trust-offline-regression.*`, `logs/online-trust-source-gui.log`.
Evidence: `output/ai-numeric-policy-20261110T185605Z/`, có cấu hình thay đổi
(chỉ tên model), catalog check, recovery 0020, source/frozen GUI report/ảnh.

## Bản EXE mới

Đã chạy **build.bat** hiện có; pip check và PyInstaller thành công. Không
đóng gói cache/output/SQLite/settings cá nhân, không thay EXE cũ.

`dist/ImageTranslatorVN-20261110T191355235181Z/ImageTranslatorVN-20261110T191355235181Z.exe`

Giữ nguyên thư mục `_internal` bên cạnh EXE và models ngoài gói theo hướng dẫn
hiện có. Smoke thực tế bằng `--cache-ui-check --gui-only`, DB/output QA riêng,
`persist_settings=False`; không chạy pipeline production hoặc tiêu thụ request.
Evidence frozen: `exe-gui-final/report.json`, `exe-gui-final/gui-top.png` trong thư mục trên.
Build log: `logs/build-ImageTranslatorVN-20261110T191355235181Z.log`.

## Git & Fork Handoff

Root tự xác định từ workspace/Git, branch main. Baseline đã có 5 file sửa/mới
từ nhiệm vụ quota trước: PROJECT_STATUS, providers/agy, tests/test_agy, báo cáo
quota và fixture quota. Giữ nguyên bản sửa quota, không hoàn tác thay đổi sẵn có.

Thay đổi lượt này: `core/pipeline.py`, `scripts/validate_cache_ui.py`, các test
online/API/multipage/diagnostic/offline-scope, test mới
`tests/test_online_translation_trust.py`, README, PROJECT_STATUS và tài liệu này.
`config/settings.json` là cấu hình runtime được ignore, chỉ thay một field model.
Không đổi `.gitignore`; không đưa screenshot/log/DB/EXE hoặc dữ liệu truyện vào
source review. Core OCR/imaging/multipage/whole/resume giữ nguyên hash baseline.
EXE cũ giữ nguyên hash. Kiểm tra Git/diff/ignore/secret ghi `final-handoff.json`.
Commit message gợi ý nếu người dùng review sau:
`Trust online translation content and retain offline validation`.

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT.**
