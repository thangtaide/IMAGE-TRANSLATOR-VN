# Nghiệm thu xóa chữ và EXE — 10/11/2026

**ĐẠT trên bộ nghiệm thu 0002, 0003, 0004 và kiểm tra mở rộng nêu dưới đây.**
Source và EXE đều chạy OCR/AGY thật, Batch và Whole thành công. Không dùng
kết quả unit test hoặc mask coverage thay cho xem ảnh.

## Root, baseline và dữ liệu thật

PROJECT_ROOT là `IMAGE-TRANSLATOR-VN-main` trong workspace hiện tại, được xác
minh bằng Git và `core.paths.ROOT`. Code lấy root từ vị trí module hoặc cấu
trúc `project/dist/<build>/<build>.exe`; các đường dẫn dưới đây tương đối root.

Git: branch `main`, HEAD `f82a6db7513245af41f6c23b694d473f51d2f6fc`.
Đầu lượt đã có 17 file sửa/untracked, gồm bản sửa mask/layout của lượt trước.
Giữ nguyên các sửa đó; không hoàn nguyên hoặc ghi đè thay đổi không liên quan.
Baseline: `output/acceptance-20261110T114108Z/baseline.json`.

Tìm đúng ba output có hậu tố `vi-0efed4e2` qua cache metadata, từ thư mục
người dùng chỉ định `../All/Bậc Thầy Bắt Thú Cưng/Chap 20`. Ảnh nguồn tương
ứng ở thư mục sibling `第20话 – tooncn_files`; tham chiếu từng file trong
`forensic/<case>/metadata.json`. Không đoán tên ảnh nguồn hoặc thay bằng ảnh
tổng hợp. Capture thêm 0005–0011: tổng 10 cặp ảnh thật.

Evidence của lượt này: `output/acceptance-20261110T114108Z/`, gọi là RUN.
Không ghi đè output cũ. 21 file được bảo vệ bằng SHA256 gồm 10 cặp nguồn/output
và database cũ đều không đổi; xem `RUN/preservation-final.json`.

## Root cause và pipeline

| Ảnh | Bằng chứng và nguyên nhân | Kết quả mới |
| --- | --- | --- |
| 0002 | OCR đã bao vùng chữ phía trên. Mask Otsu chọn một cực sáng/tối, bảo vệ component cắt rìa ROI bỏ sót nét trắng/viền đen trên nền phức tạp; Chinese còn trong ảnh sau xóa, trước render. Các box nội dung chính phía trên không giao nhau: hiện tượng chen chữ ở đây do chữ cũ chồng bản dịch, không có bằng chứng render trùng bản dịch. | Nét cũ không gây nhiễu; hai dòng Việt và các box riêng được bố trí đủ, không giao nhau. |
| 0003 | Mảng tối tái hiện ngay trong ảnh inpaint của thuật toán cũ, trước khi vẽ tiếng Việt. Đây chủ yếu là thân/viền chữ cũ còn sót và bị inpaint kéo thành mảng. Options thực tế stroke=1, không có shadow/background fill đen; không có bằng chứng cần giảm style mặc định. | Hai dòng dưới rõ, không còn mảng chữ đen gây khó đọc. Giữ stroke=1. |
| 0004 | OCR có vùng chữ dưới. Mask cũ bỏ sót nét trắng/outline như 0002. Nội dung dưới nằm trong một box; không thấy render lặp. Câu dài cần đo theo vùng thực nhưng không chứng minh được đây là lỗi collision riêng. | Chữ cũ được xóa; câu Việt dài vừa vùng dưới, không cắt câu hoặc vượt biên. Câu đủ chỗ được giữ một dòng. |

Các JPEG cũ là output lịch sử của batch `0efed4e2`, không có `render_layout`
trong metadata. Không có trace lưu tên EXE đã tạo chúng, nên không khẳng định
chính xác binary lịch sử. Đã tái hiện mask/inpaint cũ bằng `core/imaging.py`
tại HEAD, lưu `RUN/forensic/legacy-imaging.py`; đây là **tái hiện thuật toán**,
không phải giả làm ảnh debug chụp được lúc chạy cũ. `final-existing.png` là
output cũ thật. Mốc thời gian/metadata nằm trong từng thư mục forensic.

Lỗi collision riêng được xác minh ở ảnh bổ sung 0011: box nhiều dòng giao
box từng dòng, renderer cũ vẽ độc lập. Renderer mới gom thành flow trong vùng
chữ; không quy nguyên nhân đó cho các box nội dung chính của 0002–0004 khi
chúng không giao nhau. Các credit nhỏ của 0002/0003 có giao box và cũng được
gom, nhưng không phải nguyên nhân khó đọc phần nội dung chính.

