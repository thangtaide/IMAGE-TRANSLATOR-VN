# Khôi phục chọn lọc 0014 / 0029 / 0085 — 11/11/2026

**CHƯA ĐẠT chất lượng cả ba ảnh.** Đã xác minh và sửa hai lỗi số giả cùng
LAYOUT_UNFIT; render lại đúng ba ảnh bằng dữ liệu cũ. 0085 đọc được. 0014/0029
vẫn còn chữ Trung do vấn đề OCR/mask khác được phát hiện khi xem ảnh thật.
Không thay thuật toán OCR, mask hoặc inpainting theo giới hạn nhiệm vụ.

Project root được xác định từ workspace chứa `AGENTS.md`, `core/`, `providers/`
và `main.py`; script dùng vị trí module. Evidence tương đối:
`output/selective-recovery-20261110T165759Z/` (gọi tắt là evidence bên dưới).
Job `832ba2b61fa073ef1a5df98bfc3353fd31901bacfc07b0df5c6eb50bbdfa23db`.

## Dữ liệu và quyền giải mã

- Đọc ba bản ghi `logs/diagnostics/<job>/errors.jsonl`, options/items trong
  SQLite snapshot nhất quán, OCR cache và journal hiện có. Không ghi DB production.
- Đường dẫn ảnh thực tế được lấy từ job, không đoán theo thư mục chương trước.
  Job này thuộc **Chap 21**, không phải Chap 20 trong yêu cầu cũ.
- Người dùng cho phép giải mã riêng stdout của attempt
  `01aef63cccf646538c3a05c3721cfcc6` bằng DPAPI CurrentUser, cục bộ trong RAM.
  Giải mã thành công; 13.479 byte khớp SHA256 capture. Không lưu raw stdout,
  JSON phản hồi hoặc bản dịch bị che dưới dạng văn bản rõ. Ảnh render là kết quả
  người dùng yêu cầu; summary chỉ chứa số, kích thước, hash và trạng thái.
- Parser hiện tại ACCEPT **23/23 region, 3 page**, exit 0. Đối chiếu 21 target
  đã có trong cache trùng phản hồi; hai target còn lại phục hồi trong RAM.
  Đây không phải lỗi provider/parser. Không sửa parser.
- Recovery chặn AGY `_invoke`, OCR `recognize`, socket `connect/connect_ex`.
  Dùng validator hiện tại với raw_target và cache RAM, rồi `erase_text` →
  `TextRenderer.render` → xuất JPEG mới. Không chạy lại toàn chương.

## 0014.jpg

Region **9 sau lọc alphabet**, polygon `(18,336)–(734,445)`, confidence
0,979260. OCR có `下降百分之20`; ảnh gốc xác nhận chữ số **20**. Target có **20%**.
Guard cũ lấy token literal `20` và `20%`, báo sai dù giá trị và đơn vị tương đương.
Không tự thay chữ số, không bỏ bảo vệ numeric.

Bản sửa chỉ chuẩn hóa đơn vị rõ ràng `百分之` ngay trước token số thành `%`
trong phép so sánh. Dấu, thứ tự, dấu phân cách và số vẫn so sánh chặt chẽ.
Tạo namespace cache riêng cho nguồn có đơn vị này; giữ cache cũ nguyên trạng.

Thử nghiệm: cả 14 target giữ nguyên; validator và layout PASS. Nhưng ký tự
**攻** ở nhãn “攻击” không có trong OCR cache, vẫn còn bên trái target “Kích”.
Không thể coi ảnh này dịch đầy đủ hoặc sạch chữ Trung. **Ảnh CHƯA ĐẠT**.

[Trước/sau](../output/selective-recovery-20261110T165759Z/recovered/0014/comparison.jpg)
· [Bằng chứng vùng OCR/mask/inpaint](../output/selective-recovery-20261110T165759Z/recovered/0014/text-detail.png)
· [JPEG thử nghiệm](../output/selective-recovery-20261110T165759Z/recovered/0014/final.jpg).

## 0029.jpg

