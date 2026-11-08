# Hướng dẫn sử dụng Image Translator VN

## Stage3D.2 — luồng chọn và phân tích chương

1. Tab Link truyện: nhập URL, bấm **Phân tích link** hoặc chủ động nhấn Enter.
   Chỉ nhập URL không tự gọi website; Enter cũng không bắt đầu tải/dịch.
2. Danh sách chương ở ngay dưới metadata. Chọn chương, hoặc Chọn tất cả/Bỏ chọn
   tất cả. Quyền truy cập/số ảnh/điều kiện tải vẫn có trong tooltip và nâng cao.
3. Bấm **Phân tích chương đã chọn** ngay trên bảng. Không cần mở Tùy chọn
   nguồn/cache. Mỗi lượt tối đa10chương như giới hạn worker cũ; nếu chọn hơn,
   nút giải thích lý do disabled. Việc phân tích giữ selection/thứ tự, không
   tải file ảnh, không dịch và vẫn qua access gate của adapter.
4. Sau khi điều kiện tải hợp lệ, chủ động **Tải và dịch** dưới bảng. Tạm dừng/
   Tiếp tục từ cache/Hủy/Mở kết quả giữ hành vi cũ. Resume chỉ bật khi có mô tả
   checkpoint của chương hiện tại; worker vẫn xác minh đầy đủ trước xử lý.
5. Thư mục xuất/cache/chi tiết kỹ thuật nằm dưới phần chính, có thể mở rộng.
   Menu Thêm chứa khôi phục job đã lưu và retry. Cửa sổ nhỏ/high DPI có vùng cuộn.

Thông báo lỗi mặc định chỉ có tiêu đề/mã/hướng xử lý ngắn. Bấm **Chi tiết** để
xem nguyên nhân, bằng chứng request, provider/model/trang và nhật ký đã lọc.
× chỉ ẩn thông báo; không resume hay đổi provider. Lỗi đã lưu được ghi rõ là
lịch sử, không được coi là request mới trong phiên hiện tại.

Với Gemini API: đủ Free tier/key presence chỉ tạo `READY_UNVERIFIED` cục bộ.
`ACCESS_DENIED` không tự chứng minh key sai hoặc phải bật billing. Chỉ banner có
metadata RESPONSE_RECEIVED + status403 mới nói HTTP403. NOT_ATTEMPTED là chưa
gọi HTTP trong attempt đó; ATTEMPT_STARTED chưa chứng minh đến Google; UNKNOWN
là chưa đủ bằng chứng. Không tạo key mới, đổi model hoặc bật billing chỉ vì
thông báo chung. Lỗi **Nguồn truyện từ chối truy cập** là từ website nguồn,
không phải Gemini. Giữ nguyên các hướng dẫn thiết lập bên dưới.

## Stage3D.1 — giao diện gọn và preflight

Nếu app đang mở từ trước cập nhật, đóng an toàn và mở lại `run_source.bat` để
nạp GUI mới; EXE cũ chưa chứa hotfix. Công việc đã lưu có thể khôi phục qua Thêm,
không tự tiếp tục khi mở ứng dụng.

- Thanh trên dùng chung ba tab: OCR → phương thức dịch → model/provider → Cài đặt.
  Provider Online/Offline phụ và ô đồng ý Auto Fallback nằm trong Cài đặt; chỉ
  đổi layout không đổi phương thức hoặc tự bật gửi Online.
- Tab Link truyện: nhập URL và Phân tích link chỉ discovery, không tự tải/dịch.
  Bấm **Thư mục xuất** để xem/đổi đường dẫn. **Tùy chọn nguồn/cache** chứa giữ
  cache, thử lại phân tích, phân tích ảnh và cột nâng cao.
- Bảng chương còn Chọn/Thứ tự/Tên chương/Trạng thái. Hover tên chương hoặc mở
  tùy chọn để đọc truy cập/số URL ảnh/điều kiện tải; không mất dữ liệu hoặc đổi
  thứ tự xử lý. Metadata vẫn hiển thị số URL ảnh, thông tin đầy đủ ở tooltip.