Đã truy vết nhánh đang tạo ảnh thực: Qt MainWindow → ProcessingWorker →
ProcessingManager → Paddle OCR → AGY Batch → erase_text → render(erased) →
JPEG. Whole dùng WholeChapterJob/AGYWholeChapterTranslator và nhánh render
chung. Cả source và frozen EXE dùng database/workspace mới, OCR và request
thật; không lấy thành công từ cache cũ. Payload cũ chỉ dùng cho lượt cached
để chỉnh/đối chiếu ảnh không tốn API.

`core/pipeline.py:580` dùng đúng `erased`; không tìm thấy nhánh đưa ảnh gốc
trở lại ở compositing. Runtime capture xác nhận đầu vào render là ảnh inpaint,
audit đủ ID/nội dung và không giao paint bbox. Không thay provider/Bridge để
che lỗi. Không có fallback ảnh gốc trong bốn lượt AGY thực thành công.

## Code đã sửa và đóng gói

- `core/imaging.py:48`: seed sáng trung tính kèm hỗ trợ viền tối, fill nét và
  halo có kiểm soát, context theo kích thước chữ; xử lý mép ảnh thật, giữ mask
  cũ cho các vùng thường. Không phủ hình chữ nhật đen hoặc thêm model nặng.
- `core/imaging.py:134`: mask rỗng/inpaint lỗi trả `TEXT_REMOVAL_FAILED`, giữ
  alpha và pixel ngoài mask; không render chồng lên ảnh gốc khi bước xóa lỗi.
- `core/imaging.py:194`: nhóm OCR giao nhau và đóng nhóm theo union envelope;
  chỉ loại duplicate chính xác polygon+source+target, giữ các ID để audit.
  Plan toàn trang trước draw; wrap/fit/line spacing và paint bbox gồm dấu/viền.
  Không vừa hoặc vùng nhóm quá thưa thì `LAYOUT_UNFIT`, không cắt câu.
- `core/pipeline.py:467,591`: revision `readable-outline-layout-v4` tham gia
  cache/job identity; metadata lưu layout. Job/output cũ không tự được sửa.
- `scripts/debug_readability.py`: capture read-only, thêm chọn `--job-prefix`
  để đối chiếu đúng output cũ thay vì nhầm bản khác của cùng ảnh.
- `main.py:12`, `scripts/acceptance_readability.py`: cổng QA rõ ràng chạy cùng
  code trong source/EXE, ghi từng bước thực, xác minh frozen interpreter và
  giới hạn AGY bằng ledger trước transport. Không dựng OCR/response/target.
- `scripts/gui_smoke_actions.py`, test GUI AGY/Gemini: chọn mode bằng item data
  vì label hiển thị đã đổi; giữ nguyên assertions về hành vi.
- `tests/test_readability.py`, `tests/test_acceptance_budget.py`: regression
  nét trắng/viền/bóng/biên, duplicate/layout/content/order/failure và chặn lần
  gọi thứ 7. Fixtures provider vẽ ink thật thay bitmap trắng dưới OCR stub.
- `ImageTranslatorVN.spec`: chỉ bỏ đường dẫn máy cũ trong comment; giữ hệ
  thống PyInstaller đang có.

Mask/layout/revision đã có trong working tree khi bắt đầu lượt nghiệm thu;
lượt này giữ và xác minh chúng trên pipeline thực, sửa QA chọn mode cũ, thêm
capture/budget/frozen QA rồi đóng gói. Không tuyên bố viết lại thuật toán đó
trong lượt này hoặc thay toàn bộ kiến trúc.

## AGY thật — 4/6, còn 2

Model cấu hình hiện có: `gemini-3.8-flash-medium`. Mỗi request chỉ gồm ba ảnh
0002–0004; không chạy lại cả chương lớn. Không retry tự động, đổi provider,
tài khoản hoặc lưu key/token trong báo cáo.

| Lần | Mục đích/phạm vi | Bắt đầu UTC | Transport | Kết quả pipeline | Còn |
| --- | --- | --- | --- | --- | --- |
| 1 | Source Qt GUI Batch, 3 ảnh | 11:49:17 | 25,91 giây, exit 0 | 3 hoàn tất, 0 fail/fallback | 5 |
| 2 | Source Whole, 3 ảnh | 11:53:32 | 51,72 giây, exit 0 | 3 hoàn tất, 0 fail/fallback | 4 |
| 3 | Frozen EXE Qt GUI Batch, 3 ảnh | 12:03:28 | 33,50 giây, exit 0 | 3 hoàn tất, 0 fail/fallback | 3 |
| 4 | Frozen EXE Whole, 3 ảnh | 12:04:16 | 44,41 giây, exit 0 | 3 hoàn tất, 0 fail/fallback | 2 |

