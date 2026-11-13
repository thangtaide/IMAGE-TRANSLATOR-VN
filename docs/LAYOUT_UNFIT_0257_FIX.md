# Sửa LAYOUT_UNFIT 0257.jpg — 14/11/2026

**Bổ sung sau phản hồi mới:** receipt mới có bản dịch nhãn dài hơn và lỗi
nhóm [0,1]. Người dùng đã cho phép lấn nền; xem
[mở rộng chữ qua texture và kiểm tra cả 0252/0257](LAYOUT_BACKGROUND_OVERLAP.md).
Kết quả dưới đây giữ lại theo case/receipt cũ đã kiểm chứng.

Đã tái hiện và sửa bằng OCR, bản dịch và Options lưu trong run thật. Không gọi
provider, không chạy lại OCR, không sửa database/journal/output production.

## Nguyên nhân

Diagnostic `5ef7859125a9e724785e5667436efa5a551b8d6a9bc6c0944be7d18efeccb820`
ghi lỗi nhóm [2]. Khung đúng là **179×23 px** tại `[1095,9,1274,32]` trên ảnh
1280×720, không phải một chiều dài 17923 px. Renderer đã có word wrap theo từ.
Với Arial, font_min=10, stroke=1, spacing hiệu dụng=2, bản dịch cache được wrap
thành hai dòng; multiline_textbbox là `(-1,-2,169,25)`, cao **27 px**. Khung chỉ
cao 23 px nên không vừa dù xuống dòng đúng. Cơ chế cũ chỉ nới ngang một số
identifier Latin giữ nguyên, không nới vùng cho nội dung dịch này.

Đây là nhãn ở góc phải trên, có dòng email OCR phía dưới tại y=33..56. Không
thể tăng chiều cao xuống dưới tùy tiện hoặc bỏ kiểm tra va chạm.

## Sửa code

- `core/imaging.py::TextRenderer._fit_text`: tùy chọn thử các chiều rộng wrap
  thay thế. Luồng fit cũ vẫn chạy trước, giữ nguyên layout đã hợp lệ.
- `TextRenderer._expand_on_flat_background`: chỉ chạy khi fit cũ thất bại và
  có bitmap sau xóa chữ để kiểm tra. Tìm vùng nền phẳng liên thông cục bộ,
  thử kích thước/neo khung, đo bbox thật, chọn font trong giới hạn hiện có.
- `TextRenderer.plan_layout`: nhận image/protected_regions tùy chọn; giữ
  grouping cũ, kiểm tra thêm OCR gốc, vùng bảo vệ và khung đã lập kế hoạch.
- `TextRenderer.render`: chỉ layout mới dùng tile clipping, có padding raster
  1 px; mọi chữ phải được đo là vừa trước khi vẽ, không dùng clipping để cắt chữ.
- `core/pipeline.py`: chỉ truyền `preserved_regions` sẵn có vào renderer để
  các vùng số/ký hiệu được giữ nguyên trở thành blockers. Không đổi orchestration,
  OCR, mask, inpainting, provider, checkpoint/resume hoặc fallback.
- `scripts/validate_layout.py`, `main.py`: nhánh QA `--layout-check` để replay
  dữ liệu đã lưu bằng source/EXE trong thư mục output riêng.
- `tests/test_safe_layout_expansion.py`, `tests/test_readability.py`: regression
  mới và cập nhật test spy để nhận protected_regions.

Không đổi IMAGING_REVISION: các layout hợp lệ giữ nguyên pixel/identity, chỉ
phục hồi ca trước đây thất bại. Nhờ vậy Retry có thể dùng translation receipt
đang có, không ép dịch lại hoặc vô hiệu hóa các ảnh đã hoàn thành.

## Wrap, mở rộng và giới hạn an toàn

Giữ từng từ tiếng Việt, dấu và thứ tự chữ; không cắt word/chuỗi dài để ép vừa.
Thử wrap khác trong khung hiện tại sau khi fit cũ không thành công. Chỉ sau đó
mới tìm khung rộng/cao hơn trong vùng ảnh đã kiểm tra. Ưu tiên font dễ đọc trong
font_min..font_max, rồi diện tích mở rộng nhỏ, dịch tâm ít và số dòng hợp lý.

Mỗi cạnh ngang được nới tối đa min(96, max(12, 40% chiều rộng gốc)) px; cạnh
dọc tối đa min(64, max(8, hai lần chiều cao gốc)) px. Khung phải chứa box gốc,
nằm trong ảnh và ROI; phân tích nền giới hạn hai triệu pixel. Không dùng cả
ảnh trống làm quyền vẽ tự do.

