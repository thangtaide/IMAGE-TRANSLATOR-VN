from __future__ import annotations

import json

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QDoubleSpinBox, QVBoxLayout,
    QScrollArea, QWidget, QGroupBox)

from core.types import Options
from providers.agy_models import MODELS,selection,identifier


class SettingsDialog(QDialog):
    def __init__(self, options: Options, parent=None, focus_section=None):
        super().__init__(parent)
        self.options = options
        self.setWindowTitle('Cài đặt')
        self.resize(640, 720)
        screen = self.screen().availableGeometry()
        self.resize(min(640, screen.width()-40), min(720, screen.height()-60))
        outer = QVBoxLayout(self)
        self.api_group = QGroupBox('Gemini API — thiết lập cục bộ')
        api_form = QFormLayout(self.api_group)
        api_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.font = QLineEdit(options.font)
        browse = QPushButton('Chọn TTF/OTF')
        browse.clicked.connect(self.choose_font)
        font_row = QHBoxLayout()
        font_row.addWidget(self.font)
        font_row.addWidget(browse)
        form.addRow('Font (trống = tự chọn)', font_row)
        self.fields = {}
        batch_note = QLabel('AGY batch: tối đa 24 trang / 60 vùng / 3.000 ký tự nguồn; chờ 5–10 giây giữa lần dịch. '
                           'Gemini API giữ planner 16 trang và giới hạn riêng. Whole Chapter AGY gửi một lần, không dùng các ngưỡng batch.')
        batch_note.setWordWrap(True)
        form.addRow(batch_note)
        for title, name, low, high in [('Cỡ chữ tối thiểu', 'font_min', 4, 80), ('Cỡ chữ tối đa', 'font_max', 8, 200),
                ('Khoảng cách dòng', 'line_spacing', 0, 20), ('Viền chữ', 'stroke', 0, 5),
                ('Nới mask (px)', 'mask_expand', 0, 8), ('Chất lượng JPEG/WEBP', 'quality', 10, 100),
                ('Tile OCR (px)', 'tile_size', 512, 2400),
                ('AGY / API ký tự mục tiêu/batch', 'agy_batch_chars', 100, 12000),
                ('AGY / API vùng tối đa/batch', 'agy_batch_regions', 1, 60)]:
            widget = QSpinBox()
            widget.setRange(low, high)
            widget.setValue(getattr(options, name))
            form.addRow(title, widget)
            self.fields[name] = widget
        self.fields['agy_batch_chars'].setToolTip('AGY có trần cứng 3.000 ký tự nguồn dù đặt mục tiêu cao hơn. Gemini API giữ phạm vi cấu hình cũ.')
        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(.1, .99)
        self.confidence.setSingleStep(.05)
        self.confidence.setValue(options.confidence)
        form.addRow('Ngưỡng tin cậy OCR', self.confidence)
        self.combos = {}
        for title, name, entries in [
                ('Định dạng xuất', 'output_format', [('Giữ định dạng gốc', 'original'), ('PNG', 'png'), ('JPEG', 'jpg'), ('WEBP', 'webp')]),
                ('Xóa chữ', 'erase_mode', [('Inpainting tự động', 'inpaint'), ('Nền trắng', 'white'), ('Mask tùy chỉnh', 'custom')]),
                ('Căn chữ', 'alignment', [('Giữa', 'center'), ('Trái', 'left')]),
                ('Màu chữ', 'foreground', [('Đen', 'black'), ('Trắng', 'white')]),
                ('Thứ tự đọc', 'reading_direction', [('Trên xuống, trái sang phải', 'ltr'), ('Cột phải sang trái (chữ dọc)', 'rtl')])]:
            combo = QComboBox()
            for label, value in entries:
                combo.addItem(label, value)
            combo.setCurrentIndex(max(0, combo.findData(getattr(options, name))))
            form.addRow(title, combo)
            self.combos[name] = combo
        self.mask = QLineEdit(options.mask_path)
        mask_browse = QPushButton('Chọn mask')
        mask_browse.clicked.connect(self.choose_mask)
        mask_row = QHBoxLayout()
        mask_row.addWidget(self.mask)
        mask_row.addWidget(mask_browse)
        form.addRow('Mask: trắng = vùng xóa', mask_row)
        self.endpoint = QLineEdit(options.endpoint)
        form.addRow('LibreTranslate miễn phí / tự host', self.endpoint)
        for title, name, values in [('Provider Offline', 'offline_provider', ['Argos', 'CTranslate2', 'M2M100']),
                                    ('Provider Online', 'online_provider', ['MyMemory', 'LibreTranslate'])]:
            combo = QComboBox()
            for value in values:
                combo.addItem(value, value)
            combo.setCurrentIndex(max(0, combo.findData(getattr(options, name))))
            form.addRow(title, combo)
            self.combos[name] = combo
        self.allow_fallback = QCheckBox('Cho phép gửi OCR Online khi chọn Auto Fallback')
        self.allow_fallback.setChecked(options.allow_online_fallback)
        form.addRow('Nâng cao — không tự bật', self.allow_fallback)
        self.agy_executable = QLineEdit(options.agy_executable)
        self.agy_executable.setPlaceholderText('Trống: tìm AGY đã cài; không thay PATH hệ thống')
        form.addRow('AGY executable (.exe)', self.agy_executable)
        self.ai_group=QGroupBox('AI dịch thuật (AGY)')
        ai_form=QFormLayout(self.ai_group);ai_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.ai_model=QComboBox();self.ai_model.setObjectName('aiModel');self.ai_model.setMinimumContentsLength(18)
        for choice in MODELS:self.ai_model.addItem(choice.label,choice.key)
        self.ai_effort=QComboBox();self.ai_effort.setObjectName('aiEffort')
        self.ai_description=QLabel();self.ai_description.setWordWrap(True)
        ai_form.addRow('Model AI',self.ai_model);ai_form.addRow('Mức suy luận',self.ai_effort)
        ai_form.addRow(self.ai_description);form.insertRow(0,self.ai_group);form.insertRow(1,self.api_group)
        self.ai_model.currentIndexChanged.connect(self.update_ai_efforts)
        self.ai_effort.currentIndexChanged.connect(self.update_ai_description)
        try:
            choice,effective=selection(options.agy_model,options.agy_effort)
            self.ai_model.setCurrentIndex(self.ai_model.findData(choice.key));self.update_ai_efforts()
            self.ai_effort.setCurrentIndex(self.ai_effort.findData(effective or ''))
        except ValueError:
            # Preserve unknown/invalid legacy choices visibly until the user
            # deliberately chooses a supported model; never silently choose Low.
            self.ai_model.addItem('Model đã lưu cần kiểm tra','unsupported')
            self.ai_model.setCurrentIndex(self.ai_model.findData('unsupported'))
        self.update_ai_description()
        self.gemini_api_model = QLineEdit(options.gemini_api_model)
        self.gemini_api_model.setReadOnly(True)
        api_form.addRow('Model (không tự chuyển)', self.gemini_api_model)
        self.gemini_api_free = QCheckBox('Đã kiểm tra project Free tier, không gắn billing')
        self.gemini_api_free.setChecked(options.gemini_api_free_tier_confirmed)
        api_form.addRow(self.gemini_api_free)
        api_note = QLabel('Kiểm tra project của key tại <a href="https://aistudio.google.com/api-keys">Google AI Studio</a> trước khi xác nhận. '
                          'Key lấy từ GEMINI_API_KEY; có key chưa chứng minh quyền model hoặc Free tier. Không tự kiểm tra mạng/billing.')
        api_note.setWordWrap(True)
        api_note.setOpenExternalLinks(True)
        api_form.addRow(api_note)
        for title, name, low, high in [('Timeout AGY (giây)', 'agy_timeout', 10, 300),
                                      ('Lượt AGY tối đa/job', 'agy_max_requests', 1, 128),
                                      ('Timeout Gemini API (giây)', 'gemini_api_timeout', 10, 300),
                                      ('Lượt Gemini API tối đa/phiên', 'gemini_api_max_requests', 1, 128)]:
            widget = QSpinBox()
            widget.setRange(low, high)
            widget.setValue(getattr(options, name))
            form.addRow(title, widget)
            self.fields[name] = widget
        form_widget = QWidget()
        form_widget.setLayout(form)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_widget)
        scroll.setMinimumHeight(120)
        outer.addWidget(scroll, 1)
        self.diagnostic_text = QCheckBox('Lưu văn bản OCR/bản dịch bị lỗi trong diagnostic cục bộ (giới hạn độ dài)')
        self.diagnostic_text.setChecked(options.diagnostic_text)
        form.addRow(self.diagnostic_text)
        self.agy_context = QCheckBox('AGY / Gemini API: mang theo tối đa1600ký tự ngữ cảnh đã qua validation')
        self.agy_context.setChecked(options.agy_context)
        form.addRow(self.agy_context)
        note = QLabel('MyMemory API ẩn danh: 5.000 ký tự/ngày, tối đa 500 byte/request.\n'
                      'Online Free gửi OCR ra ngoài; MyMemory có thể lưu và chia sẻ với đối tác MT.\n'
                      'Chỉ dùng endpoint LibreTranslate bạn có quyền sử dụng miễn phí. Không nhập API key.\n'
                      'Thuật ngữ/tên riêng: mỗi dòng là chữ gốc = tiếng Việt. Marker phải được provider giữ nguyên.')
        note.setWordWrap(True)
        form.addRow(note)
        self.glossary = QPlainTextEdit('\n'.join(f'{k} = {v}' for k, v in options.glossary.items()))
        self.glossary.setMaximumHeight(120)
        form.addRow(self.glossary)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('Lưu')
        buttons.button(QDialogButtonBox.Cancel).setText('Hủy')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self.buttons=buttons
        if focus_section == 'gemini_api':
            self.gemini_api_free.setFocus()

    def choose_font(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Chọn font hỗ trợ tiếng Việt', self.font.text(), 'Font (*.ttf *.otf)')
        if path:
            self.font.setText(path)

    def update_ai_efforts(self):
        self.ai_effort.blockSignals(True);self.ai_effort.clear()
        choice=next((c for c in MODELS if c.key==self.ai_model.currentData()),None)
        if choice:
            for effort,_ in choice.variants:
                self.ai_effort.addItem(effort.title() if effort else 'Theo mặc định của model',effort)
        self.ai_effort.setEnabled(bool(choice and len(choice.variants)>1))
        self.ai_effort.blockSignals(False);self.update_ai_description()

    def update_ai_description(self):
        choice=next((c for c in MODELS if c.key==self.ai_model.currentData()),None)
        if not choice:
            self.ai_description.setText('Cấu hình đã lưu chưa được xác nhận. Hãy chọn rõ model được hỗ trợ trước khi Lưu.');return
        effort=self.ai_effort.currentData()
        texts={'low':'Low: ưu tiên tiết kiệm mức suy luận, phù hợp dịch truyện hàng loạt.',
               'medium':'Medium: cân bằng giữa chất lượng và mức suy luận.',
               'high':'High: dành cho nội dung phức tạp.'}
        self.ai_description.setText(texts.get(effort,choice.label+' '+choice.version+'. Theo mặc định của model; ứng dụng không ép mức suy luận khác.'))
        self.ai_model.setToolTip(choice.label+' '+choice.version)

    def choose_mask(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Chọn mask cùng kích thước ảnh nguồn', '', 'Ảnh (*.png *.bmp)')
        if path:
            self.mask.setText(path)

    def accept(self) -> None:
        glossary = {}
        try:
            for line in self.glossary.toPlainText().splitlines():
                if line.strip():
                    key, value = line.split('=', 1)
                    if not key.strip() or not value.strip():
                        raise ValueError('Thuật ngữ rỗng')
                    glossary[key.strip()] = value.strip()
            if self.fields['font_min'].value() > self.fields['font_max'].value():
                raise ValueError('Cỡ chữ tối thiểu phải ≤ cỡ tối đa')
            effort=self.ai_effort.currentData()
            model=identifier(self.ai_model.currentData(),effort)
            selection(model,effort)
        except ValueError as exc:
            QMessageBox.warning(self, 'Cài đặt chưa hợp lệ', str(exc))
            return
        for name, widget in self.fields.items():
            setattr(self.options, name, widget.value())
        self.options.diagnostic_text = self.diagnostic_text.isChecked()
        self.options.agy_context = self.agy_context.isChecked()
        self.options.agy_executable = self.agy_executable.text().strip()
        self.options.agy_model = model
        self.options.agy_effort = effort
        self.options.gemini_api_free_tier_confirmed = self.gemini_api_free.isChecked()
        self.options.allow_online_fallback = self.allow_fallback.isChecked()
        for name, combo in self.combos.items():
            setattr(self.options, name, combo.currentData())
        self.options.font = self.font.text().strip()
        self.options.mask_path = self.mask.text().strip()
        self.options.endpoint = self.endpoint.text().strip()
        self.options.confidence = self.confidence.value()
        self.options.glossary = glossary
        super().accept()
