from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QLabel, QMessageBox,
    QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from core.models import CATALOG
from ui.workers import ModelWorker


class ModelManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Quản lý mô hình AI — tải riêng trước khi chạy Offline')
        self.resize(1040, 640)
        self.worker = None
        layout = QVBoxLayout(self)
        notice = QLabel('Chỉ nút Tải mới truy cập mạng. Không tải tự động khi dịch.\n'
                        'Offline Trung/Hàn cần model nguồn → en và en → vi. Auto OCR cần cả 4 bộ OCR.\n'
                        'Dung lượng trong bảng là ước tính; tiến trình dùng số byte tải thực. Kiểm tra dùng SHA-256 cục bộ.\n'
                        'Nguồn: PaddlePaddle (Apache-2.0), Argos (MIT/CC0). Model không được nhúng trong EXE.')
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.table = QTableWidget(len(CATALOG), 6)
        self.table.setHorizontalHeaderLabels(['Model', 'Ngôn ngữ', 'Engine', 'Ước tính', 'Giấy phép', 'Trạng thái'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.status = QLabel('Chọn model cần quản lý')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        controls = QHBoxLayout()
        self.buttons = []
        for title, action in [('Tải', 'download'), ('Kiểm tra model', 'verify'), ('Xóa model', 'delete')]:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, a=action: self.act(a))
            controls.addWidget(button)
            self.buttons.append(button)
        self.cancel = QPushButton('Hủy tải')
        self.cancel.setEnabled(False)
        self.cancel.clicked.connect(self.cancel_download)
        controls.addWidget(self.cancel)
        layout.addLayout(controls)
        self.refresh()

    def refresh(self) -> None:
        for row, spec in enumerate(CATALOG):
            status = 'Đã cài; bấm Kiểm tra' if (spec.directory / 'integrity.json').is_file() else 'Chưa cài'
            for column, text in enumerate([spec.name, spec.languages, spec.engine, f'~{spec.size_mb} MB', spec.license, status]):
                self.table.setItem(row, column, QTableWidgetItem(text))
        self.table.resizeColumnsToContents()
        if self.table.currentRow() < 0:
            self.table.selectRow(0)

    def act(self, action: str) -> None:
        row = self.table.currentRow()
        if row < 0 or (self.worker and self.worker.isRunning()):
            return
        spec = CATALOG[row]
        if action == 'delete' and QMessageBox.question(self, 'Xóa model', f'Xóa {spec.name}? Có thể tải lại sau.') != QMessageBox.Yes:
            return
        self.worker = ModelWorker(spec, action, self)
        self.worker.progress.connect(self.download_progress)
        self.worker.result.connect(self.action_result)
        self.worker.finished.connect(self.action_finished)
        self.progress.setRange(0, 0)
        self.status.setText('Đang thực hiện: ' + spec.name)
        for button in self.buttons:
            button.setEnabled(False)
        self.cancel.setEnabled(action == 'download')
        self.worker.start()

    def download_progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, 100 if total else 0)
        if total:
            self.progress.setValue(int(done*100/total))
        self.status.setText(f'Đã tải {done/1048576:.1f} MB / {total/1048576:.1f} MB' if total else f'Đã tải {done/1048576:.1f} MB')

    def action_result(self, success: bool, message: str) -> None:
        self.status.setText(message)
        self.progress.setRange(0, 100)
        self.progress.setValue(100 if success else 0)

    def action_finished(self) -> None:
        self.cancel.setEnabled(False)
        for button in self.buttons:
            button.setEnabled(True)
        self.refresh()

    def cancel_download(self) -> None:
        if self.worker:
            self.worker.control.cancel()
            self.status.setText('Đang hủy; chờ thao tác mạng hiện tại kết thúc (timeout tối đa 25 giây).')
            self.cancel.setEnabled(False)

    def closeEvent(self, event) -> None:
        if self.worker and self.worker.isRunning():
            self.cancel_download()
            event.ignore()
        else:
            event.accept()
