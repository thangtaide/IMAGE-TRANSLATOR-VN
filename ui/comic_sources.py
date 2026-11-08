"""Source selection and chapter UI, kept separate from the existing folder UI."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QThread, Qt, QUrl, Signal, QSignalBlocker
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QProgressBar, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QGroupBox, QToolButton, QMenu, QSizePolicy)

from core.paths import CACHE, CONFIG, ROOT
from core.pipeline import JobControl
from core.types import CancelledError, Options
from sources.cache import atomic_json
from sources.collection import discover_local
from sources.contracts import AccessStatus, SourceError, StructureChanged, WebsiteAdapter
from sources.registry import resolve_adapter
from sources.service import LocalComicJob
from sources.states import AnalysisState, DownloadState, ProcessingState, chapter_access, selectable


class ComicSourceWorker(QThread):
    event = Signal(dict)

    def __init__(self, action: str, request: dict, parent=None):
        super().__init__(parent)
        self.action, self.request = action, request
        self.control = JobControl()

    def run(self) -> None:
        phase = self.action
        active_chapter = None
        try:
            if self.action == 'local':
                comic, chapters = discover_local(Path(self.request['path']), self.control)
                self.event.emit({'type': 'collection', 'comic': comic, 'chapters': chapters})
            elif self.action == 'url':
                phase = 'url'
                adapter = resolve_adapter(self.request['url'])
                comic = self.request.get('comic')
                if comic is None:
                    phase = 'metadata'
                    comic = adapter.get_comic_info(self.request['url'], self.control)
                    self.event.emit({'type': 'metadata', 'comic': comic, 'chapters': [], 'adapter': adapter})
                phase = 'chapters'
                self.event.emit({'type': 'analysis_phase', 'phase': phase})
                refresh = getattr(adapter, 'refresh_chapters', adapter.get_chapters)
                chapters = (refresh if self.request.get('comic') else adapter.get_chapters)(comic, self.control)
                if not chapters:
                    raise StructureChanged('Danh sách chương rỗng; metadata đã lấy được vẫn được giữ.')
                self.event.emit({'type': 'collection', 'comic': comic, 'chapters': chapters, 'adapter': adapter,
                                 'warnings': getattr(chapters, 'warnings', ()), 'complete': getattr(chapters, 'complete', None)})
                if comic.source_kind == 'chapter':
                    phase = 'images'
                    active_chapter = chapters[0].chapter_id
                    images = adapter.get_chapter_images(chapters[0], self.control)
                    self.event.emit({'type': 'images_ready', 'chapter_id': active_chapter, 'images': images,
                                     'warnings': getattr(images, 'warnings', ()), 'complete': getattr(images, 'complete', None)})
            elif self.action == 'images':
                phase = 'images'
                chapters = self.request['chapters']
                if not 1 <= len(chapters) <= 10:
                    raise StructureChanged('Chọn từ 1 đến 10 chương để phân tích ảnh trong một lượt; không tải ảnh.')
                for index, chapter in enumerate(chapters):
                    active_chapter = chapter.chapter_id
                    self.control.checkpoint()
                    if index:
                        # Public page analysis is sequential and limited; never parallel image fetching.
                        until = time.monotonic() + 1
                        while time.monotonic() < until:
                            self.control.checkpoint()
                            time.sleep(.1)
                    images = self.request['adapter'].get_chapter_images(chapter, self.control)
                    self.event.emit({'type': 'images_ready', 'chapter_id': active_chapter, 'images': images,
                                     'warnings': getattr(images, 'warnings', ()), 'complete': getattr(images, 'complete', None)})
            elif self.action == 'process':
                from core.runtime import prepare_inference_runtime
                self.control.checkpoint()
                prepare_inference_runtime()
                self.control.checkpoint()
                LocalComicJob(**self.request, control=self.control, emit=self.event.emit).run()
            elif self.action == 'restore':
                from sources.resume import restore_source_request
                from core.runtime import prepare_inference_runtime
                self.control.checkpoint()
                request = restore_source_request(self.request['record'], self.request['database'],
                                                 self.request['options'])
                self.event.emit(dict(type='collection', comic=request['comic'], chapters=request['chapters']))
                prepare_inference_runtime()
                LocalComicJob(**request, control=self.control, emit=self.event.emit).run()
            else:
                raise SourceError('Tác vụ nguồn ảnh không được hỗ trợ.')
        except CancelledError:
            if self.action in ('process', 'restore'):
                self.event.emit({'type': 'job_finished', 'state': 'cancelled', 'chapters_completed': 0,
                                 'chapters_failed': 0, 'images_exported': 0, 'images_failed': 0,
                                 'errors': [], 'outputs': []})
            else:
                self.event.emit({'type': 'source_error', 'category': 'cancelled', 'detail': 'Đã hủy an toàn.'})
        except Exception as exc:
            logging.getLogger(__name__).exception('Comic source action failed: %s', self.action)
            self.event.emit({'type': 'source_error', 'category': getattr(exc, 'category', 'source'),
                             'phase': phase, 'chapter_id': active_chapter, 'detail': str(exc) or type(exc).__name__})
            if self.action in ('process', 'restore'):
                self.event.emit({'type': 'job_finished', 'state': 'error', 'chapters_completed': 0,
                                 'chapters_failed': 0, 'images_exported': 0, 'images_failed': 0,
                                 'errors': [{'chapter_id': None, 'detail': str(exc)}], 'outputs': []})


class ComicSourcesPanel(QWidget):
    busyChanged = Signal(bool)
    importRequested = Signal()
    settingsRequested = Signal()

    def __init__(self, options: Options, parent=None, settings_path: Path | None = None,
                 database: Path | None = None, fixed_kind: int | None = None, options_factory=None):
        super().__init__(parent)
        self.setWindowTitle('Nguồn ảnh và truyện URL')
        self.resize(1040, 720)
        self.options = Options.from_dict(options.to_dict())
        self.settings_path = settings_path or CONFIG / 'online_comics.json'
        self.database = database
        self.options_factory = options_factory
        self.adapter = None
        self.source_resume_id = None
        self.analysis_state = AnalysisState.IDLE
        self.metadata_state = AnalysisState.IDLE
        self.chapter_state = AnalysisState.IDLE
        self.processing_state = ProcessingState.IDLE
        self.download_decisions = {}
        self.image_states = {}
        self.discovered_images = {}
        self.last_error_category = None
        self.worker = None
        self.comic = None
        self.chapters = []
        self.failed_ids = set()
        self.last_result = None
        self.provider_paused = False
        self.paused_chapter = None
        self.review_pages = []
        self.source_resume_id = None
        self.busy = False
        self.position = 1
        self.total_chapters = 1
        self.loaded_input = None
        try:
            saved = json.loads(self.settings_path.read_text(encoding='utf-8'))
            if not isinstance(saved, dict):
                saved = {}
        except (OSError, ValueError):
            saved = {}
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        self.ui_job_state = 'IDLE'
        self.inputs = QWidget()
        inputs = QVBoxLayout(self.inputs)
        inputs.setContentsMargins(0, 0, 0, 0)
        self.kind = QComboBox()
        self.kind.addItems(['Ảnh đơn', 'Thư mục ảnh / các chương', 'Link truyện online'])
        self.kind.setCurrentIndex(1)
        inputs.addWidget(self.kind)
        row = QHBoxLayout()
        self.location = QLineEdit(saved.get('local_path', ''))
        self.location.setPlaceholderText('Chọn ảnh hoặc thư mục chứa các chương')
        self.browse = QPushButton('Chọn nguồn')
        self.analyze = QPushButton('Đọc danh sách ảnh/chương')
        row.addWidget(self.location, 1)
        row.addWidget(self.browse)
        row.addWidget(self.analyze)
        inputs.addLayout(row)
        self.advanced = QToolButton()
        self.advanced.setText('Tùy chọn nguồn / cache')
        self.advanced.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.advanced.setArrowType(Qt.RightArrow)
        self.advanced.setCheckable(True)
        self.advanced.setChecked(False)
        self.advanced_body = QWidget()
        advanced = QVBoxLayout(self.advanced_body)
        advanced.setContentsMargins(0, 0, 0, 0)
        self.advanced_body.hide()
        self.advanced.toggled.connect(self.advanced_body.setVisible)
        self.advanced.toggled.connect(lambda opened: self.advanced.setArrowType(Qt.DownArrow if opened else Qt.RightArrow))
        self.import_local = QPushButton('Nhập chương từ ảnh đã lưu hợp lệ')
        advanced.addWidget(self.import_local)
        self.policy = QLabel('Ảnh gốc luôn được giữ nguyên. Phương thức dịch lấy từ cửa sổ chính; không tự tải model.')
        self.policy.setWordWrap(True)
        advanced.addWidget(self.policy)
        self.title = QLabel('Chưa chọn truyện. Chương không được tự động chọn.')
        self.title.setWordWrap(True)
        inputs.addWidget(self.title)
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel('Thư mục xuất'))
        self.output = QLineEdit(saved.get('output', options.output or str(ROOT / 'output' / 'translated_comics')))
        self.output_browse = QPushButton('Chọn thư mục kết quả')
        output_row.addWidget(self.output, 1)
        output_row.addWidget(self.output_browse)
        self.output_group = QToolButton()
        self.output_group.setText('Thư mục xuất')
        self.output_group.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.output_group.setArrowType(Qt.RightArrow)
        self.output_group.setCheckable(True)
        self.output_group.setChecked(False)
        self.output_body = QWidget()
        self.output_body.setLayout(output_row)
        self.output_group.toggled.connect(self.output_body.setVisible)
        self.output_group.toggled.connect(lambda opened: self.output_group.setArrowType(Qt.DownArrow if opened else Qt.RightArrow))
        self.output_body.hide()
        inputs.addWidget(self.output_group)
        inputs.addWidget(self.output_body)
        self.keep = QCheckBox('Giữ bản sao ảnh nguồn trong cache sau khi xuất thành công')
        self.keep.setChecked(saved.get('keep_cached', True))
        advanced.addWidget(self.keep)
        self.configuration = QLabel(f'OCR: {options.language} • Offline: {options.offline_provider} • '
                                    'Dùng cấu hình font/xuất ảnh của cửa sổ chính.')
        advanced.addWidget(self.configuration)
        inputs.addWidget(self.advanced)
        inputs.addWidget(self.advanced_body)
        from ui.provider_notice import ProviderNotice
        self.provider_notice = ProviderNotice()
        self.provider_notice.settingsRequested.connect(self.settingsRequested)
        layout.addWidget(self.provider_notice)
        selection = QHBoxLayout()
        self.select_all = QPushButton('Chọn tất cả')
        self.select_none = QPushButton('Bỏ chọn tất cả')
        self.retry_analysis = QPushButton('Thử lại danh sách chương')
        self.analyze_images = QPushButton('Phân tích chương đã chọn')
        selection.addWidget(self.select_all)
        selection.addWidget(self.select_none)
        advanced.addWidget(self.retry_analysis)
        selection.addWidget(self.analyze_images)
        self.technical_columns = QCheckBox('Hiện cột truy cập / số ảnh / điều kiện tải')
        advanced.addWidget(self.technical_columns)
        self.technical_columns.toggled.connect(self.set_technical_columns)
        self.chapter_detail = QLabel('Chọn một dòng để xem quyền truy cập, số ảnh và điều kiện tải.')
        self.chapter_detail.setWordWrap(True)
        self.chapter_detail.setTextFormat(Qt.PlainText)
        advanced.addWidget(self.chapter_detail)
        inputs.addLayout(selection)
        layout.addWidget(self.inputs)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(['Chọn', 'Thứ tự', 'Tên chương', 'Truy cập chương', 'Ảnh xác minh', 'Trạng thái / lỗi', 'Điều kiện tải'])
        self.table.setMinimumHeight(160)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.currentCellChanged.connect(self.show_chapter_detail)
        self.table.itemChanged.connect(self.update_chapter_tooltip)
        layout.addWidget(self.table, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        layout.addWidget(self.progress)
        self.status = QLabel('Sẵn sàng.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.download_status = QLabel()
        self.download_status.setWordWrap(True)
        layout.addWidget(self.download_status)
        controls = QGridLayout()
        controls.setSpacing(8)
        self.start = QPushButton('Dịch ảnh đã có')
        self.download = QPushButton('Tải và dịch')
        self.download.setEnabled(False)
        self.download.setToolTip('Kuaikan: quyền tải tự động chưa xác minh; không có downloader được kích hoạt.')
        self.pause = QPushButton('Tạm dừng')
        self.resume = QPushButton('Tiếp tục từ cache')
        self.cancel = QPushButton('Hủy')
        self.retry = QPushButton('Thử lại chương lỗi / chưa xong')
        self.open_output = QPushButton('Mở kết quả')
        self.restore_cached = QPushButton('Tiếp tục công việc đã lưu (ưu tiên cache)')
        self.restore_cached.setToolTip('Chỉ chạy khi bấm. Giữ ảnh cache hợp lệ; chương chưa tải sẽ được xác minh lại quyền truy cập và policy trước khi tải.')
        self.restore_cached.clicked.connect(self.restore_cached_job)
        self.restore_cached.setParent(self)
        self.restore_cached.hide()
        from core.resume import ResumeStore
        self.resume_store = ResumeStore(database or CACHE / 'online_comics/pipeline.sqlite3')
        self.restorable = self.resume_store.latest('source')
        self.restore_cached.hide()
        self.review_button = QPushButton('Trang cần xem lại / log')
        self.review_button.setEnabled(False)
        self.review_button.clicked.connect(self.show_review)
        self.review_button.setParent(self)
        self.review_button.hide()
        controls.addWidget(self.start, 0, 0)
        controls.addWidget(self.download, 0, 0)
        controls.addWidget(self.open_output, 0, 4)
        for column, button in enumerate((self.pause, self.resume, self.cancel), 1):
            controls.addWidget(button, 0, column)
        self.retry.setParent(self)
        self.retry.hide()
        self.more = QToolButton()
        self.more.setText('Thêm')
        self.more.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.more)
        self.extra_actions = []
        for label, button in [('Khôi phục công việc đã lưu', self.restore_cached),
                              ('Thử lại chương lỗi', self.retry), ('Trang cần xem lại / log', self.review_button)]:
            action = menu.addAction(label)
            action.triggered.connect(button.click)
            self.extra_actions.append((action, button))
        menu.aboutToShow.connect(lambda: [a.setEnabled(b.isEnabled() and
            (b != self.restore_cached or bool(self.restorable))) for a, b in self.extra_actions])
        self.more.setMenu(menu)
        controls.addWidget(self.more, 0, 5)
        layout.addLayout(controls)
        # URL/title/selection → table → compact notice → translate/progress.
        layout.removeWidget(self.provider_notice)
        layout.insertWidget(layout.indexOf(self.table)+1, self.provider_notice)
        layout.removeItem(controls)
        layout.insertLayout(layout.indexOf(self.table)+2, controls)
        layout.removeWidget(self.progress)
        layout.insertWidget(layout.indexOf(self.table)+3, self.progress)
        layout.removeWidget(self.status)
        layout.insertWidget(layout.indexOf(self.table)+4, self.status)
        layout.removeWidget(self.download_status)
        advanced.addWidget(self.download_status)
        self.source_options = QWidget()
        options_layout = QVBoxLayout(self.source_options)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_row = QHBoxLayout()
        for widget in (self.output_group, self.output_body, self.advanced, self.advanced_body):
            inputs.removeWidget(widget)
        options_row.addWidget(self.output_group)
        options_row.addWidget(self.advanced)
        options_row.addStretch()
        options_layout.addLayout(options_row)
        options_layout.addWidget(self.output_body)
        options_layout.addWidget(self.advanced_body)
        layout.addWidget(self.source_options)
        self.kind.currentIndexChanged.connect(self.source_changed)
        self.location.textChanged.connect(self.invalidate_collection)
        self.browse.clicked.connect(self.choose_source)
        self.analyze.clicked.connect(self.analyze_source)
        self.location.returnPressed.connect(lambda: self.analyze_source() if not self.busy else None)
        self.retry_analysis.clicked.connect(self.retry_chapters)
        self.analyze_images.clicked.connect(self.discover_selected_images)
        self.import_local.clicked.connect(self.choose_local)
        self.output_browse.clicked.connect(self.choose_output)
        self.select_all.clicked.connect(lambda: self.check_all(True))
        self.select_none.clicked.connect(lambda: self.check_all(False))
        self.table.itemChanged.connect(self.refresh_start)
        self.start.clicked.connect(lambda: self.begin())
        self.download.clicked.connect(lambda: self.begin())
        self.retry.clicked.connect(self.retry_failed)
        self.pause.clicked.connect(self.pause_job)
        self.resume.clicked.connect(self.resume_job)
        self.cancel.clicked.connect(self.cancel_job)
        self.open_output.clicked.connect(self.show_output)
        if fixed_kind is not None:
            self.kind.setCurrentIndex(fixed_kind)
            self.kind.hide()
            self.configuration.hide()
        self.source_changed(clear=False)
        self.set_busy(False)

    def invalidate_collection(self, *_):
        self.source_resume_id = None
        self.loaded_input = None
        self.comic = None
        self.chapters = []
        self.failed_ids.clear()
        self.adapter = None
        self.analysis_state = AnalysisState.IDLE
        self.metadata_state = AnalysisState.IDLE
        self.chapter_state = AnalysisState.IDLE
        self.download_decisions.clear()
        self.image_states.clear()
        self.discovered_images.clear()
        self.processing_state = ProcessingState.IDLE
        self.table.setRowCount(0)
        self.title.setText('Nguồn đã đổi. Hãy phân tích lại; chưa có chương nào được chọn.')
        self.progress.setValue(0)
        self.status.setText('Chưa phân tích nguồn mới.')
        self.refresh_start()

    def source_changed(self, *_, clear=True):
        online = self.kind.currentIndex() == 2
        if hasattr(self, 'resume_store'):
            self.restorable = self.resume_store.latest('source', lambda data:
                (data.get('comic', {}).get('site_id') != 'local') == online)
            self.restore_cached.hide()
            if self.restorable and self.restorable.get('state') == 'paused_provider':
                self.provider_notice.show_saved_error()
        single = self.kind.currentIndex() == 0
        if clear:
            self.invalidate_collection()
            self.location.clear()
        self.location.setPlaceholderText('URL topic hoặc https://www.kuaikanmanhua.com/webs/comic-next/<id>' if online else 'Đường dẫn ảnh / thư mục')
        self.browse.setVisible(not online)
        self.analyze.setText('Phân tích link' if online else 'Đọc ảnh' if single else 'Đọc danh sách ảnh/chương')
        self.browse.setText('Chọn ảnh' if single else 'Chọn thư mục')
        self.policy.setText('Phân tích link để xem thông tin và danh sách chương. '
                            'Điều kiện đọc và tải được kiểm tra riêng cho từng chương.'
                            if online else 'Ảnh gốc luôn được giữ nguyên. Phương thức dịch lấy từ cửa sổ chính; không tự tải model.')
        self.import_local.setVisible(online)
        self.retry_analysis.setVisible(online)
        self.analyze_images.setVisible(online)
        self.download.setVisible(online)
        self.download_status.setVisible(online)
        self.start.setVisible(not online)
        self.title.setVisible(self.kind.currentIndex() != 0)
        self.set_technical_columns(self.technical_columns.isChecked())
        self.select_all.setText('Chọn tất cả')
        self.table.horizontalHeaderItem(2).setText('Ảnh đã chọn' if single else 'Tên chương')
        self.retry.setText('Thử lại ảnh lỗi / chưa xong' if single else 'Thử lại chương lỗi / chưa xong')
        self.start.setText('Bắt đầu dịch')
        self.refresh_start()

    def choose_source(self):
        if self.kind.currentIndex() == 0:
            path, _ = QFileDialog.getOpenFileName(self, 'Chọn ảnh đã lưu hợp lệ', self.location.text(),
                                                'Ảnh (*.png *.jpg *.jpeg *.webp *.bmp)')
        else:
            path = QFileDialog.getExistingDirectory(self, 'Chọn thư mục ảnh hoặc các thư mục chương', self.location.text())
        if path:
            self.location.setText(path)
            if self.kind.currentIndex() == 0:
                self.analyze_source()

    def choose_local(self):
        if self.kind.isHidden():
            self.importRequested.emit()
            return
        self.kind.setCurrentIndex(1)
        self.choose_source()

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, 'Chọn nơi lưu kết quả', self.output.text())
        if path:
            self.output.setText(path)

    def launch(self, action, request):
        self.worker = ComicSourceWorker(action, request, self)
        self.worker.event.connect(self.handle_event)
        self.worker.finished.connect(lambda: self.set_busy(False))
        self.set_busy(True)
        self.worker.start()

    def analyze_source(self):
        self.invalidate_collection()
        location = self.location.text().strip()
        if not location:
            self.status.setText('Hãy nhập URL hoặc chọn nguồn ảnh.')
            return
        self.status.setText('Đang đọc nguồn trong worker...')
        if self.kind.currentIndex() == 2:
            self.analysis_state = AnalysisState.ANALYZING
            self.launch('url', {'url': location})
        else:
            if self.kind.currentIndex() == 0 and not Path(location).is_file():
                self.status.setText('Chế độ Ảnh đơn cần chọn một file ảnh, không phải thư mục.')
                return
            self.launch('local', {'path': location})

    def retry_chapters(self):
        if not self.busy and self.comic and self.kind.currentIndex() == 2:
            self.analysis_state = AnalysisState.ANALYZING
            self.status.setText('Đang thử lại danh sách chương; giữ metadata đã lấy được...')
            self.launch('url', {'url': self.comic.source_url, 'comic': self.comic})

    def discover_selected_images(self):
        chapters = self.selected()
        if not self.busy and self.adapter and chapters and self.analyze_images.isEnabled():
            self.status.setText('Đang phân tích URL ảnh trong HTML chương; chưa tải file ảnh...')
            self.launch('images', {'adapter': self.adapter, 'chapters': chapters})

    def selected(self):
        return [chapter for row, chapter in enumerate(self.chapters)
                if self.table.item(row, 0) is not None and self.table.item(row, 0).checkState() == Qt.Checked
                and selectable(chapter)]

    def check_all(self, checked):
        for row, chapter in enumerate(self.chapters):
            if selectable(chapter):
                self.table.item(row, 0).setCheckState(Qt.Checked if checked else Qt.Unchecked)

    def refresh_start(self, *_):
        selected = self.selected()
        online = self.kind.currentIndex() == 2
        self.start.setEnabled(not self.busy and not online and bool(selected))
        decisions = [self.download_decisions.get(c.chapter_id) for c in selected]
        capability = self.adapter and type(self.adapter).download_chapter is not WebsiteAdapter.download_chapter
        ready = (online and self.chapter_state == AnalysisState.CHAPTER_LIST_READY and bool(selected)
                 and capability and all(d and d.allowed for d in decisions))
        self.download.setEnabled(not self.busy and bool(ready))
        if not self.busy and self.processing_state in (ProcessingState.IDLE, ProcessingState.READY):
            self.processing_state = ProcessingState.READY if ready or (not online and selected) else ProcessingState.IDLE
        reason = ('Phân tích link để lấy danh sách chương.' if not self.chapters else
                  'Chọn chương cần đọc; chưa tải ảnh.' if not selected else
                  '\n'.join(dict.fromkeys(d.reason for d in decisions if d)) or 'Ảnh cục bộ đã sẵn sàng.')
        if ready:
            reason = '\n'.join(dict.fromkeys(d.reason for d in decisions if d))
        elif decisions and all(d and d.allowed for d in decisions) and not capability:
            reason = 'Quyết định ứng dụng cho phép nhưng adapter chưa có downloader tương thích.'
        self.download_status.setText(reason)
        self.download_status.setToolTip(reason)
        self.download.setToolTip(reason)
        self.retry_analysis.setEnabled(not self.busy and bool(self.comic))
        self.analyze_images.setEnabled(not self.busy and online and 1 <= len(selected) <= 10 and self.adapter is not None)
        self.analyze_images.setToolTip('Đợi tác vụ hiện tại kết thúc.' if self.busy else
            'Chọn ít nhất một chương có thể truy cập.' if not selected else
            'Mỗi lượt chỉ phân tích 1–10 chương; bỏ bớt lựa chọn để tiếp tục.' if len(selected) > 10 else
            'Phân tích link trước để xác định website.' if self.adapter is None else
            'Chỉ lấy metadata/danh sách URL ảnh; không tải ảnh hoặc dịch. Giữ lựa chọn và thứ tự.')
        self.retry.setEnabled(not self.busy and bool(self.failed_ids))
        self.restore_cached.setEnabled(not self.busy)

    def set_technical_columns(self, checked):
        if not hasattr(self, 'table'):
            return
        for column in (3, 4, 6):
            self.table.setColumnHidden(column, not checked)
        self.table.setColumnHidden(1, self.kind.currentIndex() == 0)

    def show_chapter_detail(self, row, *_):
        if row < 0:
            return
        values = [(self.table.horizontalHeaderItem(c).text(), self.table.item(row, c)) for c in (2, 3, 4, 6)]
        text = '\n'.join(label + ': ' + item.text() for label, item in values if item)
        self.chapter_detail.setText(text)

    def update_chapter_tooltip(self, item):
        row = item.row()
        title = self.table.item(row, 2)
        if title is None:
            return
        text = '\n'.join(self.table.item(row, c).text() for c in (2, 3, 4, 6) if self.table.item(row, c))
        with QSignalBlocker(self.table):
            title.setToolTip(text)
        if self.table.currentRow() == row:
            self.show_chapter_detail(row)

    def check_provider_setup(self):
        from core.provider_preflight import check_configuration
        self.options = self.options_factory() if self.options_factory else self.options
        result = check_configuration(self.options)
        if not result.ready:
            self.ui_job_state = 'CONFIGURATION_BLOCKED'
            self.provider_notice.show_error(result.event())
            self.status.setText(result.code + ' • Mở Cài đặt để hoàn tất thiết lập; chưa khởi chạy lượt mới.')
        return result.ready

    def set_busy(self, busy):
        self.busy = busy
        self.inputs.setEnabled(not busy)
        self.source_options.setEnabled(not busy)
        self.table.setEnabled(not busy)
        self.pause.setEnabled(busy)
        self.resume.setEnabled(False)
        self.cancel.setEnabled(busy)
        self.refresh_start()
        self.busyChanged.emit(busy)
        if not busy and self.provider_paused:
            self.resume.setEnabled(bool(self.source_resume_id and self.paused_chapter))

    def begin(self, chapters=None, retry_only=False):
        chapters = chapters or self.selected()
        if not chapters or not self.comic or self.busy:
            return
        online = self.kind.currentIndex() == 2
        self.refresh_start()
        if online and not retry_only and not self.download.isEnabled():
            self.status.setText(self.download_status.text())
            return
        if self.options_factory:
            self.options = self.options_factory()
        if not self.check_provider_setup():
            return
        self.provider_paused = False
        self.ui_job_state = 'RUNNING'
        self.paused_chapter = None
        self.provider_notice.hide()
        self.failed_ids = {chapter.chapter_id for chapter in chapters}
        self.last_result = None
        self.review_pages = []
        self.review_button.setEnabled(False)
        self.processing_state = ProcessingState.TRANSLATING
        self.progress.setValue(0)
        self.status.setText('Đang kiểm tra nguồn/cache và phương thức dịch đã chọn...')
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_json(self.settings_path, {'local_path': '' if online else self.location.text(), 'output': self.output.text(),
                                             'keep_cached': self.keep.isChecked()})
        except OSError as exc:
            self.status.setText('Không lưu được cấu hình nguồn ảnh: ' + str(exc))
            return
        self.launch('process', {'comic': self.comic, 'chapters': chapters, 'output': Path(self.output.text()),
                                'options': self.options, 'keep_cached': self.keep.isChecked(), 'database': self.database,
                                'adapter': self.adapter if online else None, 'retry_only': retry_only})

    def retry_failed(self):
        self.begin([chapter for chapter in self.chapters if chapter.chapter_id in self.failed_ids], retry_only=True)

    def update_comic_label(self):
        if not self.comic:
            return
        count = self.comic.chapter_count
        image_label = 'ảnh cục bộ' if self.comic.site_id == 'local' else 'URL ảnh đã phát hiện'
        self.title.setToolTip(f'{self.comic.title or "Truyện gốc chưa xác minh"} • Nguồn: {self.comic.site_id} • '
                           f'Tác giả: {self.comic.author or "chưa xác định"} • '
                           f'Số nội dung công bố: {count if count is not None else "chưa xác định"} • '
                           f'Đã lấy: {len(self.chapters)} chương, {sum(c.image_count or 0 for c in self.chapters)} {image_label}')
        self.title.setText(f'{self.comic.title or "Truyện gốc chưa xác minh"} • {len(self.chapters)} mục • '
                           f'{sum(c.image_count or 0 for c in self.chapters)} {image_label} • {self.comic.site_id}')

    def handle_event(self, event):
        kind = event.get('type')
        if kind == 'source_resume_ready':
            self.source_resume_id = event['resume_id']
            return
        chapter_id = event.get('chapter_id')
        row = next((i for i, chapter in enumerate(self.chapters) if chapter.chapter_id == chapter_id), None)
        if kind in ('metadata', 'collection'):
            self.comic, self.chapters = event['comic'], event['chapters']
            self.adapter = event.get('adapter')
            self.metadata_state = AnalysisState.METADATA_READY
            self.analysis_state = AnalysisState.METADATA_READY if kind == 'metadata' else AnalysisState.CHAPTER_LIST_READY
            self.chapter_state = AnalysisState.IDLE if kind == 'metadata' else AnalysisState.CHAPTER_LIST_READY
            self.download_decisions = {c.chapter_id: self.adapter.download_decision(c) for c in self.chapters} if self.adapter else {}
            self.loaded_input = self.location.text()
            self.update_comic_label()
            self.table.setRowCount(len(self.chapters))
            for index, chapter in enumerate(self.chapters):
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemIsEnabled | (Qt.ItemIsUserCheckable if selectable(chapter) else Qt.NoItemFlags))
                item.setCheckState(Qt.Unchecked)
                self.table.setItem(index, 0, item)
                for column, value in enumerate((chapter.order_index + 1,
                    chapter.local_source.name if self.kind.currentIndex() == 0 and chapter.local_source else chapter.chapter_title or chapter.chapter_id,
                    'Ảnh người dùng cung cấp' if chapter.access_status == AccessStatus.LOCAL else chapter_access(chapter),
                    chapter.image_count if chapter.image_count is not None else 'Chưa xác minh', 'Chờ chọn'), 1):
                    self.table.setItem(index, column, QTableWidgetItem(str(value)))
                decision = self.download_decisions.get(chapter.chapter_id)
                self.table.setItem(index, 6, QTableWidgetItem(decision.state.value if decision else 'Không cần tải'))
                if decision:
                    self.table.item(index, 6).setToolTip(decision.reason)
                if self.kind.currentIndex() == 0:
                    item.setCheckState(Qt.Checked)
            self.status.setText('Đã đọc ảnh. Bấm Bắt đầu dịch.' if self.kind.currentIndex() == 0 else
                                'Đã đọc nguồn. Hãy chọn chương cần dịch; chưa tải ảnh website.')
            if event.get('warnings'):
                self.status.setText(self.status.text() + '\n' + '\n'.join(event['warnings']))
            self.refresh_start()
        elif kind == 'images_ready' and row is not None:
            images = event['images']
            self.discovered_images[chapter_id] = images
            self.image_states[chapter_id] = AnalysisState.IMAGE_LIST_READY
            self.analysis_state = AnalysisState.IMAGE_LIST_READY
            self.chapters[row] = replace(self.chapters[row], image_count=len(images), image_list_complete=event.get('complete'))
            self.update_comic_label()
            self.table.item(row, 4).setText(str(len(images)))
            self.table.item(row, 5).setText('Đã tìm thấy URL ảnh (chưa tải)')
            if self.adapter:
                decision = self.adapter.download_decision(self.chapters[row])
                self.download_decisions[chapter_id] = decision
                self.table.item(row, 6).setText(decision.state.value)
                self.table.item(row, 6).setToolTip(decision.reason)
            self.status.setText(f'IMAGE_LIST_READY: tìm thấy {len(images)} phần tử/URL ảnh; chưa tải ảnh.\n' + '\n'.join(event.get('warnings', ())))
            self.refresh_start()
        elif kind == 'analysis_phase':
            self.chapter_state = AnalysisState.ANALYZING
            self.analysis_state = AnalysisState.ANALYZING
            self.status.setText('Đã có metadata. Đang phân tích danh sách chương...')
        elif kind == 'source_error':
            category = event['category']
            self.last_error_category = category
            state = {'url': AnalysisState.URL_INVALID, 'network': AnalysisState.CONNECTION_ERROR,
                     'access': AnalysisState.ACCESS_ERROR, 'usage_limit': AnalysisState.USAGE_LIMIT,
                     'analysis': AnalysisState.CHAPTER_LIST_ERROR}.get(category, AnalysisState.TECHNICAL_ERROR)
            if event.get('phase') == 'images':
                self.analysis_state = AnalysisState.IMAGE_LIST_ERROR
                if chapter_id:
                    self.image_states[chapter_id] = AnalysisState.IMAGE_LIST_ERROR
                if row is not None:
                    self.table.item(row, 5).setText('Lỗi phân tích ảnh: ' + event['detail'])
            elif event.get('phase') == 'chapters':
                self.chapter_state = AnalysisState.CHAPTER_LIST_ERROR
                self.analysis_state = AnalysisState.CHAPTER_LIST_ERROR
            else:
                self.analysis_state = AnalysisState.METADATA_ERROR if category == 'analysis' else state
            label = {'url': 'URL không hợp lệ', 'network': 'kết nối', 'access': 'quyền truy cập',
                     'analysis': 'phân tích website', 'usage_limit': 'giới hạn sử dụng',
                     'website': 'website chưa hỗ trợ', 'cancelled': 'đã hủy'}.get(category, 'kỹ thuật')
            prefix = ('Không lấy được danh sách chương' if event.get('phase') == 'chapters' else
                      'Không phân tích được danh sách ảnh' if event.get('phase') == 'images' else 'Lỗi')
            self.status.setText(f"{prefix} ({label} / {category}): {event['detail']}")
            if category in ('access', 'usage_limit'):
                self.provider_notice.show_error(dict(code='SOURCE_ACCESS_DENIED', origin='source'))
            if self.adapter and row is not None:
                decision = self.adapter.download_decision(self.chapters[row])
                self.download_decisions[chapter_id] = decision
                self.table.item(row, 6).setText(decision.state.value)
            self.refresh_start()
        elif kind == 'chapter_start':
            self.position, self.total_chapters = event['position'], event['total_chapters']
            if row is not None:
                self.table.item(row, 5).setText('Đang kiểm tra/cache')
        elif kind == 'download':
            index, total = event.get('index', 1), max(1, event.get('total', 1))
            expected, received = event.get('expected_bytes'), event.get('bytes_received', 0)
            fraction = min(1, received / expected) if expected else (1 if event.get('stage') in ('cached', 'downloaded') else 0)
            self.progress.setValue(int(1000 * (index - 1 + fraction) / total))
            self.status.setText(f'Tải ảnh {index}/{total} • {event.get("stage")} • {received:,} byte')
            if row is not None:
                self.table.item(row, 5).setText('Tải ảnh: ' + event.get('stage', ''))
        elif kind == 'cache':
            self.status.setText(f"Cache ảnh cục bộ: {event['index']} / {event['total']}")
        elif kind == 'image_source_error':
            self.review_pages.append(event['review'])
            review = event['review']
            self.status.setText(f"DOWNLOAD_ERROR • Trang {review.get('image_index') or '?'} • "
                                f"{review['error_message']}\n{review.get('diagnostic_path') or review.get('diagnostic_error')}")
        elif kind == 'pipeline' and event.get('pipeline_event_type') == 'provider_paused':
            self.provider_paused = True
            self.ui_job_state = 'PAUSED_PROVIDER'
            self.paused_chapter = chapter_id
            self.provider_notice.show_error(event)
            self.status.setText('Đang tạm dừng; xem thông báo và Chi tiết. Kết quả đã hoàn tất được giữ.')
        elif kind == 'pipeline' and event.get('pipeline_event_type') == 'gemini_api_usage':
            from ui.provider_notice import gemini_usage_text
            self.policy.setText(gemini_usage_text(event))
        elif kind == 'pipeline' and event.get('pipeline_event_type') in ('agy_batch', 'gemini_api_batch'):
            provider = 'Gemini API' if event['pipeline_event_type'] == 'gemini_api_batch' else 'AGY'
            self.status.setText(f"{provider}: {event['pages']} trang • {event['regions']} vùng • {event['characters']} ký tự")
            if row is not None:
                self.table.item(row, 5).setText('Đang dịch batch nhiều trang')
        elif kind == 'pipeline' and event.get('stage'):
            if event.get('review'):
                self.review_pages.append(event['review'])
            if row is not None:
                self.table.item(row, 5).setText(event['stage'])
                if event.get('detail'):
                    self.table.item(row, 5).setToolTip(event['detail'])
            fraction = (event['index'] - 1 + event['percent'] / 100) / max(1, event['total'])
            self.progress.setValue(int(1000 * (self.position - 1 + fraction) / self.total_chapters))
            self.status.setText(f"{Path(event['file']).name} • {event['stage']} • "
                                f"{event['index']}/{event['total']} ảnh • Lỗi: {event['failed']}")
            if event.get('review'):
                review = event['review']
                self.status.setText(f"Trang {review['image_index']} • {review['image_filename']} • "
                    f"{review['stage']} • {review.get('provider') or '—'} • {review['error_code']} • "
                    f"{review['output_status']}\n{review.get('diagnostic_path') or review.get('diagnostic_error') or ''}")
        elif kind == 'pipeline' and event.get('pipeline_event_type') == 'fatal':
            self.status.setText('Lỗi khởi tạo OCR/dịch: ' + event.get('detail', 'Chưa rõ nguyên nhân'))
        elif kind == 'chapter_done':
            self.failed_ids.discard(chapter_id)
            if row is not None:
                self.table.item(row, 5).setText('Hoàn thành')
        elif kind == 'chapter_warning':
            self.failed_ids.add(chapter_id)
            if row is not None:
                counts = event['counts']
                self.table.item(row, 5).setText(f"COMPLETED_WITH_WARNINGS • {counts['files_exported']}/{counts['images_total']} file • "
                    f"Dịch: {counts['translated_success']} • Gốc: {counts['fallback_original']} • Xem lại: {counts['needs_review']}")
        elif kind == 'chapter_error':
            if row is not None:
                self.table.item(row, 5).setText('Lỗi: ' + event['detail'])
                self.table.item(row, 5).setToolTip(event['detail'])
                if self.adapter:
                    decision = self.adapter.download_decision(self.chapters[row])
                    self.download_decisions[chapter_id] = decision
                    self.table.item(row, 6).setText(decision.state.value)
        elif kind == 'job_finished':
            self.last_result = event
            if event['state'] == 'paused_provider':
                self.status.setText('Đang tạm dừng. '
                    'Chương chưa bắt đầu được giữ trong lựa chọn, không tự tải tiếp.')
                return
            self.review_pages = event.get('review_pages', self.review_pages)
            self.ui_job_state = event['state'].upper()
            self.review_button.setEnabled(bool(self.review_pages))
            self.processing_state = {'done': ProcessingState.COMPLETED, 'cancelled': ProcessingState.CANCELLED}.get(event['state'], ProcessingState.FAILED)
            if event['state'] == 'done':
                self.progress.setValue(1000)
            details = '\n'.join(error['detail'] for error in event['errors'])
            state_label = {'done': 'Hoàn tất', 'cancelled': 'Đã hủy', 'errors': 'Kết thúc có lỗi', 'error': 'Lỗi khởi tạo'}.get(event['state'], event['state'])
            self.status.setText(f"{state_label} • Chương xong: {event['chapters_completed']} • "
                                f"Chương lỗi: {event['chapters_failed']} • Ảnh xuất: {event['images_exported']} • "
                                f"Ảnh lỗi: {event['images_failed']}\n{details}")
            if self.kind.currentIndex() == 0:
                self.status.setText(f"{state_label} • Ảnh xuất: {event['images_exported']} • Ảnh lỗi: {event['images_failed']}\n{details}")
            if 'translated_success' in event:
                if event['state'] == 'completed_with_warnings':
                    self.processing_state = ProcessingState.COMPLETED_WITH_WARNINGS
                    self.progress.setValue(1000)
                self.status.setText(f"{event['state'].upper()} • File xuất: {event['images_exported']}/{event['images_total']} • "
                    f"Dịch hoàn chỉnh: {event['translated_success']} • Dịch một phần: {event['partial_translation']} • "
                    f"Ảnh gốc dự phòng: {event['fallback_original']} • Không output: {event['failed_no_output']} • "
                    f"Bỏ qua checkpoint: {event['skipped']} • Cần xem lại: {len(self.review_pages)}\n{details}")

    def pause_job(self):
        if self.worker:
            self.worker.control.pause()
            self.pause.setEnabled(False)
            self.resume.setEnabled(True)
            self.status.setText('Đã yêu cầu tạm dừng tại checkpoint an toàn.')
            self.ui_job_state = 'PAUSED_BY_USER'

    def restore_cached_job(self):
        if self.busy:
            return
        record = self.resume_store.read(self.source_resume_id) if self.source_resume_id else self.restorable
        if not record:
            self.status.setText('Không có journal nguồn để khôi phục.')
            return
        if not self.check_provider_setup():
            return
        self.options = self.options_factory() if self.options_factory else self.options
        self.output.setText(record['output'])
        self.processing_state = ProcessingState.TRANSLATING
        self.provider_paused = False
        self.status.setText('Đang xác minh cache/output; chương chưa tải sẽ được kiểm tra truy cập và policy trước khi tải...')
        self.launch('restore', dict(record=record, database=self.database or CACHE / 'online_comics/pipeline.sqlite3',
                                   options=self.options))

    def resume_job(self):
        if self.provider_paused and not self.busy:
            chapters = [c for c in self.chapters if c.chapter_id == self.paused_chapter]
            self.begin(chapters, retry_only=True)
            return
        if self.worker:
            self.worker.control.resume()
            self.pause.setEnabled(True)
            self.resume.setEnabled(False)

    def cancel_job(self):
        if self.worker:
            self.worker.control.cancel()
            self.cancel.setEnabled(False)
            self.pause.setEnabled(False)
            self.resume.setEnabled(False)
            self.status.setText('Đang hủy an toàn; giữ kết quả, manifest và file dở để tiếp tục.')

    def show_output(self):
        path = Path(self.output.text())
        if path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
        else:
            self.status.setText('Thư mục kết quả chưa tồn tại.')

    def show_review(self):
        from ui.review_dialog import ReviewDialog
        ReviewDialog(self.review_pages, self).exec()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.cancel_job()
            event.ignore()
        else:
            event.accept()


class ComicSourcesDialog(QDialog):
    """Compatibility host for existing QA/scripts; MainWindow embeds panels directly."""
    def __init__(self, options, parent=None, **kwargs):
        super().__init__(parent)
        self.setWindowTitle('Nguồn ảnh và truyện URL')
        self.resize(1040, 720)
        self.panel = ComicSourcesPanel(options, self, **kwargs)
        QVBoxLayout(self).addWidget(self.panel)

    def __getattr__(self, name):
        panel = self.__dict__.get('panel')
        if panel is not None:
            return getattr(panel, name)
        raise AttributeError(name)

    def reject(self):
        if self.panel.worker and self.panel.worker.isRunning():
            self.panel.cancel_job()
        else:
            super().reject()

    def closeEvent(self, event):
        if self.panel.worker and self.panel.worker.isRunning():
            self.panel.cancel_job()
            event.ignore()
        else:
            event.accept()