Ledger: `RUN/agy-budget.json`, gồm thời gian kết thúc, model, số ảnh, status,
exit code và số lần còn lại. `source-whole` lần chuẩn bị đầu tiên FAIL vì QA
chưa truyền manifest confirmation; guard chặn trước transport, không gọi AGY.
Đã sửa driver đi đúng prepare → confirmed manifest → run, rồi thành công ở
`source-whole-2`. Giữ báo cáo FAIL đầu tiên, không sửa thành PASS.

## Source, regression và GUI

| Kiểm tra | Kết quả | Evidence |
| --- | --- | --- |
| Source GUI Batch + Whole thực | PASS, 3 ảnh mỗi nhánh | RUN/source-batch và RUN/source-whole-2/report.json |
| Cached source và EXE | PASS, 10 ảnh mỗi lượt, 0 inference | RUN/source-cached, RUN/exe-cached |
| Mask/inpaint/layout/error/budget | 51 PASS, 0 FAIL | logs/acceptance-related.xml |
| Full regression cuối | 582 PASS, 0 FAIL, 12 SKIP; 347,25 giây | logs/acceptance-full-node.xml |
| Full regression đầu | 576 PASS, 3 FAIL, 12 SKIP; thiếu Node | logs/acceptance-full.xml |
| Source Qt Windows smoke | PASS | logs/gui-smoke-20261110T115329Z-cbd308/report.json |
| Frozen EXE Qt Windows smoke | PASS | logs/gui-smoke-20261110T120305Z-a806e0/report.json |
| Frozen EXE Batch + Whole thực | PASS, 3 ảnh mỗi nhánh | RUN/exe-batch và RUN/exe-whole/report.json |

Đã tải Node portable `v22.23.4`, npm `10.9.9` từ nodejs.org và kiểm SHA256
theo SHASUMS256 chính thức; ghi `logs/acceptance-node.json`. Chỉ thêm PATH
cho process regression, không sửa PATH hệ thống hoặc Chrome Bridge. Ba test
JavaScript ToonCN từng FAIL do thiếu Node đã PASS ở full run cuối. Test host
Python chạy được. Không sửa assertion để bỏ qua lỗi môi trường.

12 SKIP: thiếu OCR en/ml/zt, MT ko/zt, M2M100 tùy chọn; online integration
chưa opt-in; thiếu hai DOM thật Kuaikan; ba live Kuaikan tests chưa opt-in.
Không báo các chức năng đó đã chạy live. ToonCN adapter/Bridge/host fixtures
trong full run PASS; không tuyên bố kiểm chứng live Chrome/website.

GUI Batch thực có chọn folder, click Start, worker, heartbeat (source 1039,
EXE 1264), đủ 3 ảnh, nút phục hồi và screenshot cửa sổ. Các thao tác dùng Qt
QTest trên Windows platform; không tuyên bố kiểm thử màn hình vật lý hoặc
native Windows chooser. Whole được chạy qua job/translator thật của ứng dụng.

## Ảnh nghiệm thu

Đường dẫn sau tương đối root; mở ở 1280×720. Đã xem ảnh inpaint riêng và final
thực, kể cả JPEG được export bởi EXE, không chỉ PNG chụp trước encode.

| Ảnh | So sánh trước/sau | Các bước thực của EXE | JPEG cuối |
| --- | --- | --- | --- |
| 0002 | [Trước/sau](../output/acceptance-20261110T114108Z/exe-batch/0002/before-after.png) | [Original/OCR/mask/inpaint/layout/final](../output/acceptance-20261110T114108Z/exe-batch/0002/pipeline-comparison.png) | [Final](../output/acceptance-20261110T114108Z/exe-batch/0002/final-exported.jpg) |
| 0003 | [Trước/sau](../output/acceptance-20261110T114108Z/exe-batch/0003/before-after.png) | [Các bước](../output/acceptance-20261110T114108Z/exe-batch/0003/pipeline-comparison.png) | [Final](../output/acceptance-20261110T114108Z/exe-batch/0003/final-exported.jpg) |
| 0004 | [Trước/sau](../output/acceptance-20261110T114108Z/exe-batch/0004/before-after.png) | [Các bước](../output/acceptance-20261110T114108Z/exe-batch/0004/pipeline-comparison.png) | [Final](../output/acceptance-20261110T114108Z/exe-batch/0004/final-exported.jpg) |

[So sánh vùng đọc ba ảnh](../output/acceptance-20261110T114108Z/comparison-main.png).
Mask/inpaint cũ tái hiện và hiện tại: `RUN/forensic/<case>/mask-legacy.png`,
`inpainted-legacy.png`, `mask-current.png`, `inpainted-current.png`,
`forensic-comparison.png`. File `*-before` trong capture ban đầu là source
đã có sửa ở đầu lượt; không nhầm nó với thuật toán HEAD cũ `*-legacy`.

