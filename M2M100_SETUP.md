# M2M100 Offline — trạng thái và cài model cục bộ

## Trạng thái sau khôi phục 06/11/2026

Provider riêng `providers/m2m100.py` đã được tích hợp vào lựa chọn Offline của GUI và factory của pipeline. Argos vẫn giữ nguyên và là mặc định. **Chưa có trọng số M2M100 trên máy**, người dùng đã xác nhận; suy luận và chất lượng M2M100 **NOT TESTED**. Unit contract tests dùng mock được ghi rõ; không coi chúng là bằng chứng model dịch được.

## Nguồn, tài nguyên và kết nối

- [Model chính thức AI at Meta](https://huggingface.co/facebook/m2m100_418M): MIT, hỗ trợ zh/vi và dịch trực tiếp. Không cần API trả phí.
- [Danh sách file chính thức](https://huggingface.co/facebook/m2m100_418M/tree/main): trọng số PyTorch khoảng 1.94 GB, SentencePiece 2.42 MB, vocab 3.71 MB. Không cần tải thêm bản trọng số Rust trùng lặp.
- [CT2 4.6.0 M2M100](https://github.com/OpenNMT/CTranslate2/blob/v4.6.0/docs/guides/transformers.md#m2m-100): hỗ trợ chuyển đổi, target language prefix; runtime cấu hình CPU int8. Kích thước bản chuyển đổi và RAM thực tế **chưa đo**.
- Máy: khoảng 34.19 GB RAM vật lý, 16.11 GB khả dụng ở thời điểm audit, 20 logical CPU, ổ D còn 298.83 GB. Có dư dung lượng cho nguồn và bản chuyển đổi; đây chưa phải kiểm thử tải/suy luận model.
- `logs/network-diagnostics-20261106T094805Z/diagnostics.json`: sandbox `CODEX_SANDBOX_NETWORK_DISABLED=1`, proxy quản lý `127.0.0.1:9`, HTTPS bị từ chối. Không tắt/bỏ proxy hoặc chính sách. Không thực hiện tải lớn hay cài thêm dependency.

## Chuẩn bị khi có nguồn và kết nối được phép

Chỉ thực hiện bước tải ở một môi trường có quyền mạng hợp lệ. Lưu nguồn chính thức và tokenizer tại `D:\TransTool\models\translation\m2m100-source`. Giữ thông tin revision/hash nguồn. Chuyển đổi bằng converter CT2 4.6.0 từ **đường dẫn cục bộ**, CPU int8:

```bat
.venv\Scripts\ct2-transformers-converter.exe --model D:\TransTool\models\translation\m2m100-source --output_dir D:\TransTool\models\translation\m2m100-converted --quantization int8
```

Converter cần Transformers; **Transformers chưa cài và lệnh chuyển đổi chưa chạy** trong phiên này. Không nâng cấp CT2/setuptools hoặc cài lại requirements để xử lý bước tùy chọn này. Cần xác minh dependency chuyển đổi riêng trước khi cài. Runtime provider của ứng dụng chỉ dùng CT2/SentencePiece đã có, không cần Transformers và không gọi Hugging Face.

Khi đã có bản chuyển đổi đúng định dạng và tokenizer chính thức:

```bat
.venv\Scripts\python.exe scripts\prepare_m2m100.py --converted D:\TransTool\models\translation\m2m100-converted --tokenizer D:\TransTool\models\translation\m2m100-source
```

Lệnh nhập chỉ đọc/sao chép file cục bộ, kiểm tra dung lượng, cấu trúc, language token, native load CPU và tạo receipt SHA-256. Cài tại `models/translation/m2m100_418m_ct2`. Không ghi đè cài đặt có sẵn; staging lỗi được giữ để chẩn đoán. Receipt bảo vệ tính toàn vẹn sau nhập, **không tự chứng minh nguồn gốc trọng số**. Cần giữ bằng chứng tải nguồn chính thức. Lệnh nhập chưa được kiểm thử với model thật vì thiếu trọng số.

## Runtime và so sánh

Nguồn được encode thành language prefix + SentencePiece + EOS; decoder dùng target prefix và loại special token đúng hướng. Tham khảo [tokenizer chính thức](https://github.com/huggingface/transformers/blob/v4.46.3/src/transformers/models/m2m_100/tokenization_m2m_100.py). Provider lazy load một model, tái sử dụng, khóa suy luận, batch nhỏ, từ chối đầu vào/đầu ra vượt giới hạn; không âm thầm cắt chữ. Chưa xác minh đối chiếu tokenizer/model thật.

```bat
.venv\Scripts\python.exe scripts\compare_translation.py
.venv\Scripts\python.exe scripts\validate_e2e.py --engine M2M100
```

So sánh sử dụng cùng 24 câu trong corpus trước. Hiện `output/translation-comparison/20261106T095505Z-9ff6bc/` chứa Argos suy luận thật và M2M100 **SKIPPED**; không có bản dịch M2M100 giả. Chưa thể kết luận M2M100 tốt hơn Argos. Không đổi provider mặc định trước khi kiểm thử ngữ nghĩa thực tế.
