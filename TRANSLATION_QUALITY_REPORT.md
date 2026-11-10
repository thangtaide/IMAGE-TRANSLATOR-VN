# Kiểm tra chất lượng Offline — 06/11/2026

## Cập nhật Stage3 — 08/11/2026

Benchmark mới150 mẫu OCR thật,99dev/51holdout,0 independent human references.
Thử4 ứng viên QA; LP1.0 có regression số holdout, handler ngày chưa promotion.
Không đổi production/guard/model/cache hoặc phục hồi111. Chất lượng tổng thể
chưa có đủ reference để công bố accuracy. **STAGE_3_RESEARCH_ONLY**.
Chi tiết đầy đủ và nguồn model direct mới xác minh:
[STAGE3_TRANSLATION_QUALITY_REPORT.md](docs/STAGE3_TRANSLATION_QUALITY_REPORT.md).
Các kết quả24/61 ảnh dưới đây giữ lịch sử, không thay cho benchmark150 mẫu mới.

## Quan sát trên 61 ảnh truyện thật — sau 10:18 UTC

Đã nhận corpus `ImgTest`, suy luận OCR/Argos thật qua pipeline chuẩn. Sau sửa kỹ thuật bảo vệ số, 61 ảnh xử lý xong, 75 vùng chữ dịch thật, 2 vùng số/ký hiệu giữ nguyên; **không nghiệm thu ngữ nghĩa**. Chi tiết `REAL_IMAGE_REPORT.md` và `output/real-image-validation-20261106-numeric-fix/`.

`第13话` → `Rule 13` → **“Nguyên tắc 13”**: bảo toàn số không sửa được nghĩa “chương/tập”. Credit/tên riêng có output `Name`, `Lỗi`, `I wassa`, có lược tên. Đây là lỗi chất lượng quan sát được. Marker số đã được thay bằng kiểm tra số nguyên dạng sau dịch; số mất/đổi/thêm vẫn chặn, glossary marker vẫn được kiểm tra. Không hardcode “Chương 13” để làm đẹp output.

M2M100 vẫn thiếu trọng số và kết nối hợp lệ; adapter tích hợp không có nghĩa model đã suy luận. Bảng so sánh 24 câu giữ M2M100 SKIPPED. Cần model trực tiếp và bộ tham chiếu người dịch trước khi công bố cải thiện chất lượng.

## Cập nhật sau khôi phục — 09:55 UTC

Đã giữ nguyên Argos và chạy lại **cùng 24 câu**, lưu nguồn, chặng Anh và output Việt tại `output/translation-comparison/20261106T095505Z-9ff6bc/results.json/md`. Argos suy luận thật PASS kỹ thuật; câu chào mừng vẫn sai. M2M100 **SKIPPED vì thiếu trọng số**, không tạo output giả hoặc kết luận model mới tốt hơn.

Provider `M2M100` CPU đã tích hợp riêng, lazy/reuse/batch, source prefix/EOS và target prefix, receipt/hash, báo thiếu model an toàn. Các kiểm thử contract dùng mock có nhãn riêng; integration model thật skip. Không cài Transformers hay nâng CT2/setuptools. Nguồn/license/dung lượng, tài nguyên máy và quy trình nhập gói cục bộ trong `M2M100_SETUP.md`. Sandbox hiện chặn HTTPS nên không tải model lớn; người dùng xác nhận chưa có model cục bộ.

Việc cải thiện mask không làm thay đổi bản dịch. Sản phẩm **chưa đạt nghiệm thu ngữ nghĩa**; chờ suy luận M2M100 và đánh giá trên corpus thực tế. Báo cáo phân tích từng chặng bên dưới vẫn có giá trị.

## Phạm vi và bằng chứng nguyên gốc

Đã chạy `scripts/evaluate_translation.py` bằng `.venv`, với **24 câu Trung** ngắn/câu thoại. Không mock, không có bản dịch tham chiếu ép vào model, không chỉnh output sau suy luận.

Kết quả giữ nguyên tại:

- `output/translation-quality/20261106T083515Z-bdb3f5/results.json`: nguồn, từng chặng, token, model metadata/hash, kết quả kiểm tra.
- `output/translation-quality/20261106T083515Z-bdb3f5/results.md`: bảng 24 câu để đọc.

Model: `translate-zh_en-1_9` và `translate-en_vi-1_9`, đều kiểm tra receipt/hash trước khi load, đúng `from_code`/`to_code`. Tổng dung lượng cài khoảng 86.14 MB + 79.38 MB (decimal), CPU/int8.

