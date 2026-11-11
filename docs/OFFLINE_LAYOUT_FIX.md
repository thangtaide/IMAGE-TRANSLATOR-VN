# Sửa layout offline cho OCR boxes giao nhẹ ở góc — 12/11/2026

Đã sửa renderer tổng quát và kiểm thử bằng ảnh/chữ trung tính. Không xử lý lại
các ảnh Chap 27 đã xác định có nội dung tình dục trực diện. Không đưa ảnh mới
vào thư mục truyện hoặc tuyên bố ba ảnh đó đã được khôi phục.

## Nguyên nhân và sửa đổi

OCR có thể trả hai box độc lập giao nhau rất ít ở góc. Renderer trước đây gộp
mọi giao nhau thành một bounding rectangle. Với một dòng ngang gần một cột
dọc, rectangle đó chứa nhiều khoảng trống, vượt guard diện tích và báo
`LAYOUT_UNFIT`. Đây là vấn đề layout sử dụng OCR regions, không phải bằng
chứng engine OCR hoặc dịch vụ dịch bị lỗi.

`core/imaging.py` thêm fallback giới hạn cho **nhóm vốn thất bại vì thưa**:

- Chỉ xét 2–8 vùng, giao nhau thực sự ở góc theo cả hai trục; phần giao tối đa
  8% diện tích box nhỏ hơn.
- Chỉ thu hẹp vùng đặt chữ trong box OCR ban đầu; không mở sang vùng hình khác.
  Mỗi cạnh đổi tối đa 8 px, giữ ít nhất 85% diện tích box.
- Chọn phần thu hẹp ít nhất mà toàn bộ bản dịch vẫn vừa ở `font_min`.
- Giữ từng nội dung riêng, nguyên IDs/duplicate receipts; kiểm tra va chạm
  và toàn vẹn nội dung trước khi vẽ bất kỳ chữ nào.
- Nếu không bố trí được an toàn, tiếp tục báo `LAYOUT_UNFIT`, không cắt câu
  hoặc vẽ một phần ảnh rồi coi là thành công.
- Các nhóm đã hợp lệ trước đó giữ cách gộp/layout cũ. Metadata ghi
  `corner-overlap-trim` và `source_box` khi có thu hẹp.

Tách hàm fit font/wrap dùng chung, giữ phép đo và khoảng cách dòng cũ.
`IMAGING_REVISION` tăng thành `readable-outline-layout-v5-corner-trim` để lượt
xử lý mới nhận diện phiên bản renderer mới. Không sửa/migrate/xóa cache hoặc
checkpoint, không ghi lại ảnh đã hoàn thành.

**Không đổi** engine OCR, OCR grouping, mask hoặc inpainting. `TEXT_REMOVAL_FAILED`
khi mask rỗng vẫn được giữ: bản sửa layout không tự cho phép render đè lên chữ
gốc khi bước xóa chữ thất bại. Các ca phức tạp hơn giới hạn trên vẫn có thể
báo `LAYOUT_UNFIT`.

## Kiểm chứng

Evidence: `output/offline-layout-20261111T185101Z/`.

- Trước sửa, bộ tám test mới ban đầu: 4 FAIL / 4 PASS, tái hiện lỗi giao góc.
- Sau sửa, layout/mask/selective: 36 PASS; bộ test cuối thêm giới hạn 8 px và
  đường đi qua `group_lines`: 10 PASS (có tám test trùng bộ trước).
- Regression core, AGY Batch/multipage, Whole Chapter, cache/resume và online
  trust: 136 PASS. Toàn bộ fixture/mocks, không gọi AGY thật.
- Hợp các testcase chạy cuối: **174 PASS / 0 FAIL / 0 SKIP**. Đây là các bộ
  liên quan, không phải full regression toàn repository.
- E2E offline thật, không mock OCR/MT: PaddleOCR nhận `你好`, Argos cục bộ
  zh→en→vi trả `Xin chào.`, inpaint/render/export PASS, ảnh gốc nguyên hash.
  Network/AGY bị chặn trong test, **0 lần gọi hoặc cố gọi**.
- Lượt E2E tiếng Anh trước đó FAIL vì thiếu model OCR `det-en`; đây là thiếu
  model cục bộ, không sửa code để bỏ lỗi hoặc tải model trong job. Giữ nguyên
  evidence thất bại ở `offline-e2e/`, lượt tiếng Trung ở `offline-e2e-zh/`.

Log: `logs/offline-layout-before.xml`, `logs/offline-layout-after.xml`,
`logs/offline-layout-final-ocr.xml`, `logs/offline-layout-regression.xml`.

Ảnh trung tính đã xem trực quan:

- `neutral-corner/original.png`, `mask.png`, `inpainted.png`, `layout.png`,
  `final.png`, `comparison.png`: mock OCR geometry được ghi rõ; trước sửa
  `LAYOUT_UNFIT`, sau sửa hai vùng riêng, không chồng/cắt/mất chữ.
- `offline-e2e-zh/export/neutral.vi-f6e8503c.png`: kết quả OCR/MT/render thật,
  đọc rõ “Xin chào.”. Không lấy fixture geometry làm bằng chứng OCR thật.

## Sử dụng và giới hạn

Chạy source bằng `run.bat`. Renderer nhận OCR/bản dịch có sẵn và chạy cục bộ,
không tự gọi API. Chọn **Offline** nếu muốn cả bước dịch cũng dùng model cục bộ;
phải có đủ model OCR và model dịch cho ngôn ngữ nguồn. Không tự tải trong job.

**Chưa build EXE trong nhiệm vụ này.** Các EXE hiện có vẫn là bản trước; không
khẳng định chúng chứa sửa đổi mới. Không thay cấu hình người dùng để chạy QA.

File sửa: `core/imaging.py`, `tests/test_offline_layout.py` (mới), tài liệu
này, `README.md`, `PROJECT_STATUS.md`. Không sửa OCR/model/AGY/Chrome Bridge.

## Git & Fork Handoff

PROJECT_ROOT suy ra từ workspace/module; root phiên này là
`D:/WebLocal/IMAGE-TRANSLATOR-VN-main`, branch `main`.
Baseline: 24 modified + 14 untracked, index/unmerged trống; giữ nguyên toàn bộ
thay đổi có sẵn. Baseline và hash nằm ở `baseline.json`; kiểm tra cuối ở
`git-review.json` trong evidence. Config, database, checkpoint và EXE baseline
nguyên hash. Không đổi `.gitignore`.

Cuối lượt: 25 modified + 16 untracked (gồm thay đổi cũ), HEAD không đổi,
index/unmerged vẫn trống. `git diff --check` PASS; chỉ có cảnh báo CRLF/LF.
Source/test/docs mới hiển thị để review; runtime cache/output/logs được ignore
đúng. Không có runtime đã track, file sửa/mới >2 MiB hoặc credential khớp các
mẫu đã rà; scan regex không thay thế review thủ công.

Review source/test/docs trước khi tự stage trong Fork. Không commit logs,
output fixture, DB/cache, models, config riêng hoặc EXE. Message đề xuất:
`fix(renderer): separate sparse corner overlaps within OCR boxes`.

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT**
