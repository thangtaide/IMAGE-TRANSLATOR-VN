from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from core.paths import ROOT
from core.storage import TranslationCache, load_options, save_options
from core.types import Options
from ui.models_dialog import ModelManagerDialog
from ui.preview import PreviewDialog
from ui.settings_dialog import SettingsDialog
from ui.workers import ProcessingWorker


def duration(seconds: float | None) -> str:
    if seconds is None:
        return 'Đang ước tính'
    seconds = max(0, int(seconds))
    return f'{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}'


class MainWindow(QMainWindow):
    def __init__(self, cache_path: Path | None = None):
        super().__init__()
        self.cache_path = cache_path
        from ui.fonts import configure_ui_font
        self.font_report = configure_ui_font()
        self.setWindowTitle('IMAGE TRANSLATOR VN')
        self.resize(1180, 850)
        self.options = load_options()
        if not self.options.output:
            self.options.output = str(ROOT / 'output')
        self.worker: ProcessingWorker | None = None
        self.rows: dict[str, int] = {}
        self.outputs: dict[str, str] = {}
        self.details: dict[str, str] = {}
        self.failed: list[str] = []
        self.unfinished: list[str] = []
        self.started = 0.0
        self.paused_at = None
        self.pause_seconds = 0.0
        self.pending_options = None
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        title = QLabel('IMAGE TRANSLATOR VN')
        title.setObjectName('title')
        outer.addWidget(title)
        subtitle = QLabel('OCR • Dịch sang tiếng Việt • Phục hồi nền • Xuất ảnh   |   CPU • Miễn phí')
        subtitle.setObjectName('subtitle')
        outer.addWidget(subtitle)
        self.config_panel = QGroupBox('Nguồn ảnh và cấu hình')
        config = QVBoxLayout(self.config_panel)
        self.source = QLineEdit(self.options.source)
        self.output = QLineEdit(self.options.output)
        for label, widget, title_text in [('THƯ MỤC ẢNH NGUỒN', self.source, 'Chọn thư mục'),
                                          ('THƯ MỤC XUẤT (trong D:\\TransTool)', self.output, 'Chọn nơi lưu')]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addWidget(widget, 1)
            button = QPushButton(title_text)
            button.clicked.connect(lambda checked=False, w=widget: self.choose_folder(w))
            row.addWidget(button)
            config.addLayout(row)
        choices = QHBoxLayout()
        self.recursive = QCheckBox('Quét thư mục con')
        self.recursive.setChecked(self.options.recursive)
        self.keep_original = QCheckBox('Giữ nguyên ảnh gốc (bắt buộc)')
        self.keep_original.setChecked(True)
        self.keep_original.setEnabled(False)
        self.skip = QCheckBox('Bỏ qua ảnh đã xử lý thành công')
        self.skip.setChecked(self.options.skip_success)
        self.structure = QCheckBox('Giữ cấu trúc thư mục nguồn')
        self.structure.setChecked(self.options.preserve_structure)
        for widget in [self.recursive, self.keep_original, self.skip, self.structure]:
            choices.addWidget(widget)
        config.addLayout(choices)
        row = QHBoxLayout()
        row.addWidget(QLabel('OCR'))
        self.language = QComboBox()
        for label, code in [('Trung giản thể', 'zh'), ('Trung phồn thể', 'zt'), ('Hàn', 'ko'), ('Anh', 'en'), ('Tự động (4 bộ model)', 'auto')]:
            self.language.addItem(label, code)
        self.language.setCurrentIndex(max(0, self.language.findData(self.options.language)))
        row.addWidget(self.language)
        row.addWidget(QLabel('Dịch'))
        self.mode = QComboBox()
        self.mode.addItems(['Offline', 'Online', 'Auto Fallback'])
        self.mode.setCurrentText(self.options.mode)
        row.addWidget(self.mode)
        self.online_provider = QComboBox()
        self.online_provider.addItems(['MyMemory', 'LibreTranslate'])
        self.online_provider.setCurrentText(self.options.online_provider)
        self.offline_provider = QComboBox()
        self.offline_provider.addItems(['Argos', 'CTranslate2', 'M2M100'])
        self.offline_provider.setItemData(2, 'Dịch trực tiếp; cần cài riêng model M2M100 đã chuyển đổi. '
                                        'Chưa có model sẽ báo lỗi, không tự tải.', Qt.ToolTipRole)
        self.offline_provider.setCurrentText(self.options.offline_provider)
        row.addWidget(QLabel('Online'))
        row.addWidget(self.online_provider)
        row.addWidget(QLabel('Offline'))
        row.addWidget(self.offline_provider)
        config.addLayout(row)
        self.allow_fallback = QCheckBox('Tôi đồng ý gửi văn bản OCR tới provider Online miễn phí nếu Offline lỗi (chỉ Auto Fallback)')
        self.allow_fallback.setChecked(self.options.allow_online_fallback)
        config.addWidget(self.allow_fallback)
        self.privacy = QLabel()
        self.privacy.setWordWrap(True)
        config.addWidget(self.privacy)
        self.mode.currentTextChanged.connect(self.update_mode)
        self.update_mode()
        outer.addWidget(self.config_panel)
        self.resume_previous = QPushButton('Khôi phục cấu hình công việc chưa hoàn thành')
        self.resume_previous.clicked.connect(self.restore_previous)
        outer.addWidget(self.resume_previous)
        cache = TranslationCache(self.cache_path)
        self.pending_options = cache.pending_job()
        cache.close()
        self.resume_previous.setVisible(self.pending_options is not None)
        controls = QHBoxLayout()
        self.start_button = QPushButton('Bắt đầu dịch')
        self.start_button.setObjectName('primary')
        self.pause_button = QPushButton('Tạm dừng')
        self.continue_button = QPushButton('Tiếp tục')
        self.cancel_button = QPushButton('Hủy')
        self.retry_button = QPushButton('Thử lại ảnh lỗi / chưa xong')
        self.open_button = QPushButton('Mở kết quả')
        self.models_button = QPushButton('Quản lý mô hình AI')
        self.settings_button = QPushButton('Cài đặt')
        for button in [self.start_button, self.pause_button, self.continue_button, self.cancel_button,
                       self.retry_button, self.open_button, self.models_button, self.settings_button]:
            controls.addWidget(button)
        outer.addLayout(controls)
        self.start_button.clicked.connect(lambda: self.start())
        self.pause_button.clicked.connect(self.pause)
        self.continue_button.clicked.connect(self.resume)
        self.cancel_button.clicked.connect(self.cancel)
        self.retry_button.clicked.connect(self.retry)
        self.open_button.clicked.connect(self.open_output)
        self.models_button.clicked.connect(self.show_models)
        self.settings_button.clicked.connect(self.show_settings)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setFormat('%p%')
        outer.addWidget(self.progress)
        self.current = QLabel('Sẵn sàng. Cài model qua Quản lý mô hình AI trước khi dịch.')
        self.current.setWordWrap(True)
        outer.addWidget(self.current)
        self.stats = QLabel('Tổng số ảnh: 0  •  Hoàn thành: 0  •  Lỗi: 0  •  Bỏ qua: 0')
        self.clock_label = QLabel('Đã chạy: 00:00:00  •  Còn lại: Đang ước tính')
        outer.addWidget(self.stats)
        outer.addWidget(self.clock_label)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['Tên file', 'Ngôn ngữ', 'Trạng thái', 'Tiến trình', 'Kết quả / Chi tiết'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.inspect)
        outer.addWidget(self.table, 1)
        outer.addWidget(QLabel('Nhấp đúp một hàng để xem ảnh trước/sau hoặc chi tiết lỗi. Nền phức tạp và chữ dọc cần kiểm tra preview.'))
        self.eta = None
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_clock)
        self.set_running(False)
        self.setStyleSheet('''
            QMainWindow, QDialog { background: #111827; color: #e5e7eb; }
            QWidget { font-size: 12px; color: #e5e7eb; }
            QGroupBox { border: 1px solid #374151; border-radius: 8px; margin-top: 14px; padding: 14px 8px 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; }
            QLabel#title { font-size: 27px; font-weight: 700; color: #60a5fa; }
            QLabel#subtitle { color: #9ca3af; padding-bottom: 10px; }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit { background: #1f2937; border: 1px solid #4b5563; border-radius: 4px; padding: 6px; }
            QComboBox QAbstractItemView { background: #1f2937; selection-background-color: #2563eb; }
            QPushButton { background: #273449; border: 1px solid #475569; border-radius: 5px; padding: 9px; }
            QPushButton:hover { background: #334155; }
            QPushButton#primary { background: #2563eb; font-weight: 600; }
            QPushButton:disabled { color: #6b7280; background: #1f2937; }
            QTableWidget { background: #172033; alternate-background-color: #1f2937; gridline-color: #374151; }
            QHeaderView::section { background: #273449; padding: 8px; border: 0; }
            QProgressBar { border: 1px solid #374151; text-align: center; min-height: 22px; border-radius: 4px; }
            QProgressBar::chunk { background: #2563eb; }
        ''')

    def choose_folder(self, field: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, 'Chọn thư mục', field.text() or str(ROOT))
        if path:
            field.setText(path)

    def update_mode(self, *_args) -> None:
        mode = self.mode.currentText()
        self.online_provider.setEnabled(mode != 'Offline')
        self.offline_provider.setEnabled(mode != 'Online')
        self.allow_fallback.setEnabled(mode == 'Auto Fallback')
        self.privacy.setText('Offline: toàn bộ OCR và dịch chạy cục bộ; thiếu model sẽ báo lỗi, không tải hoặc gửi dữ liệu.' if mode == 'Offline'
                             else 'Online: chỉ gửi văn bản OCR để dịch. MyMemory có hạn mức miễn phí; ảnh luôn xử lý trên máy.' if mode == 'Online'
                             else 'Auto Fallback: thử Offline trước. Chỉ gọi Online khi ô đồng ý được bật.')

    def collect_options(self) -> Options:
        self.options.source = self.source.text().strip()
        self.options.output = self.output.text().strip()
        self.options.language = self.language.currentData()
        self.options.mode = self.mode.currentText()
        self.options.online_provider = self.online_provider.currentText()
        self.options.offline_provider = self.offline_provider.currentText()
        self.options.allow_online_fallback = self.allow_fallback.isChecked()
        self.options.recursive = self.recursive.isChecked()
        self.options.preserve_structure = self.structure.isChecked()
        self.options.skip_success = self.skip.isChecked()
        return Options.from_dict(self.options.to_dict())

    def start(self, only: list[str] | None = None) -> None:
        if self.worker and self.worker.isRunning():
            return
        options = self.collect_options()
        if not options.source or not options.output:
            QMessageBox.warning(self, 'Thiếu thư mục', 'Chọn thư mục nguồn và thư mục xuất trước.')
            return
        try:
            save_options(options)
        except OSError as exc:
            QMessageBox.critical(self, 'Không lưu được cấu hình', str(exc))
            return
        self.failed = []
        self.unfinished = []
        self.outputs = {}
        self.details = {}
        self.rows = {}
        self.table.setRowCount(0)
        self.progress.setValue(0)
        self.eta = None
        self.started = time.monotonic()
        self.pause_seconds = 0
        self.paused_at = None
        self.current.setText('Đang quét thư mục và kiểm tra model...')
        self.worker = ProcessingWorker(options, only, self, cache_path=self.cache_path)
        self.worker.event.connect(self.handle_event)
        self.worker.finished.connect(self.worker_finished)
        self.set_running(True)
        self.timer.start()
        self.worker.start()

    def set_running(self, running: bool) -> None:
        self.config_panel.setEnabled(not running)
        self.start_button.setEnabled(not running)
        self.pause_button.setEnabled(running)
        self.continue_button.setEnabled(False)
        self.cancel_button.setEnabled(running)
        self.retry_button.setEnabled(not running and bool(self.failed or self.unfinished))
        self.models_button.setEnabled(not running)
        self.settings_button.setEnabled(not running)
        self.resume_previous.setEnabled(not running)

    def handle_event(self, event: dict) -> None:
        kind = event.get('type')
        if kind == 'files':
            paths = event['files']
            self.unfinished = list(paths)
            self.table.setRowCount(len(paths))
            for row, path in enumerate(paths):
                self.rows[path] = row
                for column, value in enumerate([str(Path(path).relative_to(Path(self.options.source).resolve())), '', 'Chờ', '0%', '']):
                    self.table.setItem(row, column, QTableWidgetItem(value))
            return
        if kind == 'fatal':
            self.current.setText('Lỗi: ' + event['detail'])
            QMessageBox.warning(self, 'Không thể xử lý', event['detail'])
            return
        if kind == 'finished':
            self.failed = event['errors']
            if event['state'] == 'done':
                self.current.setText('Đã hoàn tất. Nhấp đúp hàng để xem trước kết quả và cảnh báo.')
                self.progress.setValue(1000)
            elif event['state'] == 'cancelled':
                self.current.setText('Đã hủy an toàn. Kết quả đã hoàn thành và checkpoint được giữ lại.')
            elif event['state'] == 'errors':
                self.current.setText('Batch kết thúc với ảnh lỗi. Xem chi tiết và dùng nút Thử lại sau khi khắc phục.')
            return
        path = event.get('file')
        if path not in self.rows:
            return
        row = self.rows[path]
        for column, value in [(2, event['stage']), (3, f"{event['percent']}%")]:
            self.table.item(row, column).setText(value)
        if event.get('language'):
            self.table.item(row, 1).setText(event['language'])
        if event.get('output'):
            self.outputs[path] = event['output']
            self.table.item(row, 4).setText(Path(event['output']).name)
        if event.get('detail'):
            self.details[path] = event['detail']
            self.table.item(row, 4).setToolTip(event['detail'])
            if not event.get('output'):
                self.table.item(row, 4).setText(event['detail'])
        terminal = event['stage'] in ('Hoàn thành', 'Bỏ qua', 'Lỗi')
        if terminal and path in self.unfinished:
            self.unfinished.remove(path)
        self.current.setText(f"Đang xử lý: {Path(path).name}  •  Công đoạn: {event['stage']}  •  {event['index']} / {event['total']} ảnh")
        self.stats.setText(f"Tổng số ảnh: {event['total']}  •  Hoàn thành: {event['completed']}  •  Lỗi: {event['failed']}  •  Bỏ qua: {event['skipped']}")
        fractional = event['index']-1 + event['percent']/100
        self.progress.setValue(int(1000*fractional/max(1, event['total'])))
        self.eta = event.get('eta')
        self.update_clock()

    def update_clock(self) -> None:
        elapsed = time.monotonic()-self.started if self.started else 0
        self.clock_label.setText(f'Đã chạy: {duration(elapsed)}  •  Còn lại: {duration(self.eta)}')

    def pause(self) -> None:
        if self.worker:
            self.worker.control.pause()
            self.pause_button.setEnabled(False)
            self.continue_button.setEnabled(True)
            self.current.setText('Đã yêu cầu tạm dừng; tác vụ hiện tại sẽ dừng ở checkpoint an toàn.')

    def resume(self) -> None:
        if self.worker:
            self.worker.control.resume()
            self.pause_button.setEnabled(True)
            self.continue_button.setEnabled(False)
            self.current.setText('Đang tiếp tục xử lý...')

    def cancel(self) -> None:
        if self.worker:
            self.worker.control.cancel()
            self.cancel_button.setEnabled(False)
            self.pause_button.setEnabled(False)
            self.continue_button.setEnabled(False)
            self.current.setText('Đang hủy an toàn; chờ OCR/model hoặc yêu cầu mạng hiện tại kết thúc.')

    def retry(self) -> None:
        paths = list(dict.fromkeys(self.failed + self.unfinished))
        if paths:
            self.start(paths)

    def worker_finished(self) -> None:
        self.timer.stop()
        self.update_clock()
        self.set_running(False)

    def inspect(self, row: int, column: int) -> None:
        path = next((p for p, r in self.rows.items() if r == row), None)
        if path is None:
            return
        if path in self.outputs:
            if self.details.get(path):
                QMessageBox.information(self, 'Cảnh báo chất lượng', self.details[path])
            PreviewDialog(path, self.outputs[path], self).exec()
        else:
            QMessageBox.information(self, 'Chi tiết ảnh', self.details.get(path, self.table.item(row, 2).text()))

    def open_output(self) -> None:
        path = Path(self.output.text())
        if path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
        else:
            QMessageBox.information(self, 'Thư mục kết quả', 'Thư mục kết quả chưa tồn tại.')

    def show_models(self) -> None:
        ModelManagerDialog(self).exec()

    def show_settings(self) -> None:
        self.collect_options()
        if SettingsDialog(self.options, self).exec():
            save_options(self.options)

    def restore_previous(self) -> None:
        if self.pending_options:
            save_options(self.pending_options)
            # Reconstruct widget state in-place without starting a second window.
            p = self.pending_options
            self.options = Options.from_dict(p.to_dict())
            self.source.setText(p.source)
            self.output.setText(p.output)
            self.language.setCurrentIndex(max(0, self.language.findData(p.language)))
            self.mode.setCurrentText(p.mode)
            self.online_provider.setCurrentText(p.online_provider)
            self.offline_provider.setCurrentText(p.offline_provider)
            self.recursive.setChecked(p.recursive)
            self.skip.setChecked(True)
            self.structure.setChecked(p.preserve_structure)
            self.allow_fallback.setChecked(p.allow_online_fallback)
            self.current.setText('Đã khôi phục cấu hình. Bấm Bắt đầu dịch; ảnh thành công có checksum hợp lệ sẽ được bỏ qua.')

    def closeEvent(self, event) -> None:
        if self.worker and self.worker.isRunning():
            self.cancel()
            QMessageBox.information(self, 'Đang hủy công việc', 'Chờ công việc dừng an toàn rồi đóng cửa sổ.')
            event.ignore()
        else:
            try:
                save_options(self.collect_options())
            except OSError:
                pass
            event.accept()
