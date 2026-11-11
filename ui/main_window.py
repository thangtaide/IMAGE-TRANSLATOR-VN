from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QToolButton, QMenu, QSizePolicy)

from core.paths import CONFIG, ROOT
from core.storage import TranslationCache, load_options, save_options
from core.types import Options
from providers.agy import MODE as AGY_MODE, WHOLE_MODE
from providers.gemini_api import MODE as GEMINI_API_MODE, key_available
from ui.provider_notice import gemini_usage_text
from core.provider_preflight import check_configuration
from ui.models_dialog import ModelManagerDialog
from ui.preview import PreviewDialog
from ui.settings_dialog import SettingsDialog
from ui.workers import ProcessingWorker
from providers.agy_models import label as ai_model_label


def duration(seconds: float | None) -> str:
    if seconds is None:
        return 'Đang ước tính'
    seconds = max(0, int(seconds))
    return f'{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}'


class MainWindow(QMainWindow):
    def __init__(self, cache_path: Path | None = None, persist_settings: bool = True):
        super().__init__()
        from core.run_cache import RunRegistry
        from ui.theme import apply_dark_theme
        apply_dark_theme()
        self.run_registry = RunRegistry(cache_path)
        self.cache_path = self.run_registry.database
        self.active_cache_path = self.cache_path
        self.active_run_id = None
        self.persist_settings = persist_settings
        from ui.fonts import configure_ui_font
        self.font_report = configure_ui_font()
        self.setWindowTitle('IMAGE TRANSLATOR VN')
        self.resize(1180, 850)
        screen = self.screen().availableGeometry()
        self.resize(min(1100, screen.width()-40), min(760, screen.height()-60))
        self.ui_job_state = 'IDLE'
        self.options = load_options()
        restored_run=self.run_registry.active(self.options)
        if restored_run:
            self.active_cache_path=Path(restored_run['database']);self.active_run_id=restored_run['run_id']
        tools_menu = self.menuBar().addMenu('Công cụ')
        tools_menu.addAction('Whole Chapter Translation (nâng cao)…', self.show_whole_chapter)
        self.whole_dialog = None
        self.last_whole_output = None
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
        central.setMinimumWidth(540)
        scroll.setWidget(central)
        self.setCentralWidget(scroll)
        outer = QVBoxLayout(central)
        outer.setSpacing(8)
        outer.setContentsMargins(12,10,12,12)
        title = QLabel('IMAGE TRANSLATOR VN')
        title.setObjectName('title')
        outer.addWidget(title)
        subtitle = QLabel('OCR • Dịch sang tiếng Việt • Phục hồi nền • Xuất ảnh   |   CPU • Miễn phí')
        subtitle.setObjectName('subtitle')
        subtitle.hide()
        self.source_tabs = QTabWidget()
        self.folder_page = QWidget()
        folder_layout = QVBoxLayout(self.folder_page)
        folder_layout.setSpacing(10)
        self.folder_inputs = QGroupBox('1. Nguồn và đầu ra')
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
        self.folder_choices = QGroupBox('2. Tùy chọn')
        choices = QGridLayout(self.folder_choices)
        self.recursive = QCheckBox('Quét thư mục con')
        self.recursive.setChecked(self.options.recursive)
        self.keep_original = QCheckBox('Giữ nguyên ảnh gốc (bắt buộc)')
        self.keep_original.setChecked(True)
        self.keep_original.setEnabled(False)
        self.skip = QCheckBox('Bỏ qua ảnh đã xử lý thành công')
        self.skip.setChecked(self.options.skip_success)
        self.skip.setToolTip('Bật: bỏ qua output có checksum hợp lệ. Tắt: tạo bản render mới, vẫn có thể dùng OCR/bản dịch cache. Dùng Dịch lại từ đầu để OCR/dịch mới hoàn toàn.')
        self.structure = QCheckBox('Giữ cấu trúc thư mục nguồn')
        self.structure.setChecked(self.options.preserve_structure)
        for i,widget in enumerate([self.recursive, self.keep_original, self.skip, self.structure]):
            choices.addWidget(widget,i//2,i%2)
        header=QWidget();self.folder_header=QGridLayout(header);self.folder_header.setContentsMargins(0,0,0,0)
        self.folder_header.addWidget(self.folder_inputs,0,0);self.folder_header.addWidget(self.folder_choices,1,0)
        folder_layout.addWidget(header)
        self.config_panel = QGroupBox('OCR và dịch')
        config = QVBoxLayout(self.config_panel)
        row = QGridLayout()
        row.setColumnStretch(1,1)
        row.addWidget(QLabel('OCR'),0,0)
        self.language = QComboBox()
        for label, code in [('Trung giản thể', 'zh'), ('Trung phồn thể', 'zt'), ('Hàn', 'ko'), ('Anh', 'en'), ('Tự động (4 bộ model)', 'auto')]:
            self.language.addItem(label, code)
        self.language.setCurrentIndex(max(0, self.language.findData(self.options.language)))
        row.addWidget(self.language,0,1)
        self.mode_label = QLabel('Dịch')
        row.addWidget(self.mode_label,1,0)
        self.mode = QComboBox()
        for label, value in [('Offline','Offline'), ('Online Free','Online Free'),
                ('AI qua AGY — Batch', AGY_MODE), ('AI qua AGY — Toàn chương (1 lần)', WHOLE_MODE),
                (GEMINI_API_MODE,GEMINI_API_MODE), ('Auto Fallback','Auto Fallback')]:
            self.mode.addItem(label, value)
        self.mode.setCurrentIndex(max(0,self.mode.findData('Online Free' if self.options.mode=='Online' else self.options.mode)))
        self.mode.setItemData(0, 'Offline — Argos Translate / model cục bộ', Qt.ToolTipRole)
        self.mode.setItemData(1, 'Online Free — MyMemory Machine Translation API', Qt.ToolTipRole)
        self.mode.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.mode.setMinimumContentsLength(10)
        row.addWidget(self.mode,1,1,1,2)
        self.online_provider = QComboBox()
        self.online_provider.addItems(['MyMemory', 'LibreTranslate'])
        self.online_provider.setCurrentText(self.options.online_provider)
        self.offline_provider = QComboBox()
        self.offline_provider.addItems(['Argos', 'CTranslate2', 'M2M100'])
        self.offline_provider.setItemData(2, 'Dịch trực tiếp; cần cài riêng model M2M100 đã chuyển đổi. '
                                        'Chưa có model sẽ báo lỗi, không tự tải.', Qt.ToolTipRole)
        self.offline_provider.setCurrentText(self.options.offline_provider)
        self.online_label = QLabel('Online')
        for widget in (self.online_label, self.online_provider, self.offline_provider):
            widget.setParent(self.config_panel)
            widget.hide()  # Compatibility state; edited in Settings, never silently changed.
        self.provider_info = QLabel()
        self.provider_info.setWordWrap(True)
        self.provider_info.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        row.addWidget(self.provider_info,2,0,1,3)
        self.settings_button = QPushButton('Cài đặt')
        row.addWidget(self.settings_button,0,2)
        config.addLayout(row)
        self.allow_fallback = QCheckBox('Tôi đồng ý gửi văn bản OCR tới provider Online miễn phí nếu Offline lỗi (chỉ Auto Fallback)')
        self.allow_fallback.setChecked(self.options.allow_online_fallback)
        self.allow_fallback.setParent(self.config_panel)
        self.allow_fallback.hide()
        self.privacy = QLabel()
        self.privacy.setWordWrap(True)
        config.addWidget(self.privacy)
        self.mode.currentTextChanged.connect(self.update_mode)
        self.update_mode()
        outer.addWidget(self.config_panel)
        from ui.provider_notice import ProviderNotice
        self.provider_notice = ProviderNotice()
        self.provider_notice.settingsRequested.connect(self.show_api_settings)
        outer.addWidget(self.provider_notice)
        self.resume_previous = QPushButton('Khôi phục cấu hình công việc chưa hoàn thành')
        self.resume_previous.clicked.connect(self.restore_previous)
        folder_layout.addWidget(self.resume_previous)
        self.pending_cache_path=self.active_cache_path
        self.pending_run_id=self.active_run_id
        cache = TranslationCache(self.active_cache_path)
        self.pending_options = cache.pending_job()
        cache.close()
        from core.resume import ResumeStore
        self.pending_journal = ResumeStore(self.active_cache_path).latest('pipeline')
        if not self.pending_options and not self.pending_journal and self.active_cache_path!=self.cache_path:
            # A completed isolated run must not hide a legacy unfinished checkpoint.
            cache=TranslationCache(self.cache_path)
            self.pending_options=cache.pending_job();cache.close()
            self.pending_journal=ResumeStore(self.cache_path).latest('pipeline')
            self.pending_cache_path=self.cache_path;self.pending_run_id=None
        if self.pending_journal:
            self.pending_options = Options.from_dict(self.pending_journal['options'])
            self.resume_previous.setText('Khôi phục công việc còn dở (không tự chạy)')
        self.resume_previous.hide()
        controls = QGridLayout()
        controls.setSpacing(8)
        self.start_button = QPushButton('Bắt đầu dịch')
        self.start_button.setObjectName('primary')
        self.fresh_button = QPushButton('Dịch lại từ đầu')
        self.fresh_button.setObjectName('restart')
        self.fresh_button.setToolTip('Tạo lượt riêng: OCR và dịch mới, không đọc cache/checkpoint cũ; giữ nguyên dữ liệu cũ.')
        self.pause_button = QPushButton('Tạm dừng')
        self.continue_button = QPushButton('Tiếp tục')
        self.continue_button.setToolTip('Tiếp tục worker đang tạm dừng hoặc checkpoint của lượt hiện tại; giữ các ảnh đã hoàn tất.')
        self.cancel_button = QPushButton('Hủy')
        self.retry_button = QPushButton('Thử lại ảnh lỗi / chưa xong')
        self.open_button = QPushButton('Mở kết quả')
        self.review_button = QPushButton('Trang cần xem lại / log')
        self.review_button.setEnabled(False)
        self.review_button.clicked.connect(self.show_review)
        self.review_button.setParent(self.folder_page)
        self.review_button.hide()
        self.models_button = QPushButton('Quản lý mô hình AI')
        self.settings_button.setToolTip('Thiết lập Gemini API, provider nâng cao, font và xuất ảnh')
        for position, button in enumerate([self.start_button,self.fresh_button,self.pause_button,
                                          self.continue_button,self.cancel_button]):
            controls.addWidget(button,position//3,position%3)
        operations = QGroupBox('3. Thao tác chính')
        operations.setLayout(controls);folder_layout.addWidget(operations)
        tools = QGroupBox('4. Công cụ');tool_layout = QGridLayout(tools)
        self.cache_open_button = QPushButton('Mở thư mục cache')
        self.cache_manager_button = QPushButton('Quản lý cache')
        for i,button in enumerate([self.open_button,self.cache_open_button,self.cache_manager_button]):
            tool_layout.addWidget(button,0,i)
        self.folder_more = QToolButton()
        self.folder_more.setText('Thêm')
        self.folder_more.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.folder_more)
        actions = []
        for title_text, button in [('Thử lại ảnh lỗi', self.retry_button), ('Trang cần xem lại / log', self.review_button),
                                  ('Khôi phục công việc đã lưu', self.resume_previous), ('Mô hình cục bộ', self.models_button)]:
            button.setParent(self.folder_page)
            button.hide()
            action = menu.addAction(title_text)
            action.triggered.connect(button.click)
            actions.append((action, button))
        menu.aboutToShow.connect(lambda: [a.setEnabled(b.isEnabled() and
            (b != self.resume_previous or self.pending_options is not None)) for a,b in actions])
        self.folder_more.setMenu(menu)
        tool_layout.addWidget(self.folder_more,0,3)
        self.cache_scope_label = QLabel('Cache hợp lệ • Lượt thông thường')
        self.cache_scope_label.setObjectName('muted');self.cache_scope_label.setWordWrap(True)
        if self.active_run_id:self.cache_scope_label.setText('Run '+self.active_run_id[:12]+' • cache riêng đã lưu • chưa tự chạy')
        tool_layout.addWidget(self.cache_scope_label,1,0,1,4)
        folder_layout.addWidget(tools)
        common = QHBoxLayout()
        common.addStretch()
        self.models_button.setText('Mô hình cục bộ')
        self.start_button.clicked.connect(lambda: self.start())
        self.fresh_button.clicked.connect(self.start_fresh)
        self.cache_open_button.clicked.connect(self.open_cache)
        self.cache_manager_button.clicked.connect(self.manage_cache)
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
        progress_box = QGroupBox('5. Tiến trình');progress_layout = QVBoxLayout(progress_box)
        progress_layout.addWidget(self.progress)
        self.current = QLabel('Sẵn sàng. Cài model qua Quản lý mô hình AI trước khi dịch.')
        self.current.setWordWrap(True)
        progress_layout.addWidget(self.current)
        self.stats = QLabel('Tổng ảnh: 0 • Đã xử lý: 0 • Thành công: 0 • Lỗi: 0 • Bỏ qua: 0')
        self.clock_label = QLabel('Đã chạy: 00:00:00  •  Còn lại: Đang ước tính')
        self.stats.setWordWrap(True);self.clock_label.setWordWrap(True)
        progress_layout.addWidget(self.stats)
        progress_layout.addWidget(self.clock_label)
        folder_layout.addWidget(progress_box)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['Tên file', 'Ngôn ngữ', 'Trạng thái', 'Tiến trình', 'Kết quả / Chi tiết'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.inspect)
        self.table.setMinimumHeight(160)
        list_box = QGroupBox('6. Danh sách ảnh');list_layout = QVBoxLayout(list_box)
        list_layout.addWidget(self.table);folder_layout.addWidget(list_box,1)
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
        for panel in (self.image_panel, self.url_panel):
            panel.settingsRequested.connect(self.show_api_settings)
            panel.wholeRequested.connect(self.open_selected_whole)
        outer.addWidget(self.source_tabs, 1)
        self.set_running(False)
        QTimer.singleShot(0,self.adjust_folder_layout)


    def choose_folder(self, field: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, 'Chọn thư mục', field.text() or str(ROOT))
        if path:
            field.setText(path)

    def adjust_folder_layout(self):
        if not hasattr(self,'folder_header'):return
        self.folder_header.removeWidget(self.folder_choices)
        self.folder_header.addWidget(self.folder_choices,0,1) if self.width()>=980 else self.folder_header.addWidget(self.folder_choices,1,0)
        self.folder_header.setColumnStretch(0,3)
        self.folder_header.setColumnStretch(1,2 if self.width()>=980 else 0)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'folder_header'):QTimer.singleShot(0,self.adjust_folder_layout)

    def update_mode(self, *_args) -> None:
        mode = self.mode.currentData()
        folder = True  # Translation selection is shared by all three input tabs.
        for widget in (self.online_provider, self.online_label, self.offline_provider, self.allow_fallback):
            widget.hide()
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
            self.privacy.setText('AI qua AGY: chỉ gửi các vùng OCR qua phiên AGY đã đăng nhập. '
                'Model: ' + self.options.agy_model + '. Không dùng API key riêng hoặc tự dùng thêm credits; '
                'file/shell/web/MCP bị chặn. Batch tối đa 24 trang / 60 vùng / 3.000 ký tự nguồn; '
                'chờ 5–10 giây giữa các lần dịch. Chỉ chạy khi bấm Bắt đầu; không tự đổi provider.')

        if mode == GEMINI_API_MODE:
            self.privacy.setText('Gemini API • ' + self.options.gemini_api_model +
                (' • GEMINI_API_KEY: đã có (chưa kiểm tra mạng).' if key_available() else ' • Chưa có GEMINI_API_KEY.') +
                ' Chỉ gửi OCR/context; không ảnh/tools. Kiểm tra project Free tier trong Cài đặt; không tự đổi provider.')
        if mode == WHOLE_MODE:
            self.privacy.setText('Toàn bộ chữ của chương/ảnh đã chọn → một invocation AGY sau xác nhận riêng. '
                'Không phải batch 24 trang, không chờ 5–10 giây. Kết quả riêng; không tiếp công việc Batch hoặc tự fallback.')
        info = (self.options.gemini_api_model + (' • có key • ' if key_available() else ' • thiếu key • ') + check_configuration(self._mode_options()).code
                if mode == GEMINI_API_MODE else 'AI: '+ai_model_label(self.options.agy_model,self.options.agy_effort) if mode in (AGY_MODE, WHOLE_MODE) else
                self.online_provider.currentText() if mode in ('Online', 'Online Free') else self.offline_provider.currentText())
        self.provider_info.setText(info)
        if mode == AGY_MODE:
            self.provider_info.setText(info)
        if mode == WHOLE_MODE:
            self.provider_info.setText(info + ' • toàn chương • 1 invocation sau xác nhận')
        if hasattr(self, 'start_button'):
            self.start_button.setText('Chuẩn bị toàn chương' if mode == WHOLE_MODE else 'Bắt đầu dịch')
        for panel in (getattr(self,'image_panel',None),getattr(self,'url_panel',None)):
            if panel is not None:
                panel.translation_mode = mode
                panel.refresh_start()
        self.provider_info.setToolTip(self.privacy.text())
        self.privacy.hide()
        if hasattr(self, 'provider_notice'):
            self.provider_notice.setVisible(self.provider_notice.active and
                self.source_tabs.currentWidget() == self.folder_page)
        ready = check_configuration(self._mode_options()).ready
        for owner in (self, getattr(self, 'image_panel', None), getattr(self, 'url_panel', None)):
            notice = getattr(owner, 'provider_notice', None)
            if ready and notice and getattr(notice, 'last_code', None) in ('API_KEY_MISSING', 'FREE_TIER_UNCONFIRMED'):
                notice.hide()  # Retain history/pending; choosing settings never resumes.
                owner.ui_job_state = 'READY_UNVERIFIED' if mode == GEMINI_API_MODE else 'READY'

    def _mode_options(self):
        options = Options.from_dict(self.options.to_dict())
        options.mode = self.mode.currentData()
        return options

    def check_provider_setup(self, options):
        result = check_configuration(options)
        if not result.ready:
            self.ui_job_state = 'CONFIGURATION_BLOCKED'
            self.provider_notice.show_error(result.event())
            self.current.setText(result.code + ' • Cần hoàn tất Cài đặt; chưa khởi chạy lượt mới.')
        return result.ready

    def collect_options(self) -> Options:
        # Start/resume/close must not overwrite a model changed by another
        # window or an explicit local settings update while this window is open.
        # SettingsDialog saves explicit choices immediately; QA opts stay local.
        if self.persist_settings and (CONFIG / 'settings.json').is_file():
            saved = load_options()
            if (saved.agy_model,saved.agy_effort) != (self.options.agy_model,self.options.agy_effort):
                self.options.agy_model,self.options.agy_effort = saved.agy_model,saved.agy_effort
                self.update_mode()
        self.options.source = self.source.text().strip()
        self.options.output = self.output.text().strip()
        self.options.language = self.language.currentData()
        self.options.mode = self.mode.currentData()
        self.options.online_provider = self.online_provider.currentText()
        self.options.offline_provider = self.offline_provider.currentText()
        self.options.allow_online_fallback = self.allow_fallback.isChecked()
        self.options.recursive = self.recursive.isChecked()
        self.options.preserve_structure = self.structure.isChecked()
        self.options.skip_success = self.skip.isChecked()
        return Options.from_dict(self.options.to_dict())

    def current_cache_database(self):
        if self.mode.currentData()==WHOLE_MODE and self.last_whole_output:
            return self.last_whole_output.parent/'qa.sqlite3'
        return self.active_cache_path

    def open_cache(self):
        from ui.cache_manager import open_cache_directory
        return open_cache_directory(self.current_cache_database(),self)

    def manage_cache(self):
        from ui.cache_manager import CacheManagerDialog
        dialog=CacheManagerDialog(self.run_registry,self.current_cache_database(),self)
        dialog.restoreRequested.connect(self.restore_isolated_run)
        dialog.exec()

    def restore_isolated_run(self,run_id):
        try:
            from core.resume import ResumeStore
            record=self.run_registry.read(run_id)
            with self.run_registry.claim(run_id):
                self.pending_options=Options.from_dict(record['options'])
                self.pending_journal=ResumeStore(Path(record['database'])).latest('pipeline')
                self.pending_cache_path=Path(record['database']);self.pending_run_id=run_id
                self.run_registry.activate(run_id)
            self.restore_previous()
            self.active_cache_path=Path(record['database']);self.active_run_id=run_id
            self.cache_scope_label.setText('Run '+run_id[:12]+' • cache riêng • tiếp tục checkpoint của lượt này')
        except (OSError,ValueError,KeyError) as exc:
            QMessageBox.warning(self,'Không khôi phục được lượt',str(exc))

    def start_fresh(self):
        if self.worker and self.worker.isRunning():return
        if any(p.worker and p.worker.isRunning() for p in (self.image_panel,self.url_panel)):return
        from ui.fresh_run import FreshRunDialog
        from PySide6.QtWidgets import QDialog
        options=self.collect_options()
        if self.active_run_id:
            try:
                previous=self.run_registry.read(self.active_run_id)
                options.output=previous.get('output_base',str(Path(previous['output']).parent))
            except (OSError,ValueError,KeyError):pass
        if not options.source or not Path(options.source).is_dir():
            QMessageBox.warning(self,'Thiếu nguồn','Chọn thư mục ảnh nguồn tồn tại.');return
        if not options.output:
            QMessageBox.warning(self,'Thiếu đầu ra','Chọn thư mục xuất trước.');return
        dialog=FreshRunDialog(options,self.run_registry,self)
        if dialog.exec()!=QDialog.Accepted:return
        if options.mode==WHOLE_MODE:
            self.open_selected_whole(dict(kind='folder',path=options.source,recursive=options.recursive,
                options=options,force_new=True,fresh_plan=dialog.plan))
            return
        if not self.check_provider_setup(options):return
        try:
            record=self.run_registry.create(dialog.plan,options)
            self.output.setText(record['output'])  # Clears old resume intent before binding the new namespace.
            self.skip.setChecked(True)
            self.active_cache_path=Path(record['database']);self.active_run_id=record['run_id']
            self.cache_scope_label.setText('Run '+record['run_id'][:12]+' • cache bypass cũ • OCR/dịch mới')
            self.start()
        except (OSError,ValueError,KeyError) as exc:
            QMessageBox.warning(self,'Không tạo được lượt mới',str(exc))

    def start(self, only: list[str] | None = None, *, resume: bool = False) -> None:
        if self.worker and self.worker.isRunning():
            return
        preferred_options = self.collect_options()
        options = Options.from_dict(preferred_options.to_dict())
        if options.mode == WHOLE_MODE:
            if only is not None:
                QMessageBox.information(self, 'Retry thuộc công việc Batch',
                    'Chọn lại phương thức Batch để retry các trang lỗi cũ. Toàn chương dùng nút Chuẩn bị toàn chương và kết quả riêng.')
                return
            self.open_selected_whole(dict(kind='folder', path=options.source, recursive=options.recursive,
                                           options=options))
            return
        if resume and self.resume_id:
            from core.resume import ResumeStore
            from providers.agy_models import bind_run_model
            try:
                saved = ResumeStore(self.active_cache_path).read(self.resume_id)
                bind_run_model(options, saved['options'])
            except (OSError, ValueError, KeyError) as exc:
                QMessageBox.warning(self, 'Không tiếp tục được lượt cũ', str(exc))
                return
        if not self.check_provider_setup(options):
            return
        if not options.source or not options.output:
            QMessageBox.warning(self, 'Thiếu thư mục', 'Chọn thư mục nguồn và thư mục xuất trước.')
            return
        try:
            if self.persist_settings:
                # The pinned model of an old run is not the user's new-run preference.
                save_options(preferred_options)
        except OSError as exc:
            QMessageBox.critical(self, 'Không lưu được cấu hình', str(exc))
            return
        if not resume:
            # Start always creates a new journal; only Continue/Retry may bind
            # a previous checkpoint. skip_success controls cache, not run intent.
            if self.active_run_id and options.mode == AGY_MODE:
                try:
                    old = self.run_registry.read(self.active_run_id)['options']
                except (OSError, ValueError, KeyError) as exc:
                    QMessageBox.warning(self, 'Không đọc được lượt đã lưu', str(exc))
                    return
                if old.get('mode') == AGY_MODE and old.get('agy_model') != options.agy_model:
                    self.clear_resume_intent()  # Keep the old isolated run immutable.
            self.resume_id = None
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
        self.current.setText('Đang tiếp tục lượt cũ...' if resume else 'Đang quét thư mục và kiểm tra model...')
        if options.mode == AGY_MODE:
            self.provider_info.setText('AI: '+ai_model_label(options.agy_model, options.agy_effort)
                                      +(' · tiếp tục lượt cũ' if resume else ''))
        self.worker = ProcessingWorker(options, only, self, cache_path=self.active_cache_path, resume_id=self.resume_id,
            run_id=self.active_run_id,run_base=self.cache_path)
        self.worker.event.connect(self.handle_event)
        self.worker.finished.connect(self.worker_finished)
        self.set_running(True)
        self.timer.start()
        self.worker.start()

    def clear_resume_intent(self, *_):
        # Choosing a new input/output starts a new work scope, retaining the old journal.
        self.resume_id = None
        self.active_cache_path = self.cache_path
        self.active_run_id = None
        if hasattr(self,'cache_scope_label'):
            self.cache_scope_label.setText('Cache hợp lệ • Lượt thông thường')
        self.provider_paused = False
        self.provider_pending = []

    def set_running(self, running: bool) -> None:
        if running:
            self.ui_job_state = 'RUNNING'
        self.config_panel.setEnabled(not running)
        self.folder_inputs.setEnabled(not running)
        self.folder_choices.setEnabled(not running)
        self.source_tabs.tabBar().setEnabled(not running)
        self.start_button.setEnabled(not running)
        self.fresh_button.setEnabled(not running)
        self.cache_manager_button.setEnabled(not running)
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
        if kind == 'agy_batch_wait':
            self.current.setText(f"Đang chờ trước batch tiếp theo • còn {event['remaining_seconds']} giây")
            return
        if kind in ('agy_batch', 'gemini_api_batch'):
            self.current.setText(f"{'Gemini API' if kind == 'gemini_api_batch' else 'AGY'}: {event['pages']} trang • {event['regions']} vùng • {event['characters']} ký tự")
            return
        if kind=='agy_run_selection':
            self.provider_info.setText('AI: '+ai_model_label(event['model'],'' if event.get('effort')=='default' else event.get('effort',''))+' · lượt đang chạy')
            return
        if kind == 'gemini_api_usage':
            self.privacy.setText(gemini_usage_text(event))
            self.provider_info.setText(event['model'] + ' • token: ' + str(event.get('usage', {}).get('totalTokenCount', '?')))
            self.provider_info.setToolTip(self.privacy.text())
            return
        if kind == 'provider_paused':
            self.provider_paused = True
            self.ui_job_state = 'PAUSED_PROVIDER'
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
            self.ui_job_state = event['state'].upper()
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
        self.stats.setText(f"Tổng ảnh: {event['total']} • Đã xử lý: {event['completed']+event['failed']+event['skipped']} • "
            f"Thành công: {event['completed']} • Lỗi: {event['failed']} • Ảnh gốc dự phòng: {event.get('fallback_original', 0)} • "
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
            self.ui_job_state = 'PAUSED_BY_USER'

    def resume(self) -> None:
        if self.mode.currentData() == WHOLE_MODE:
            self.start()
            return
        if self.provider_paused and (not self.worker or not self.worker.isRunning()):
            self.start(list(self.provider_pending), resume=True)
            return
        if self.worker and not self.worker.isRunning() and self.resume_id and self.unfinished:
            self.start(list(self.unfinished), resume=True);return
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
            self.start(paths, resume=True)

    def worker_finished(self) -> None:
        self.timer.stop()
        self.update_clock()
        self.set_running(False)
        if self.provider_paused:
            self.continue_button.setEnabled(bool(self.provider_pending))
        elif self.resume_id and self.unfinished:
            self.continue_button.setEnabled(True)

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
        path = (self.last_whole_output if self.mode.currentData() == WHOLE_MODE and self.last_whole_output
                else Path(self.output.text()))
        if path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
        else:
            QMessageBox.information(self, 'Thư mục kết quả', 'Thư mục kết quả chưa tồn tại.')

    def show_review(self) -> None:
        from ui.review_dialog import ReviewDialog
        ReviewDialog(self.review_pages, self).exec()

    def show_whole_chapter(self) -> None:
        # The experimental dialog never reuses production output/database/settings.
        if self.worker and self.worker.isRunning():
            return
        for panel in (self.image_panel, self.url_panel):
            if getattr(panel, 'worker', None) is not None and panel.worker.isRunning():
                return
        if self.whole_dialog and self.whole_dialog.isVisible():
            self.whole_dialog.raise_(); return
        from ui.whole_chapter import WholeChapterDialog
        WholeChapterDialog(self.options, self).exec()

    def open_selected_whole(self, context):
        if self.worker and self.worker.isRunning(): return
        if any(p.worker and p.worker.isRunning() for p in (self.image_panel,self.url_panel)): return
        if self.whole_dialog and self.whole_dialog.isVisible():
            self.whole_dialog.raise_(); return
        if context['kind']=='folder' and (not str(context.get('path','')).strip() or not Path(context['path']).is_dir()):
            QMessageBox.warning(self,'Chọn nguồn ảnh','Chọn thư mục ảnh chương trước khi chuẩn bị toàn chương.')
            return
        from ui.whole_chapter import WholeChapterDialog
        options = context.get('options') or self.collect_options()
        dialog = WholeChapterDialog(options, self, bound_context=context, translator_kind='agy')
        self.whole_dialog = dialog
        dialog.exec()  # Modal: normal batch controls cannot start alongside this job.
        if dialog.workspace:
            self.last_whole_output = dialog.workspace/'rendered'
            if context['kind']=='chapter':
                panel=self.image_panel if context['comic'].site_id=='local' else self.url_panel
                panel.whole_output = self.last_whole_output
                panel.status.setText('Kết quả toàn chương riêng: '+str(self.last_whole_output)+'. Kết quả Batch cũ được giữ nguyên.')
            else:
                self.current.setText('Kết quả toàn chương riêng: '+str(self.last_whole_output)+'. Kết quả Batch cũ được giữ nguyên.')
        self.whole_dialog = None

    def show_models(self) -> None:
        ModelManagerDialog(self).exec()

    def show_comic_sources(self) -> None:
        self.source_tabs.setCurrentIndex(2)

    def show_api_settings(self):
        self.show_settings('gemini_api')

    def show_settings(self, focus_section=None) -> None:
        self.collect_options()
        if SettingsDialog(self.options, self, focus_section=focus_section).exec():
            self.online_provider.setCurrentText(self.options.online_provider)
            self.offline_provider.setCurrentText(self.options.offline_provider)
            self.allow_fallback.setChecked(self.options.allow_online_fallback)
            if self.persist_settings:
                save_options(self.options)
            self.update_mode()

    def restore_previous(self) -> None:
        if self.pending_options:
            target_cache=self.pending_cache_path;target_run=self.pending_run_id
            from core.resume import PROVIDER_FIELDS
            selected = self.collect_options()
            restored = Options.from_dict(self.pending_options.to_dict())
            for name in PROVIDER_FIELDS:
                setattr(restored, name, getattr(selected, name))
            if self.persist_settings:
                save_options(restored)
            # Reconstruct widget state in-place without starting a second window.
            p = restored
            self.options = Options.from_dict(p.to_dict())
            self.source.setText(p.source)
            self.output.setText(p.output)
            self.language.setCurrentIndex(max(0, self.language.findData(p.language)))
            self.mode.setCurrentIndex(max(0,self.mode.findData('Online Free' if p.mode=='Online' else p.mode)))
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
                if self.pending_journal.get('state') == 'paused_provider':
                    self.provider_notice.show_saved_error()
            self.active_cache_path=target_cache;self.active_run_id=target_run
            self.cache_scope_label.setText('Run '+target_run[:12]+' • cache riêng đã khôi phục' if target_run else 'Cache chung • checkpoint đã khôi phục')

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