- Các nút chính: Tải và dịch, Tạm dừng, Tiếp tục từ cache, Hủy, Mở kết quả.
  **Thêm** chứa khôi phục công việc đã lưu, retry lỗi và trang cần xem lại/log.
  Ở tab thư mục, menu Thêm cũng có Mô hình cục bộ. Nội dung dài dùng vùng cuộn,
  không cần maximize; ở scaling150% có thể cần cuộn dọc.

Nếu thấy **Cần hoàn tất thiết lập Gemini API / FREE_TIER_UNCONFIRMED**:

1. Bấm **Mở Cài đặt Gemini API** trong thông báo hoặc Cài đặt trên thanh chung.
2. Dùng liên kết Google AI Studio để **tự kiểm tra** project của key đang dùng
   là Free tier và không gắn billing. Ứng dụng không xác minh billing hoặc key.
3. Chỉ khi đã kiểm tra đúng, tự tích **Đã kiểm tra project Free tier, không gắn
   billing** và bấm OK. Ứng dụng không tự tích ô này hoặc mở billing.
4. Chủ động **Tiếp tục từ cache** nếu đang có job pending, hoặc Bắt đầu/Tải và
   dịch nếu chưa bắt đầu. Nếu vừa mở lại ứng dụng, dùng **Thêm → Khôi phục công
   việc đã lưu**, sau khi đã chọn phương thức/cài đặt mong muốn. Receipt output
   thành công được xác minh và giữ nguyên. Không tự sửa journal hoặc xóa cache.

`API_KEY_MISSING` là chưa có GEMINI_API_KEY; thiết lập biến môi trường Windows
rồi mở lại ứng dụng. `READY_UNVERIFIED` chỉ xác nhận đủ cấu hình cục bộ, không
chứng minh key hợp lệ hoặc model2.5Flash được cấp. Chưa có request API thật trong
nghiệm thu Stage3D.1. Không tự chuyển model/provider nếu bước API sau này bị từ chối.

Thông báo phân biệt thiếu thiết lập, người dùng Pause và lỗi provider. Chỉ khi
có bằng chứng tại luồng chặn mới ghi request chưa gửi, với phạm vi thao tác/batch
hiện tại; không suy rộng cho lịch sử. **Chi tiết / Nhật ký** mở lịch sử đã lọc
(mã/provider/giờ/trang nếu có), không hiển thị key, raw response hoặc OCR.
× chỉ ẩn thông báo; không resume. Sửa thiết lập sẽ ẩn cảnh báo cấu hình cũ nhưng
giữ lịch sử/pending, không tự chạy. AGY Unexpected tool use là guard từ chối,
không phải bằng chứng quota hay tool invocation thực sự.

## Stage3D — chọn Gemini API chính thức

1. Dùng bản source qua `run_source.bat`. Bốn EXE cũ chưa chứa Stage3D.
2. Cung cấp `GEMINI_API_KEY` qua biến môi trường Windows rồi mở lại ứng dụng.
   Không nhập key vào URL, glossary, config, log hoặc Git. Ứng dụng chỉ hiển thị
   đã có/chưa có key; trạng thái này chưa xác minh key trên mạng.
3. Tại AI Studio, kiểm tra project của key là **Free tier, không gắn billing**.
   Mở Cài đặt, tích xác nhận Free tier chỉ khi điều đó đúng. Kiểm tra lại khi đổi
   key/project hoặc billing. Ứng dụng không thể xác minh billing bằng key; xác
   nhận này không biến key Paid thành Free. Không dùng key Paid cho chế độ này.
4. Chọn **AI Gemini API** ở phương thức dịch chung cho cả ba tab. Offline vẫn là
   mặc định của cấu hình mới; ứng dụng không tự đổi lựa chọn đã lưu của bạn.
5. Bấm Bắt đầu/Tải và dịch hoặc Tiếp tục theo nguồn hiện tại. Dán URL/phân tích
   link/mở ứng dụng không tự gửi OCR tới Gemini. Chỉ text OCR/context được gửi,
   không ảnh, DB hoặc đường dẫn. Dữ liệu Free tier có thể được Google dùng cải
   thiện sản phẩm; không dùng với nội dung nhạy cảm.

