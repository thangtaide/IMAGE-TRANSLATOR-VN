from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from core.paths import CONFIG, ROOT
from core.storage import TranslationCache, load_options, save_options
from core.types import Options
from providers.agy import MODE as AGY_MODE
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
    def __init__(self, cache_path: Path | None = None, persist_settings: bool = True):
        super().__init__()
        self.cache_path = cache_path
        self.persist_settings = persist_settings
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
        self.review_pages: list[dict] = []
        self.started = 0.0
        self.paused_at = None
        self.pause_seconds = 0.0
        self.pending_options = None
        self.provider_paused = False
        self.provider_pending = []
        self.resume_id = None
        self.pending_journal = None
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        central = QWidget()
        central.setMinimumWidth(620)
        scroll.setWidget(central)
        self.setCentralWidget(scroll)
        outer = QVBoxLayout(central)
        outer.setSpacing(12)
        title = QLabel('IMAGE TRANSLATOR VN')
        title.setObjectName('title')
        outer.addWidget(title)
        subtitle = QLabel('OCR • Dịch sang tiếng Việt • Phục hồi nền • Xuất ảnh   |   CPU • Miễn phí')
        subtitle.setObjectName('subtitle')
        outer.addWidget(subtitle)
        self.source_tabs = QTabWidget()
        self.folder_page = QWidget()
        folder_layout = QVBoxLayout(self.folder_page)
        folder_layout.setSpacing(10)
        self.folder_inputs = QGroupBox('Thư mục ảnh')
        config = QVBoxLayout(self.folder_inputs)
        self.source = QLineEdit(self.options.source)
        self.output = QLineEdit(self.options.output)
        self.source.textChanged.connect(self.clear_resume_intent)
        self.output.textChanged.connect(self.clear_resume_intent)
        for label, widget, title_text in [('THƯ MỤC ẢNH NGUỒN', self.source, 'Chọn thư mục'),
                                          ('THƯ MỤC XUẤT', self.output, 'Chọn nơi lưu')]:
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
        self.skip.setChecked(True)
        self.skip.setEnabled(False)
        self.skip.setToolTip('Ảnh thành công có checkpoint/hash hợp lệ luôn được bảo toàn. Đổi thư mục xuất hoặc recipe để tạo bản mới.')
        self.structure = QCheckBox('Giữ cấu trúc thư mục nguồn')
        self.structure.setChecked(self.options.preserve_structure)
        for widget in [self.recursive, self.keep_original, self.skip, self.structure]:
            choices.addWidget(widget)
        config.addLayout(choices)
        folder_layout.addWidget(self.folder_inputs)
        self.config_panel = QGroupBox('OCR và dịch')
        config = QVBoxLayout(self.config_panel)
        row = QHBoxLayout()
        row.addWidget(QLabel('OCR'))
        self.language = QComboBox()
        for label, code in [('Trung giản thể', 'zh'), ('Trung phồn thể', 'zt'), ('Hàn', 'ko'), ('Anh', 'en'), ('Tự động (4 bộ model)', 'auto')]:
            self.language.addItem(label, code)
        self.language.setCurrentIndex(max(0, self.language.findData(self.options.language)))
        row.addWidget(self.language)
        self.mode_label = QLabel('Dịch')
        row.addWidget(self.mode_label)
        self.mode = QComboBox()
        self.mode.addItems(['Offline', 'Online Free', AGY_MODE, 'Auto Fallback'])
        self.mode.setCurrentText('Online Free' if self.options.mode == 'Online' else self.options.mode)
        self.mode.setItemData(0, 'Offline — Argos Translate / model cục bộ', Qt.ToolTipRole)
        self.mode.setItemData(1, 'Online Free — MyMemory Machine Translation API', Qt.ToolTipRole)
        row.addWidget(self.mode)
        self.online_provider = QComboBox()
        self.online_provider.addItems(['MyMemory', 'LibreTranslate'])
        self.online_provider.setCurrentText(self.options.online_provider)
        self.offline_provider = QComboBox()
        self.offline_provider.addItems(['Argos', 'CTranslate2', 'M2M100'])
        self.offline_provider.setItemData(2, 'Dịch trực tiếp; cần cài riêng model M2M100 đã chuyển đổi. '
                                        'Chưa có model sẽ báo lỗi, không tự tải.', Qt.ToolTipRole)
        self.offline_provider.setCurrentText(self.options.offline_provider)
        self.online_label = QLabel('Online')
        row.addWidget(self.online_label)
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
        from ui.provider_notice import ProviderNotice
        self.provider_notice = ProviderNotice()
        outer.addWidget(self.provider_notice)
        self.resume_previous = QPushButton('Khôi phục cấu hình công việc chưa hoàn thành')
        self.resume_previous.clicked.connect(self.restore_previous)
        folder_layout.addWidget(self.resume_previous)
        cache = TranslationCache(self.cache_path)
        self.pending_options = cache.pending_job()
        cache.close()
        from core.resume import ResumeStore
        self.pending_journal = ResumeStore(self.cache_path).latest('pipeline')
        if self.pending_journal:
            self.pending_options = Options.from_dict(self.pending_journal['options'])
            self.resume_previous.setText('Khôi phục công việc còn dở (không tự chạy)')
        self.resume_previous.setVisible(self.pending_options is not None)
        controls = QGridLayout()
        controls.setSpacing(8)
        self.start_button = QPushButton('Bắt đầu dịch')
        self.start_button.setObjectName('primary')
        self.pause_button = QPushButton('Tạm dừng')
        self.continue_button = QPushButton('Tiếp tục')
        self.cancel_button = QPushButton('Hủy')
        self.retry_button = QPushButton('Thử lại ảnh lỗi / chưa xong')
        self.open_button = QPushButton('Mở kết quả')
        self.review_button = QPushButton('Trang cần xem lại / log')
        self.review_button.setEnabled(False)
        self.review_button.clicked.connect(self.show_review)
        folder_layout.addWidget(self.review_button)
        self.models_button = QPushButton('Quản lý mô hình AI')
        self.settings_button = QPushButton('Cài đặt')
        for position, button in enumerate([self.start_button, self.pause_button, self.continue_button,
                                          self.cancel_button, self.retry_button, self.open_button]):
            controls.addWidget(button, position // 3, position % 3)
        folder_layout.addLayout(controls)
        common = QHBoxLayout()
        common.addStretch()
        common.addWidget(self.models_button)
        common.addWidget(self.settings_button)
        outer.addLayout(common)
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
        folder_layout.addWidget(self.progress)
        self.current = QLabel('Sẵn sàng. Cài model qua Quản lý mô hình AI trước khi dịch.')
        self.current.setWordWrap(True)
        folder_layout.addWidget(self.current)
        self.stats = QLabel('Tổng số ảnh: 0  •  Hoàn thành: 0  •  Lỗi: 0  •  Bỏ qua: 0')
        self.clock_label = QLabel('Đã chạy: 00:00:00  •  Còn lại: Đang ước tính')
        folder_layout.addWidget(self.stats)
        folder_layout.addWidget(self.clock_label)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['Tên file', 'Ngôn ngữ', 'Trạng thái', 'Tiến trình', 'Kết quả / Chi tiết'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.inspect)
        self.table.setMinimumHeight(230)
        folder_layout.addWidget(self.table, 1)
        hint = QLabel('Nhấp đúp để xem ảnh trước/sau hoặc chi tiết lỗi. Nền phức tạp và chữ dọc cần kiểm tra preview.')
        hint.setWordWrap(True)
        folder_layout.addWidget(hint)
        self.eta = None
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_clock)
        from ui.comic_sources import ComicSourcesPanel
        self.image_panel = ComicSourcesPanel(self.options, settings_path=CONFIG / 'single_source.json',
            database=cache_path, fixed_kind=0, options_factory=self.collect_options)
        self.url_panel = ComicSourcesPanel(self.options, settings_path=CONFIG / 'url_source.json',
            database=cache_path, fixed_kind=2, options_factory=self.collect_options)
        self.source_tabs.addTab(self.image_panel, 'Ảnh đơn')
        self.source_tabs.addTab(self.folder_page, 'Thư mục ảnh')
        self.source_tabs.addTab(self.url_panel, 'Link truyện online')
        self.source_tabs.setCurrentIndex(1)
        self.source_tabs.currentChanged.connect(self.update_mode)
        for panel in (self.image_panel, self.url_panel):
            panel.busyChanged.connect(self.set_running)
        self.url_panel.importRequested.connect(lambda: self.source_tabs.setCurrentIndex(1))
        outer.addWidget(self.source_tabs, 1)
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
            QScrollArea, QScrollArea > QWidget > QWidget { background: #111827; }
            QTabWidget::pane { border: 1px solid #374151; border-radius: 7px; padding: 8px; }
            QTabBar::tab { background: #1f2937; padding: 12px 24px; margin-right: 4px; }
            QTabBar::tab:selected { background: #2563eb; color: white; }
            QTableWidget { background: #172033; alternate-background-color: #1f2937; gridline-color: #374151; }
            QHeaderView::section { background: #273449; padding: 8px; border: 0; }
            QTableCornerButton::section { background: #273449; border: 0; }
            QScrollBar:vertical { background: #111827; width: 12px; }
            QScrollBar::handle:vertical { background: #475569; min-height: 24px; border-radius: 4px; }
            QProgressBar { background: #1f2937; border: 1px solid #374151; text-align: center; min-height: 22px; border-radius: 4px; }
            QProgressBar::chunk { background: #2563eb; }
        ''')

    def choose_folder(self, field: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, 'Chọn thư mục', field.text() or str(ROOT))
        if path:
            field.setText(path)

    def update_mode(self, *_args) -> None:
        mode = self.mode.currentText()
        folder = True  # Translation selection is shared by all three input tabs.
        for widget in (self.mode, self.mode_label, self.online_provider, self.online_label, self.allow_fallback):
            widget.setVisible(folder)
        self.online_provider.setEnabled(mode in ('Online', 'Online Free', 'Auto Fallback'))
        self.offline_provider.setEnabled(mode in ('Offline', 'Auto Fallback'))
        self.allow_fallback.setEnabled(folder and mode == 'Auto Fallback')
        self.privacy.setText('Offline: toàn bộ OCR và dịch chạy cục bộ; thiếu model sẽ báo lỗi, không tải hoặc gửi dữ liệu.' if mode == 'Offline'
                             else 'Online Free: văn bản OCR gửi tới provider đã chọn. MyMemory: 5.000 ký tự/ngày ẩn danh; '
                             'văn bản có thể được lưu và chia sẻ với đối tác MT. Ảnh ở trên máy; không gửi API key.' if mode in ('Online', 'Online Free')
                             else 'Auto Fallback: thử Offline trước. Chỉ gọi Online khi ô đồng ý được bật.')
        if not folder:
            self.privacy.setText('Dịch ảnh/chương bằng Offline với cấu hình OCR, font và xuất ảnh hiện tại. '
                                 'Phân tích URL chỉ đọc thông tin website; không gửi văn bản OCR ra mạng.')
        if mode == AGY_MODE:
            self.privacy.setText('AI Gemini — AGY: chỉ gửi các vùng OCR qua phiên AGY đã đăng nhập. '
                'Model: ' + self.options.agy_model + '. Không dùng API key riêng hoặc tự dùng thêm credits; '
                'file/shell/web/MCP bị chặn. Chỉ chạy khi bấm Bắt đầu; không tự đổi provider.')

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
            if self.persist_settings:
                save_options(options)
        except OSError as exc:
            QMessageBox.critical(self, 'Không lưu được cấu hình', str(exc))
            return
        self.failed = []
        self.provider_paused = False
        self.provider_pending = []
        self.provider_notice.hide()
        self.unfinished = []
        self.outputs = {}
        self.details = {}
        self.review_pages = []
        self.review_button.setEnabled(False)
        self.rows = {}
        self.table.setRowCount(0)
        self.progress.setValue(0)
        self.eta = None
        self.started = time.monotonic()
        self.pause_seconds = 0
        self.paused_at = None
        self.current.setText('Đang quét thư mục và kiểm tra model...')
        self.worker = ProcessingWorker(options, only, self, cache_path=self.cache_path, resume_id=self.resume_id)
        self.worker.event.connect(self.handle_event)
        self.worker.finished.connect(self.worker_finished)
        self.set_running(True)
        self.timer.start()
        self.worker.start()

    def clear_resume_intent(self, *_):
        # Choosing a new input/output starts a new work scope, retaining the old journal.
        self.resume_id = None
        self.provider_paused = False
        self.provider_pending = []

    def set_running(self, running: bool) -> None:
        self.config_panel.setEnabled(not running)
        self.folder_inputs.setEnabled(not running)
        self.source_tabs.tabBar().setEnabled(not running)
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
        if kind == 'resume_ready':
            self.resume_id = event['resume_id']
            return
        if kind == 'agy_batch':
            self.current.setText(f"AGY: {event['pages']} trang • {event['regions']} vùng • {event['characters']} ký tự")
            return
        if kind == 'provider_paused':
            self.provider_paused = True
            self.provider_pending = list(event['pending_paths'])
            self.provider_notice.show_error(event)
            self.current.setText(event['code'] + ' • Tạm dừng; không tự chuyển provider.')
            return
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
            if event['state'] == 'done':
                self.resume_id = None
            elif event.get('pending_paths'):
                self.provider_pending = event['pending_paths']
                self.provider_paused = True
            self.failed = event['errors']
            self.review_pages = event.get('review_pages', self.review_pages)
            self.review_button.setEnabled(bool(self.review_pages))
            if event['state'] == 'done':
                self.current.setText('Đã hoàn tất. Nhấp đúp hàng để xem trước kết quả và cảnh báo.')
                self.progress.setValue(1000)
            elif event['state'] == 'cancelled':
                self.current.setText('Đã hủy an toàn. Kết quả đã hoàn thành và checkpoint được giữ lại.')
            elif event['state'] == 'errors':
                self.current.setText('Batch kết thúc với ảnh lỗi. Xem chi tiết và dùng nút Thử lại sau khi khắc phục.')
            elif event['state'] == 'completed_with_warnings':
                self.current.setText(f"Đủ file xuất: {event['files_exported']}/{event['total']} • "
                    f"Dịch hoàn chỉnh: {event['translated_success']} • Ảnh gốc dự phòng: {event['fallback_original']} • "
                    f"Cần xem lại: {len(event['needs_retry'])}")
                self.progress.setValue(1000)
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
        if event.get('review'):
            self.review_pages.append(event['review'])
        terminal = event['stage'] in ('Hoàn thành', 'Bỏ qua', 'Lỗi', 'Ảnh gốc dự phòng')
        if terminal and path in self.unfinished:
            self.unfinished.remove(path)
        self.current.setText(f"Đang xử lý: {Path(path).name}  •  Công đoạn: {event['stage']}  •  {event['index']} / {event['total']} ảnh")
        if event.get('review'):
            review = event['review']
            self.current.setText(f"Trang {review['image_index']} • {review['image_filename']} • {review['stage']} • "
                f"{review.get('provider') or '—'} • {review['error_code']} • {review['output_status']}\n"
                f"{review.get('diagnostic_path') or review.get('diagnostic_error') or 'Không ghi được diagnostic'}")
            self.details[path] = event.get('detail', '') + '\n' + self.current.text()
            self.table.item(row, 4).setToolTip(self.details[path])
        self.stats.setText(f"Tổng: {event['total']} • Dịch mới: {event['completed']} • "
            f"Ảnh gốc dự phòng: {event.get('fallback_original', 0)} • Không output: {event.get('failed_no_output', event['failed'])} • "
            f"Bỏ qua: {event['skipped']}")
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
        if self.provider_paused and (not self.worker or not self.worker.isRunning()):
            self.start(list(self.provider_pending))
            return
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
        if self.provider_paused:
            self.continue_button.setEnabled(bool(self.provider_pending))

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

    def show_review(self) -> None:
        from ui.review_dialog import ReviewDialog
        ReviewDialog(self.review_pages, self).exec()

    def show_models(self) -> None:
        ModelManagerDialog(self).exec()

    def show_comic_sources(self) -> None:
        self.source_tabs.setCurrentIndex(2)

    def show_settings(self) -> None:
        self.collect_options()
        if SettingsDialog(self.options, self).exec():
            if self.persist_settings:
                save_options(self.options)
            self.update_mode()

    def restore_previous(self) -> None:
        if self.pending_options:
            if self.persist_settings:
                save_options(self.pending_options)
            # Reconstruct widget state in-place without starting a second window.
            p = self.pending_options
            self.options = Options.from_dict(p.to_dict())
            self.source.setText(p.source)
            self.output.setText(p.output)
            self.language.setCurrentIndex(max(0, self.language.findData(p.language)))
            self.mode.setCurrentText('Online Free' if p.mode == 'Online' else p.mode)
            self.online_provider.setCurrentText(p.online_provider)
            self.offline_provider.setCurrentText(p.offline_provider)
            self.recursive.setChecked(p.recursive)
            self.skip.setChecked(True)
            self.structure.setChecked(p.preserve_structure)
            self.allow_fallback.setChecked(p.allow_online_fallback)
            self.current.setText('Đã khôi phục cấu hình. Bấm Bắt đầu dịch; ảnh thành công có checksum hợp lệ sẽ được bỏ qua.')
            if self.pending_journal:
                self.resume_id = self.pending_journal['id']
                self.provider_pending = [p['path'] for p in self.pending_journal['pages'] if p['state'] != 'done']
                self.provider_paused = True
                self.continue_button.setEnabled(bool(self.provider_pending))
                self.current.setText('Đã khôi phục phần còn dở. Chọn phương thức rồi bấm Tiếp tục; chưa gửi dữ liệu online.')

    def closeEvent(self, event) -> None:
        for panel in (self.image_panel, self.url_panel):
            if panel.worker and panel.worker.isRunning():
                panel.cancel_job()
                event.ignore()
                return
        if self.worker and self.worker.isRunning():
            self.cancel()
            QMessageBox.information(self, 'Đang hủy công việc', 'Chờ công việc dừng an toàn rồi đóng cửa sổ.')
            event.ignore()
        else:
            try:
                if self.persist_settings:
                    save_options(self.collect_options())
            except OSError:
                pass
            event.accept()
