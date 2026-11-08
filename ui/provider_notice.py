"""Dismissible provider message; closing it never resumes work."""
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


def gemini_usage_text(event):
    usage = event.get('usage', {})
    return ('Gemini API • ' + event['model'] + ' • token input/output/total: ' +
            '/'.join(str(usage.get(k, '?')) for k in ('promptTokenCount', 'candidatesTokenCount', 'totalTokenCount')) +
            f" • request cục bộ {event['requests']}/{event['request_limit']}. Quota Google còn lại: chưa xác định; xem AI Studio.")


class ProviderNotice(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        self.message = QLabel()
        self.message.setWordWrap(True)
        row.addWidget(self.message, 1)
        self.dismiss = QPushButton('×')
        self.dismiss.setAccessibleName('Đóng thông báo; giữ công việc tạm dừng')
        self.dismiss.clicked.connect(self.hide)
        row.addWidget(self.dismiss)
        self.hide()

    def show_error(self, event):
        reset = ('Provider yêu cầu đợi ít nhất ' + str(event['retry_after']) + ' giây.'
                 if event.get('retry_after') is not None else 'Chưa xác định thời điểm khôi phục.')
        self.message.setText(f"{event['code']} • {event['detail']} Công việc đã tạm dừng. "
            'Bạn có thể đổi phương thức dịch rồi nhấn Tiếp tục. ' + reset)
        self.setToolTip(event.get('diagnostic_path') or '')
        self.show()