Model Stage3D là `gemini-2.5-flash`; Google hạn chế quyền truy cập 2.5 theo lịch sử
dự án. Nếu model không khả dụng, ứng dụng báo MODEL_UNAVAILABLE; không tự đổi
sang model khác. Chưa chạy QA API thật; không bảo đảm key/project hiện tại dùng
được model chỉ từ kết quả mock.

Batch dùng cấu hình chung **AGY / API** trong Cài đặt: mặc định3.000ký tự,
60vùng, tối đa16trang có chữ; context tối đa8vùng/1.600ký tự JSON đã qua guard,
có thể tắt. Numeric/glossary guard giữ nguyên. Qua guard không chứng minh đúng
nghĩa; cách viết ngày đổi thứ tự số vẫn có thể bị từ chối như trước.

UI hiển thị model, key presence và token input/output/total khi response cung cấp;
`?` là không có dữ liệu. Giới hạn64request/phiên là budget cục bộ, không phải
quota Google. Quota/RPM/TPM/RPD thực tế xem AI Studio; không bịa số lượt còn lại.

Quota/rate/auth/timeout/JSON lỗi làm tạm dừng, có thông báo × và diagnostic của
job. Đóng × chỉ ẩn thông báo. Không tự retry hoặc đổi provider. Bạn có thể chọn
Offline/MyMemory/AGY rồi Tiếp tục phần pending; receipt output thành công được
giữ, OCR cache tái sử dụng nếu recipe/source không đổi, cache dịch tách provider.
Không sửa journal bằng tay. Không chạy lại trang111/chương production để thử API.

## Stage3C.1 — đọc diagnostic AGY an toàn

Khi AGY bị từ chối, mở thư mục diagnostic của job, xem record mới trong
`errors.jsonl`, nhóm `agy_protocol`: classification, parser_error_code/reason,
guard_decision, event_type, path/type nghi vấn, batch/page/region/character count.
Classification chỉ là quan sát; guard_decision là verdict giao thức cũ, chưa
thay numeric/glossary validation. VALID_TRANSLATION_RESPONSE không bảo đảm đúng nghĩa.

Tool metadata chưa rõ sẽ UNKNOWN; khai báo kiểu có cấu trúc có thể được gắn
TOOL_METADATA_ONLY nhưng **vẫn bị từ chối như trước**. Không tự nới guard/đổi
provider/retry. Không coi ACTUAL_TOOL_REQUEST là bằng chứng công cụ đã thực thi.
Thông báo UI chung vẫn như Stage3C; dùng diagnostic để biết lý do cụ thể.

Các record mới có agy_protocol không lưu OCR/target/path/raw exception hoặc
raw stdout/stderr, kể cả bật diagnostic văn bản. Argos/MyMemory giữ chính sách
diagnostic cũ. Log lịch sử không bị xóa/scrub: khi chia sẻ chỉ trích nhóm metadata
đã lọc của record mới và mã lỗi, không gửi toàn bộ log hoặc credential.

## Khi Kuaikan dừng ở IMAGE_LIST_READY (08/11/2026)

`Phân tích ảnh chương` chỉ tìm URL ảnh, không tải bitmap. Sau khi phân tích,
giữ chương được chọn và bấm **Tải và dịch** nếu nút đã bật. Khi đó worker mới
tải/cache ảnh và đưa vào pipeline dịch. Tiến độ 0% trước bước này là bình thường.

Xem cột **Điều kiện tải**: `ALLOWED_BY_USER_POLICY` cho phép theo cấu hình chủ
ứng dụng dù **quyền nội dung** còn UNKNOWN; đây không phải giấy phép chính thức.
`DOWNLOAD_UNKNOWN` là quyết định khác: chưa đủ điều kiện tải, nút bị tắt và lý
do nằm dưới bảng/tooltip. Không bỏ qua UNKNOWN về truy cập, VIP hoặc hạn chế.
Nếu nút đang bật nhưng bấm không chạy, cần lưu trạng thái sau khi bấm và lỗi
cụ thể; không chỉ chụp dòng IMAGE_LIST_READY trước khi bấm.

## AI Gemini AGY — trạng thái Stage3B

