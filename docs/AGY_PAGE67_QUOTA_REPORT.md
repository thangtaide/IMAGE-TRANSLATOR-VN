# AGY Trang 67: quota và phân loại lỗi — 11/11/2026

**BLOCKED_BY_PROVIDER / CHƯA ĐẠT end-to-end.** Đã sửa lỗi ứng dụng gán nhầm
thông báo quota thành PROVIDER_UNAVAILABLE. AGY thật vẫn từ chối do hạn mức;
không có bản dịch hoặc ảnh mới để nghiệm thu, chưa build EXE.

Project root được xác định từ workspace/Git, code dùng module ROOT; evidence:
`output/agy-page67-20261110T181103Z/`. Không có đường dẫn project cố định trong
bản sửa. Người dùng cấp tối đa 6 request và quyền giải mã DPAPI cho điều tra
này; đã dùng **1**, còn **5**, không dùng tiếp khi quota vẫn lỗi.

## Nguyên nhân ba attempt

| Attempt | UTC | Thời gian | Exit | stdout/stderr byte |
|---|---|---:|---:|---:|
| `9256526949d14e6ab2a095b658aec8ce` | 10/11 17:48:03 | 2,578 s | 3 | 9638 / 412 |
| `74271ef97915487f9e4e9eed7c69bd82` | 10/11 17:59:34 | 3,640 s | 3 | 9638 / 412 |
| `ca7cd07990494cdc839689fe5aa349b1` | 10/11 18:07:04 | 2,438 s | 3 | 9639 / 414 |

Cả ba cùng job `66f9042a8876fd519ec447c0e571b4e2b0a7ab5b23bea0f818b14ddf8a168602`,
model `gemini-3.8-flash-medium`, CLI 1.5.5, cùng batch 14 trang/57 vùng/564 ký tự.
Batch SHA256: `a7580938239fa1fda9e906f53381de98d6ea828846e66e1766a24dc9475e5706`;
payload SHA256: `8a023da1c17c079462b426b004b99fd2792f42fd670b9a050c7dc5d0da7398ce`.
Các retry có nội dung payload giống nhau, không phải timeout 300 giây.

Đọc metadata/outcome và giải mã stdout/stderr CurrentUser DPAPI thành công,
kiểm tra hash capture. Chỉ ghi tóm tắt đã bỏ ID lỗi/đường dẫn/token; không lưu
raw plaintext hoặc gửi diagnostic ra ngoài. Cả ba có:

- Một terminal result hợp lệ về envelope: `status=ERROR`, `finished_reason=error`.
- `error` là **chuỗi** “Individual quota reached”, không phải object có `code`.
- stderr AGY_ERROR báo `status=RESOURCE_EXHAUSTED`, `error_code=429`,
  `retryable=true`. Ứng dụng không coi retryable là quyền tự gửi lại.
- Không có response hoặc structured_output chứa bản dịch để khôi phục.
- `parser_reason=NONE` đúng vì không phải lỗi JSON/schema/tool guard.
  Outcome cả ba: `paused_provider`.

Provider/CLI đang báo hết hạn mức cá nhân. Đồng thời parser ứng dụng chỉ nhận
`RESOURCE_EXHAUSTED`/`QUOTA_EXCEEDED` trong terminal error; terminal dạng chuỗi
không có hai enum này nên rơi xuống PROVIDER_UNAVAILABLE. Đây là lỗi **phân
loại**, không phải bỏ qua bản dịch thành công.

CLI có đưa countdown reset khoảng 104–105 giờ ở ba log. Không coi countdown
là thời điểm reset đã được backend xác nhận. Trạng thái backend nhận request
và tính phí: **UNKNOWN**, không suy ra miễn phí từ exit code hoặc lỗi quota.

## Bản sửa tối thiểu

`providers/agy.py`, nhánh terminal status/exit lỗi: nhận diện thêm đúng cụm
`INDIVIDUAL QUOTA REACHED` không phân biệt hoa/thường và trả
`ProviderSuspended('QUOTA_EXCEEDED', ...)` với thông báo tiếng Việt hiện có.

Giữ nguyên JSON/ID/count/schema/tool/numeric validation, prompt, provider
identity, model, session settings, OCR, mask, inpaint và renderer. Không đổi
GUI, tài khoản, token, hooks hoặc cấu hình bảo mật. Không tự chuyển credits,
API key/model/provider. Không thêm retry hay vòng chờ quota.

Phát lại ba stdout thật trong RAM bằng parser baseline và parser mới:
**3/3 PROVIDER_UNAVAILABLE → QUOTA_EXCEEDED**, cả hai đều REJECT, không tạo
bản dịch hợp lệ giả. Dữ liệu: `parser-replay.json`, `diagnostic-summary.json`.

## Request AGY thật

| Lượt | Mục đích/phạm vi | Kết quả |
|---|---|---|
| 1/6 | Source ProcessingManager, đúng ảnh `0067.jpg`, OCR thật đã lưu: 3 vùng/43 ký tự; cùng model, không mock CLI | 18:16:59–18:17:02 UTC, 2,938 s CLI, exit 3; **QUOTA_EXCEEDED**, BLOCKED_BY_PROVIDER |

