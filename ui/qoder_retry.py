"""Explicit, one-time authorization of uncertain Qoder attempts; never deletes receipts."""
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from core.storage import atomic_json
from providers.qoder import read_receipt
from providers.online import ProviderSuspended


def confirm_unknown_receipts(root, parent):
    root = Path(root)
    unknown = []
    if root.exists():
        for path in root.rglob('*.json'):
            try:
                data = read_receipt(path)
            except ProviderSuspended:
                QMessageBox.warning(parent,'Qoder: receipt không hợp lệ','Giữ dữ liệu; không thể xác nhận gửi lại khi receipt bị đổi hoặc hỏng.')
                return False
            if data.get('state') == 'unknown':
                unknown.append((path, data))
    if not unknown:
        return True
    answer = QMessageBox.question(parent, 'Qoder: batch chưa rõ kết quả',
        f'{len(unknown)} batch đã bắt đầu nhưng chưa có receipt hợp lệ. Có thể đã tiêu thụ Credits. '
        'Bạn có muốn cho phép gửi lại các batch này một lần khi tiếp tục? Kết quả đã hoàn thành được giữ.',
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    if answer != QMessageBox.Yes:
        return False
    for path, data in unknown:
        data['state'] = 'retry_authorized'
        atomic_json(path, data)
    return True