Lượt đầu lỗi giao thức INVALID_RESPONSE; lượt bổ sung được duyệt đã OCR→AGY→ảnh
PASS trên fixture tổng hợp3vùng, chưa nghiệmthu wholechapter/truyện phức tạp.
Không cần restart hoặc đăng nhập lại vì thiếu PATH trong phiên Codex cũ: app tìm
AGY.exe trong PATH/LocalAppData; Cài đặt cho phép nhập executable đã cài nếu cần.

Khu vực dịch chung3tab có **AI Gemini AGY**. Settings hiện có thêm model slug
Gemini,timeout vàmaxrequests/job. AGY dùng phiên account sẵn có, không nhập API
key. Khi bấm Bắt đầu mới gửi OCR theo batchID; không gửi ảnh/DB trong prompt,
không cấp file/shell/web/MCP, không dùng thêmcredits hoặc tự đổi phương thức.
CLI tự quản lý auth/conversation/metadata riêng theo thiết lập Google của bạn.

Quota/rate/auth/protocol/timeout sẽ dừng dispatch. × chỉ ẩn thông báo; sau khi
khắc phục có thể chọn phương thức rồi Tiếp tục pending trong cùng phiên; output
đã hoàn tất giữ receipt. Không dùng việc đổi provider rồi chạy cảfolder để giả
resume sau restart; giới hạn Stage3A/3C vẫn còn. Không retry111 từ thao tác QA.

Nếu AGY có hooks/MCP tự động không rỗng, ứng dụng từ chối trước khi gửi prompt,
không tự sửa cấu hình AGY. Không bật skip-permissions để vượt qua. Xem
STAGE3B_AGY_TRANSLATION_REPORT.md; hai lượtQA đã được dùng, chạy QA thật thêm
phải được duyệt riêng. Không tự retry111 hoặc đổi numeric guard khi AGY trả ngày
theo cách viết khác; xem diagnostic và chọn phương thức tiếp tục nếu cần.

## Online Free — Stage3A (bản source)

1. Chạy run_source.bat; chọn nguồn ảnh, output và OCR như trước.
2. Chọn **Online Free**, provider **MyMemory** ở khu vực OCR/dịch chung3tab.
   Đây là thao tác cho phép gửi text OCR của job tới MyMemory; ảnh ở trên máy.
   Dịch vụ có thể lưu/chia sẻ text với đối tácMT. Không dùng cho text bí mật.
3. Bấm Bắt đầu/Tải và dịch sau khi chọn đúng ảnh/chương. Dán URL hay phân tích
   chương không tự gửi OCR. Chỉ chương được chọn mới xử lý; không tự tải model.
4. MyMemory ẩn danh miễn phí5.000ký tự/ngày; app chia nhỏ theo giới hạn byte,
   giãn request. Không hiện số lượt còn lại vì không có số liệu đáng tin.
5. Khi QUOTA_EXCEEDED/RATE_LIMITED/AUTH_REQUIRED: công việc dừng an toàn, giữ
   ảnh/output/checkpoint. × chỉ đóng notice, không resume hoặc đổi phương thức.
6. Trong cùng phiên, có thể chọn Offline hoặc giữ Online Free rồi bấm Tiếp tục.
   Chỉ phần chưa hoàn tất chạy; đổi phương thức tạo recipe mới, kết quả trước đó
   giữ receipt riêng. URL nhiều chương: resume chương đang dở từ cache; những
   chương chưa bắt đầu phải chọn/bắt đầu sau, không tự tải tiếp.

Sau khi đóng app, pending UI cho thao tác đổi provider chưa được khôi phục tự
động. Cùng recipe có thể khôi phục/bỏ qua thành công theo checkpoint/hash;
**không đổi provider rồi chạy cảfolder nếu chỉ muốn retry pending**. Giữ cache và
manifest để bổ sung cross-restart resume ở Stage3C. Không sửa checkpoint bằng tay.

Numeric guard giữ nguyên: bản dịch ngày hợp nghĩa có thể đổi thứ tự token số
và bị reject. Đọc diagnostic/Trang cần xem lại; fallback không được gọi là dịch
thành công. Stage3A không tự retry trang111 hoặc dùng handler ngày QA.