Kết quả xem ảnh: 0002 không còn Chinese trên gây nhiễu, hai dòng Việt tách rõ;
0003 hai dòng dưới đọc được, không có mảng đen nét cũ; 0004 câu Việt dưới
không chồng/cắt. Không mất target đã dịch: render audit đối chiếu nội dung
(trừ khoảng trắng định dạng), toàn bộ region IDs và collision bằng 0. Không
tuyên bố đây là đánh giá tuyệt đối độ đúng ngữ nghĩa của AGY.

Kiểm tra mở rộng 0005–0011 gồm nhiều vùng, top/bottom, nền sáng/tối, hiệu ứng
lửa, box OCR giao nhau 0011. Xem `RUN/source-cached-contact.png` và final
0011 ở kích thước đọc thực. 10/10 ảnh source và EXE có PNG final, PNG inpaint
và layout giống hệt khi cùng payload: `RUN/bundle-audit.json`.

Vệt inpaint tại dải chữ vẫn rõ, nền không được phục chế hoàn hảo. Không thấy
vùng lớn của mặt/nhân vật hoặc chi tiết chính bị xóa. Đánh giá ĐẠT dựa trên
khả năng đọc theo tiêu chí được người dùng chấp nhận, không dựa vào texture.

## Build và chạy EXE

Build bằng hệ thống hiện có: `cmd /c "build.bat <nul"`, sau source test liên
quan và source E2E PASS. Full regression chạy song song và kết thúc PASS
trước khi chạy nghiệm thu EXE. Packaging mặc định không chạy test, nên dùng
các evidence thực bên trên, không giả gate `--validated`.

EXE mới:
`dist/ImageTranslatorVN-20261110T115939410209Z/ImageTranslatorVN-20261110T115939410209Z.exe`

PyInstaller exit 0, pip check không hỏng dependency; 19.980.822 byte, SHA256
`aa5d262284b494dc3a9c296d0d73e16298384abfba55ebacab9d192159cebd7e`.
Log `logs/build-ImageTranslatorVN-20261110T115939410209Z.log`.
Fingerprint code/spec tại build khớp source, ghi trong `RUN/prebuild.json`
và `RUN/build.json`. Không sửa code chạy sau build.

EXE thật (frozen=True) đã chạy GUI, chọn folder và hoàn tất pipeline Batch;
Whole thật cũng hoàn tất. GUI không lỗi Qt plugin hoặc dependency; có
`_internal/PySide6/plugins/platforms/qwindows.dll`. Render dùng Arial sẵn có
trên Windows, GUI Segoe UI kiểm tra glyph tiếng Việt PASS; không có TTF được
bundle và không phân phối lại font Microsoft. Models tiếp tục ở project/models.

Bundle 5.389 file không có thư mục config/cache/output/models của root, không
chứa bản sao 21 file riêng đã bảo vệ; spec chỉ lấy assets và thư viện. Không
nhúng credential. Bốn EXE cũ giữ nguyên SHA256. Không xóa dữ liệu cũ.

Giữ cả thư mục EXE và `_internal` tại vị trí dưới project/dist; không chạy
file trung gian trong build/. Chưa nghiệm thu portable trên máy sạch.
Output JPEG thực từ EXE: `RUN/exe-batch/translated/0002.vi-3ea3a447.jpg`
và tương tự 0003/0004. Bản sửa không tự cập nhật ảnh đã dịch hoặc job done cũ;
tạo lượt xử lý mới với EXE mới để có output mới, giữ output cũ để so sánh.

## Giới hạn và Git & Fork handoff

Không cam kết xóa ký tự OCR chưa nhận ra trên mọi trang. Mask theo nét vẫn có
thể cần preview ở nền/glyph dính liền; layout không vừa báo lỗi thay vì cắt
nội dung. 10 ảnh đều từ dữ liệu truyện 3D hiện có, chưa đại diện mọi loại truyện.
Chưa kiểm thử máy sạch, website live hoặc model của 12 mục SKIP. Không thay
Chrome Bridge, provider production hoặc credentials. Không thêm Stage/model AI.

Danh sách file thay đổi đầy đủ, tách baseline và lượt này, nằm tại
`RUN/changed-files.json`. File chính cần review: imaging/pipeline, QA scripts,
main/spec, tests và tài liệu. Runtime evidence/cache/Node/dist/log/venv được
ignore; không đưa vào source commit. `.gitignore` giữ nguyên, không stage hay
untrack file. Kiểm tra cuối: diff --check không lỗi, index rỗng, không unmerged.
Giữ nguyên branch/HEAD. Không thực hiện commit/push/tag hoặc Git phá hủy.

Kết luận **ĐẠT bộ nghiệm thu được yêu cầu trên máy hiện tại**, với các giới hạn
đã nêu. NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT.
