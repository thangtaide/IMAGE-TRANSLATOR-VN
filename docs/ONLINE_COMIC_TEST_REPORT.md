# Online Comic Integration Test Report — 07/11/2026

**Luồng ảnh/chương cục bộ PASS kỹ thuật. URL Kuaikan đầy đủ BLOCKED**,
không đánh dấu website là SUPPORTED hoặc chất lượng dịch đã đạt yêu cầu.

## Phạm vi

Bổ sung 9 module Python `sources/`, `ui/comic_sources.py`,
`scripts/validate_comic_sources.py`, `tests/test_comic_sources.py`, `run_source.bat`
và 3 tài liệu `docs/`. Sửa MainWindow để thêm nút, `scripts/qa_common.py` để đưa
sources vào fingerprint; cập nhật README, PROJECT_STATUS, INSTALL_REPORT,
E2E_REPORT và BUILD_REPORT.

Core/providers/native guard, BAT/launcher/spec/requirements/.venv/model/EXE cũ
giữ nguyên. Không thêm dependency, không tải model. Downloader HTTP ảnh chưa
được triển khai; nút tải bị khóa có giải thích.

## Kết quả đã chạy

- Baseline pytest: 76 PASS, 7 SKIPPED (`logs/url-source-baseline-20261107.xml`).
- 30 ca mới: URL/SSRF/DNS/redirect, parser fixture, HTTP lỗi/rate limit/timeout/size,
  Windows filename, image decode, cache/quota/tamper/resume/cleanup, bảo toàn nguồn/
  alpha/kích thước, JobControl, Qt selection, cancel trước khởi tạo, lỗi pipeline
  giữ nguyên nguyên nhân và fingerprint bao gồm adapter.
- HTTP/HTML dùng fixture/mock có nhãn. Copy/hash/Pillow/SQLite/Qt chạy thật;
  không có bài test giả tải Kuaikan. Bộ cũ có integration OCR và MT thật.
- Full regression/unittest/GUI/E2E: xem mục evidence cuối bên dưới.
- EXE mới: NOT TESTED / chưa build. EXE cũ không có tính năng mới.

## GUI và ảnh truyện cục bộ thật

PASS: `output/comic-source-validation/20261107T042411Z-a93ecf/report.json`.
Qt platform **windows**, database QA mới riêng, không dùng kết quả OCR/MT từ
database thường. Nguồn là hai ảnh có sẵn trong ImgTest, không xác minh xuất xứ
website nên gắn provenance LOCAL.

| Chỉ số lượt đầu | Thực tế |
| --- | --- |
| Chương cục bộ chọn xử lý | 2 |
| Ảnh nguồn duy nhất / cache hợp lệ | 2 / 2 |
| Ảnh OCR thành công | 2, tổng 3 vùng chữ |
| Ảnh dịch Offline thành công | 2, tổng 3 bản dịch |
| Ảnh xuất PNG | 2, giữ kích thước gốc |
| Lỗi chương / ảnh | 0 / 0 |
| Network connect attempts | 0; audit hook từ chối nếu phát sinh |
| GUI heartbeat | 194 |

Nhấn nút thật: phân tích thư mục chương, không tự chọn, chọn tất cả, pause/resume,
start, worker mới/checkpoint, cancel/retry. Hash output không đổi sau resume.
Kiểm tra thêm ảnh đơn (1 output, dùng cache OCR/MT hợp lệ), URL ngoài registry,
URL Kuaikan trong sandbox báo lỗi mạng và không gửi HTTP/tải ảnh. Không cộng
lượt resume/retry vào số ảnh dịch duy nhất.

Cùng folder chứa chapter manifests, `ocr-translation-<id>.json`, events JSON,
ảnh chụp GUI và `url-access-status.png`; output tại `translated/` và
`single-image-translated/`. Ảnh gốc giữ SHA-256. Kiểm tra Unicode, Chapter2 trước
Chapter10, kích thước và cách ly chương.

Offscreen trên source cuối PASS tại `20261107T042716Z-a2bc8b/`, 179 heartbeat,
cùng fingerprint với lượt Windows. Đã xem ảnh chụp offscreen và Windows: chữ Việt hiển thị.
Chưa đánh giá mọi DPI/màn hình hoặc thao tác chọn file bằng tay trên mọi dialog hệ thống.

## Lỗi đã gặp và sửa; giữ nguyên evidence cũ

1. Hai lượt harness dùng QTest.qWait bị kẹt khi QThread import Paddle; stack tại
   `20261107T041332Z-968249/runtime-stacks.log`. Đã dừng riêng tiến trình QA, giữ
   file dở/cache. Dùng QEventLoop thật giải quyết hiện tượng; không sửa DLL hoặc
   quy kết model hỏng. Hai lượt đó INTERRUPTED, không gọi PASS.
