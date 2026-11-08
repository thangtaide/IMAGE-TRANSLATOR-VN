"""Dismissible provider message; closing it never resumes work."""
from datetime import datetime, timezone
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
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setTextFormat(Qt.PlainText)
        layout.addWidget(self.title)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.PlainText)
        layout.addWidget(self.message)
        row = QHBoxLayout()
        self.settings = QPushButton('Mở Cài đặt Gemini API')
        self.settings.clicked.connect(self.settingsRequested)
        row.addWidget(self.settings)
        row.addStretch()
        self.dismiss = QPushButton('×')
        self.dismiss.setAccessibleName('Đóng thông báo; giữ công việc tạm dừng')
        self.dismiss.clicked.connect(self.hide)
        row.addWidget(self.dismiss)
        layout.addLayout(row)
        self.log_toggle = QToolButton()
        self.log_toggle.setText('Chi tiết / Nhật ký')
        self.log_toggle.setCheckable(True)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(50)
        self.log.setMaximumHeight(110)
        self.log.hide()
        self.log_toggle.toggled.connect(self.log.setVisible)
        layout.addWidget(self.log_toggle)
        layout.addWidget(self.log)
        self.hide()

    def show_error(self, event):
        # Never echo arbitrary detail, paths, model output or unknown error strings.
        known = {'API_KEY_MISSING', 'FREE_TIER_UNCONFIRMED', 'READY_UNVERIFIED', 'AUTH_REQUIRED',
                 'ACCESS_DENIED', 'MODEL_UNAVAILABLE', 'RATE_LIMITED', 'QUOTA_EXCEEDED', 'NETWORK_ERROR',
                 'TIMEOUT', 'INVALID_RESPONSE', 'REQUEST_BUDGET', 'PROVIDER_UNAVAILABLE', 'INVALID_REQUEST',
                 'RESPONSE_BLOCKED', 'UNEXPECTED_TOOL_USE', 'CANCELLED', 'PAUSED_BY_USER'}
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
            title = 'Guard AGY đã từ chối phản hồi'
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
            }.get(code, 'Provider hoặc cấu hình chưa cho phép tiếp tục an toàn.')
        facts = ('Chưa khởi chạy lượt xử lý mới, chưa gửi OCR trong thao tác này.' if local else
                 'Kết quả đã hoàn tất được giữ. Chưa xác minh trạng thái gửi request từ thông báo này.')
        if event.get('phase') == 'provider_preflight' and event.get('request_sent') is False:
            facts = 'Request của batch hiện tại bị chặn trước HTTP. Những lần gọi trước chưa được xác minh tại đây.'
        remedy = ('Mở Cài đặt Gemini API → kiểm tra project ở Google AI Studio → xác nhận Free tier khi đúng → chủ động Tiếp tục hoặc Bắt đầu.'
                  if config else 'Xem mã lỗi và diagnostic cục bộ. Chủ động Tiếp tục khi đã xử lý nguyên nhân; không tự retry hoặc đổi provider.')
        delay = event.get('retry_after')
        reset = (' Provider yêu cầu đợi ít nhất ' + str(delay) + ' giây.'
                 if type(delay) is int and 0 <= delay < 10**7 else ' Chưa xác định thời điểm khôi phục.')
        self.title.setText(title + ' • ' + code)
        self.last_code = code
        self.message.setText(cause + '\n' + facts + '\n' + remedy + ('' if config else reset))
        self.settings.setVisible(config)
        stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
        provider = event.get('provider', event.get('mode', ''))
        provider = provider if provider in ('AI Gemini API', 'AI Gemini AGY', 'Gemini API', 'AGY Gemini', 'MyMemory', 'Offline') else 'Provider'
        page = event.get('image_index')
        page_label = ' • Trang ' + str(page) if type(page) is int and 0 < page < 10**7 else ''
        self.log.appendPlainText(stamp + ' • ' + provider + ' • ' + code + page_label + '\n' + facts + '\n' + remedy)
        self.show()
