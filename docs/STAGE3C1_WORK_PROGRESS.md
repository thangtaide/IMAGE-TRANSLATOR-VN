# Stage3C.1 — checkpoint công việc Codex

## A — Audit hoàn tất, 08/11/2026

- Đọc AGENTS/PROJECT_STATUS, báo cáo Stage3C/điều tra pause và parser/guard,
  multipage/pipeline/diagnostics/resume, test liên quan.
- Git main/HEADeb5554b; có sẵn PROJECT_STATUS sửa và báo cáo điều tra untracked.
  Không hoàn nguyên hoặc commit. Xem logs/latest-stage3c1.json cho evidence.
- Snapshot hash runtime/job276337 theo trạng thái thực tế mới (xemB), cache/DB/
  journal/model/config/4EXE trước sửa. Không Resume/provider/network.
- Guard quét key truthy đệ quy và event tool; không quét text string/stderr.
  Nested metadata mơ hồ phải UNKNOWN, chưa có bằng chứng false positive thực.
- Quyết định: diagnostic observer tách riêng, không đổi predicate/verdict,
  prompt/CLI/budget/cache identity/numeric guard/journal schema.
- Test mới: CHƯA CHẠY. Bước tiếp: triển khai observer đã lọc, nối logging lỗi
  batch, thêm fixture/tests; cập nhật progress sau mỗi giai đoạn.

## B/C — Triển khai observer và logging (đang kiểm thử)

- Người dùng xác nhận đã tự tiếp tục job trước Stage3C.1. Baseline thật đã
  snapshot:113output/112normal+fallback106/needs_retry106; không còn57pending.
  Không rollback về trạng thái lỗi lịch sử. Snapshot1058file tại evidence.
- Thêm providers/agy_diagnostics.py; wrapper quanh parser legacy, predicate
  tool/schema/ID vẫn nguyên. Không đổi prompt/settings/identity/budget.
- Thêm counters transport, attachment metadata batch/provider; log writer lọc
  lại allowlist và loại OCR/target/path/raw exception trong AGY diagnostic.
- core/pipeline chỉ nối log pause/cancel/error, không đổi checkpoint/verdict.
  Không migration journal. Thêm20case fixture MANUAL có nhãn, không phải live.
- Test cũ AGY/multipage đang chạy; tiếp theo thêm test privacy/fixture/resume,
  full regression và đối chiếu hash. Chưa ghi kết quả PASS khi chưa kiểm tra.

## D — Fixture/contract tests hoàn tất; regression đang chạy

- 20case MANUAL: valid, explicit named request+arguments, khai báo kiểu JSON
  Schema, declaration chưa xác minh, mixed text/request, malformed/unknown,
  missing/wrong/duplicate ID/result và text literal. Không gọi đó là capture thật.
- 19test mới targeted PASS;59test AGY/multipage cũ PASS. Có test process Python
  cục bộ cho stdout/stderr cap, timeout/cancel; không gọi executable AGY thật.
- Test privacy, no-cache/no-render khi reject, region/receipt giữ nguyên qua
  pause→manual Offline resume, budget/cache không đổi. Observer-failure cũng
  không được đổi verdict; full suite đang xác minh bản cuối.
- Snapshot AST/byte chứng minh predicate guard, prompt/CLI, identity, numeric/
  glossary/cache method và packing thresholds không đổi (behavior-preservation.json).
- Bước tiếp: lấy kết quả full pytest/unittest, kiểm định job113output/hash,
  cập nhật báo cáo/tài liệu và Git/Fork. Không live/production resume/build.

## E/F — Regression và bảo toàn hoàn tất

- Full pytest368PASS/10SKIPPED/0FAIL; unittest368PASS/10SKIPPED/0FAIL (378ca).
  Lý do skip cũ giữ nguyên; test mới19, fixture subcases20. Không live.
-1058/1058file bảo vệ giữ hash; audit bitmap/receipt/SQLite chỉ đọc PASS.
  Job276337 giữ113output,112normal+fallback106/needs_retry106;4EXE/model/config
  nguyên. Báo cáo điều tra trước giữ nguyên hash. Không journal migration.
- Cập nhật PROJECT_STATUS, USER_GUIDE, TROUBLESHOOTING; tạo báo cáo
  STAGE3C1_AGY_TOOL_USE_DIAGNOSTICS_REPORT.md. Trạng thái:
  STAGE_3C1_DIAGNOSTICS_WITH_WARNINGS. Không biết nguyên nhân sâu hơn của lỗi cũ.
- Bước cuối: Git diff/check-ignore/secret+binary review, ghi handoff; không
  stage/commit/push/tag/reset/clean. Không hotfix guard hoặc live tái hiện.

## G — Bàn giao hoàn tất

- Git diff --check PASS; .gitignore không đổi, source/test/fixture/docs hiện
  đúng, runtime/model/log/output/EXE bị ignore. Không file binary lớn hoặc
  credential mới trong review.7tracked sửa/6untracked; trong đó báo cáo điều
  tra pause là untracked cũ, không do Stage3C.1 tạo.
- Đề xuất commit sau review: fix(agy): add safe tool-use protocol diagnostics.
  NO_COMMIT / NO_PUSH / NO_TAG / NO_DESTRUCTIVE_GIT. Người dùng tự commit Fork.
- Không làm tiếp guard fix/CLI change/live QA. Nếu nối phiên, đọc report và
  progress này trước; chỉ thực hiện nhiệm vụ tiếp theo khi người dùng yêu cầu.