2. Cancel trước khi khởi tạo job thiếu terminal result: worker nay emit
   job_finished/cancelled, có regression test. Evidence FAIL cũ:
   `20261107T041454Z-cd1662/report.json`.
3. Database QA riêng va chạm staging của lần test ảnh đơn trước; pipeline từ chối
   ghi đè đúng cơ chế bảo vệ. Đã thêm namespace staging theo database. FAIL cũ:
   `20261107T042335Z-2cefe9/report.json`; PASS sau sửa: `20261107T042411Z-a93ecf/`.

Không chỉnh kết quả cũ hoặc nhập tay OCR/bản dịch để làm PASS.

## Hồi quy và bảo toàn

Audit: 16/16 imports, 18/18 pins, Ready True tại `logs/install-audit-20261107T041423Z`.
Đối chiếu `logs/online-comic-20261107/preservation-before.json` và
`preservation-after.json`: trong 31 file được bảo vệ, chỉ MainWindow thay đổi có
chủ đích. Core/providers/main.py/requirements, các BAT/spec/3 EXE cũ không đổi.
5 model verify PASS, integrity receipt không đổi. Thay đổi riêng qa_common đã mô
tả; fingerprint bao gồm adapter, không nới các gate build khác.

GUI workflow thư mục cũ PASS: `output/gui-workflow/20261107T042709Z-16a90b/`
(pause/cancel/retry, ảnh hỏng, preview/settings/model, inference thật).
Traceback ảnh hỏng trong log là ca lỗi chủ động, không phải batch crash.

Lượt xác nhận cuối trên source sau sửa:

| Kiểm tra | Kết quả | Evidence |
| --- | --- | --- |
| pytest | **106 PASS, 7 SKIPPED**, 43.96 giây | logs/online-comic-20261107/acceptance-pytest.xml |
| unittest | **113 ca, 106 PASS, 7 SKIPPED**, 0 lỗi/fail | logs/online-comic-20261107/acceptance-unittest/test-results.json |
| GUI smoke | **PASS**, không mock | logs/gui-smoke-20261107T042609Z-49acce/report.json |
| E2E Offline chuẩn | **PASS**, OCR/MT thật trên fixture tổng hợp | output/e2e-validation/20261107T042612Z-cd1450/report.json |
| GUI thư mục cũ | **PASS**, gồm inference và ca ảnh hỏng | output/gui-workflow/20261107T042709Z-16a90b/report.json |
| GUI chương ảnh / ảnh đơn | **PASS**, ảnh truyện thật, Windows và offscreen | output/comic-source-validation/20261107T042411Z-a93ecf/ và 20261107T042716Z-a2bc8b/ |
| EXE tính năng mới | **SKIPPED / NOT TESTED** | Không build, EXE cũ bảo toàn |

Fingerprint source: `f740979db970210eb299c6b1cc658811728c83949f84a2ccea594ba3ed2dadd2`.
Tất cả lệnh ở lượt acceptance trả exit code 0; bảng không tính mock HTTP thành live PASS.
7 SKIPPED có lý do sẵn có: OCR Anh/Hàn/phồn thể thiếu model, MT Hàn/phồn thể thiếu
route, Online không opt-in, M2M100 chưa có weights; không đổi thành PASS.

NOT TESTED: live metadata HTTP từ Python, image downloader, disk-full thực (quota
đã unit test), mọi DPI, output ngoài writable workspace, EXE tính năng mới.

## Live Kuaikan

Xem [phân tích website](KUAIKANMANHUA_ANALYSIS_REPORT.md). URL 6677 và 15425 có
metadata quan sát qua trình duyệt; URL 3791 không lấy được. Python bị sandbox/proxy
giới hạn. Số chương có ID/link lấy được: **0**. Ảnh chương xác minh: **0**.
Ảnh tải/OCR/dịch/xuất từ Kuaikan: **0/0/0/0**. Đây là BLOCKED, không phải PASS.

Người dùng chưa có quyền tải tự động; không thử lấy ảnh để tìm cách vượt gate.
Parser metadata chưa được kiểm chứng trên raw HTML thật. Các con số công bố ở
trang truyện không được chuyển thành danh sách chương giả trong GUI.

## Tài liệu AI

[WEBSITE_ADAPTER_AI_GUIDE.md](WEBSITE_ADAPTER_AI_GUIDE.md) mô tả source thực, registry,
cache/pipeline/UI, quy trình nghiên cứu quyền/cấu trúc, test và prompt cho website mới.