LibreTranslate custom cũ chỉ dùng khi bạn có endpoint tựhost/miễn phí được phép;
không coi libretranslate.com hoặc mọi mirror là miễn phí. Không có Gemini ở Stage3A.
Chi tiết: STAGE3A_ONLINE_FREE_TRANSLATION_REPORT.md. Chưa build EXE mới.

## Stage3 — kết quả nghiên cứu, chưa đổi cách dịch

Benchmark150 mẫu có0 bản dịch tham chiếu được người rà soát độc lập. Những
thử nghiệm ở `qa/` **chưa có trong GUI**, không đổi Argos/default/numeric guard
và không tự cài/tải model. App/source/EXE chạy như Stage2; chương274872 vẫn có
120 output,119 hoàn tất pipeline và1 ảnh gốc dự phòng111 cần xem lại.

Không đổi length_penalty sang1.0 theo hai ví dụ Name đẹp hơn: thử nghiệm có
thêm số ngoài nguồn ở holdout. Handler ngày QA tạo được `Từ ngày20/5 đến ngày30/5`
nhưng chưa đủ điều kiện dùng production. Không sửa cache/checkpoint hoặc bấm
Retry lặp lại để ép ảnh111 thành công; model/input hiện tại vẫn có thể sai như cũ.

Muốn hỗ trợ đánh giá ngữ nghĩa, mở
`logs/stage3-translation-quality-20261107T204426Z/human-reference-template.csv`:
xem source và ảnh, điền bản dịch/biến thể chấp nhận,người/ngày xác minh trước
khi xem `outputs-for-review.csv`. Bản dịch tham chiếu đang trống; output Argos
hoặc ứng viên không tự trở thành đáp án chuẩn. Chưa có form review online hay
quy trình tải dữ liệu lên dịch vụ bên ngoài.

OPUS-MT zh-vi,M2M100,NLLB chỉ được tra cứu nguồn/metadata; chưa tải trọng số,
chưa đo chất lượng trên máy. Việc thử model mới cần chấp thuận riêng. Báo cáo:
[STAGE3_TRANSLATION_QUALITY_REPORT.md](STAGE3_TRANSLATION_QUALITY_REPORT.md).

## Cập nhật Stage 2 — 08/11/2026

Chương274872 đã phục hồi đúng hai trang từ cache: **120/120 file**,119 ảnh hoàn
tất pipeline bình thường,1 ảnh gốc dự phòng,1 trang cần xem lại. Trang74 giữ
nguyên byte ảnh sau khi bỏ vùng OCR giả theo bằng chứng; **không có văn bản
cần dịch**, không gọi provider, không phải fallback. Trang111 vẫn sai bản dịch
ngày tháng, dùng `original/0111.jpg`, nằm trong needs_retry. Lần Retry tiếp theo
chỉ chọn trang111; không tự tải CDN. Bản dịch đúng cho trang111 chưa có.

Override OCR nằm ở `overrides/ocr_regions.json` cạnh source/data root, không ở
cache OCR. Mỗi mục có id/version, hash ảnh, text/polygon chính xác, action,
reason/evidence và `enabled`. Profile hiện chỉ có vùng hoa văn đã xác minh.
Tắt/thu hồi bằng `enabled=false`; đổi phiên bản khi sửa bằng chứng. Không dùng
profile để bỏ chữ khó dịch. Không có editor vùng OCR trong GUI ở Stage2.

Hash/polygon không khớp gây diagnostic/fallback, không chọn vùng gần giống.
Locator tương đối chỉ định đúng ảnh để phát hiện hash bị đổi; không hardcode
tên0074 trong engine. Cùng hash vẫn phải khớp text/polygon. Cache OCR gốc không
sửa. Override được ghi receipt trong metadata, thay fingerprint riêng ảnh đó,
không đổi job ID hoặc fingerprint118 ảnh cũ. Thu hồi có hiệu lực ở lần xử lý
ảnh đó tiếp theo; không tự xóa output đã xuất hoặc tự đưa ảnh thành công vào
needs_retry. Nếu cần đánh giá lại ảnh đã xong sau khi sửa profile, dùng công cụ
phục hồi có phạm vi rõ hoặc job/thư mục mới; không ghi đè output cũ.