Region **2**, polygon `(5,679)–(1234,711)`, confidence 0,947954.
OCR có `原来的百分之70`; ảnh gốc xác nhận **70**. Target có **70%**, dài 112 ký tự.
Nguyên nhân guard giống 0014; không phải AGY đổi số, dấu âm hay separator.

Sau sửa, cả ba target giữ nguyên, dòng tiếng Việt vừa vùng, không chồng các
target và không cắt nội dung. Tuy nhiên nhiều ký tự trắng/hồng nằm trong OCR
box chưa được mask phủ, còn nguyên ở ảnh **sau inpaint, trước render**, tiếp tục
gây nhiễu ở final. Đây là vấn đề xóa chữ riêng, không phải outline tiếng Việt
hay lỗi số. **Ảnh CHƯA ĐẠT**. Không sửa mask ngoài phạm vi được yêu cầu.

[Trước/sau](../output/selective-recovery-20261110T165759Z/recovered/0029/comparison.jpg)
· [Bằng chứng mask còn bỏ sót](../output/selective-recovery-20261110T165759Z/recovered/0029/text-detail.png)
· [JPEG thử nghiệm](../output/selective-recovery-20261110T165759Z/recovered/0029/final.jpg).

## 0085.jpg

Lỗi thật nằm ở **region 3**, nhãn Latin trên xe; không phải hai câu thoại cuối
ảnh. OCR/target cùng là `ETDKTENOAOSTEE`; box `(407,457)–(469,468)` chỉ **62×11 px**.
Arial cỡ tối thiểu 8, stroke 1 cần **76×8 px**; từ đơn không thể xuống dòng.
Line spacing cấu hình 3, bị giới hạn 2 ở cỡ 8; nhãn chỉ có một dòng.

Fallback mới chỉ áp dụng khi layout thông thường thất bại: một box nhỏ chứa
identifier ASCII, target giống hệt OCR, mở ngang có giới hạn, không vượt ảnh,
không giao box khác. Không hạ dưới font_min hoặc cắt từ. Ảnh này mở **7 px mỗi
bên**, thành `(400,457)–(476,468)`. Các trường hợp không an toàn vẫn LAYOUT_UNFIT.

Hai OCR box thoại giao nhau được cơ chế hiện có gộp và render đủ nội dung ở
cỡ **24**, một dòng, spacing 3; không sửa thuật toán gộp. Sáu target giữ nguyên,
không collision/clipping. Xem original, mask, inpaint và JPEG ở 1280×720:
không còn chữ Trung gây nhiễu trong các vùng dịch, không hỏng chi tiết lớn.
**0085 ĐẠT cho phục hồi payload hiện có**. Nhãn Latin vẫn giữ lỗi nhận diện
của OCR, không tuyên bố đã sửa đúng tên thương hiệu.

[Trước/sau](../output/selective-recovery-20261110T165759Z/recovered/0085/comparison.jpg)
· [Vùng thoại](../output/selective-recovery-20261110T165759Z/recovered/0085/text-detail.png)
· [JPEG thử nghiệm](../output/selective-recovery-20261110T165759Z/recovered/0085/final.jpg).

## Kiểm thử và bảo toàn

- Regression Python chọn lọc: **182 test khác nhau PASS sau sửa môi trường**.
  Lần chạy tổng: 181 PASS, 1 FAIL do Node không ở PATH của Python host.
  Chạy lại đúng test lỗi với Node portable đã có: 1 PASS, 0 FAIL.
  Không thay PATH hệ thống, không cài dependency.
- Phạm vi: numeric (16 tình huống trong fixture đã làm sạch), layout/mask,
  rendering, Stage2 recovery, AGY Batch/parser/diagnostics, Whole Chapter,
  ToonCN adapter/bridge, cache/run isolation. Các test provider dùng fixture/mock,
  không phải chứng cứ AGY dịch vụ thật.
