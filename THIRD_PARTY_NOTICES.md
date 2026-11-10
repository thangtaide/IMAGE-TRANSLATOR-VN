# Thành phần miễn phí và nguồn chính thức

Danh sách dưới đây ghi nguồn lựa chọn và chính sách sử dụng; chưa có binary/model được tải qua mạng trong phiên triển khai hiện tại.

| Thành phần | Giấy phép / điều kiện | Nguồn |
| --- | --- | --- |
| PySide6 / Qt for Python | LGPLv3/GPLv3/commercial; dự án sử dụng bản open source, giữ Qt DLL động và tuân thủ LGPL khi phân phối | https://doc.qt.io/qtforpython-6/licenses.html |
| PaddleOCR, PaddlePaddle và model danh mục | Apache-2.0 | https://github.com/PaddlePaddle/PaddleOCR ; https://github.com/PaddlePaddle/Paddle |
| Argos Translate | MIT hoặc CC0 | https://github.com/argosopentech/argos-translate |
| Model Argos | Tác giả xác nhận MIT/CC0; giữ README/metadata của gói | https://github.com/argosopentech/argos-translate/issues/533 |
| CTranslate2 | MIT | https://github.com/OpenNMT/CTranslate2 |
| SentencePiece | Apache-2.0 | https://github.com/google/sentencepiece |
| OpenCV | Apache-2.0 ở phiên bản dùng | https://github.com/opencv/opencv |
| Pillow | HPND | https://github.com/python-pillow/Pillow |
| NumPy | BSD-3-Clause | https://github.com/numpy/numpy |
| Requests | Apache-2.0 | https://github.com/psf/requests |
| Noto Sans | SIL OFL 1.1, giữ font và OFL cùng nhau khi phân phối | https://github.com/notofonts/noto-fonts |
| pytest / pytest-qt | MIT | https://github.com/pytest-dev/pytest ; https://github.com/pytest-dev/pytest-qt |
| PyInstaller | GPL với ngoại lệ bootloader | https://pyinstaller.org/en/stable/license.html |
| MyMemory API | Anonymous GET miễn phí có quota; tuân thủ điều khoản, không mua credit | https://mymemory.translated.net/doc/spec.php ; https://mymemory.translated.net/doc/usagelimits.php |
| LibreTranslate | Chỉ endpoint miễn phí/tự host có quyền sử dụng; server riêng tuân thủ AGPL | https://github.com/LibreTranslate/LibreTranslate |

Nguồn danh mục OCR dùng code PaddleOCR 2.9.1:
https://github.com/PaddlePaddle/PaddleOCR/blob/v2.9.1/paddleocr.py

Nguồn danh mục Argos:
https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json

Không gọi API OpenAI, Google Cloud Translation hay DeepL. Không hardcode key, không provider thu phí, không proxy rotation/CAPTCHA bypass. Chỉ runtime use font Windows được cài sẵn khi Noto chưa tải được; không phân phối font Windows. Trước khi phát hành EXE cần thu gom license của dependencies thực tế và kiểm tra đầy đủ nghĩa vụ phân phối Qt cùng các thành phần chuyển tiếp.
