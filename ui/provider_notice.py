"""Dismissible provider message; closing it never resumes work."""
from datetime import datetime, timezone
import re
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QWidget, QToolButton, QPlainTextEdit


def gemini_usage_text(event):
    usage = event.get('usage', {})
    return ('Gemini API • ' + event['model'] + ' • token input/output/total: ' +
            '/'.join(str(usage.get(k, '?')) for k in ('promptTokenCount', 'candidatesTokenCount', 'totalTokenCount')) +
            f" • request cục bộ {event['requests']}/{event['request_limit']}. Quota Google còn lại: chưa xác định; xem AI Studio.")


class ProviderNotice(QWidget):
    settingsRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        heading = QHBoxLayout()
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setTextFormat(Qt.PlainText)
        heading.addWidget(self.title, 1)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.PlainText)
        row = QHBoxLayout()
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.PlainText)
        row.addWidget(self.summary, 1)
        self.settings = QPushButton('Mở Cài đặt Gemini API')
        self.settings.clicked.connect(self.settingsRequested)
        row.addWidget(self.settings)
        self.dismiss = QPushButton('×')
        self.dismiss.setAccessibleName('Đóng thông báo; giữ công việc tạm dừng')
        self.dismiss.clicked.connect(self.hide)
        self.log_toggle = QToolButton()
        self.log_toggle.setText('Chi tiết')
        self.log_toggle.setAccessibleName('Mở Chi tiết / Nhật ký')
        self.log_toggle.setCheckable(True)
        heading.addWidget(self.log_toggle)
        heading.addWidget(self.dismiss)
        layout.addLayout(heading)
        layout.addLayout(row)
        self.details = QWidget()
        expanded = QVBoxLayout(self.details)
        expanded.setContentsMargins(0, 0, 0, 0)
        expanded.addWidget(self.message)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(50)
        self.log.setMaximumHeight(110)
        expanded.addWidget(self.log)
        self.details.hide()
        self.log_toggle.toggled.connect(self.details.setVisible)
        layout.addWidget(self.details)
        self.active = False
        self.hide()

    def hide(self):
        self.active = False
        super().hide()

    def show_error(self, event):
        if event.get('provider')=='Qoder CLI':
            known={'CLI_NOT_FOUND','AUTH_REQUIRED','MODEL_UNAVAILABLE','QUOTA_OR_CREDITS_EXCEEDED',
                'TIMEOUT','CANCELLED','INVALID_RESPONSE','PROVIDER_ERROR','BLOCKED_BY_ISOLATION','QODER_RESULT_UNKNOWN'}
            code=event.get('code') if event.get('code') in known else 'PROVIDER_ERROR'
            self.last_code=code;self.active=True
            message={'CLI_NOT_FOUND':'Chưa tìm thấy Qoder CLI .exe; kiểm tra Cài đặt AI.',
                'AUTH_REQUIRED':'Qoder CLI chưa đăng nhập; mở CLI và /login bằng trình duyệt.',
                'QUOTA_OR_CREDITS_EXCEEDED':'Qoder hết Credits hoặc giới hạn quota; giữ checkpoint, không tự retry.',
                'BLOCKED_BY_ISOLATION':'Không xác minh được cô lập Qoder; chưa cho phép gửi OCR.',
                'QODER_RESULT_UNKNOWN':'Batch chưa rõ kết quả, có thể đã tính Credits. Tiếp tục cần xác nhận gửi lại.',
                'TIMEOUT':'Qoder hết thời gian chờ; kết quả chưa rõ, không tự gửi lại.'}.get(code,
                'Qoder dừng; giữ kết quả đã hoàn thành và checkpoint, không đổi provider.')
            self.title.setText('Qoder CLI · '+code);self.summary.setText(message);self.message.setText(message)
            self.settings.setText('Mở Cài đặt AI');self.settings.setVisible(code in ('CLI_NOT_FOUND','AUTH_REQUIRED','MODEL_UNAVAILABLE'))
            self.log.appendPlainText('Qoder CLI · '+code+' · Không tự retry/fallback.');self.show();return
        if event.get('provider')=='GroqCloud' or event.get('groq_request'):
            from providers.groq_api import MODEL_IDS
            known={'API_KEY_MISSING','AUTH_REQUIRED','ACCESS_DENIED','MODEL_UNAVAILABLE','INVALID_REQUEST',
                   'RATE_LIMITED','PROVIDER_UNAVAILABLE','TIMEOUT','NETWORK_ERROR','INVALID_RESPONSE','REQUEST_BUDGET'}
            code=event.get('code') if event.get('code') in known else 'PROVIDER_UNAVAILABLE'
            self.last_code=code;self.active=True
            text={'API_KEY_MISSING':'Chưa có GROQ_API_KEY trong môi trường Windows.',
                'AUTH_REQUIRED':'GroqCloud từ chối API key. Kiểm tra GROQ_API_KEY.',
                'MODEL_UNAVAILABLE':'Model không tồn tại hoặc chưa được cấp quyền; không tự đổi model.',
                'RATE_LIMITED':'GroqCloud giới hạn tốc độ/quota. Chỉ chủ động Tiếp tục sau Retry-After nếu có.'}.get(code,
                'Giữ checkpoint và kết quả đã xong; kiểm tra cấu hình/kết nối rồi chủ động Tiếp tục.')
            delay=event.get('retry_after')
            if type(delay) in (int,float) and 0<=delay<=86400:text+=' Retry-After: '+str(delay)+' giây.'
            self.title.setText('GroqCloud · '+code);self.summary.setText(text);self.message.setText(text)
            self.settings.setText('Mở Cài đặt AI');self.settings.setVisible(code in ('API_KEY_MISSING','AUTH_REQUIRED'))
            model=event.get('model') or (event.get('groq_request') or {}).get('model')
            self.log.appendPlainText('GroqCloud · '+code+(' · '+model if isinstance(model,str) and model in MODEL_IDS else ''))
            self.show();return
        # Never echo arbitrary detail, paths, model output or unknown error strings.
        self.active = True
        known = {'API_KEY_MISSING', 'FREE_TIER_UNCONFIRMED', 'READY_UNVERIFIED', 'AUTH_REQUIRED',
                 'ACCESS_DENIED', 'MODEL_UNAVAILABLE', 'RATE_LIMITED', 'QUOTA_EXCEEDED', 'NETWORK_ERROR',
                 'TIMEOUT', 'INVALID_RESPONSE', 'REQUEST_BUDGET', 'PROVIDER_UNAVAILABLE', 'INVALID_REQUEST',
                 'RESPONSE_BLOCKED', 'UNEXPECTED_TOOL_USE', 'CANCELLED', 'PAUSED_BY_USER', 'SAVED_ERROR', 'SOURCE_ACCESS_DENIED',
                 'AGY_AUTOMATIC_EXTENSIONS','AGY_NOT_FOUND','AGY_MODEL','AGY_CAPABILITY','AGY_INITIALIZATION_ERROR','AGY_START_FAILED'}
        code = event.get('code') if event.get('code') in known else 'UNKNOWN_ERROR'
        local = event.get('phase') == 'local_preflight' and event.get('request_sent') is False
        config = code in ('FREE_TIER_UNCONFIRMED', 'API_KEY_MISSING')
        if code == 'FREE_TIER_UNCONFIRMED':
            title = 'Cần hoàn tất thiết lập Gemini API'
            cause = 'Chưa ghi nhận xác nhận cấu hình Free tier. Có key chưa chứng minh key hợp lệ, model khả dụng hoặc dự án miễn phí.'
        elif code == 'API_KEY_MISSING':
            title = 'Chưa có API key Gemini'
            cause = 'Chưa tìm thấy GEMINI_API_KEY trong môi trường của ứng dụng.'
        elif code == 'INVALID_RESPONSE' and 'Unexpected tool use' in str(event.get('detail', '')):
            title = 'AGY bị chặn bởi bộ kiểm tra an toàn (Guard AGY)'
            cause = 'Parser AGY phát hiện dấu hiệu tool use. Đây không phải lỗi quota; chưa đủ bằng chứng phân biệt invocation thật với metadata.'
        elif code == 'PAUSED_BY_USER':
            title = 'Bạn đã yêu cầu tạm dừng'
            cause = 'Worker sẽ dừng tại checkpoint an toàn; không tự chuyển phương thức.'
        else:
            title = 'Công việc đang tạm dừng'
            cause = {
                'AUTH_REQUIRED': 'Provider từ chối xác thực; kiểm tra key hoặc phiên đăng nhập.',
                'ACCESS_DENIED': 'Provider từ chối quyền truy cập.',
                'MODEL_UNAVAILABLE': 'Model không khả dụng; ứng dụng không tự đổi model.',
                'RATE_LIMITED': 'Provider báo giới hạn tốc độ; chưa chứng minh hết quota ngày.',
                'QUOTA_EXCEEDED': 'Provider báo đã đạt hạn mức sử dụng.',
                'NETWORK_ERROR': 'Không kết nối được provider.', 'TIMEOUT': 'Yêu cầu đã hết thời gian chờ.',
                'REQUEST_BUDGET': 'Đạt budget request cục bộ; không phải bằng chứng hết quota Google.',
                'INVALID_RESPONSE': 'Phản hồi không qua kiểm tra giao thức/JSON/ID.',
                'RESPONSE_BLOCKED': 'Nhà cung cấp báo phản hồi bị bộ lọc nội dung chặn.',
            }.get(code, 'Provider hoặc cấu hình chưa cho phép tiếp tục an toàn.')
        from providers.gemini_diagnostics import clean
        api = clean(event.get('gemini_api_request'))
        saved = event.get('origin') == 'journal' or code == 'SAVED_ERROR'
        if code == 'ACCESS_DENIED':
            title = 'Gemini API chưa thể tiếp tục'
            cause = 'ACCESS_DENIED — Chưa xác định được lỗi phát sinh trước hay sau khi gửi yêu cầu.'
            if api['request_state'] == 'RESPONSE_RECEIVED' and api['http_status'] == 403 and not saved:
                title = 'Gemini API từ chối quyền truy cập (HTTP 403)'
                cause = 'Client Gemini API đã nhận HTTP 403 từ endpoint Google cấu hình cố định; chưa xác định nguyên nhân quyền cụ thể.'
        if saved:
            title = 'Công việc có lỗi đã lưu'
            cause = 'Đây là trạng thái lỗi từ lần chạy trước. Chưa có bằng chứng yêu cầu Gemini API mới được gửi trong phiên hiện tại.'
        if code == 'SOURCE_ACCESS_DENIED':
            title = 'Nguồn truyện từ chối truy cập'
            cause = 'Website nguồn hạn chế truy cập chương. Đây là lỗi source adapter, không phải Gemini API.'
        facts = ('Chưa khởi chạy lượt xử lý mới, chưa gửi OCR trong thao tác này.' if local else
                 'Kết quả đã hoàn tất được giữ. Chưa xác minh trạng thái gửi request từ thông báo này.')
        if event.get('phase') == 'provider_preflight' and event.get('request_sent') is False:
            facts = 'Request của batch hiện tại bị chặn trước HTTP. Những lần gọi trước chưa được xác minh tại đây.'
        if not saved and api['request_state'] == 'NOT_ATTEMPTED':
            facts = 'Attempt hiện tại chưa gọi HTTP; không phải bằng chứng Google từ chối. Output/cache hoàn tất được giữ.'
        elif not saved and api['request_state'] == 'ATTEMPT_STARTED':
            facts = 'Client đã bắt đầu HTTP attempt; chưa có bằng chứng đã tới Google hoặc nhận response. Output/cache hoàn tất được giữ.'
        elif not saved and api['request_state'] == 'RESPONSE_RECEIVED':
            facts = 'Đã nhận HTTP response' + (f" ({api['http_status']})" if api['http_status'] is not None else '') + '. Output/cache hoàn tất được giữ; không tự retry.'
        remedy = ('Mở Cài đặt Gemini API → kiểm tra project ở Google AI Studio → xác nhận Free tier khi đúng → chủ động Tiếp tục hoặc Bắt đầu.'
                  if config else 'Xem mã lỗi và diagnostic cục bộ. Chủ động Tiếp tục khi đã xử lý nguyên nhân; không tự retry hoặc đổi provider.')
        agy_init = code.startswith('AGY_') and event.get('phase')=='agy_preflight'
        if agy_init:
            title = 'AGY bị chặn trước bước dịch'
            cause = ('Cấu hình hooks/MCP chưa được xác minh an toàn.' if code=='AGY_AUTOMATIC_EXTENSIONS'
                     else 'AGY không khởi tạo được; xem mã lỗi và cấu hình provider/model.')
            facts = ('Chưa khởi chạy AGY, chưa gửi yêu cầu dịch từ ứng dụng.' if code=='AGY_AUTOMATIC_EXTENSIONS'
                     else 'Chưa bắt đầu gửi OCR để dịch; CLI probe có thể đã chạy. Xem metadata để biết trạng thái tiến trình.')
            facts += ' Công việc tạm dừng; không tạo ảnh Origin mới cho phần pending.'
            remedy = 'Kiểm tra cấu hình AGY an toàn; không bỏ guard hoặc reset journal. Chủ động tiếp tục hoặc tạo lượt mới sau khi xử lý nguyên nhân.'
        elif code=='AUTH_REQUIRED' and event.get('provider')=='AGY Gemini':
            title = 'AGY cần đăng nhập'
            cause = 'AGY CLI chưa có phiên xác thực hợp lệ hoặc đăng nhập đã hết thời gian chờ.'
            facts = 'Output/cache đã hoàn tất được giữ. Công việc tạm dừng; không tự gửi lại phần pending.'
            remedy = ('Mở PowerShell, chạy agy và hoàn tất đăng nhập bằng tài khoản của bạn. '
                      'Sau đó quay lại ứng dụng và chủ động Tiếp tục. Không cần đổi model hoặc API key.')
        elif code=='TIMEOUT' and event.get('provider')=='AGY Gemini':
            title = 'AGY hết thời gian chờ'
            seconds = event.get('agy_timeout')
            cause = ('CLI đã chạy nhưng hết thời gian chờ' if event.get('agy_process_started') is True else 'Không nhận được kết quả trong thời gian chờ')
            if type(seconds) is int and 10<=seconds<=1800: cause += ' '+str(seconds)+' giây'
            facts = 'Không xác định được backend đã nhận request hay chưa; không tự retry hoặc đổi provider.'
            remedy = 'Thông tin lỗi được lưu nếu ghi diagnostic thành công. Xem attempt bên dưới khi cần điều tra.'
        elif code=='RESPONSE_BLOCKED' and event.get('provider')=='AGY Gemini':
            title = 'AGY: nhà cung cấp chặn phản hồi'
            cause = 'Bộ lọc nội dung của nhà cung cấp đã chặn phản hồi. Đây không phải validator bản dịch của ứng dụng.'
            facts = 'Kết quả đã hoàn tất được giữ; batch hiện tại còn pending.'
            remedy = 'Không tự gửi lại batch bị chặn hoặc chấp nhận phản hồi ERROR làm thành công. Xem diagnostic để đối chiếu.'
        elif code=='NETWORK_ERROR' and event.get('provider')=='AGY Gemini':
            title = 'AGY: kết nối bị gián đoạn'
            cause = 'AGY báo luồng HTTP/2 bị máy chủ đóng (GOAWAY); batch chưa hoàn tất.'
            facts = 'Checkpoint và ảnh hoàn tất được giữ; trạng thái backend/chi phí chưa xác minh.'
            remedy = 'Kiểm tra tình trạng dịch vụ/kết nối trước khi chủ động Tiếp tục; không tự retry hoặc đổi provider.'
        delay = event.get('retry_after')
        reset = (' Provider yêu cầu đợi ít nhất ' + str(delay) + ' giây.'
                 if type(delay) is int and 0 <= delay < 10**7 else ' Chưa xác định thời điểm khôi phục.')
        self.title.setText(title + ' • ' + code)
        self.last_code = code
        self.message.setText(cause + '\n' + facts + '\n' + remedy + ('' if config or agy_init or code=='RESPONSE_BLOCKED' else reset))
        short = ('Mở Cài đặt và kiểm tra project ở AI Studio; chỉ xác nhận khi đúng.' if config else
                 'Đây là lỗi đã lưu; xem chi tiết trước khi chủ động tiếp tục.' if saved else
                 'Kiểm tra quyền truy cập website nguồn; không vượt login/VIP/paywall/CAPTCHA.' if code == 'SOURCE_ACCESS_DENIED' else
                 'Kiểm tra quyền model/project tại AI Studio. Xem Chi tiết; không tự đổi key/billing.' if code == 'ACCESS_DENIED' else
                 'Xem Chi tiết/Nhật ký để biết bằng chứng và cách xử lý; kết quả cũ được giữ.')
        if code=='RESPONSE_BLOCKED' and event.get('provider')=='AGY Gemini':
            short = 'Nhà cung cấp chặn phản hồi bằng bộ lọc nội dung; giữ pending, không tự gửi lại batch.'
        self.summary.setText('Kiểm tra cấu hình AGY; đã pause, không tạo Origin mới.' if agy_init else short)
        self.settings.setVisible(config)
        stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
        provider = event.get('provider', event.get('mode', ''))
        provider = provider if provider in ('AI Gemini API', 'AI Gemini AGY', 'Gemini API', 'AGY Gemini', 'MyMemory', 'Offline') else 'Provider'
        page = event.get('image_index')
        page_label = ' • Trang ' + str(page) if type(page) is int and 0 < page < 10**7 else ''
        log_facts = cause+'\n'+facts if provider=='AGY Gemini' and code in ('RESPONSE_BLOCKED','NETWORK_ERROR') else facts
        display_provider='AGY' if provider=='AGY Gemini' else provider
        self.log.appendPlainText(stamp + ' • ' + display_provider + ' • ' + code + page_label + '\n' + log_facts + '\n' + remedy)
        model=event.get('model')
        from providers.agy_models import MODEL_IDS
        if isinstance(model,str) and model in MODEL_IDS:
            self.log.appendPlainText('Model đã cấu hình: '+model)
            effort=event.get('effort')
            if effort in ('low','medium','high','default'):self.log.appendPlainText('Mức suy luận: '+effort)
        attempt = event.get('agy_attempt_id')
        if isinstance(attempt,str) and re.fullmatch('[a-f0-9]{32}',attempt):
            from core.paths import ROOT
            path = ROOT/'logs/diagnostics/agy_errors'/attempt
            self.log.appendPlainText('Attempt: '+attempt+' • '+str(path)+
                (' • Không lưu đủ evidence; giữ lỗi gốc.' if event.get('agy_evidence_error') else ''))
            self.summary.setText(self.summary.text()+' • Attempt '+attempt)
        if event.get('gemini_api_request'):
            self.log.appendPlainText('Request: ' + api['request_state'] + ' • HTTP: ' + str(api['http_status']) +
                ' • reason: ' + api['error_reason'] + ' • model: ' + api['model'])
        self.show()

    def show_saved_error(self):
        self.show_error(dict(code='SAVED_ERROR', origin='journal'))
