# AGY lỗi mới và model bị ghi đè — 11/11/2026

**Đã xác minh nguyên nhân; batch Trang 112 vẫn BLOCKED_BY_PROVIDER.** Sửa
phân loại/thông báo lỗi và lỗi model bị ghi đè; không tuyên bố đã gỡ chặn bộ
lọc của nhà cung cấp. Đã kiểm tra metadata/outcome, giải mã DPAPI được cấp
quyền và chạy AGY Low thật trên fixture riêng.
Evidence tương đối: `output/agy-recurring-20261111T045708Z/`.

| Attempt | Trang | Exit | Thời gian | stdout/stderr byte |
|---|---:|---:|---:|---:|
| `eb5c690474a1404991251fb0d48cdc34` | 18 | 3 | 91,031 s | 10413 / 535 |
| `2e8d41af84cd43ea93ee8259b5e3f05c` | 112 | 0 | 122,719 s | 34783 / 0 |
| `6b49ae4534a44bc68d6dc7c8c443bf8e` | 112 | 0 | 90,469 s | 42148 / 0 |

Cả ba dùng `gemini-3.8-flash-medium`, CLI 1.5.5, timeout cấu hình 300 s,
outcome `paused_provider`, parser_reason NONE. Hai attempt Trang 112 có cùng
job/batch/payload hash, batch 17 trang/59 vùng/691 ký tự; lần Trang 18 là job và
batch khác, 16 trang/60 vùng/503 ký tự. Không tự tiếp tục hoặc retry các job.

Snapshot production hiện tại: job của Trang 18 đã `completed_with_warnings`
(127 done, 3 fallback); đó là lỗi lịch sử. Job của Trang 112 còn
`paused_provider` (111 done, 1 item paused), các ảnh còn lại giữ pending.
Outcome bundle là trạng thái tại lần attempt, không phải trạng thái job cập
nhật về sau. Không xử lý lại 111 ảnh đã thành công.

Người dùng đã cấp mọi quyền cần thiết cho điều tra. Giải mã stdout của cả ba
và stderr có dữ liệu của lần đầu bằng CurrentUser DPAPI trong RAM, đối chiếu
SHA256/length. Không lưu raw plaintext, response hoặc nội dung model bị che;
chỉ tóm tắt lỗi đã bỏ ID riêng/URL/token. File `decrypted-summary.json` và
`recoverability-summary.json` trong evidence.

**Trang 18:** terminal ERROR, finished_reason error, response rỗng; báo
`http2: server sent GOAWAY ... server_shutting_down`. Đây là stream bị máy
chủ đóng, không phải bằng chứng quota hoặc validator sai. Chưa có response
dịch để khôi phục. Bản sửa phân loại **NETWORK_ERROR**, giữ checkpoint.

**Hai lần Trang 112:** terminal ERROR, finished_reason error, num_turns 2;
đều báo **“blocked by content safety filters”**. Exit code 0 của CLI không
biến terminal ERROR thành SUCCESS. Đây là tín hiệu bộ lọc của provider,
không phải kiểm tra số/thuật ngữ của ứng dụng. Bản sửa báo **RESPONSE_BLOCKED**,
không lặp lại batch hoặc hướng dẫn đổi model/provider để vượt bộ lọc.

Hai bundle có structured_output gồm 59 target không rỗng, khớp 59 ID, nhưng
response string không phải strict JSON và terminal vẫn ERROR/multi-turn.
Đây là candidate được giữ trong ciphertext, **không được tự gắn nhãn thành
công, đẩy vào cache hợp lệ hoặc render như kết quả đã nghiệm thu**. Không nới
status/turn/tool guard hoặc giả có terminal SUCCESS. Tool metadata không phải
nguyên nhân chính suy đoán: tín hiệu ERROR/filter đã được xác minh trực tiếp.