Help/version chỉ là local CLI capability probes, không tính là request dịch.
Ledger durable được cập nhật trước invocation, giới hạn provider=1 cho lượt
probe, không retry. Không gửi lại batch 14 trang khi request nhỏ cũng báo quota.
Không dịch lại cả chương.

Thử nghiệm dùng SQLite/journal/output riêng trong `source-live/`; chỉ seed OCR
từ SQLite snapshot read-only. Chặn inference OCR mới để phát hiện cache miss.
Source pipeline thực nhận lỗi quota, dừng ở `paused_provider`; zero translation
cache entry, zero output file, không xuất fallback giả thành công. Capture và
service close không giữ stdout plaintext trong cache/DB.

Evidence thật: `agy-budget.json`, `live-plan.json`, `source-live/report.json`,
`logs/agy-page67-live.log`. Dữ liệu thật này chỉ chứng minh lỗi quota và đường
dừng đúng; **không** chứng minh dịch/render end-to-end thành công.

## Checkpoint và regression

Production journal có 144 trang, 65 `done`, một `fallback_original` (ảnh 0020,
lỗi numeric riêng ngoài phạm vi), 78 `pending`; Trang 67 là trang pending tiếp
theo. Có 232 region receipt. Không xóa, sửa hoặc chủ động resume journal này.
Ba attempt dừng cùng batch còn pending vì không nhận được bản dịch hợp lệ;
không có bằng chứng checkpoint gây lỗi quota. Không suy đoán ai đã bấm resume.

- Trước sửa: **58 PASS** (AGY, diagnostic, timeout lifecycle).
- Fixture mới tái hiện trước sửa: **2 FAIL** đúng lỗi mã phân loại.
- Sau sửa, ba test mới: **3 PASS**; fixture tổng hợp đã khử dữ liệu nhạy cảm.
- Regression sau sửa: **148 PASS / 0 FAIL / 0 SKIP**. Gồm AGY Batch, Whole,
  diagnostic, finish/tool guard, disabled hooks, timeout, multipage và resume.
- Test checkpoint với lỗi quota dạng chuỗi kiểm tra ảnh đầu tiên đã thành
  công giữ nguyên hash/receipt; chỉ hai ảnh pending được xử lý khi chủ động
  resume bằng fixture. Có test hai tiến trình Python khác nhau. Đây là test
  mock/fixture, không phải một lần resume production thành công với AGY thật.
- **SKIP/BLOCKED:** AGY dịch/validation/render thành công, đúng batch 14 trang
  sau quota, full suite toàn ứng dụng, build và chạy/smoke EXE mới.

Log/XML: `logs/agy-page67-baseline.*`, `logs/agy-page67-reproduction.*`,
`logs/agy-page67-fixed.*`, `logs/agy-page67-regression.*`.

## Điều kiện tiếp tục và EXE

Cần quota của tài khoản/model đang dùng khả dụng trở lại trước khi kiểm thử
dịch end-to-end. Không thể khắc phục hạn mức bằng thay validator hoặc chấp
nhận một response lỗi. Sau đó người dùng chủ động tiếp tục; cần kiểm tra lại
batch pending trong run riêng trước khi bàn giao EXE. Không bấm tiếp tục nhiều
lần trong lúc CLI còn báo quota.

Theo yêu cầu chỉ build sau khi sửa và kiểm thử đạt, **không chạy build.bat** khi
live source vẫn BLOCKED. Chưa có EXE mới; EXE cũ chưa chứa thay đổi phân loại
ở lượt này và được giữ nguyên. Không tuyên bố nghiệm thu thành công.

## Git & Fork Handoff

Root/branch lấy từ Git; branch `main`, baseline sạch, HEAD
`00213e305b280d99b52946b9e12159d21ee49982`. Không có thay đổi sẵn có bị ghi đè.
Các file cần review:

- `providers/agy.py`: phân loại explicit quota string.
- `tests/test_agy.py`: quota Batch/Whole, latch, không cache lỗi, strict guard,
  checkpoint giữ thành công.
- `tests/fixtures/agy_individual_quota.json`: fixture tổng hợp, không raw capture.
- `PROJECT_STATUS.md`, `docs/AGY_PAGE67_QUOTA_REPORT.md`.

Evidence/log/cache không đưa vào source review; `.gitignore` giữ nguyên.
230 file dữ liệu được theo dõi và một EXE hiện có giữ nguyên hash. Không thay
DB/schema/checkpoint/config. Kết quả bảo toàn hash,
status/index/unmerged, diff check, ignore và rà secret lưu `final-handoff.json`
trong thư mục evidence. Commit message gợi ý để người dùng review nếu muốn:
`Classify AGY individual quota errors without retrying`.

**NO_COMMIT · NO_PUSH · NO_TAG · NO_DESTRUCTIVE_GIT.**
