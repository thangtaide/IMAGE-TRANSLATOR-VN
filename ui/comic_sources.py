"""Source selection and chapter UI, kept separate from the existing folder UI."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QProgressBar, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

from core.paths import CONFIG, ROOT
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
            else:
                raise SourceError('Tác vụ nguồn ảnh không được hỗ trợ.')
        except CancelledError:
            if self.action == 'process':
                self.event.emit({'type': 'job_finished', 'state': 'cancelled', 'chapters_completed': 0,
                                 'chapters_failed': 0, 'images_exported': 0, 'images_failed': 0,
                                 'errors': [], 'outputs': []})
            else:
                self.event.emit({'type': 'source_error', 'category': 'cancelled', 'detail': 'Đã hủy an toàn.'})
        except Exception as exc:
            logging.getLogger(__name__).exception('Comic source action failed: %s', self.action)
            self.event.emit({'type': 'source_error', 'category': getattr(exc, 'category', 'source'),
                             'phase': phase, 'chapter_id': active_chapter, 'detail': str(exc) or type(exc).__name__})
            if self.action == 'process':
                self.event.emit({'type': 'job_finished', 'state': 'error', 'chapters_completed': 0,
                                 'chapters_failed': 0, 'images_exported': 0, 'images_failed': 0,
                                 'errors': [{'chapter_id': None, 'detail': str(exc)}], 'outputs': []})


class ComicSourcesPanel(QWidget):
    busyChanged = Signal(bool)
    importRequested = Signal()

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
        self.import_local = QPushButton('Nhập chương từ ảnh đã lưu hợp lệ')
        inputs.addWidget(self.import_local)
        self.policy = QLabel('Ảnh gốc luôn được giữ nguyên. Phương thức dịch lấy từ cửa sổ chính; không tự tải model.')
        self.policy.setWordWrap(True)
        inputs.addWidget(self.policy)
        self.title = QLabel('Chưa chọn truyện. Chương không được tự động chọn.')
        self.title.setWordWrap(True)
        inputs.addWidget(self.title)
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel('Thư mục xuất'))
        self.output = QLineEdit(saved.get('output', options.output or str(ROOT / 'output' / 'translated_comics')))
        self.output_browse = QPushButton('Chọn thư mục kết quả')
        output_row.addWidget(self.output, 1)
        output_row.addWidget(self.output_browse)
        inputs.addLayout(output_row)
        self.keep = QCheckBox('Giữ bản sao ảnh nguồn trong cache sau khi xuất thành công')
        self.keep.setChecked(saved.get('keep_cached', True))
        inputs.addWidget(self.keep)
        self.configuration = QLabel(f'OCR: {options.language} • Offline: {options.offline_provider} • '
                                    'Dùng cấu hình font/xuất ảnh của cửa sổ chính.')
        inputs.addWidget(self.configuration)
        from ui.provider_notice import ProviderNotice
        self.provider_notice = ProviderNotice()
        inputs.addWidget(self.provider_notice)
        selection = QHBoxLayout()
        self.select_all = QPushButton('Chọn tất cả chương có thể xử lý')
        self.select_none = QPushButton('Bỏ chọn tất cả')
        self.retry_analysis = QPushButton('Thử lại danh sách chương')
        self.analyze_images = QPushButton('Phân tích ảnh chương')
        selection.addWidget(self.select_all)
        selection.addWidget(self.select_none)
        selection.addWidget(self.retry_analysis)
        selection.addWidget(self.analyze_images)
        inputs.addLayout(selection)
        layout.addWidget(self.inputs)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(['Chọn', 'Thứ tự', 'Tên chương', 'Truy cập chương', 'Ảnh xác minh', 'Trạng thái / lỗi', 'Điều kiện tải'])
        self.table.setMinimumHeight(230)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
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
        self.resume = QPushButton('Tiếp tục')
        self.cancel = QPushButton('Hủy')
        self.retry = QPushButton('Thử lại chương lỗi / chưa xong')
        self.open_output = QPushButton('Mở kết quả')
        self.review_button = QPushButton('Trang cần xem lại / log')
        self.review_button.setEnabled(False)
        self.review_button.clicked.connect(self.show_review)
        layout.addWidget(self.review_button)
        controls.addWidget(self.start, 0, 0)
        controls.addWidget(self.download, 0, 0)
        controls.addWidget(self.open_output, 0, 1, 1, 3)
        for column, button in enumerate((self.pause, self.resume, self.cancel, self.retry)):
            controls.addWidget(button, 1, column)
        layout.addLayout(controls)
        self.kind.currentIndexChanged.connect(self.source_changed)
        self.location.textChanged.connect(self.invalidate_collection)
        self.browse.clicked.connect(self.choose_source)
        self.analyze.clicked.connect(self.analyze_source)
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
                            if online else 'Ảnh gốc luôn được giữ nguyên. Dịch Offline; không tự tải model.')
        self.import_local.setVisible(online)
        self.retry_analysis.setVisible(online)
        self.analyze_images.setVisible(online)
        self.download.setVisible(online)
        self.download_status.setVisible(online)
        self.start.setVisible(not online)
        self.title.setVisible(self.kind.currentIndex() != 0)
        for column in (1, 3, 4):
            self.table.setColumnHidden(column, self.kind.currentIndex() == 0)
        self.table.setColumnHidden(6, not online)
        self.select_all.setText('Chọn tất cả chương' if online else 'Chọn tất cả ảnh' if single else 'Chọn tất cả ảnh/chương')
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
        if not self.busy and self.adapter and chapters:
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
        self.download.setToolTip(reason)
        self.retry_analysis.setEnabled(not self.busy and bool(self.comic))
        self.analyze_images.setEnabled(not self.busy and online and bool(selected) and self.adapter is not None)
        self.retry.setEnabled(not self.busy and bool(self.failed_ids))

    def set_busy(self, busy):
        self.busy = busy
        self.inputs.setEnabled(not busy)
        self.table.setEnabled(not busy)
        self.pause.setEnabled(busy)
        self.resume.setEnabled(False)
        self.cancel.setEnabled(busy)
        self.refresh_start()
        self.busyChanged.emit(busy)
        if not busy and self.provider_paused:
            self.resume.setEnabled(True)

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
        self.provider_paused = False
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
        self.title.setText(f'{self.comic.title or "Truyện gốc chưa xác minh"} • Nguồn: {self.comic.site_id} • '
                           f'Tác giả: {self.comic.author or "chưa xác định"} • '
                           f'Số nội dung công bố: {count if count is not None else "chưa xác định"} • '
                           f'Đã lấy: {len(self.chapters)} chương, {sum(c.image_count or 0 for c in self.chapters)} {image_label}')

    def handle_event(self, event):
        kind = event.get('type')
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
            self.paused_chapter = chapter_id
            self.provider_notice.show_error(event)
            self.status.setText(event['code'] + ' • Tạm dừng; không chuyển provider tự động.')
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
                self.status.setText('Tạm dừng Online Free. Đổi phương thức nếu muốn rồi Tiếp tục chương hiện tại từ cache. '
                    'Chương chưa bắt đầu được giữ trong lựa chọn, không tự tải tiếp.')
                return
            self.review_pages = event.get('review_pages', self.review_pages)
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
