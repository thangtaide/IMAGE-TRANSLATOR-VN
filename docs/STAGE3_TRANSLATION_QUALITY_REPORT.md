# Stage 3 — chất lượng Trung→Việt và quyết định triển khai

Ngày: **08/11/2026 (+07)**. Kết luận: **STAGE_3_RESEARCH_ONLY**.
Đã hoàn thành benchmark QA/từng chặng, thử4 ứng viên, nghiên cứu model trực tiếp,
regression và bảo toàn dữ liệu. **Không đưa ứng viên vào production, không retry
trang111, không đổi model/provider/guard/cache/recipe, không build EXE.**

## 1. Dữ liệu, nguồn và split

Nguồn chỉ từ dữ liệu đã có, không tải ảnh hoặc gọi Kuaikan:

| Nguồn | Ảnh có OCR cache ánh xạ đúng hash/model/config | Vùng OCR thô |
|---|---:|---:|
| Chương274872, snapshot pipeline.sqlite3 | 120 | 106 |
| Corpus ImgTest cũ, snapshot batch-state.sqlite3 | 61 | 77 |
| Tổng | 181 lượt ảnh nguồn | **183** |

Gộp trùng **chính xác text + chính sách giữ nguyên**, còn165 mẫu. Chọn150 mẫu
theo phủ nhóm/confidence và seed cố định, không dùng output/model score. Bỏ15
mẫu duy nhất theo chính sách chọn đã ghi rõ. Trong150 mẫu có167 occurrence
(97 từ chương hiện tại,70 ImgTest),146 cần MT và4 control giữ nguyên. Không
gọi150 là150 ảnh hoặc150 câu độc lập.

**99 development / 51 holdout**, chốt trước suy luận. Text chuẩn hóa phục vụ
gom nhóm (NFKC/punctuation/whitespace) không được đưa vào model thay source thật.
Các text giống/near-duplicate ≥.88 ở cùng family/split. Nhóm lỗi đã biết từ task
(ngày/Name/hoa văn) luôn development. Không sửa ứng viên sau khi xem holdout;
hash code/dataset và `candidates-frozen.json` lưu bằng chứng.

Split này không độc lập theo ảnh, nhân vật hoặc bộ truyện; có thể cùng bối cảnh
giữa hai tập. Kiểm soát near-duplicate theo tiêu chí text, không tuyên bố loại
mọi trùng lặp ngữ nghĩa. Chỉ một bộ truyện/những panel đã có, không đủ đại diện
mọi truyện Trung hoặc ảnh dài.

### Phủ nhóm (tag chồng lấp, phần lớn là heuristic nguồn)

| Nhóm | Số mẫu |
|---|---:|
| Hội thoại ngắn / dài candidate | 102 / 15 |
| Cảm thán / câu hỏi | 19 / 11 |
| Thông báo hoặc credit | 24 |
| Tên riêng candidate / danh xưng / thành ngữ candidate | 32 / 28 / 3 |
| Ngày tháng / số lượng / số tiền | 1 / 5 / 1 |
| Một–hai ký tự | 27 |
| Confidence thấp / trung bình / cao | 20 / 15 / 115 |
| Giữ nguyên đã xác định | 4 |
| Có khoảng trắng ghép OCR, chưa chứng minh nhiều dòng | 27 |
| Tuổi / literal newline / điện thoại-ID tự nhiên | **0 / 0 / 0** |

Không bịa thêm mẫu thật để lấp nhóm thiếu. Các fixture ngày/giờ/điện thoại/ID/
giá tiền là bộ kiểm tra cấu trúc tổng hợp riêng, không gộp vào150 mẫu tự nhiên.

## 2. Ground truth và giới hạn chấm điểm

**0 bản dịch tham chiếu được người rà soát độc lập.** Cả150 row là
`UNVERIFIED_REFERENCE`, reference_vi=null. Có1 kỳ vọng ngày tháng do người dùng
nêu trong task, ghi riêng `USER_TASK_EXPECTATION_NOT_INDEPENDENT_CORPUS_GT`.
Output Argos cũ hoặc ứng viên không được coi là đáp án chuẩn.

Tạo `human-reference-template.csv` chỉ có source/provenance và cột tham chiếu
trống; nên dịch/đối chiếu ảnh trước khi mở `outputs-for-review.csv` để hạn chế
thiên kiến. Không tính BLEU/COMET/accuracy, không tự chấm một tỷ lệ đúng nghĩa.
Các nhận xét trợ lý về ảnh/câu khó đều gắn trạng thái chưa có human review.

