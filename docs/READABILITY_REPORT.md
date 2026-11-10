# Mask và chữ Việt — nghiệm thu theo khả năng đọc

> Cập nhật 10/11/2026: đã có [nghiệm thu source/EXE với AGY thật](READABILITY_ACCEPTANCE_20261110.md),
> 0002/0003/0004 ĐẠT, 582 PASS/0 FAIL/12 SKIP, AGY 4/6. Báo cáo dưới đây giữ
> lịch sử của lượt sửa local trước đó; trạng thái không build/không gọi AGY và
> thiếu Node của lượt trước không phải kết quả mới nhất.

## PROJECT_ROOT và dữ liệu

PROJECT_ROOT là thư mục project tìm được trong workspace hiện tại, kiểm tra
bằng git rev-parse và ROOT của module; không hardcode đường dẫn máy cũ trong
source/script mới. Code dùng ROOT tương đối vị trí file, output/test/docs dùng
đường dẫn tương đối. AGENTS.md cập nhật quy tắc root động theo yêu cầu mới.

Không có output/removal-debug-20261110 trong root hiện tại. Đã dùng metadata
của cache/state.sqlite3 hiện có để tìm đúng0002,0007,0011, đọc nguồn/output thật,
giữ bản dịch và options của đúng job. Không đoán đường dẫn, không OCR hoặc gọi
provider lại. Evidence mới: `output/readability-review/`; mọi tham chiếu nguồn
trong metadata debug được chuyển tương đối PROJECT_ROOT, kể cả nguồn ngoài
root. DB mở mode=ro, không migration/UPDATE/DELETE.7file được kiểm hash gồm
DB và3cặp ảnh nguồn/output cũ đều giữ nguyên.

## Lỗi và sửa

**Xóa chữ:** Otsu một cực và bảo vệ component chạm rìa ROI làm bỏ sót thân/viền
trên nền tối có texture. Bổ sung seed sáng trung tính có hỗ trợ viền tối, tách
seed theo dòng trước connected components. Fill contour/counter, halo chỉ qua
pixel tối gần nét chữ trong3–8px, antialias1px; context5–24px, xử lý mép ảnh thật.
Giữ nhánh mask cũ cho ảnh thường, tránh chọn nền sáng chiếm đa số support.
Không tô hình chữ nhật mặc định, không blur cả vùng và không thêm model.

**0011:** một box hai dòng giao với box từng dòng; renderer cũ vẽ mỗi box độc
lập nên target đè nhau. Không phải AGY trả lại target hai lần. Renderer mới
lập nhóm giao nhau, đóng nhóm theo union envelope để không vẽ qua box bên
cạnh, flow từng target theo thứ tự input trong vùng chữ đã có. Không mở vùng
vẽ ngoài envelope; nhóm quá thưa có nguy cơ che artwork bị từ chối.

Chỉ deduplicate khi toàn bộ polygon, OCR text và target giống hệt. Giữ các ID
bản trùng trong duplicate_indices để audit; nội dung khác hoặc lặp ở vị trí
khác vẫn giữ. Không sửa OCR/target upstream, numeric/glossary hoặc ID AGY.

Word wrap và giảm font trong giới hạn options. Plan toàn bộ trang trước draw,
kiểm bbox thực gồm stroke/diacritics trong ảnh, không giao nhau và bảo toàn
chuỗi nội dung (ngoại trừ khoảng trắng định dạng). Nếu không vừa, báo LAYOUT_UNFIT
thay vì cắt câu/vẽ chồng. Mask rỗng hoặc inpaint hỏng báo TEXT_REMOVAL_FAILED.
Pipeline giữ erase_text → renderer.render(erased); lỗi không báo translated_success.
render_layout được lưu trong metadata để kiểm tra lại.

Revision readable-outline-layout-v4 tách output/cache identity. Không tự ghi đè
ảnh đã hoàn tất; source mới không tự cập nhật EXE cũ hoặc các job cũ đã done.
Không build EXE trong nhiệm vụ.

## Ảnh trước/sau và kiểm tra thực tế

[So sánh3ảnh](../output/readability-review/comparison-main.png).

| Ảnh | Các bước trước/sau | Final mới | Kiểm tra |
| --- | --- | --- | --- |
|0002|[Original/OCR/mask/inpaint/final](../output/readability-review/0002/comparison-after.png)|[Final](../output/readability-review/0002/final-after.png)|Không còn chữ Trung dễ nhận ra trong vùng dịch; Việt tách dòng rõ|
|0007|[Các bước](../output/readability-review/0007/comparison-after.png)|[Final](../output/readability-review/0007/final-after.png)|Nét/viền cũ không còn gây nhiễu; vùng panel và nhân vật vẫn đọc được|
|0011|[Các bước](../output/readability-review/0011/comparison-after.png)|[Final](../output/readability-review/0011/final-after.png)|Không chồng Việt;14box thành8nhóm, nhóm đầu3dòng24px|

Đã xem trực tiếp original, OCR boxes, mask, inpainted trước render và final.
25mục dịch được account đúng một lần qua17nhóm; không có paint bbox giao nhau;
word-wrap giữ nguyên nội dung từng nhóm. Nội dung chính16–28px, credit10px.
Pixels ngoài mask xóa chữ giữ nguyên trước render. Mặt/người và cấu trúc chính
trong3ảnh không bị xóa vùng lớn. Có vệt/nhòe nhẹ ở dải chữ đã xóa, được chấp
nhận theo P2 mới; không tuyên bố khôi phục texture chính xác. Chất lượng ngữ
nghĩa/OCR sẵn có không được tự sửa hoặc chấm lại bằng kết quả layout.