Khi không còn vùng cần dịch và giữ định dạng gốc, pipeline sao chép nguyên byte
nguồn vào **output hoàn tất bình thường**. Metadata `no_text_to_translate=true`
và cảnh báo nói rõ; khác với sao chép do lỗi `FALLBACK_ORIGINAL`. Tổng số hoàn
tất pipeline có thể gồm ảnh không có chữ, không phải số ảnh đã dịch văn bản.

Numeric guard hiện `literal-numbers-v2-signed`: giữ chặt dấu số, không tự chuẩn
hóa ngày hoặc thập phân. Dữ liệu signed legacy không được tin mù quáng; cache
có dấu dùng namespace v4. Không xóa cache v3 unsigned và không xử lý lại118
output cũ. Lỗi trang111 mới đã xác nhận pivot dịch sai, không phải lý do để tắt
validator. Xem [báo cáo Stage2](STAGE2_NUMERIC_OCR_RECOVERY_REPORT.md).

Stage2 chỉ có ở source hiện tại, dùng **run_source.bat**. EXE cũ và hướng dẫn
Stage1 dưới đây giữ nguyên; chưa có bản build mới, portable management hoặc
benchmark chất lượng Stage3.

## Chạy ứng dụng

Chạy **run_source.bat** để dùng source mới nhất trong môi trường đã cài.
Các launcher và bốn EXE cũ được giữ nguyên. EXE cũ chưa có diagnostic/fallback
Stage 1; chưa build EXE mới cho thay đổi này. Hướng dẫn setup máy phát triển
trong README và các báo cáo cài đặt vẫn áp dụng.

## Chọn nguồn

- **Ảnh đơn**: chọn ảnh, đọc danh sách, chọn thư mục kết quả rồi dịch ảnh đã có.
- **Thư mục ảnh**: chọn nguồn và đích riêng biệt, cấu hình quét thư mục con,
  OCR và Offline, rồi Bắt đầu dịch.
- **Link truyện online**: nhập URL topic/chương Kuaikan, Phân tích link, chọn
  chương cần xử lý rồi Tải và dịch. Dán/phân tích URL không tự tải ảnh.
  Chính sách hiện tại `default_allow_public` là lựa chọn của chủ ứng dụng,
  không phải website cấp phép. Nội dung khóa/hạn chế và chặn kỹ thuật vẫn dừng.

Pipeline truyện và ảnh đơn sử dụng Offline. Chế độ Online của tab thư mục
chỉ dùng khi bạn chủ động chọn; không tự bật Online để xử lý lỗi số.

## Model

Dùng **Quản lý mô hình AI** để xem model đã cài, kiểm tra hoặc chủ động tải
model được ứng dụng liệt kê. Không có model M2M100 cục bộ thì không coi engine
đó đã sẵn sàng. Không tải lại model đang hợp lệ. Job Offline không tự tải model.
Thiếu model hoặc runtime có thông báo rõ; Stage 4 về first-run/portable dependency
management **chưa thực hiện trong lượt Stage 1**.

## Tiến độ và trạng thái ảnh

Progress lấy từ tác vụ thật. Tạm dừng có hiệu lực tại checkpoint; hủy chờ tác vụ
đang chạy về checkpoint và giữ file đã hoàn thành.

| Trạng thái | Ý nghĩa |
|---|---|
| `TRANSLATED_SUCCESS` | Hoàn tất pipeline với các vùng chữ cần dịch đã qua kiểm tra; ảnh không có chữ cần dịch cũng có thể hoàn tất |
| `PARTIAL_TRANSLATION` | Dự phòng cho bản dịch một phần; Stage 1 chưa tự xuất dạng này |
| `FALLBACK_ORIGINAL` | Bản sao nguyên byte của ảnh nguồn hợp lệ, chưa phải bản dịch hoàn chỉnh |
| `FAILED_NO_OUTPUT` | Chưa có output hợp lệ, ví dụ ảnh hỏng/mất hoặc không ghi được file |

Stage 1 chọn cách bảo toàn toàn ảnh: nếu một vùng lỗi, không inpaint/chèn bản
dịch chưa hợp lệ vào ảnh xuất. Nếu render sau đó lỗi, bản dự phòng vẫn lấy từ
**nguồn**, không lấy ảnh đã xóa chữ dở. Không có thao tác sửa số tự động.