Nền tham chiếu là median RGB của box sau inpaint. Chỉ component liên thông
4 hướng, lệch màu ≤10, gradient Sobel ≤16 và alpha=255 mới được xem xét;
component phải phủ ít nhất 85% box gốc. Mọi pixel thêm vào phải thuộc component
này. Viền/bề mặt có texture và vùng không xác minh được đều chặn mở rộng.
Biên khung thoại kín tách component và không thể bị vượt qua bởi khung mới.

Blockers gồm toàn bộ OCR khác (kể cả box gốc trước corner trim), preserved
regions và các khung đã được lập kế hoạch, có khoảng đệm 1 px. Kiểm tra cuối
giữ paint_box trong khung/ảnh và không giao nhau. Tất cả layout được lập trước
khi vẽ, nên thất bại vẫn fallback an toàn, không xuất ảnh chỉ mới xóa chữ.
Đây là kiểm tra pixel bảo thủ; nền không đủ bằng chứng vẫn LAYOUT_UNFIT.

## Kết quả trang thật

**0257.jpg render thành công bằng cả source và EXE.** Nhóm [2] có box mới
`[1095,1,1274,32]` = **179×31 px**, nới lên trên 8 px, font **11**, hai dòng.
Paint box `[1097,3,1272,30]` nằm hoàn toàn trong ảnh và không giao dòng email.
Giữ đủ năm vùng OCR, gồm bốn nhóm render do grouping cũ gộp [0,1].

Response hash và target_hash của cả năm bản dịch đã đối chiếu với receipt và
checkpoint, không sửa chữ. So với renderer HEAD trên cùng ảnh đã inpaint và
các vùng vốn hợp lệ, mọi pixel ngoài nhãn được sửa giống hệt. Source hash và
ảnh fallback cũ không đổi. Không cập nhật checkpoint production thành done.

Kết quả PNG để review:

```text
output/layout-wrap-20261113T181450Z/exe-real/0257-rendered.png
```

Font cấu hình được giữ nguyên. Target cache có bốn ký tự CJK còn nguyên trong
chuỗi; Arial hiện thiếu glyph nên hiển thị ô thay thế, tương tự các vùng CJK
khác. Sửa font fallback/CJK hoặc nội dung bản dịch không thuộc thay đổi này.

## Regression và EXE

**187 test PASS**, gồm 15 case mới về 179×23 px, hai/ba dòng, bốn mép ảnh,
tiếng Việt có dấu, box gần nhau/duplicate, protected numbers, bubble border,
texture, alpha, không mất từ, clipping/collision và không đủ chỗ vẫn fallback.
Gồm regression readability, corner layout, core, fallback, multipage/resume
và Whole Chapter. Không gọi đây là full repository suite.

QA ban đầu có hai lỗi fixture đã sửa: render spy cũ không nhận keyword mới;
fixture kiểm tra protected_regions dùng ảnh trắng không có glyph nên mask
rỗng trước render. Fixture sau tách đúng bước erase được mock; kiểm tra mask
thật giữ nguyên và các regression tương ứng PASS.

Build.bat PASS; bytecode imaging/pipeline/QA trong EXE khớp source cuối.
EXE replay dữ liệu 0257.jpg PASS, frozen=true, không OCR inference, **0 request
dịch**. AST các hàm build_mask, erase_text, outlined glyph mask, open_image,
default_font, atomic_save giống HEAD. 402 file baseline, gồm config/DB/journal/
receipt/EXE cũ/source và fallback 0257, giữ nguyên SHA256.

EXE mới, tính từ PROJECT_ROOT `./IMAGE-TRANSLATOR-VN-main`:

```text
dist/ImageTranslatorVN-20261113T183157119104Z/ImageTranslatorVN-20261113T183157119104Z.exe
```

Đóng bản cũ, mở bản này rồi chủ động Retry trang lỗi của run hiện tại. Không
cần xóa cache, đổi provider hoặc dịch lại chương. File review nằm trong QA
riêng; ảnh fallback cũ được giữ để đối chiếu.

## Git & Fork Handoff

Branch main, baseline sạch; không sửa index, HEAD hoặc branch. .gitignore giữ
nguyên, source/test/docs hiện để review; output/logs/dist được ignore.
diff --check PASS. Review các hunk renderer, một keyword ở pipeline và QA/test;
không stage config riêng, ảnh/case.json có dữ liệu nguồn, DB, evidence hoặc EXE.
Commit message gợi ý: `fix: recover tight text layouts with bounded background-safe expansion`.

Evidence: `output/layout-wrap-20261113T181450Z/`: baseline.json, before-error.txt,
case.json, translation-validation.json, source-real/report.json,
exe-real/report.json, layout/crop images, accepted-regions-comparison.json,
unchanged-functions.json, regression.xml, packaging.json,
data-preservation.json và git-handoff.json. Log build:
`logs/build-ImageTranslatorVN-20261113T183157119104Z.log`.

NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT.