- Node **v22.23.4**, npm **10.9.9**; ba test JS ToonCN synthetic: **3 PASS**.
- Có hai lần test mới thất bại trước đó do helper test truyền sai tham số và
  fixture CJK quá ngắn để overflow với font host; đã sửa test và chạy lại.
  Giữ các log lỗi để truy vết, không coi lần thất bại là PASS.
- Đối chiếu layout **137 metadata ảnh khác** cùng chương bằng code baseline
  và code mới: 137/137 accepted plan giống hệt, không ghi ảnh khác.
- **294 file** ảnh nguồn/output/DB/journal/capture được theo dõi giữ nguyên hash;
  **12 EXE cũ** giữ nguyên. Ba hàm `_outlined_glyph_mask`, `build_mask`,
  `erase_text` giống AST baseline; OCR/adapter/GUI không sửa.
- Không bump IMAGING_REVISION vì không thay các layout đã hợp lệ; fallback mới
  chỉ cứu trường hợp từng fail. Validator version được tăng; Whole Chapter sẽ
  không coi receipt đã xác thực bằng validator cũ là receipt của version mới.
  Không migrate/xóa receipt hay tự chạy lại job production.
- **SKIP:** full suite toàn ứng dụng, live AGY/ToonCN, build và chạy EXE.
  AGY **0/6** lượt được cấp thêm; không cần gọi mới để khôi phục payload ba ảnh.

Log: `logs/selective-recovery-related.log` (lần đầu),
`logs/selective-recovery-corrected.log` (fixture CJK chưa đủ dài),
`logs/selective-recovery-regression.log` và `.xml` (181/1),
`logs/selective-recovery-node-path.log` và `.xml` (1/0),
`logs/selective-recovery-node.log` (3 JS PASS).
Evidence: `recovered/summary.json`, `numeric-evidence.json`, `visual-review.json`,
`other-page-layout-regression.json`, `preservation-check.json` dưới thư mục evidence.
Mỗi ảnh có original, OCR, mask, inpainted, layout, final và comparison riêng.

## Phạm vi còn lại và build

Đã khôi phục được bản dịch cũ và render thử cả ba ảnh, không gửi request mới.
Để cả ba ảnh đạt đọc truyện, cần xử lý thêm **OCR thiếu chữ ở 0014 và mask bỏ
sót ở 0029**, trong khi nhiệm vụ này giới hạn không đổi thuật toán OCR/mask.
Không chỉnh thủ công bản dịch/số để che hai vấn đề đó, không nhập kết quả thử
vào DB production và không báo fallback là thành công.

Không build EXE ở lượt điều tra này. EXE hiện có chưa chứa bản sửa. Nếu dùng
bản sửa bằng EXE cần build/kiểm thử riêng sau khi người dùng review; nên xử lý
hai giới hạn chất lượng trên trước khi nghiệm thu bộ ba ảnh.

## Git & Fork Handoff

Root thực tế lấy bằng `git rev-parse --show-toplevel`; branch `main`;
baseline sạch, HEAD `b5c9bd0e811437a37181763d68aa2b86fc0a8ddf`.
File thay đổi cần review:

- `core/pipeline.py`: canonical percent và namespace cache có phạm vi.
- `core/diagnostics.py`: validator version.
- `core/imaging.py`: fallback layout identifier nhỏ.
- `scripts/recover_selected_pages.py`: phục hồi offline riêng ba ảnh, RAM-only
  plaintext, không mở DB production, từ chối ghi đè thư mục `recovered` đã có.
- `tests/test_selective_recovery.py`, `tests/fixtures/selective_numeric_layout.json`:
  regression đã làm sạch; `tests/test_whole_chapter.py`: expected validator version.
- `PROJECT_STATUS.md` và báo cáo này.

Không đổi `.gitignore`; evidence/cache/log/build không đưa vào source review.
Index và unmerged entries trống, `git diff --check` sạch. Rà text thay đổi không
phát hiện credential thật theo các mẫu đã kiểm tra; không cam kết quét toàn lịch sử.
Commit message gợi ý để người dùng review nếu muốn:
`Fix explicit percent validation and bounded tiny-identifier layout`.

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT.**
