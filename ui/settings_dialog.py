from __future__ import annotations

import json

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QDoubleSpinBox, QVBoxLayout,
    QScrollArea, QWidget)

from core.types import Options


class SettingsDialog(QDialog):
    def __init__(self, options: Options, parent=None):
        super().__init__(parent)
        self.options = options
        self.setWindowTitle('Cài đặt xuất ảnh, font và thuật ngữ')
        self.resize(640, 720)
        outer = QVBoxLayout(self)
        form = QFormLayout()
        self.font = QLineEdit(options.font)
        browse = QPushButton('Chọn TTF/OTF')
        browse.clicked.connect(self.choose_font)
        font_row = QHBoxLayout()
        font_row.addWidget(self.font)
        font_row.addWidget(browse)
        form.addRow('Font (trống = tự chọn)', font_row)
        self.fields = {}
        for title, name, low, high in [('Cỡ chữ tối thiểu', 'font_min', 4, 80), ('Cỡ chữ tối đa', 'font_max', 8, 200),
                ('Khoảng cách dòng', 'line_spacing', 0, 20), ('Viền chữ', 'stroke', 0, 5),
                ('Nới mask (px)', 'mask_expand', 0, 8), ('Chất lượng JPEG/WEBP', 'quality', 10, 100),
                ('Tile OCR (px)', 'tile_size', 512, 2400)]:
            widget = QSpinBox()
            widget.setRange(low, high)
            widget.setValue(getattr(options, name))
            form.addRow(title, widget)
            self.fields[name] = widget
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
        self.agy_executable = QLineEdit(options.agy_executable)
        self.agy_executable.setPlaceholderText('Trống: tìm AGY đã cài; không thay PATH hệ thống')
        form.addRow('AGY executable (.exe)', self.agy_executable)
        self.agy_model = QLineEdit(options.agy_model)
        form.addRow('AGY Gemini model slug', self.agy_model)
        for title, name, low, high in [('Timeout AGY (giây)', 'agy_timeout', 10, 300),
                                      ('Lượt AGY tối đa/job', 'agy_max_requests', 1, 128)]:
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
        scroll.setMinimumHeight(260)
        outer.addWidget(scroll, 1)
        self.diagnostic_text = QCheckBox('Lưu văn bản OCR/bản dịch bị lỗi trong diagnostic cục bộ (giới hạn độ dài)')
        self.diagnostic_text.setChecked(options.diagnostic_text)
        outer.addWidget(self.diagnostic_text)
        note = QLabel('MyMemory API ẩn danh: 5.000 ký tự/ngày, tối đa 500 byte/request.\n'
                      'Online Free gửi OCR ra ngoài; MyMemory có thể lưu và chia sẻ với đối tác MT.\n'
                      'Chỉ dùng endpoint LibreTranslate bạn có quyền sử dụng miễn phí. Không nhập API key.\n'
                      'Thuật ngữ/tên riêng: mỗi dòng là chữ gốc = tiếng Việt. Marker phải được provider giữ nguyên.')
        note.setWordWrap(True)
        outer.addWidget(note)
        self.glossary = QPlainTextEdit('\n'.join(f'{k} = {v}' for k, v in options.glossary.items()))
        self.glossary.setMaximumHeight(120)
        outer.addWidget(self.glossary)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def choose_font(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Chọn font hỗ trợ tiếng Việt', self.font.text(), 'Font (*.ttf *.otf)')
        if path:
            self.font.setText(path)

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
            model = self.agy_model.text().strip()
            if not model.startswith('gemini-') or not model.replace('-', '').replace('.', '').isalnum():
                raise ValueError('AGY cần model slug Gemini đã có trong agy models')
        except ValueError as exc:
            QMessageBox.warning(self, 'Cài đặt chưa hợp lệ', str(exc))
            return
        for name, widget in self.fields.items():
            setattr(self.options, name, widget.value())
        self.options.diagnostic_text = self.diagnostic_text.isChecked()
        self.options.agy_executable = self.agy_executable.text().strip()
        self.options.agy_model = model
        for name, combo in self.combos.items():
            setattr(self.options, name, combo.currentData())
        self.options.font = self.font.text().strip()
        self.options.mask_path = self.mask.text().strip()
        self.options.endpoint = self.endpoint.text().strip()
        self.options.confidence = self.confidence.value()
        self.options.glossary = glossary
        super().accept()