Audit: `output/readability-review/audit.json`, `preservation.json`, từng layout.json.
Không dùng coverage mask/test PASS thay việc xem ảnh; không ngoại suy sang mọi
trang hoặc chữ chưa được OCR phát hiện.

## Tái tạo evidence và test

Chạy từ PROJECT_ROOT, với môi trường đã có:

```powershell
.\.venv\Scripts\python.exe scripts\debug_readability.py --capture --directory output\readability-another-run
.\.venv\Scripts\python.exe scripts\debug_readability.py --directory output\readability-another-run
.\.venv\Scripts\python.exe -m pytest tests\test_readability.py tests\test_adaptive_mask.py tests\test_core.py tests\test_error_fallback.py -q
```

Capture từ chối ghi đè directory cũ. Muốn before thật phải capture trước khi
đổi source; capture sau sửa là baseline của phiên bản đang chạy. Bản evidence
phiên này có before-imaging.py/before-pipeline.py chụp trước sửa và final-existing
là output cũ thật. Không dựng bản dịch hoặc kết quả OCR.

Test mới kiểm tra viền/bóng/trắng-đen/biên/nhiều dòng, mask không đổi ngoài vùng,
nhóm box giao nhau và closure, exact duplicate và repeated phrase hợp lệ,
polygon khác cùng bbox, nội dung/newline/font/bounds, không đủ chỗ phải lỗi,
không vẽ phần trang trước khi plan hợp lệ, pipeline dùng ảnh erased và failure
không báo dịch xong; test thêm với metadata3ảnh thật khi có evidence.

Fixtures provider cũ khai có chữ bằng OCR stub nhưng tạo bitmap hoàn toàn
trống. Chặn empty mask mới phát hiện giả định đó. tests/image_fixtures.py vẽ
ink thật, giữ corner marker và mọi assertion provider/resume.11lệnh tạo bitmap
trong7module test thay đổi, không sửa provider production hoặc nới assertion.
Đây là raster/contract với provider mock, không phải AGY inference thật.

Số test cuối và phân loại Node/Python host ghi ở phần kết quả bên dưới.
Không gọi AGY thật, không cài dependency, không thay registry Chrome Bridge.

### Kết quả thực chạy

| Nhóm | PASS | FAIL | SKIP | Evidence |
| --- | ---: | ---: | ---: | --- |
| Mask/inpaint/layout/renderer/core/error fallback |92|0|0|logs/readability-related-final.log và .xml|
| Hợp đồng chọn lọc ToonCN/Bridge/Batch/Whole |42|3|0|logs/readability-contracts-final.log và .xml|

Nhóm92 gồm các test mới và test cũ, không phải92ca mới. Nhóm45 chọn lọc gồm
ToonCN adapter/bridge/connection, Batch quota-resume giữ kết quả cũ, resume qua
hai Python process và Whole1/16/100/120trang. Provider là mock, CV/render/SQLite
chạy thật trong fixture riêng. Không gọi AGY thật hoặc trang truyện thật.

3FAIL đều FileNotFoundError khi subprocess yêu cầu `node`: capture local JS,
background request fake Chrome và image fetch fake browser. `node` không có
trong PATH; không cài Node trong nhiệm vụ. Không biến FAIL thành SKIP hoặc
PASS. Python host tại `.venv/Scripts/python.exe` hiện có, các test registration
plan/conflict/unregistration mock chạy được; không còn lỗi host-files-missing
của root ở máy/bản khác. Không thay host/registry/profile Chrome.

**Không full regressionPASS.** Toàn suite không được tuyên bố đã chạy; nhóm
chọn lọc còn3FAIL môi trường dù các test mask/layout liên quan đềuPASS. Hai
suite cuối độc lập, không cộng các lượt thử trung gian vào số ca.

## Giới hạn và kết luận

**ĐẠT khả năng đọc trên3ảnh mẫu theo tiêu chí mới**: sạch chữ gây nhiễu trong
vùng dịch, Việt không chồng, đủ nội dung, không hỏng lớn chi tiết quan trọng.
Không đánh trượt vì vệt inpaint nhẹ. Không khẳng định mọi ảnh tương lai đều đạt:
OCR bỏ sót, mask không tách được artwork hoặc target quá dài vẫn cần kiểm tra;
layout không an toàn được báo lỗi. Không thêm inpainting AI nặng.

Không tuyên bố full regressionPASS; thiếu runtime JS và các kiểm tra chưa chạy
phải báo riêng. Không tạo Stage, không build EXE, không gọi AGY hoặc xóa dữ liệu.

## Git & Fork Handoff

Repository workspace hợp lệ, branch main, HEAD/baseline trong
`logs/readability-git-baseline.json`; lúc kiểm tra đầu working tree sạch,
index không staged và không conflict. Snapshot baseline sau khi thêm debug
script có đúng script đó untracked; không nhận nó là thay đổi người dùng.

Source: core/imaging.py, core/pipeline.py; rule AGENTS.md; script debug;
tests/test_readability.py, tests/image_fixtures.py và7fixture modules. Docs:
PROJECT_STATUS.md, README.md, docs/TROUBLESHOOTING.md, báo cáo này.
Giữ thay đổi auth/build/export trước đó trong repository, không hoàn nguyên.
.gitignore không đổi; ảnh/metadata debug/DB/cache/log/venv/model không commit.

Cuối lượt kiểm git status/diff/check/stat, staged/unmerged, runtime check-ignore,
hash nguồn/output/DB và file lớn/secret trong patch. Danh sách review/evidence
cuối trong logs/readability-handoff.json. Không stage/commit/push/tag hoặc đổi
branch/lịch sử. Message đề xuất cho người dùng review trong Fork:
`fix: remove outlined text and prevent overlapping translation layouts`.
NO_COMMIT, NO_PUSH, NO_TAG, NO_DESTRUCTIVE_GIT.
