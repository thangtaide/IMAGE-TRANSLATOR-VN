"""Confirmation and asynchronous input counting; no OCR or provider initialization."""
from pathlib import Path
import os

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (QDialog, QFormLayout, QLabel,
    QPushButton, QFileDialog, QVBoxLayout, QScrollArea, QWidget, QHBoxLayout)

from core.imaging import SUPPORTED
from providers.agy import WHOLE_MODE


class CountImages(QThread):
    counted = Signal(int)
    failed = Signal(str)

    def __init__(self, options, parent=None):
        super().__init__(parent); self.options = options

    def run(self):
        try:
            root=Path(self.options.source).resolve(); output=Path(self.options.output).resolve()
            if not root.is_dir():raise ValueError('Chọn thư mục ảnh nguồn tồn tại')
            count=0
            for folder,dirs,files in os.walk(root,followlinks=False):
                if self.isInterruptionRequested():return
                dirs[:]=[d for d in dirs if not (Path(folder)/d).is_symlink() and
                    not (Path(folder)/d).resolve().is_relative_to(output)] if self.options.recursive else []
                for name in files:
                    if self.isInterruptionRequested():return
                    p=Path(folder)/name
                    if p.suffix.lower() in SUPPORTED and not p.is_symlink() and not p.resolve().is_relative_to(output):count+=1
            self.counted.emit(count)
        except (OSError, ValueError) as exc:
            self.failed.emit(str(exc))


class FreshRunDialog(QDialog):
    def __init__(self, options, registry, parent=None):
        super().__init__(parent)
        from ui.theme import apply_dark_theme
        apply_dark_theme()
        self.options,self.registry=options,registry
        self.plan=registry.plan(options,whole=options.mode==WHOLE_MODE)
        self.setWindowTitle('Dịch lại toàn bộ ảnh từ đầu?');self.setMinimumWidth(420)
        screen=self.screen().availableGeometry();self.resize(min(680,screen.width()-60),min(650,screen.height()-80))
        outer=QVBoxLayout(self);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QScrollArea.NoFrame)
        body=QWidget();body.setMinimumWidth(360);scroll.setWidget(body);outer.addWidget(scroll)
        layout=QVBoxLayout(body);layout.setSpacing(14)
        title=QLabel('Dịch lại toàn bộ ảnh từ đầu?');title.setObjectName('title');title.setWordWrap(True);layout.addWidget(title)
        note=QLabel('OCR sẽ được chạy lại. AGY sẽ được gọi lại nếu đang chọn AGY. '
            'Có thể phát sinh thời gian và chi phí.\nCache, checkpoint và kết quả cũ được giữ nguyên. '
            'Một thư mục kết quả mới sẽ được tạo; không ghi đè file cũ.')
        note.setWordWrap(True);layout.addWidget(note)
        form=QFormLayout();form.setRowWrapPolicy(QFormLayout.WrapLongRows);layout.addLayout(form)
        self.count=QLabel('Đang đếm ảnh…');form.addRow('Số ảnh dự kiến',self.count)
        for label,value in [('Chế độ',options.mode),('Model',options.agy_model if 'AGY' in options.mode else options.offline_provider),
                ('Thư mục nguồn',options.source),('Run ID',self.plan['run_id'])]:
            text=QLabel(value);text.setWordWrap(True);text.setTextInteractionFlags(Qt.TextSelectableByMouse);form.addRow(label,text)
        self.destination=QLabel(self.plan['output']);self.destination.setWordWrap(True);form.addRow('Thư mục xuất mới',self.destination)
        self.choose=QPushButton('Chọn vị trí xuất khác…');self.choose.setVisible(options.mode!=WHOLE_MODE)
        self.choose.clicked.connect(self.choose_output);layout.addWidget(self.choose)
        policy=QLabel('Cache bypass: BẬT — DB riêng, không đọc OCR/bản dịch/render hoặc checkpoint của lượt cũ.')
        policy.setWordWrap(True);layout.addWidget(policy)
        self.buttons=QWidget();bar=QHBoxLayout(self.buttons);bar.setContentsMargins(0,0,0,0);bar.addStretch()
        self.cancel=QPushButton('Hủy');self.confirm=QPushButton('Xác nhận dịch lại')
        bar.addWidget(self.cancel);bar.addWidget(self.confirm);self.cancel.setDefault(True);self.confirm.setAutoDefault(False)
        self.confirm.setObjectName('restart');self.confirm.setEnabled(False)
        self.cancel.clicked.connect(self.reject);self.confirm.clicked.connect(self.validate_accept);outer.addWidget(self.buttons)
        self.counter=CountImages(options,self);self.counter.counted.connect(self.set_count);self.counter.failed.connect(self.count_error)
        self.counter.finished.connect(self.counter_finished);self._closing=False;self._image_count=0;self.counter.start()

    def set_count(self, count):
        self.count.setText(str(count));self._image_count=count

    def count_error(self, message):
        self.count.setText(message);self.confirm.setEnabled(False)

    def choose_output(self):
        base=QFileDialog.getExistingDirectory(self,'Chọn thư mục cha cho kết quả mới',self.options.output)
        if base:
            self.plan['output']=str(Path(base)/Path(self.plan['output']).name);self.destination.setText(self.plan['output'])

    def validate_accept(self):
        if Path(self.plan['output']).exists():
            self.count.setText('Đích đã tồn tại; chọn vị trí khác để giữ nguyên file cũ.');return
        if self.confirm.isEnabled():self.accept()

    def reject(self):
        if self.counter.isRunning():
            self._closing=True;self.counter.requestInterruption();self.confirm.setEnabled(False);self.cancel.setEnabled(False);return
        super().reject()

    def counter_finished(self):
        if self._closing:super().reject()
        else:self.confirm.setEnabled(self._image_count>0)

    def closeEvent(self,event):
        if self.counter.isRunning():
            event.ignore();self.reject()
        else:super().closeEvent(event)
