"""Small, read-only list of pages needing review; text diagnostics stay on disk."""
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHeaderView, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)


class ReviewDialog(QDialog):
    def __init__(self, records: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle('Trang cần xem lại')
        self.resize(1040, 430)
        self.records = records
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Ảnh dự phòng giữ nguyên nội dung nguồn; chưa phải bản dịch hoàn chỉnh.'))
        self.table = QTableWidget(len(records), 7)
        self.table.setHorizontalHeaderLabels(['Trang', 'Ảnh', 'Giai đoạn', 'Provider', 'Mã lỗi', 'Output', 'Chi tiết / log'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        for row, record in enumerate(records):
            values = [record.get(k) for k in ('image_index', 'image_filename', 'stage', 'provider', 'error_code', 'output_status')]
            values.append(record.get('error_message', '') + '\n' + (record.get('diagnostic_path') or record.get('diagnostic_error') or 'Không ghi được diagnostic'))
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value or ''))
                item.setToolTip(str(value or ''))
                self.table.setItem(row, col, item)
        layout.addWidget(self.table)
        self.open_log = QPushButton('Mở thư mục log của dòng chọn')
        self.open_log.clicked.connect(self.show_log)
        self.open_log.setEnabled(any(r.get('diagnostic_path') for r in records))
        layout.addWidget(self.open_log)
        close = QPushButton('Đóng')
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        if records:
            self.table.selectRow(0)

    def show_log(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.records):
            value = self.records[row].get('diagnostic_path')
            if value and Path(value).parent.is_dir():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(value).parent.resolve())))
