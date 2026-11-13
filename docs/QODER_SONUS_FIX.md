# Sonus MODEL_UNAVAILABLE — sửa 13/11/2026

Lỗi ở adapter Image Translator VN: Qoder CLI 1.1.89 nhận `--model Sonus`, trả
JSON dịch thành công nhưng ghi tên nội bộ **smodel** trong modelUsage. Adapter
trước đó so sánh trực tiếp với `sonus`, tự báo MODEL_UNAVAILABLE sau khi đã nhận
bản dịch hợp lệ. Diagnostic của run người dùng xác nhận đúng nhánh lỗi này;
preflight vẫn đăng nhập/catalog thành công, không phải thiếu quyền model.

Đã thêm bảng ánh xạ metadata được kiểm chứng: Ultimate → ultimate,
Sonus → smodel. Giữ nguyên model CLI, effort, isolation, kiểm tra JSON/ID,
quota, timeout và quy tắc không tự retry/fallback. Model metadata sai hoặc
alias chưa xác minh vẫn bị từ chối. Không đổi contract/cache identity, không
migrate hoặc sửa checkpoint của người dùng.

## Kiểm chứng

- Một invocation Sonus thật mới với ba đoạn OCR trung tính, ba ảnh/ba vùng:
  CLI exit 0, success, end_turn, một lượt, stderr rỗng; modelUsage auto/smodel.
  Adapter cũ tái hiện MODEL_UNAVAILABLE. Không gửi lại OCR của chương bị lỗi.
- Adapter sau sửa đã nhận nguyên byte response thật đó với đúng packet/identity,
  lưu receipt done và đọc lại mà không gọi CLI. Đây là replay, không phải lượt
  sinh nội dung thứ hai. Tổng từ đầu tích hợp: 3 invocation thật (2 trước, 1 fix).
- **74 test PASS**, gồm Qoder, Groq, AI settings/model sync. Bổ sung fixture
  Sonus thực đã loại session/request ID và thông tin billing, kiểm tra alias
  thật, alias sai vẫn bị từ chối, lưu receipt và resume pin Sonus/Ultimate.
  Không gọi đây là full repository regression.
- Source và EXE: Sonus Batch/Whole ba ảnh, render và resume PASS bằng fixture;
  EXE GUI Settings/dark popup PASS. Không gọi thêm live từ EXE.
- Build.bat PASS; bytecode Qoder và QA trong EXE khớp source. EXE cũ giữ nguyên.
- **319 file baseline nguyên SHA256**, gồm config riêng, database/journal và EXE
  cũ; run của người dùng giữ nguyên 225 trang pending. Không xử lý run đó.

## EXE và cách tiếp tục

Tính từ PROJECT_ROOT `./IMAGE-TRANSLATOR-VN-main`:

```text
dist/ImageTranslatorVN-20261113T165328912911Z/ImageTranslatorVN-20261113T165328912911Z.exe
```

Đóng EXE cũ, mở EXE mới, giữ Sonus và bấm **Tiếp tục** run đã lưu.
Không cần xóa cache/journal hoặc đổi provider. Response bị bản cũ loại không
được giữ trong receipt; lần Continue phải gửi lại phần pending và có thể tiêu
Credits thêm. Ứng dụng không tự gửi lại trước khi người dùng bấm Continue.

## Thay đổi và Git & Fork Handoff

Source: `providers/qoder.py`, `scripts/validate_qoder.py` (thêm tham số model
cho smoke), `tests/test_qoder.py`, `tests/fixtures/qoder_sonus_1_1_89.json`.
Docs: báo cáo này, `QODER_CLI_SETUP.md`, `EXPORT_AND_BUILD.md`, `PROJECT_STATUS.md`.
Không sửa AGY/Groq/OCR/mask/inpainting/renderer/layout.

Branch main, baseline sạch/index trống; không stage/commit/push/tag. Ignore
giữ nguyên, source/test/docs hiện để review; evidence/build/output vẫn ignore.
diff --check PASS. Review ánh xạ metadata và fixture thực trước khi stage bằng
Fork. Không commit config riêng/DB/ảnh/EXE/runtime evidence. Commit message
gợi ý: `fix: accept verified Sonus model usage alias from Qoder CLI`.

Evidence: `output/qoder-model-fix-20261113T164915Z/` gồm baseline,
sonus-stdout.json, request.json (OCR trung tính), real-response-replay.json,
regression.xml, source-sonus/report.json, exe-sonus/report.json,
exe-gui/report.json, packaging.json, data-preservation.json và git-handoff.json.
Build log: `logs/build-ImageTranslatorVN-20261113T165328912911Z.log`.

NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT.