Phát lại ba stdout thật qua parser mới: 3/3 vẫn REJECT, đổi mã lần lượt từ
PROVIDER_UNAVAILABLE sang NETWORK_ERROR/RESPONSE_BLOCKED/RESPONSE_BLOCKED.
Không phải một bản dịch SUCCESS bị từ chối chỉ do bộ validator nội dung online.
Trạng thái backend nhận request và tính phí: **UNKNOWN**.

## Code phân loại và thông báo

- `providers/agy.py`: nhận đúng hai tín hiệu lỗi trong nhánh terminal lỗi,
  trả ProviderSuspended tương ứng, latching/no-auto-retry như cũ. Exit 0 có
  provider error được ghi CLI_RESPONSE thay vì gán chung PARSER.
- `providers/agy_diagnostics.py`, `core/agy_error_evidence.py`: whitelist hai
  mã tĩnh để diagnostic/DPAPI metadata không biến chúng thành UNKNOWN.
- `ui/provider_notice.py`: log và banner tiếng Việt nêu rõ GOAWAY hoặc bộ lọc
  provider. Không echo raw error/credential; không gợi ý gửi lại batch bị chặn.
- Fixture/test đã khử dữ liệu nhạy cảm, có ERROR kèm đủ structured candidate
  và retry hint; vẫn phải từ chối/latch, không cache thành công giả.

## Model Low: lỗi source đã tái hiện và sửa

File cấu hình thực tế lúc điều tra ghi medium, mtime 04:56:13 UTC; EXE hiện
có nằm tại `dist/ImageTranslatorVN/ImageTranslatorVN.exe` (mtime 00:33:22 UTC).
Không có lịch sử writer nên không khẳng định ai đã lưu lại medium.

Đã chứng minh một cơ chế ghi đè có thật: MainWindow đọc options một lần, rồi
start/resume/close lưu cả snapshot. Một cửa sổ giữ Medium có thể ghi đè lựa
chọn Low mới hơn trên đĩa. Test isolated trước sửa: **2 FAIL / 2 PASS**.

Sửa `collect_options` của cửa sổ có persist_settings: đọc model mới nhất từ
settings trước khi thu thập/lưu, cập nhật nhãn model khi cần. Dialog Cài đặt
vẫn được chủ động đổi model và lưu ngay; QA không persistent không đọc lại
settings người dùng. Không đổi recipe/checkpoint, không khởi động provider.

Đặt default Options và AGYProvider thành `gemini-3.8-flash-low`; giữ chuỗi
PROMPT_VERSION/identity legacy để không vô hiệu cache model đã có. Model
explicit vẫn quyết định effort và identity theo cơ chế hiện tại. Khôi phục
settings hiện tại về Low, chỉ thay field agy_model, không đổi tài khoản/token.

Sau sửa model **48 PASS**, gồm bốn test model, AGY và cache GUI. Giữ nguyên
chính sách bỏ validator nội dung online; không sửa OCR/mask/inpaint/renderer.

## Kiểm thử thật, regression và EXE

- Regression sau sửa: **201 PASS / 0 FAIL / 0 SKIP**, gồm model/GUI/cache,
  Batch/Whole, API, timeout, tool/finish guard, multipage/checkpoint/resume và
  chính sách tin cậy nội dung online. Không gọi đây là full suite toàn repo.
- Test tái hiện provider trước sửa: 3 FAIL/1 PASS đúng lỗi phân loại/UI.
  Một assertion UI sau sửa sai chữ hoa/thường đã sửa test; log lỗi được giữ.
- **AGY thật thêm 1 request**, 14:41:05–14:41:13 UTC, 7,875 s, exit 0,
  model/effort Low. Ba ảnh fixture / 3 vùng / 17 ký tự được OCR thật bằng
  Paddle trước, CLI dịch thật, parser/ứng dụng nhận và render **3/3 PASS**.
  Đây là fixture thông thường, không phải replay batch bị chặn. Không gửi lại
  batch Trang 112 hoặc dịch lại toàn chương. `source-live/report.json` ghi rõ.