## 3. Baseline thật và điều kiện chạy

Argos `zh→en→vi`, hai model1_9 hiện có, CPU int8, intra_threads2/inter_threads1,
beam4,length_penalty0.2,max_decode768,replace_unknowns=true. Không thay tokenizer,
grouping, source, provider route hoặc decode khi đo baseline. Observer gọi decode
gốc, không sửa output; đối chiếu3 source development với provider nguyên bản
cho kết quả giống nhau. Không vượt384 input token hoặc lỗi suy luận trong150 mẫu.

Hai process development/holdout riêng, model load khoảng0,273/0,279 giây (OS
disk cache không được kiểm soát), peak working set420.807/419.734 MB. Máy
i7-12700F12 core/20 logical, khoảng32GiB RAM; không dùng GPU. Đây là RAM process
chứa hai model/runtime, không phải RAM riêng từng model hay bảo đảm trên máy khác.

Mean baseline **202,1 ms/mẫu cần MT**, CPU time tổng37,19 giây cho146 mẫu. Các
lượt chạy tuần tự, cùng thứ tự mẫu, không randomized timing/repeat trials;
không kết luận tốc độ có ý nghĩa thống kê từ chênh lệch vài ms.

**158 historical accepted-cache occurrences khớp output baseline mới**,0 khác.
Đây là tái hiện kỹ thuật, không phải158 bản dịch được xác nhận đúng. Các output
`Name` tái hiện trực tiếp qua model, không phải dấu hiệu cache bị ghi nhầm.

## 4. Lỗi quan sát theo chặng

| Nguồn thật | zh→en | en→vi | Quan sát |
|---|---|---|---|
| 活动时间 | Activity Time | Name | Chặng EN→VI mất nội dung; user đã nêu lỗi này |
| 活动时间和活动内容 | Activity time and content | Name | Chặng EN→VI; không phải lỗi OCR/grouping để tạo Name |
| 5月20日—5月30日 | 20-30 May | 20 giờ 30 tháng 5 | Lỗi nghĩa ngày→giờ ở EN→VI, tái hiện Stage2 |
| 第13话 | Rule 13 | Nguyên tắc 13 | Lệch nghĩa ngay ZH→EN dù số13 giữ đúng; phân tích chưa có independent reference |
| 千城确实有很大责任， | It is true that thousands of cities are responsible. | Đúng là hàng ngàn thành phố phải chịu trách nhiệm. | Tên nhân vật bị hiểu như danh từ/số nhiều ở ZH→EN; cần human review ngữ cảnh |
| 今天可是赵王府楚世子 与顾家大小姐大喜的日子 | It's the birthday of Prince Chu of Zhao and Miss Gu's family. | Hôm nay là sinh nhật… | Wedding context nhưng English thành birthday; vấn đề bắt đầu ở chặng đầu, không đổ hết cho chặng hai |
| 值足有百万两。 | It's worth a million taels. | Nó trị giá cả triệu lượng. | Ví dụ giữ được ý số tiền quan sát được; không biến thành điểm GT toàn corpus |
| 回去！ | Go back! | Quay lại! | Câu ngắn đơn giản có output phù hợp quan sát |

Không đủ ground truth để kết luận định lượng lỗi “chủ yếu” nằm ở chặng nào.
Nhóm cần chú ý: credit/tên riêng, danh xưng, câu ngắn thiếu ngữ cảnh, câu bị cắt,
thành ngữ và ngày tháng. Regex số không phát hiện được sai nghĩa như Rule13.

`visual-review.json` ghi thêm3 mẫu xem ảnh: mép ảnh0030/0072 có glyph bị cắt và
OCR khả nghi; các vùng `米` trên ảnh ImgTest có dấu hiệu là hoa văn, kể cả
confidence≈.998. Đây là **ASSISTANT_VISUAL_REVIEW_UNVERIFIED**, không tự sửa text,
không thêm override và không biến suy đoán thành human ground truth. Câu bị
cắt/đứt giữa vùng không nên quy toàn bộ cho MT hoặc tự ghép hai nhân vật.

Taxonomy đầy đủ được lưu trong `error-analysis.json`; mẫu chưa đủ dữ liệu giữ
`INSUFFICIENT_EVIDENCE`. Numeric guard rejection không tự động được gọi là
semantic NUMERIC_ERROR. Không tìm thấy hậu xử lý số gây các lỗi Name/ngày đã
tái hiện: output cuối là kết quả native decoder sau strip.

## 5. Bốn ứng viên QA, tách riêng từng thay đổi

