# Qoder: 20 trang/batch, chữ trắng và giới hạn lệnh — 14/11/2026

Đã tăng trần ảnh của cả planner Batch và Qoder provider từ 10 lên **20**.
Whole Chapter dùng chung packer nên cũng áp dụng trần mới. Giữ giới hạn
3.000 ký tự OCR, 60 vùng, prompt 24.000 byte và output 4.096 token; batch có
thể nhỏ hơn 20 khi không vừa ngân sách. Không ép gửi quá giới hạn output.

Đặt preference hiện tại, default Options và config mẫu sang **chữ trắng,
viền đen 1 px**. Renderer hiện có tự chọn viền đen khi foreground là white;
không sửa thuật toán OCR/mask/inpainting/renderer/layout. Ảnh preview ở
evidence xác nhận có cả pixel chữ trắng và viền đen.

## Nguyên nhân PROVIDER_ERROR trang 0239.jpg

Diagnostic ghi rõ `Đạt giới hạn invocation Qoder của lượt chạy.` tại vị trí
ảnh 191. Provider đang dùng `agy_max_requests=64` và gán nhầm việc chạm giới
hạn cục bộ thành PROVIDER_ERROR. Đây không phải bằng chứng Qoder CLI lỗi hoặc
hết Credits. Có 64 receipt done; run đã giữ 186 ảnh done, 4 fallback và 35
pending tại thời điểm kiểm tra.

Đã tách **qoder_max_requests**, mặc định **128 invocation/lần chạy**, có ô
chỉnh riêng trong Cài đặt → AI dịch thuật → Qoder CLI. Không đổi giới hạn
AGY/Groq. Nếu chạm trần, báo **REQUEST_BUDGET**, request_sent=false; batch này
chưa gửi, giữ checkpoint và chờ Continue chủ động. Giới hạn vẫn được giữ,
không bỏ guard hoặc tạo vòng retry vô hạn.

Hạn mức vận hành mới không tham gia fingerprint/recipe/cache identity. Model,
effort, contract và binary identity giữ nguyên. Không sửa dữ liệu của run cũ.
Continue Qoder khôi phục foreground/stroke từ snapshot trước kiểm tra recipe;
lượt cũ giữ kiểu chữ cũ để không trộn với ảnh đã hoàn thành. Lượt mới dùng
white/black outline. Snapshot thiếu qoder_max_requests vẫn đọc được.

## Kiểm thử và EXE

- **141 test PASS**: Qoder, Groq, model/settings, core và readability. Bộ Qoder
  cuối **45 PASS**, gồm bổ sung trần 20+1 ảnh, Whole tự chia 21 ảnh, budget
  độc lập AGY, chạm trần không gửi subprocess, Save/Cancel và thông báo rõ.
- Legacy journal thiếu trường mới, đổi preference sang trắng rồi Continue:
  giữ recipe/job ID/kiểu chữ cũ, bỏ qua ảnh done, hash output không đổi.
- Source/EXE Sonus Batch/Whole/resume bằng fixture PASS; GUI Settings/dark
  popup PASS. Không chạy chương người dùng hoặc gọi Qoder thật (0 invocation).
- Build.bat PASS; bytecode tám module quan trọng trong EXE khớp source.
  Không sửa build script/spec, không bundle CLI/auth, không ghi đè EXE cũ.
- Kiểm tra baseline 384 file: 382 giữ nguyên hash; hai thay đổi có chủ đích là
  config/settings.json và config/settings.example.json. Không thiếu file nào;
  DB/journal/receipt/EXE có trước nhiệm vụ giữ nguyên.

EXE mới, tính từ PROJECT_ROOT `./IMAGE-TRANSLATOR-VN-main`:

```text
dist/ImageTranslatorVN-20261113T175152999651Z/ImageTranslatorVN-20261113T175152999651Z.exe
```

Đóng bản cũ, mở bản mới. **Continue** hoàn tất phần còn dở theo snapshot cũ.
**Bắt đầu lượt mới** dùng preference chữ trắng viền đen hiện tại. Không xóa
cache/checkpoint để xử lý lỗi giới hạn lệnh.

## File và Git & Fork Handoff

Source: providers/qoder.py; core/{multipage,types,resume,pipeline,whole_chapter}.py;
ui/{settings_dialog,provider_notice,main_window,whole_chapter}.py; tests/test_qoder.py;
config/settings.example.json. Config riêng chỉ đổi foreground và thêm hạn mức
Qoder; stroke hiện tại đã là 1. Docs cập nhật setup, status, export và báo cáo này.

Branch main. Baseline có **8 file đã stage** từ lượt trước; giữ nguyên index,
không stage/commit/hoàn nguyên chúng. .gitignore không đổi; diff --check PASS.
Review riêng hunk mới về budget/recipe/style và test trong Fork; không commit
settings riêng, DB/cache/ảnh/evidence/build/EXE. Commit message gợi ý:
`fix: separate Qoder request budget and support 20-page batches with white text`.

Evidence: `output/qoder-batch-style-20261113T174540Z/`, gồm baseline.json,
regression.xml, white-text-black-outline.png, source-sonus/report.json,
exe-sonus/report.json, source/exe GUI screenshots, packaging.json,
data-preservation.json và git-handoff.json. Build log:
`logs/build-ImageTranslatorVN-20261113T175152999651Z.log`.

NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT.