Thời gian toàn bộ phép kiểm tra **7.041 giây**, bao gồm nạp model, chạy corpus, đối chiếu từng chặng và chạy lại tham số giải mã Argos gốc. Peak working set process **417,226,752 byte**, khoảng 398 MiB; đây là peak của chương trình kiểm tra, không phải mức RAM bảo đảm trên mọi máy.

## Câu lỗi

| Công đoạn | Output thật |
| --- | --- |
| Nguồn | 欢迎使用图像翻译。 |
| zh → en | Image translation is welcome. |
| en → vi | Không có gì. |

Chặng đầu đã diễn đạt thiếu tự nhiên và lệch cấu trúc câu chào mừng. Chặng thứ hai làm mất hoàn toàn nội dung “dịch hình ảnh”. Kết quả cuối không đạt ngữ nghĩa. Không thay câu này bằng từ điển/hardcode để làm đẹp báo cáo.

## Kiểm tra nguyên nhân kỹ thuật

- Tokenizer runtime **khớp tokenizer `Package(...).tokenizer` chính thức của Argos** ở cả 24 câu và cả hai chặng.
- Câu lỗi zh gồm `▁欢迎`, `使用`, `图像`, `翻译`, `。`; roundtrip normalized trùng nguồn.
- Đầu vào en gồm `▁Image`, `▁translation`, `▁is`, `▁welcome`, `.`; roundtrip trùng đầu vào.
- Không câu nào vượt giới hạn 384 token. Không chạm giới hạn decoding 768.
- Từng input là một câu đầy đủ; không dùng sentence splitter, không có OCR/grouping trong phép kiểm tra corpus. Câu sai tái hiện trực tiếp từ text, nên grouping OCR không phải nguyên nhân của lỗi này.
- Model direction và thư mục từng chặng đúng metadata, hash hợp lệ.
- Với cả 24 câu, gọi hai chặng tách riêng cho kết quả **giống hệt** đường pivot tự động `zh → en → vi`.
- Dùng tham số giải mã Argos gốc (`beam_size=4`, `num_hypotheses=4`, `length_penalty=.2`, `replace_unknowns=True`) vẫn tạo cùng các output sai ở câu mục tiêu.

Kết luận quan sát được: **hạn chế ngữ nghĩa của model/pivot**, không tìm thấy sai tokenizer, đảo chiều, ghép nhầm OCR hoặc truyền sai đầu ra giữa hai chặng trong trường hợp này. Việc sửa DLL không sửa chất lượng model.

Các câu thoại thông dụng khác trong bảng nhìn chung giữ nội dung, ví dụ cảm ơn/xin lỗi/hỏi giờ/về nhà, nhưng có lựa chọn đại từ anh/cô không có ngữ cảnh. Chưa có đánh giá BLEU/chrF, corpus truyện tranh thực tế hay thẩm định người dịch. Không công bố điểm “accuracy” và không gắn PASS chất lượng cho toàn bộ corpus chỉ vì output không rỗng.

## Đề xuất model dịch trực tiếp miễn phí

Ứng viên: **`facebook/m2m100_418M`**, model chính thức AI at Meta, giấy phép **MIT**, hỗ trợ cả zh và vi, dịch nhiều chiều trực tiếp. Nguồn: [model card](https://huggingface.co/facebook/m2m100_418M).

Đã xác minh dung lượng tại [danh mục file chính thức](https://huggingface.co/facebook/m2m100_418M/tree/main): `pytorch_model.bin` khoảng **1.94 GB**, SentencePiece khoảng **2.42 MB**, vocab khoảng **3.71 MB**. Kho có cả trọng số Rust; không cần tải cả hai bản trọng số.

CTranslate2 **4.6.0** có tài liệu chuyển đổi M2M100 và ví dụ target prefix tại [tài liệu đúng phiên bản](https://github.com/OpenNMT/CTranslate2/blob/v4.6.0/docs/guides/transformers.md#m2m-100). Có thể chuyển đổi sang CT2 int8 để chạy CPU. Cần adapter tokenizer/source language/target prefix M2M100 riêng; không được đổi tên gói này thành Argos rồi dùng tokenizer Argos.

**Chưa tải, chuyển đổi, cài hoặc suy luận model này.** RAM, độ trễ và chất lượng zh→vi trên corpus của dự án chưa được đo. Đây là ứng viên được kiểm tra nguồn/giấy phép/dung lượng/khả năng engine, chưa phải thay thế đã nghiệm thu. Không tự tải model lớn trong lượt này.
