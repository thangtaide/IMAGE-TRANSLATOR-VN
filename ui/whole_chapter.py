"""Opt-in local QA dialog. No provider switch, settings persistence or network."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QProgressBar, QPushButton, QVBoxLayout)

from core.paths import ROOT
from core.pipeline import JobControl
from core.types import Options


class WholeChapterWorker(QThread):
    event = Signal(dict)

    def __init__(self, source, workspace, options, allow_translation, parent=None):
        super().__init__(parent)
        self.source, self.workspace, self.options = source, workspace, options
        self.allow_translation = allow_translation
        self.control = JobControl()

    def run(self):
        try:
            from core.runtime import prepare_inference_runtime
            prepare_inference_runtime()
            from core.whole_chapter import WholeChapterJob
            WholeChapterJob(self.source, self.workspace, options=self.options,
                control=self.control, emit=self.event.emit).run(allow_translation=self.allow_translation)
        except Exception as exc:
            self.event.emit(dict(type='whole_finished', state='blocked', error_code=type(exc).__name__))


class WholeChapterDialog(QDialog):
    def __init__(self, options=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Whole Chapter Translation — thử nghiệm offline')
        self.resize(640, 310)
        self.options = replace(options or Options())
        self.worker = None
        self.workspace = None
        layout = QVBoxLayout(self)
        note = QLabel('Chỉ Argos offline, một worker OCR. Chọn thư mục ảnh đã có.\n'
                      'Kết quả/cache/journal riêng trong output/stage3f-…; không tải ảnh, không gọi AGY/API.')
        note.setWordWrap(True); layout.addWidget(note)
        row = QHBoxLayout(); self.source = QLineEdit(self.options.source)
        self.choose = QPushButton('Chọn ảnh chương'); row.addWidget(self.source, 1); row.addWidget(self.choose)
        self.choose.clicked.connect(self.choose_source); layout.addLayout(row)
        self.allow = QCheckBox('Cho phép dịch Argos phần còn thiếu trong lượt bấm này (không tự retry)')
        layout.addWidget(self.allow)
        row = QHBoxLayout(); self.start = QPushButton('Chạy QA mới')
        self.restore = QPushButton('Mở journal QA…'); self.resume = QPushButton('Tiếp tục QA')
        self.cancel = QPushButton('Hủy'); self.cancel.setEnabled(False); self.resume.setEnabled(False)
        for b in (self.start, self.restore, self.resume, self.cancel): row.addWidget(b)
        layout.addLayout(row)
        self.start.clicked.connect(self.start_new); self.restore.clicked.connect(self.restore_job)
        self.resume.clicked.connect(self.start_resume); self.cancel.clicked.connect(self.cancel_job)
        self.progress = QProgressBar(); layout.addWidget(self.progress)
        self.status = QLabel('Chưa chạy. Mở journal chỉ nạp cấu hình, không tự xử lý.')
        self.status.setWordWrap(True); layout.addWidget(self.status)

    def choose_source(self):
        value = QFileDialog.getExistingDirectory(self, 'Ảnh chương đã có', self.source.text())
        if value: self.source.setText(value)

    def start_new(self):
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        self.workspace = ROOT / 'output' / ('stage3f-' + stamp + '-' + uuid4().hex[:8])
        self.begin()

    def restore_job(self):
        name, _ = QFileDialog.getOpenFileName(self, 'Chọn chapter-journal.json QA',
            str(ROOT / 'output'), 'JSON (*.json)')
        if not name: return
        try:
            from core.whole_chapter import read_json, verify
            path = Path(name)
            data = verify(read_json(path))
            if path.name != 'chapter-journal.json' or data.get('version') != 1:
                raise ValueError()
            self.options = Options.from_dict(data['options'])
            self.source.setText(data['source']); self.workspace = path.parent
            self.allow.setChecked(False); self.resume.setEnabled(True)
            self.status.setText('Đã nạp journal QA. Tích cho phép nếu cần dịch tiếp rồi chủ động bấm Tiếp tục QA.')
        except Exception:
            self.status.setText('Không đọc được journal QA hợp lệ; dữ liệu giữ nguyên.')

    def start_resume(self):
        if self.workspace: self.begin()

    def begin(self):
        if self.worker and self.worker.isRunning(): return
        self.worker = WholeChapterWorker(self.source.text(), self.workspace, self.options,
                                         self.allow.isChecked(), self)
        self.worker.event.connect(self.on_event)
        self.worker.finished.connect(lambda: self.set_running(False))
        self.set_running(True); self.worker.start()

    def set_running(self, running):
        for widget in (self.start, self.restore, self.source, self.choose, self.allow): widget.setEnabled(not running)
        self.resume.setEnabled(not running and self.workspace is not None)
        self.cancel.setEnabled(running)

    def on_event(self, event):
        if event.get('type') == 'whole_progress':
            self.progress.setValue(event['percent'])
            self.status.setText(f"{event['phase']}: {event['completed']}/{event['total']}")
        elif event.get('type') == 'whole_finished':
            self.status.setText(f"{event['state']} • {event.get('error_code', '')}\n{self.workspace}")
            if event['state'] == 'done': self.progress.setValue(100)
            self.allow.setChecked(False)
        elif event.get('stage'):
            total = max(1, event.get('total', 1))
            self.progress.setValue(int(100 * (event.get('index', 1)-1 + event.get('percent', 0)/100) / total))
            self.status.setText(f"RENDER • {event.get('index', 0)}/{event.get('total', 0)} • {event['stage']}")

    def cancel_job(self):
        if self.worker: self.worker.control.cancel()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.cancel_job()
            self.status.setText('Đang hủy tại checkpoint an toàn; chờ worker dừng rồi đóng.')
            event.ignore()
        else:
            event.accept()