Chương đủ file nhưng còn ảnh dự phòng có trạng thái **COMPLETED_WITH_WARNINGS**,
không phải dịch thành công toàn chương. Tổng kết tách dịch hoàn chỉnh, dịch một
phần (hiện bằng 0), ảnh gốc, không output, bỏ qua checkpoint và cần xem lại.

Trong tab thư mục, file dự phòng có `.fallback-original` trong tên và giữ định
dạng nguồn. Trong output truyện, chúng ở `run_<job>/original/0001.jpg`…; ảnh dịch
ở `run_<job>/0001.jpg`… Thứ tự trang vẫn theo số trong manifest. Chưa có chế độ
gộp hai thư mục thành một trình đọc truyện. Sau retry, bản dự phòng cũ vẫn giữ
lại; manifest trỏ tới bản mới nếu dịch thành công. Không đếm số file trong cả
cây thư mục để suy ra số trang hiện hành: dùng manifest/tổng kết ứng dụng.

Ảnh thành công có checkpoint/hash hợp lệ luôn được giữ nguyên, kể cả config
cũ có `skip_success=false`. Ô bỏ qua thành công được khóa bật để biểu thị việc
bảo toàn này. Muốn tạo phiên bản khác, đổi thư mục xuất hoặc cấu hình ảnh/model;
không sửa/xóa file kết quả cũ để ép retry.

## Xem lỗi và diagnostic

Bấm **Trang cần xem lại / log** sau khi job xong. Danh sách có số trang, file,
giai đoạn, provider nếu biết, mã lỗi, loại output và đường dẫn diagnostic.
Chọn một dòng rồi **Mở thư mục log của dòng chọn**. Nút Mở kết quả mở thư mục
đích. Tab thư mục vẫn có xem trước bằng nhấp đúp hàng.

Diagnostic nằm ở `logs/diagnostics/<job_id>/errors.jsonl`. Lỗi download trước
khi có pipeline job dùng transfer job ID riêng; trường chưa xác định để trống,
không tự tạo tên ảnh hay raw target. Mã lỗi tham khảo
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).

Mỗi job giới hạn 1.000 record/4 MB, văn bản tối đa 2.048 ký tự/trường, tối đa
100 numeric tokens. `truncated_fields` cho biết trường bị cắt. Nếu không ghi
được log, ảnh dự phòng vẫn được thử xuất, giao diện báo vấn đề diagnostic.
Record được flush/fsync; nếu mất điện để lại dòng cuối dở, file cũ giữ nguyên,
record mới sang file `errors-<id>.jsonl`. Không sửa dữ liệu lỗi cũ.

Trong **Cài đặt**, bỏ chọn “Lưu văn bản OCR/bản dịch bị lỗi…” để không ghi mới
source/target/numeric tokens vào diagnostic. Việc này không xóa log đã có,
không đổi job identity và không gửi log ra Internet. Hãy kiểm tra nội dung riêng
tư trước khi chia sẻ diagnostic. Lượt lỗi cũ không có raw target thì không thể
khôi phục lịch sử bằng cách giả định bản dịch của lượt mới là bản dịch cũ.

## Retry ảnh cần xem lại

- Tab thư mục: **Thử lại ảnh lỗi / chưa xong** chỉ gửi danh sách ảnh cần retry.
- Tab ảnh đơn/URL: **Thử lại…** dùng manifest và ảnh cache đã xác minh, chỉ gửi
  trang thiếu output/lỗi/fallback vào ProcessingManager. Không gọi HTTP hoặc
  tải CDN trong nhánh retry này. Trang thành công giữ nguyên.
- Cache thiếu/hỏng hoặc output bị sửa thì retry dừng rõ ràng, không tải lại,
  không ghi đè. Chương chưa từng tải/cache chưa thể dùng retry này; bắt đầu
  job nguồn tương ứng để lấy nguồn hợp lệ trước.
- Chỉ retry khi đã có cách khắc phục. Dịch lại cùng input/model có thể lặp lại
  lỗi cũ. Chưa có trình sửa OCR/bản dịch theo vùng trong Stage 1.