Mọi suy luận dùng model thật; không fake target. Code ở `qa/` không được import
bởi ứng dụng hoặc đăng ký thành provider. Không dùng DB/cache production làm nơi
thử. Tất cả chạy Offline, audit hook chặn socket/DNS.

| Ứng viên | Output đổi /150 | Guard literal /146 cần MT | Hiệu ứng có bằng chứng | Mean ms |
|---|---:|---:|---|---:|
| Baseline | — | **145 PASS,1 reject** | Name2; lỗi ngày1 | 202,1 |
| NFC/trim | 0 | 145/1 | Không có lợi ích quan sát trong corpus | 218,5 |
| Chia câu trong cùng vùng | 6 | 145/1 | Chưa có GT để xác nhận tốt hơn; không ghép vùng/bong bóng khác | 223,0 |
| length_penalty1.0 | 61 | **144/2** | Name2→0 ở dev, nhưng có **1 regression số holdout** | 224,0 |
| Khoảng ngày typed QA | 1 | **145/1 vẫn như cũ** |1 typed endpoint proof PASS; QA proposed policy146/146, chưa nối production | 211,7 |

Không gọi146/146 của policy QA là production numeric guard PASS hay semantic
accuracy. Candidate ngày vẫn bị literal guard hiện tại từ chối do đổi cách viết
ngày/tháng; nó cần một policy typed có version,cache/fingerprint,rollback riêng
trước khi có thể dùng thật. Các counter gồm4 control không cần MT được tách riêng.

### Holdout sau khi freeze

51 mẫu gồm49 cần MT/2 control. Baseline49/49 numeric accept; NFC49/49,split49/49,
date49/49 không đổi output. **Holdout không có khoảng ngày tự nhiên**, nên không
chứng minh tổng quát hóa handler ngày. LP1.0 chỉ48/49:

`分镜：墨墨子` → `Mirror: Ink` → baseline `Lỗi`, candidate **`Lỗi:% 1`**.

Nguồn và English không có digit1, chặng EN→VI thêm1. Đây là regression thật
về số/hallucinated token; `Lỗi` ở đây là **văn bản model trả**, không phải
exception chương trình. Không tiếp tục dò các penalty khác sau khi xem holdout,
không sửa rule theo sample này. **Loại LP1.0 khỏi production.**

LP1.0 cải thiện mô tả của hai ca Name nhưng còn thay đổi khó kết luận hoặc kém
hơn ở credit/“on line”; không được dùng hai ví dụ đẹp để tuyên bố toàn model tốt.
Tổng cải thiện/regression ngữ nghĩa chưa xác minh là **UNKNOWN**, không phải0.

## 6. Khoảng ngày: khả năng và những gì chưa đạt

QA handler full-match **hai ngày CJK hoàn chỉnh với delimiter rõ** (—/–/-/至/到/~),
kiểm tra calendar, endpoint/year và thứ tự; không suy năm, không dùng placeholder,
không xử lý text thừa bằng cách xóa chúng. Output dựng từ cấu trúc nguồn, không
sửa bản dịch sai của Argos bằng thay số. Kiểm tra typed source/target theo tuple
có vai trò/thứ tự, không set/multiset.

Ca thật111: **`Từ ngày 20/5 đến ngày 30/5`**, typed integrity PASS trong QA.
Đây là định dạng hóa có cấu trúc, không phải Argos đã tự dịch đúng. Chuỗi tham
chiếu trong task thiếu gạch `5月20日5月30日` được coi là nhập nhằng; không đoán
thành khoảng. Cache thật có `—`, đủ điều kiện parse QA.

- **128 fixture tổng hợp** tách biệt:64 positive/64 negative,128 đạt tiêu chí
  parser/format;192 mutation về ngày/đảo mốc/clock bị từ chối đúng.
- Có năm rõ, cùng/khác tháng,12→1 không thêm năm, ngày nhuận có năm; bác ngày
  sai, năm thiếu một phía, năm không rõ với29/2, Unicode digit ngoài phạm vi,
  text thừa, giờ/phút, số tiền/số lượng/điện thoại/ID/số âm.
- **20 date inference bổ sung** từ fixture: baseline Argos thật/candidate typed
  được lưu; candidate20/20 đúng endpoint. Baseline **0/20 có từ giờ/phút**,
  không thổi phồng thành20 lỗi ngày của model. Các output khác định dạng chưa
  được thẩm định ngữ nghĩa. Không tính fixture này vào150 mẫu tự nhiên.
