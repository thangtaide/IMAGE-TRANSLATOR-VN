"""Opt-in whole-chapter dialog. AGY needs a separate, manifest-bound confirmation."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QThread, QTimer, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QSpinBox, QVBoxLayout)

from core.paths import ROOT
from core.pipeline import JobControl
from core.types import Options


class WholeChapterWorker(QThread):
    event = Signal(dict)

    def __init__(self, source, workspace, options, allow_translation, parent=None, *,
                 translator_kind='argos', whole_timeout=600, confirmed_manifest_hash=None,
                 bound_context=None, input_paths=None):
        super().__init__(parent)
        self.source, self.workspace, self.options = source, workspace, options
        self.allow_translation = allow_translation
        self.translator_kind, self.whole_timeout = translator_kind, whole_timeout
        self.confirmed_manifest_hash = confirmed_manifest_hash
        self.bound_context, self.input_paths = bound_context, input_paths
        self.control = JobControl()

    def run(self):
        try:
            source, paths = self.source, self.input_paths
            if self.bound_context:
                from sources.whole_input import prepare_input
                collection = prepare_input(self.bound_context, self.workspace, self.control, self.event.emit)
                source, paths = collection.root, collection.paths
            self.control.checkpoint()
            from core.runtime import prepare_inference_runtime
            prepare_inference_runtime()
            from core.whole_chapter import WholeChapterJob, AGYWholeChapterTranslator
            adapter = AGYWholeChapterTranslator(self.options, self.whole_timeout) if self.translator_kind == 'agy' else None
            WholeChapterJob(source, self.workspace, options=self.options, input_paths=paths,
                control=self.control, emit=self.event.emit, translator=adapter).run(
                    allow_translation=self.allow_translation, confirmed_manifest_hash=self.confirmed_manifest_hash)
        except Exception as exc:
            from core.whole_chapter import ChapterError
            from core.agy_error_evidence import AGYErrorCapture, error_reference
            from core.types import CancelledError
            from sources.contracts import SourceError
            code = getattr(exc, 'code', None) or (str(exc) if isinstance(exc, ChapterError) else type(exc).__name__)
            if isinstance(exc, SourceError):
                code = 'WHOLE_SOURCE_' + exc.category.upper()
            if self.translator_kind=='agy' and code in ('AGY_NOT_FOUND','AGY_MODEL','WHOLE_TIMEOUT_CONFIG','AGY_AUTOMATIC_EXTENSIONS') and not getattr(exc,'agy_error_attempt_id',None):
                from core.storage import digest
                capture=AGYErrorCapture(self.options.agy_model,self.whole_timeout,
                    dict(job_id=digest(Path(self.workspace).name) if self.workspace else None,final_job_state='blocked'))
                capture.failure(exc,'APP_PREFLIGHT');capture.finish('blocked')
            self.event.emit(dict(type='whole_finished', state='cancelled' if isinstance(exc, CancelledError) else 'blocked', error_code=code,
                                 **error_reference(exc)))


class WholeChapterDialog(QDialog):
    def __init__(self, options=None, parent=None, *, bound_context=None, translator_kind=None):
        super().__init__(parent)
        self.setWindowTitle('Whole Chapter Translation — thử nghiệm')
        self.resize(700, 460)
        self.options = replace(options or Options())
        self.bound_context = bound_context
        self.fresh_plan = bound_context.get('fresh_plan') if bound_context else None
        self.fresh_run_id = self.fresh_plan['run_id'] if self.fresh_plan else None
        self.fixed_translator = translator_kind
        self.input_paths = None
        self.worker = None
        self.workspace = None
        self.manifest_info = None
        self.attempt_used = False
        self.ready_for_confirmation = False
        layout = QVBoxLayout(self)
        row = QHBoxLayout(); self.translator_label = QLabel('Phương thức'); row.addWidget(self.translator_label)
        self.translator = QComboBox(); self.translator.addItem('Argos Offline', 'argos'); self.translator.addItem('AGY CLI', 'agy')
        if translator_kind:
            self.translator.setCurrentIndex(self.translator.findData(translator_kind))
            self.translator.hide(); self.translator_label.hide()
        row.addWidget(self.translator); row.addWidget(QLabel('Timeout AGY (giây)'))
        self.timeout = QSpinBox(); self.timeout.setRange(10, 1800); self.timeout.setValue(600); row.addWidget(self.timeout)
        layout.addLayout(row)
        self.note = QLabel(); self.note.setWordWrap(True); layout.addWidget(self.note)
        row = QHBoxLayout(); self.source = QLineEdit(self.options.source)
        self.choose = QPushButton('Chọn ảnh chương'); row.addWidget(self.source, 1); row.addWidget(self.choose)
        self.choose.clicked.connect(self.choose_source); layout.addLayout(row)
        self.allow = QCheckBox('Cho phép dịch Argos phần còn thiếu trong lượt bấm này (không tự retry)')
        layout.addWidget(self.allow)
        self.counts = QLabel('Chưa đọc chữ của chương.'); self.counts.setWordWrap(True); layout.addWidget(self.counts)
        self.confirm = QPushButton('Xác nhận dịch bằng AGY…'); self.confirm.setEnabled(False)
        self.confirm.clicked.connect(self.confirm_agy); layout.addWidget(self.confirm)
        row = QHBoxLayout(); self.start = QPushButton('Chạy QA mới')
        self.restore = QPushButton('Mở lượt đã lưu…'); self.resume = QPushButton('Tiếp tục')
        self.cancel = QPushButton('Hủy'); self.cancel.setEnabled(False); self.resume.setEnabled(False)
        for b in (self.start, self.restore, self.resume, self.cancel): row.addWidget(b)
        layout.addLayout(row)
        self.start.clicked.connect(self.start_new); self.restore.clicked.connect(self.restore_job)
        self.resume.clicked.connect(self.start_resume); self.cancel.clicked.connect(self.cancel_job)
        self.progress = QProgressBar(); layout.addWidget(self.progress)
        self.status = QLabel('Chưa chạy. Mở journal chỉ nạp cấu hình, không tự xử lý.')
        self.status.setWordWrap(True); layout.addWidget(self.status)
        self.open_result = QPushButton('Mở thư mục kết quả'); self.open_result.setEnabled(False)
        self.open_result.clicked.connect(self.open_results); layout.addWidget(self.open_result)
        self.translator.currentIndexChanged.connect(self.change_translator)
        self.source.textChanged.connect(self.clear_intent)
        self.change_translator()
        if bound_context:
            self.source.setReadOnly(True); self.choose.hide(); self.restore.hide()
            if bound_context['kind'] == 'chapter':
                chapter = bound_context['chapter']
                self.source.setText(chapter.chapter_title or chapter.chapter_id)
            else:
                self.source.setText(str(bound_context['path']))
            self.setWindowTitle('AGY — Toàn chương đã chọn (1 lần)')
            try:
                from sources.whole_input import latest_workspace
                saved = None if bound_context.get('force_new') else latest_workspace(bound_context)
                if saved:
                    self.load_workspace(saved)
                else:
                    # Opening from the main Start button authorizes preparation, not AGY.
                    QTimer.singleShot(0, self.prepare_new)
            except (OSError, ValueError, TypeError, KeyError):
                self.status.setText('Không xác minh được lượt đã lưu. Giữ dữ liệu; chọn Chuẩn bị lượt mới nếu cần.')

    def clear_intent(self, *_):
        self.manifest_info = None; self.attempt_used = False; self.workspace = None
        self.ready_for_confirmation = False
        self.input_paths = None
        self.confirm.setEnabled(False); self.resume.setEnabled(False); self.open_result.setEnabled(False)
        self.counts.setText('Chưa đọc chữ; chuẩn bị hoặc tiếp tục lượt đã lưu.')

    def change_translator(self, *_):
        self.clear_intent(); self.allow.setChecked(False)
        agy = self.translator.currentData() == 'agy'
        self.allow.setVisible(not agy); self.confirm.setVisible(agy); self.timeout.setEnabled(agy)
        self.start.setText('Dịch lại toàn bộ chương (lượt mới)…' if agy else 'Chạy QA mới')
        self.note.setText(('Whole Chapter — Single AGY Invocation. Gom toàn bộ OCR, không chia batch, không chờ 5–10 giây. '
            'Model: ' + self.options.agy_model + '. Có thể tiêu thụ quota; chỉ gọi sau hộp xác nhận riêng.' if agy else
            'Argos offline, một worker OCR; dịch từng vùng nội bộ, không phải một request AI.') +
            ('\nDùng đúng chương/ảnh đã chọn. Cache hợp lệ được đọc lại; chỉ tải ảnh còn thiếu khi access/download gate cho phép. '
             'Kết quả riêng, không ghi đè kết quả Batch.' if self.bound_context else
             '\nChọn ảnh chương đã có; không tải ảnh. Kết quả mới riêng trong output/stage3g-…; không đổi provider cửa sổ chính.'))

    def update_confirm(self):
        self.confirm.setEnabled(self.translator.currentData() == 'agy' and self.workspace is not None
            and self.ready_for_confirmation and self.manifest_info is not None and self.manifest_info['regions'] > 0 and not self.attempt_used
            and not (self.worker and self.worker.isRunning()))

    def confirm_agy(self):
        if not self.confirm.isEnabled() or not self.manifest_info: return
        info = self.manifest_info
        box = QMessageBox(self); box.setWindowTitle('Xác nhận Whole Chapter AGY')
        box.setText('Bạn sắp gửi toàn bộ văn bản OCR của chương tới AGY CLI trong một lượt dịch.\n\n'
            f"Số trang: {info['pages']}\nSố vùng OCR: {info['regions']}\nTổng ký tự nguồn: {info['source_characters']}\n\n"
            'Thao tác này có thể tiêu thụ quota. Ứng dụng không tự retry/fallback nếu thất bại.\nBạn có muốn tiếp tục?')
        cancel = box.addButton('Hủy', QMessageBox.RejectRole)
        accept = box.addButton('Xác nhận dịch bằng AGY', QMessageBox.AcceptRole)
        box.setDefaultButton(cancel); box.setEscapeButton(cancel); box.exec()
        if box.clickedButton() == accept:
            self.begin(agy_confirmed=True)

    def open_results(self):
        if self.workspace:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.workspace/'rendered')))

    def choose_source(self):
        value = QFileDialog.getExistingDirectory(self, 'Ảnh chương đã có', self.source.text())
        if value: self.source.setText(value)

    def start_new(self):
        if self.worker and self.worker.isRunning(): return
        if self.translator.currentData()=='agy':
            box=QMessageBox(self); box.setWindowTitle('Dịch lại toàn bộ chương')
            box.setText('Chuẩn bị lượt mới, không tiếp job cũ hoặc dùng lại bản dịch AGY cũ. '
                        'Kết quả cũ giữ nguyên. Có thể tiêu thụ quota khi xác nhận dịch sau OCR. Tiếp tục?')
            cancel=box.addButton('Hủy',QMessageBox.RejectRole)
            accept=box.addButton('Chuẩn bị lượt mới',QMessageBox.AcceptRole)
            box.setDefaultButton(cancel); box.setEscapeButton(cancel); box.exec()
            if box.clickedButton()!=accept:return
        self.prepare_new()

    def prepare_new(self):
        if self.worker and self.worker.isRunning(): return
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        self.manifest_info = None; self.attempt_used = False; self.confirm.setEnabled(False)
        self.counts.setText('Đang chuẩn bị lượt mới độc lập; chưa gửi AGY.')
        self.workspace = ROOT / 'output' / ('stage3g-' + stamp + '-' + uuid4().hex[:8])
        if self.fresh_plan:
            from core.run_cache import plain_path
            planned=plain_path(self.fresh_plan['workspace'])
            if planned.parent != (ROOT/'output').resolve() or planned.name != 'stage3g-restart-'+self.fresh_plan['run_id']:
                self.status.setText('Lượt mới có đường dẫn không hợp lệ; không xử lý.');return
            self.workspace=planned
            self.fresh_plan=None
        try:
            self.workspace.parent.mkdir(parents=True,exist_ok=True)
            self.workspace.mkdir(exist_ok=False)
        except OSError:
            self.workspace = None
            self.status.setText('Không tạo được thư mục mới độc lập; không dùng lại hoặc ghi đè lượt cũ.')
            self.resume.setEnabled(False); self.open_result.setEnabled(False)
            return
        self.progress.setValue(0)
        if self.fresh_run_id:
            from core.storage import atomic_json
            atomic_json(self.workspace/'run-id.json',dict(run_id=self.fresh_run_id,cache_policy='isolated-new-workspace'))
            self.fresh_run_id=None
        self.begin()

    def restore_job(self):
        name, _ = QFileDialog.getOpenFileName(self, 'Chọn chapter-journal.json QA',
            str(ROOT / 'output'), 'JSON (*.json)')
        if not name: return
        try:
            self.load_workspace(Path(name).parent)
        except Exception:
            self.status.setText('Không đọc được lượt đã lưu hợp lệ; dữ liệu giữ nguyên.')

    def load_workspace(self, workspace):
        from core.whole_chapter import read_json, verify
        workspace = Path(workspace).resolve()
        relative = workspace.relative_to((ROOT/'output').resolve())
        if not relative.parts or not relative.parts[0].startswith(('stage3f-', 'stage3g-')):
            raise ValueError()
        path = workspace/'chapter-journal.json'
        if path.exists():
            data = verify(read_json(path))
            if data.get('version') != 1: raise ValueError()
            descriptor = data.get('translator', dict(kind='argos'))
            kind = descriptor['kind']
            if kind not in ('argos', 'agy') or self.fixed_translator and kind != self.fixed_translator:
                raise ValueError()
            self.options = Options.from_dict(data['options'])
            self.translator.setCurrentIndex(self.translator.findData(kind))
            if kind == 'agy':
                self.options.agy_executable = descriptor['executable']; self.options.agy_model = descriptor['model']
                self.timeout.setValue(descriptor['timeout']); self.change_translator()
            if not self.bound_context: self.source.setText(data['source'])
            self.input_paths = (tuple(Path(data['source'])/p['relative'] for p in data['pages'])
                                if data.get('explicit_paths') else None)
            self.attempt_used = bool(data.get('agy_attempt_used'))
        elif not self.bound_context:
            raise ValueError()
        self.workspace = workspace
        self.manifest_info = None; self.ready_for_confirmation = False
        self.allow.setChecked(False); self.resume.setEnabled(True); self.open_result.setEnabled(True)
        self.status.setText('Đã tìm thấy lượt toàn chương đã lưu; chưa xử lý hoặc gửi AGY. Bấm Tiếp tục để kiểm tra ảnh, '
                            'đọc chữ/render phần còn thiếu với cấu hình đã lưu. Đổi model/cấu hình: chuẩn bị lượt mới. '
                            'AGY mới luôn cần nút Xác nhận riêng. Kết quả Batch giữ nguyên.')

    def start_resume(self):
        if self.workspace: self.begin()

    def begin(self, *, agy_confirmed=False):
        if self.worker and self.worker.isRunning(): return
        agy = self.translator.currentData() == 'agy'
        confirmed_hash = self.manifest_info['manifest_hash'] if agy_confirmed and self.manifest_info else None
        self.ready_for_confirmation = False
        self.worker = WholeChapterWorker(self.source.text(), self.workspace, self.options,
            agy_confirmed if agy else self.allow.isChecked(), self,
            translator_kind=self.translator.currentData(), whole_timeout=self.timeout.value(),
            confirmed_manifest_hash=confirmed_hash, bound_context=self.bound_context, input_paths=self.input_paths)
        self.worker.event.connect(self.on_event)
        self.worker.finished.connect(lambda: self.set_running(False))
        self.set_running(True); self.worker.start()

    def set_running(self, running):
        for widget in (self.start, self.restore, self.source, self.choose, self.allow, self.translator): widget.setEnabled(not running)
        self.timeout.setEnabled(not running and self.translator.currentData() == 'agy')
        self.resume.setEnabled(not running and self.workspace is not None)
        self.cancel.setEnabled(running)
        self.open_result.setEnabled(not running and self.workspace is not None and (self.workspace/'rendered').is_dir())
        self.update_confirm()

    def on_event(self, event):
        if event.get('type') == 'whole_input_progress':
            self.status.setText(f"{event['stage']} • {event.get('index', 0)}/{event.get('total', 0)} • Bước chuẩn bị chưa gọi AGY")
        elif event.get('type') == 'whole_manifest_ready':
            self.manifest_info = event; self.attempt_used = event['agy_attempt_used']
            self.counts.setText(f"Đã đọc chữ • {event['pages']} trang • {event['regions']} vùng • {event['source_characters']} ký tự nguồn")
            if self.translator.currentData() == 'agy':
                self.status.setText('Đã chuẩn bị toàn bộ chữ. AGY mới cần xác nhận riêng; Tiếp tục chỉ kiểm tra dữ liệu đã lưu.')
        elif event.get('type') == 'whole_agy_running':
            self.attempt_used = True; self.status.setText(event['stage']); self.confirm.setEnabled(False)
        elif event.get('type') == 'whole_progress':
            self.progress.setValue(event['percent'])
            self.status.setText(f"{event['phase']}: {event['completed']}/{event['total']}")
        elif event.get('type') == 'whole_finished':
            self.attempt_used = bool(event.get('agy_attempt_used', self.attempt_used))
            self.ready_for_confirmation = event['state'] == 'awaiting_translation'
            code = event.get('error_code', '')
            reasons = {
                'AGY_NOT_FOUND':'Không tìm thấy AGY; kiểm tra đường dẫn trong Cài đặt.',
                'WHOLE_SOURCE_ACCESS_DENIED':'Nguồn truyện bị khóa/hạn chế; không tải hoặc gửi AGY.',
                'WHOLE_SOURCE_DOWNLOAD_NOT_ALLOWED':'Chưa đủ điều kiện tải chương. Phân tích chương trong bảng và xem điều kiện truy cập; không gửi AGY.',
                'WHOLE_SOURCE_CACHE_INCOMPLETE':'Cache chương chưa đầy đủ hoặc trạng thái chưa xác minh; giữ dữ liệu, không tải bù hoặc trộn trang.',
                'WHOLE_SOURCE_CACHE_CHANGED':'Ảnh cache không khớp hash; dừng, không ghi đè.',
                'WHOLE_INPUT_CHANGED':'Danh sách/ảnh đã chọn thay đổi; không dùng hoặc ghi đè kết quả cũ.',
                'WHOLE_INPUT_CONTEXT_CHANGED':'Nguồn đã chọn khác lượt lưu; không tiếp tục nhầm chương.',
                'WHOLE_SOURCE_ACCESS':'Website từ chối truy cập; đây là lỗi nguồn, không phải quota AGY.',
                'WHOLE_SOURCE_USAGE_LIMIT':'Website giới hạn truy cập; dừng, không tự thử lại.',
                'WHOLE_SOURCE_NETWORK':'Không lấy được ảnh nguồn; chưa bắt đầu gửi OCR sang AGY.',
                'AGY_MODEL':'Model slug không hợp lệ; kiểm tra Cài đặt AGY, không tự đổi model.',
                'AGY_AUTOMATIC_EXTENSIONS':'Bị chặn trước khi khởi chạy AGY; chưa gửi yêu cầu dịch. Kiểm tra hooks/MCP an toàn, không bỏ guard hoặc sửa journal.',
                'AGY_START_FAILED':'Không khởi động được AGY CLI.',
                'AUTH_REQUIRED':'AGY yêu cầu phiên đăng nhập hợp lệ.',
                'ACCESS_DENIED':'AGY từ chối quyền truy cập; không tự đổi model/tài khoản.',
                'MODEL_UNAVAILABLE':'Model AGY không khả dụng.',
                'QUOTA_EXCEEDED':'AGY báo hết hạn mức; không tự gửi lại.',
                'RATE_LIMITED':'AGY báo giới hạn tốc độ; không tự chờ rồi thử lại.',
                'TIMEOUT':'AGY quá thời gian; không biết quota đã tiêu thụ hay chưa.',
                'EMPTY_RESPONSE':'AGY không trả nội dung.',
                'CLI_EXIT_ERROR':'AGY không hoàn tất invocation; giữ dữ liệu để xem lại.',
                'INVALID_RESPONSE':'Phản hồi AGY không qua JSON/ID/tool-use guard; không kết luận hết quota.',
                'WHOLE_AGY_ATTEMPT_ALREADY_USED':'Workspace đã chốt ngân sách lượt AGY nhưng thiếu phản hồi hợp lệ. Không khẳng định đã tiêu thụ quota; không gửi lại. Giữ journal để xem lại.',
                'WHOLE_PAYLOAD_LIMIT':'Payload vượt 16 MB stdin an toàn; không cắt nội dung/chia batch.',
                'WHOLE_COMMAND_LIMIT':'Schema/argv quá dài cho Windows; không chia batch.',
                'WHOLE_MANIFEST_CHANGED':'Manifest đã đổi; không gửi/render dữ liệu không khớp. Giữ journal để xem lại.',
                'WHOLE_RECIPE_OR_SOURCE_CHANGED':'Nguồn/cấu hình/identity khác journal; không sửa hash hoặc chuyển provider để ép resume.',
                'WHOLE_AGY_RESPONSE_CHANGED':'Receipt phản hồi AGY không khớp; không dùng hoặc tự gửi lại.',
                'NUMERIC_MISMATCH':'Bản dịch bị numeric guard từ chối; không sửa số hoặc gửi lại AGY.'}
            summary = (f"{event['state']} • {code}\n{reasons.get(code, 'Dữ liệu đã lưu được giữ; xem journal nếu bị chặn.')}\n"
                       f"Vùng qua guard lượt này: {event.get('validated_regions', '?')} • Trang render mới: {event.get('completed', 0)} • "
                       f"Bỏ qua receipt hợp lệ: {event.get('skipped', 0)} • {event.get('elapsed_seconds', 0):.1f}s\n{self.workspace}")
            self.status.setText(summary)
            if event.get('agy_attempt_id'):
                self.status.setText(summary+'\nAttempt: '+event['agy_attempt_id']+
                    (' • Log lỗi: '+event['agy_error_evidence'] if event.get('agy_error_evidence') else ' • Không lưu được evidence; lỗi gốc được giữ.'))
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