Hai trang thực tế `0074.jpg` và `0111.jpg` của chương 274872 **chưa chạy phục
hồi** trong Stage 1. Cơ chế override OCR và phân tích raw target thuộc Stage 2.

## EXE trên máy khác, sao lưu và giới hạn

Onedir phải được sao chép **cả thư mục**, không chỉ file EXE. Bản cũ có thể cần
model/tài nguyên và thư mục dữ liệu đi kèm đúng bố cục hiện tại; chưa nghiệm thu
Windows sạch hoặc đường dẫn dữ liệu `%LOCALAPPDATA%` mới. Không có
`PORTABLE_EXE_PASS`, không tự pip install hoặc tải DLL vào EXE.

Khi sao lưu, đóng job an toàn rồi giữ source, model, config, toàn bộ cache/SQLite
(cả WAL/SHM nếu có), manifest, output và log. Không chỉ chép hai ảnh lỗi: để
resume cần receipt và database đúng job. Không xóa ảnh nguồn hoặc cache của
chương còn fallback. Bản dịch Argos pivot vẫn có hạn chế ngữ nghĩa; kiểm tra
preview, đặc biệt tên riêng/ngày tháng. Công việc chất lượng dịch và portable
EXE là các stage sau, chưa thay model/provider mặc định ở Stage 1.

## Stage 3C — batch nhiều trang, đóng/mở và tiếp tục

1. Chọn phương thức ở cửa sổ chính. Offline/Argos vẫn mặc định, MyMemory dùng
   API từng request như trước. Chỉ AGY gom nhiều trang trong cùng chương/lượt.
2. Cài đặt → AGY ký tự mục tiêu/batch (mặc định3.000), vùng tối đa (60),
   timeout, số lượt tối đa/job và checkbox context. App có thể OCR trước vài
   trang, sau đó mới xuất; trạng thái batch ghi số trang/vùng/ký tự thực tế.
3. Batch cuối được gửi khi hết chương. Trang không có chữ giữ nguyên nội dung;
   hoàn tất pipeline không đồng nghĩa mọi trang đều có chữ được dịch.
4. Quota/rate/auth/protocol/timeout dừng gửi và giữ OCR/cache/output. × chỉ ẩn
   thông báo. Chọn phương thức khác nếu muốn rồi chủ động Tiếp tục; không tự đổi.
5. Sau khi mở lại: tab thư mục có nút Khôi phục công việc còn dở. Nút này chỉ
   nạp cấu hình/pending, chưa chạy provider. Chọn phương thức rồi Tiếp tục.
   Tab ảnh/URL có Tiếp tục công việc đã lưu (ưu tiên cache); chọn phương thức
   chung trước khi bấm. Chương đã cache được xác minh hash, không truy cập CDN.
   Chương còn chưa tải giữ nguyên lựa chọn cũ và cần kiểm tra access/policy mới
   trước khi tải. Không tự tải khi vừa mở app hoặc chỉ phân tích URL.
6. Output thành công được xác minh bitmap/hash/receipt, giữ recipe/provider cũ.
   Chỉ phần pending dùng phương thức vừa chọn. Không đổi OCR/font/glossary/
   cấu hình render trong cùng resume; nếu cần, tạo lượt mới ở output khác.
7. Lỗi số vẫn có thể xuất ảnh gốc fallback và cần retry. Không gọi đó là dịch
   thành công; không phục hồi trang111 production trong Stage3C.

Ngữ cảnh chỉ gồm tối đa8vùng dịch trước đã qua validation, không phải ground
truth hoặc quan hệ nhân vật đã xác nhận. Giới hạn1.600ký tự JSON, không gửi lại
toàn chương. Có thể tắt trong Cài đặt; thay context/threshold tạo identity cache
AGY khác. Một trang chưa đủ mọi vùng hợp lệ sẽ không được inpaint/render dở.

Giữ cả database và thư mục journal bên cạnh khi sao lưu. Không xóa journal hoặc
cache để chữa lỗi resume. Job lịch sử chưa có journal không tự được chuyển đổi.
Bốn EXE cũ không chứa Stage3C; dùng source, chưa có build mới.