- Probe ngoài holdout phát hiện giới hạn năm0001: formatter ra năm1 nhưng proof
  target yêu cầu4 digit, nên **round-trip proof không đạt**. Lưu nguyên
  `exploratory-edge.json`, không chỉnh candidate sau holdout rồi gọi độc lập.
  Guard trong QA không chứng nhận output đó; đây là tồn tại, không production-ready.

Chưa thử placeholder mới: không có glossary tên riêng đáng tin cậy và Argos có
thể biến đổi marker. Không tạo test giả cho placeholder hoặc tuyên bố money/
phone/ID đã có bộ tái dựng riêng. Các dạng đó chỉ được kiểm tra âm tính với date
parser. Không áp dụng normalizer mạnh hoặc tự sửa OCR.

## 7. Model direct zh→vi

Máy chỉ có Argos zh_en/en_vi; **không có weights zh_vi trực tiếp**. M2M100 đã
có adapter nhưng real inference vẫn SKIPPED. Đã xác minh card/API chính thức:

| Model | Kiến trúc | PyTorch weights nguồn | License | Trên corpus150 |
|---|---|---:|---|---|
| [OPUS-MT zh-vi](https://huggingface.co/Helsinki-NLP/opus-mt-zh-vi) | Marian, direct zh→vi |312.087.009 byte +SP/vocab | Apache-2.0 | **NOT TESTED** |
| [M2M100418M](https://huggingface.co/facebook/m2m100_418M) | M2M100 multilingual |1.935.796.948 byte | MIT | **NOT TESTED** |
| [NLLB600M](https://huggingface.co/facebook/nllb-200-distilled-600M) | M2M100 family |2.460.457.927 byte | CC-BY-NC-4.0 | **NOT TESTED** |

Đây không phải dung lượng CT2 int8/RAM/latency model mới. RAM và chất lượng
ba model **chưa đo**. Metadata có revision/SHA256 server công bố, chưa hash
trọng số cục bộ vì chưa tải. Chi tiết nguồn, tokenizer,checksum,CPU/portable:
`logs/stage3-translation-quality-20261107T204426Z/model-comparison.md`.

CT2 cục bộ4.6.0 có Marian/M2M loader; docs online mới hơn không được dùng để
tuyên bố runtime đã convert thành công. **Transformers chưa cài**, không cài
để thử. OPUS cần source/target SP/vocab phù hợp, không rename thành Argos gói
single-SP. NLLB cần provider/lang tags/receipt riêng. Nguồn truy cập được không
chứng minh chất lượng hoặc portable EXE.

Ưu tiên đề xuất thử OPUS trực tiếp ở QA sau chấp thuận tải vì có nguồn cụ thể,
license và dung lượng nhỏ hơn; **không nói đã tốt hơn Argos**. M2M100 có adapter
sẵn nhưng nặng hơn; NLLB có điều kiện NC và tích hợp mới. Chưa tải model nào.

## 8. Quyết định production và trang111

**Không promotion**. Thiếu tham chiếu ngữ nghĩa độc lập; split không có ngày
holdout tự nhiên; LP làm tăng lỗi số; date QA có edge chưa đạt và chưa tích hợp
typed guard/cache/recipe an toàn. Không sửa numeric validator để chấp nhận output
QA, không tái sử dụng cache cũ dưới thuật toán mới, không đổi provider mặc định.

Trang111 **không retry thật**, vẫn FALLBACK_ORIGINAL/needs_retry111. Chương vẫn
120 output/119 hoàn tất pipeline/1 fallback,119 output cũ giữ nguyên. Không tạo
ảnh QA rồi gắn checkpoint production là done. Không thay checkpoint/manifest.

Trước nâng cấp model/algorithm cần identity có version decode/tokenizer/model
revision/hash, namespace cache tách biệt, bộ kết quả theo cùng schema và rollback.
Thay global decode cần recipe/run mới, không sửa119 checkpoint để ép reuse.
Handler typed hẹp nếu tích hợp sau phải có guard vai trò endpoint, version cache/
metadata riêng và dry-run trước, không chỉ bypass regex. Chưa triển khai các việc đó.

## 9. Regression và bảo toàn

- **Pytest261 PASS,10 SKIPPED,0 FAIL**,271 ca,58,60 giây.
- **Unittest261 PASS,10 SKIPPED,0 FAIL**,271 ca. Thêm9 test QA thực hiện được;
  không xóa test cũ. Probe early-year không đạt vẫn được báo riêng như trên.
- **GUI Qt Windows PASS**, E2E production Offline ảnh đơn/thư mục thật PASS,
 2 vùng OCR/2 bản dịch ở ảnh đơn,149 heartbeat,pause/resume,nguồn/config nguyên.
  Đây là regression pipeline hiện tại, không phải ứng viên đã vào GUI.
-10 skip giữ lý do thiếu model/ngôn ngữ/Online/live opt-in/M2M100; không nói
  sandbox đang chặn chỉ vì skip reason lịch sử có chữ đó.
- **688/688 file bảo vệ giữ hash**, bao gồm DB/cache/manifest,120 source/cache,
 120 output hiện tại (119 bình thường +fallback),model/config/override/DOM/BAT/
 spec và4 EXE. Không có model file mới. Production source fingerprint bằng
 Stage2; không ghi dữ liệu production. Không full hash toàn bộ .venv; không cài package.

Benchmarks/regression không có socket/DNS attempts. **Có truy cập mạng nghiên
cứu**: web card/docs và3 GET metadata HF,19.095 byte JSON; không gửi OCR,không
gọi Kuaikan,không tải ảnh/trọng số. Không ghi API key,cookie hoặc signed URL.

Hai lệnh tổng hợp QA từng cần sửa lỗi encoding/quote, không ảnh hưởng inference,
dataset hoặc production; ghi tại `qa-reporting-notes.txt`. Không che probe edge
hoặc regression LP, không biến test không chạy thành PASS.

## 10. File, evidence và bước tiếp

Code mới **chỉ QA**: `qa/__init__.py`, `qa/translation_quality.py`,
`qa/build_quality_dataset.py`, `qa/benchmark_translation.py`,
`qa/date_quality_fixtures.py`, `qa/analyze_quality.py`.
Test mới `tests/test_stage3_quality.py`. Không sửa core/providers/sources/ui,
model,config,launcher,spec,EXE hoặc .gitignore. AGENTS hiện có đã đủ quy tắc
cập nhật tài liệu, không bổ sung workflow mới.

Evidence `logs/stage3-translation-quality-20261107T204426Z/`:

- `dataset-manifest.json`, `snapshots/`, `inventory.json`, `protected-before.json`.
- `development/`, `holdout/`, `candidates-frozen.json`, `baseline.json`,
  `candidate-results.json`, `benchmark-metrics.json`, `error-analysis.json`.
- `structural-fixtures.json`, `structural-evaluation.json`,
  `supplementary-date-inference.json`, `exploratory-edge.json`.
- `visual-review.json`, `historical-reproduction.json`,
  `human-reference-template.csv`, `outputs-for-review.csv`.
- `model-metadata.json`, `model-comparison.md`, `promotion-decision.json`.
- `pytest-final.xml`, `unittest-final.json`, `regression-results.json`,
  `preservation.json`, `summary.json`.
- GUI/E2E: `output/source-tabs-validation/20261107T211218Z-1e1b21/report.json`.

Đã cập nhật PROJECT_STATUS, USER_GUIDE, TROUBLESHOOTING, README,
TRANSLATION_QUALITY_REPORT và M2M100_SETUP, giữ lịch sử Stage1/2. Stage4/5 chưa làm.

Tiếp theo: người rà soát điền tham chiếu độc lập; chốt phạm vi handler ngày/
sửa edge và kiểm thử mới trước integration; hoặc chấp thuận thử model direct
trong QA với checksum/tokenizer/identity đúng. Không tiếp tục dò LP theo holdout,
không tự tải/cài và không tự phục hồi111 trong lượt này.

**STAGE_3_RESEARCH_ONLY**

## Git & Fork Handoff — bổ sung 08/11/2026

Đã audit Git riêng sau báo cáo kỹ thuật. Root D:/TransTool, branch main;
baseline18 modified/61 untracked files, cuối lượt19 modified/62 untracked files.
Không staged hoặc xung đột. .gitignore sửa phạm vi DB và mở source/manifest model;
source QA/test/docs vẫn hiển thị, runtime không xuất hiện để commit. Diff --check
PASS; không phát hiện tracked runtime hoặc file review >2MiB. Fixture query sign
đã là dummy32zero; không in credential. Chi tiết danh sách commit/không commit,
baseline cũ cần review, checks và commit message trong
`docs/GIT_FORK_WORKFLOW.md`; evidence `logs/git-fork-handoff-20261108T013905Z/`.
Không chạy lại inference/regression ở lượt chỉ sửa docs/ignore. Không coi Stage3A
online provider đã triển khai. **NO_COMMIT, NO_PUSH, NO_TAG, NO_DESTRUCTIVE_GIT**.
