# Mở rộng chữ lấn nền: 0252 và 0257 — 14/11/2026

Theo yêu cầu tiếp theo của người dùng, khi bố trí cũ và mở rộng trên nền phẳng
không đủ, renderer được phép đặt chữ lên nền có texture/hình vẽ. Không còn bắt
buộc khung mở rộng nằm trong vùng phẳng hoặc bên trong viền thoại. Đây là thay
đổi chủ đích; có thể che một phần artwork. Không sửa OCR, provider, bản dịch,
mask, inpainting, checkpoint hoặc thuật toán fallback.

## Nguyên nhân lần lỗi mới

Diagnostic mới nhất 18:48 UTC ghi nhóm [0,1] của 0252 (64×30) và 0257 (64×32),
khác với nhóm [2] đã kiểm tra ở lần trước. Receipt mới lưu `Tùy Tính ACG` thay
cho nhãn CJK giữ nguyên trong receipt cũ. Nhãn này và địa chỉ web thuộc hai OCR
box giao nhau nên được renderer gộp. Bản dịch đầy đủ không vừa khung hẹp;
nền texture làm fallback nền phẳng cũ từ chối mở rộng.

Tái hiện bằng OCR cache và receipt hợp lệ của run, xác nhận source hash,
packet/response hash và target_hash của cả mười vùng trong checkpoint. Không
gọi OCR inference hoặc dịch lại. Case cũ của 0257 vẫn có layout giống hệt sau
bản sửa này; không thay đổi bản dịch để làm test vừa.

## Cơ chế mới

- `core/imaging.py::_expand_over_background`: fallback cuối, tìm khung đến
  các mép ảnh; cho phép đi qua texture, màu nền khác và viền artwork.
- `_fit_expanded_frame`: dùng chung tìm khung/wrap/font metrics cho fallback
  nền phẳng và lấn nền. Thử các mức tăng rộng/cao đến toàn kích thước ảnh,
  giữ khung chứa vùng gốc, thử neo tâm và các mép. Chỉ chọn khung đủ chứa toàn
  bộ từ tiếng Việt, bbox gồm stroke và padding một pixel.
- Bước lấn nền ưu tiên cỡ đọc được tối đa 20 trong giới hạn font cấu hình,
  tùy chiều cao khung gốc; sau đó giảm đến font_min khi cần. Trong cùng một
  cỡ chữ ưu tiên diện tích tăng ít, độ lệch tâm nhỏ, ít dòng. Không kéo chữ
  lên font_max rồi phủ cả ảnh chỉ để dùng cỡ lớn.
- Vẫn chặn OCR khác, các khung đã bố trí và protected regions với khoảng
  cách một pixel. Khung không vượt ảnh; vùng alpha trong suốt không được
  dùng để chứa chữ vô hình. Kiểm tra va chạm cuối và raster clipping giữ
  nguyên. Không đủ chỗ cho toàn bộ nội dung thì vẫn báo LAYOUT_UNFIT trước vẽ.
- Bố trí cũ hợp lệ được giữ nguyên. IMAGING_REVISION không đổi để không làm
  mất hiệu lực ảnh hoàn thành hoặc receipt dịch đã có.

`scripts/validate_layout.py` hỗ trợ tên ảnh theo source để replay cả hai trang
bằng source/EXE, kết quả chỉ ghi vào thư mục QA mới. Tests dùng ảnh trung tính.

## Kết quả source thực tế

- 0252 PASS, nhóm [0,1]: `[27,2,91,32]` → `[0,0,160,46]`, font 20, hai dòng.
  Nhóm [2] nới ngang thành `[910,9,1280,32]`, font 15, một dòng; không đụng email.
- 0257 PASS với bản dịch mới, nhóm [0,1]: `[27,0,91,32]` → `[0,0,160,44]`,
  font 20, hai dòng. Nhóm [2] vẫn dùng nới nền phẳng 179×31, font 11/hai dòng.
- Giữ đủ năm OCR regions mỗi trang, phân phối thành bốn nhóm render. Không
  cắt từ, không mất nội dung, không vượt biên, không chạm chữ OCR khác.
- Ảnh review được ghi riêng; không ghi đè source/fallback production.

Evidence: `output/layout-overlap-20261113T185141Z/`, gồm baseline.json,
0252 và 0257/case.json, before-error.txt, source-real/report.json, layout và
ảnh rendered/crop; previous-case-regression.json xác nhận case cũ không đổi.
case.json chứa dữ liệu nguồn riêng và thuộc runtime được ignore.

## Git & Fork Handoff

EXE mới: `dist/ImageTranslatorVN-20261113T185906439443Z/ImageTranslatorVN-20261113T185906439443Z.exe`.
Build bằng build.bat PASS (packaging mode, không phải full validated build).
EXE frozen fixture PASS, đủ năm vùng/bốn nhóm; các box mở rộng và font giống
source fixture. Bytecode core.imaging, core.pipeline và scripts.validate_layout
trong EXE khớp source. Không có request AI hoặc OCR inference. Log build:
`logs/build-ImageTranslatorVN-20261113T185906439443Z.log`.

Regression: **194 test PASS**, gồm 21 case tight-frame, readability, corner
layout, core, safe fallback, multipage/resume và Whole Chapter. Không full
repository suite. Test no-room cũ dùng câu ngắn nay đã có chỗ nhờ lấn nền:
thêm test xác nhận hồi phục, và giữ test fallback bằng câu thật sự vượt dung
lượng ảnh. Không bỏ test an toàn để chấp nhận clipping hay mất nội dung.

Sau source replay thành công, thư mục ảnh source chương 11 và fallback cũ
không còn ở vị trí baseline trong lúc nhiệm vụ đang chạy. Không có lệnh xóa,
di chuyển hoặc sửa những file này trong lượt làm việc. Không tự khôi phục.
Vì vậy không thể lặp lại replay ảnh gốc bằng EXE; fixture EXE được tạo trung
tính với đúng OCR boxes/bản dịch và ghi rõ đây là synthetic bitmap, không
phải bản gốc. Source-real/report.json và ảnh review đã lưu trước đó còn đủ.

DB/settings và một số journal/receipt có thay đổi đồng thời khi ứng dụng đang
hoạt động. data-preservation.json ghi rõ file thay đổi/không còn ở đường dẫn
baseline; không ghi rằng toàn bộ runtime không đổi, không hoàn nguyên dữ liệu.
Các EXE baseline giữ nguyên hash. Các script của lượt này chỉ đọc production
DB/receipt và ghi kết quả QA riêng; test dùng database tạm.

PROJECT_ROOT suy ra từ workspace; branch main. Baseline có bảy tracked modified
và ba file mới từ bản sửa trước, giữ nguyên index/HEAD/branch. Review phần
renderer mở rộng, script replay, tests và tài liệu. Không stage runtime,
config cá nhân, cache, database, ảnh QA hoặc EXE. Không thay .gitignore.
Status cuối bảy tracked modified + bốn file mới (gồm baseline); index trống,
HEAD/branch không đổi. diff --check PASS; runtime output/logs/dist được ignore,
source/test/docs không bị ignore. Scan file review không có file >2 MiB hoặc
secret theo các mẫu đã kiểm tra; đây không thay thế review diff. Evidence
kiểm tra cuối: git-handoff.json, data-preservation.json, packaging.json,
translation-validation.json, regression.xml và frozen-fixture/exe-fixture/report.json.
Commit message gợi ý: `fix: expand unfittable text frames over background within image bounds`.

NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT.
