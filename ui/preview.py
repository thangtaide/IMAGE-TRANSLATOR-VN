from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QGraphicsScene, QGraphicsView, QHBoxLayout,
                              QLabel, QPushButton, QSlider, QSplitter, QVBoxLayout)


class ImageView(QGraphicsView):
    def __init__(self, path: str):
        super().__init__()
        scene = QGraphicsScene(self)
        self.setScene(scene)
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scene.addPixmap(pixmap)
        else:
            scene.addText('Không đọc được ảnh preview')
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def fit(self) -> None:
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def zoom(self, value: int) -> None:
        self.resetTransform()
        self.scale(value / 100, value / 100)


class PreviewDialog(QDialog):
    def __init__(self, source: str, output: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle('So sánh trước / sau — ' + Path(source).name)
        self.resize(1200, 780)
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        controls.addWidget(QLabel('Kéo ảnh để di chuyển • Zoom'))
        zoom = QSlider(Qt.Horizontal)
        zoom.setRange(10, 300)
        zoom.setValue(100)
        controls.addWidget(zoom)
        fit = QPushButton('Vừa cửa sổ')
        controls.addWidget(fit)
        layout.addLayout(controls)
        splitter = QSplitter(Qt.Horizontal)
        self.views = []
        for title, path in [('Ảnh gốc', source), ('Ảnh đã Việt hóa', output)]:
            pane = QDialog()
            pane.setWindowFlags(Qt.Widget)
            box = QVBoxLayout(pane)
            box.addWidget(QLabel(title))
            view = ImageView(path)
            box.addWidget(view)
            splitter.addWidget(pane)
            self.views.append(view)
        layout.addWidget(splitter)
        fit.clicked.connect(lambda: [v.fit() for v in self.views])
        zoom.valueChanged.connect(lambda value: [v.zoom(value) for v in self.views])

    def showEvent(self, event) -> None:
        super().showEvent(event)
        for view in self.views:
            view.fit()