- Ngân sách: 1 lượt trước trong điều tra quota + 1 lượt này = **2/6**, còn 4;
  backend/chi phí UNKNOWN. `agy-budget.json` ghi mục đích/thời gian/ảnh/kết quả.
- Chạy **build.bat** có sẵn, pip check/PyInstaller thành công; tạo thư mục mới,
  không thay EXE cũ, giữ `_internal`, không đưa config/cache/output vào gói.
- EXE mới chạy GUI Windows, smoke PASS: model/effort Low, classifier hai mã
  đúng, online content guard tắt/offline giữ, cache dấu số tái sử dụng đúng.
- EXE **offline E2E thật PASS**: normal OCR/MT/inpaint/render 1 ảnh; lần cache
  bỏ qua ảnh thành công; fresh có OCR/MT/render mới; hủy sau OCR thật rồi
  reopen/resume cùng DB, OCR trên resume=0. Run cũ giữ nguyên hash/receipt.
  Không gọi AGY trong bài EXE này; không tuyên bố đã chạy AGY thật bên trong EXE.
- Lần QA EXE offline đầu FAIL vì driver cố định 1 fixture nhưng nhận 3 ảnh;
  app đã xử lý 3/3 done. Đã chạy lại bằng 1 fixture trong run riêng và PASS,
  không xóa/sửa evidence thất bại hoặc nới assertion để coi PASS.
- **527 file** production DB/journal/ảnh nguồn/output và ba bundle cũ giữ
  nguyên hash từ mốc bảo toàn trước nghiệm thu EXE. EXE cũ nguyên hash.

EXE mới:
`dist/ImageTranslatorVN-20261111T144631162670Z/ImageTranslatorVN-20261111T144631162670Z.exe`.
Giữ kèm `_internal`; dùng bản mới và đóng cửa sổ EXE cũ. Build log
`logs/build-ImageTranslatorVN-20261111T144631162670Z.log`.

Evidence: `parser-replay.json`, `model-update.json`, `source-live/report.json`,
`exe-gui/report.json`/ảnh GUI,
`single-fixture-acceptance/exe-offline/report.json` và `final-handoff.json`.
Log/XML: `logs/agy-recurring-regression.*`, `logs/agy-recurring-live.log`.

**Giới hạn còn lại:** không thể tắt bộ lọc Google bằng cách bỏ validator trong
app. Trang 112 vẫn bị provider chặn; không có nghiệm thu batch đó. Lỗi server
đóng kết nối cũng không thể bảo đảm biến mất vĩnh viễn bằng parser. Client giờ
báo đúng nguyên nhân và giữ dữ liệu, không báo thành công giả.

## Git & Fork Handoff

Root tự xác định từ Git/workspace, branch main; baseline có 15 file sửa/mới
từ các nhiệm vụ trước, index trống. Giữ nguyên các thay đổi đó. Thay đổi thêm:
`core/types.py`, model/classification trong `providers/agy.py`,
`providers/agy_diagnostics.py`, `core/agy_error_evidence.py`, `ui/main_window.py`,
`ui/provider_notice.py`, `scripts/validate_cache_ui.py`,
`tests/test_model_settings_sync.py`, `tests/test_agy_provider_failures.py`,
`tests/fixtures/agy_provider_failures.json`, README, PROJECT_STATUS và báo cáo này. Runtime
settings được ignore, chỉ sửa lựa chọn model được người dùng yêu cầu trước.
Log `logs/model-sync-before.*`, `logs/model-sync-after.*`.

Không đổi `.gitignore`, không stage/commit hoặc chỉnh Git history. Rà cuối
diff/status/index/ignore và source hashes ghi `final-handoff.json` trong evidence.
Commit message gợi ý sau khi người dùng review:
`Preserve latest AGY model preference across open windows`.

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT.**
