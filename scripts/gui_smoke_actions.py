"""Actions inside the real Qt application; only imported by explicit --smoke-test."""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from scripts.qa_common import ROOT, source_fingerprint


def schedule(window, app, path: Path) -> None:
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QFileDialog, QLineEdit
    from core.pipeline import scan_images
    from core.types import Options
    from ui.models_dialog import ModelManagerDialog
    from ui.preview import PreviewDialog
    from PIL import Image

    path = path.resolve()
    if not path.is_relative_to((ROOT/'logs').resolve()):
        raise ValueError('Smoke evidence must be inside project logs')
    report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'python': sys.executable,
              'source_fingerprint': source_fingerprint(), 'mock': False, 'display_mode': 'Qt offscreen',
              'overall': 'FAIL', 'checks': {}, 'desktop_display_verified': False,
              'not_tested': ['OCR/MT progress while processing real images', 'Native Windows folder picker', 'Physical desktop rendering']}
    report['font'] = window.font_report
    report['display_mode'] = app.platformName()
    checks = report['checks']
    original = Options.from_dict(window.options.to_dict())
    old_source, old_mode = window.source.text(), window.mode.currentText()
    heartbeat = QTimer(window)
    heartbeat.setInterval(20)
    beats = []
    heartbeat.timeout.connect(lambda: beats.append(time.monotonic()))
    heartbeat.start()
    fixtures = ROOT/'output/gui-validation'/path.parent.name
    fixtures.mkdir(parents=True, exist_ok=False)

    def step(name, action):
        try:
            action()
            checks[name] = {'status': 'PASS'}
        except Exception as exc:
            checks[name] = {'status': 'FAIL', 'reason': str(exc)}

    def require(condition, message):
        if not condition:
            raise AssertionError(message)

    def actions():
        step('vietnamese_font_glyphs', lambda: require(window.font_report['status']=='PASS', 'Vietnamese glyphs missing'))
        step('main_window_visible', lambda: require(window.isVisible(), 'MainWindow not visible'))
        def modes():
            for mode in ['Online Free', 'Offline', 'Auto Fallback']:
                window.mode.setCurrentIndex(window.mode.findData(mode))
                require(window.mode.currentData()==mode, 'Cannot select mode')
            window.mode.setCurrentText('Offline')
            require(not window.online_provider.isEnabled(), 'Online provider enabled in Offline mode')
        step('select_modes', modes)
        step('idle_buttons', lambda: require(window.start_button.isEnabled() and not window.pause_button.isEnabled() and not window.cancel_button.isEnabled(), 'Invalid initial button states'))
        def choose():
            def accept_picker():
                for widget in app.topLevelWidgets():
                    if isinstance(widget, QFileDialog):
                        widget.setDirectory(str(fixtures.parent))
                        def enter_directory(dialog=widget):
                            edit = dialog.findChild(QLineEdit, 'fileNameEdit')
                            if edit is not None:
                                edit.setText(str(fixtures))
                            else:
                                dialog.selectFile(str(fixtures))
                            report['picker_observation'] = {'directory':dialog.directory().absolutePath(),
                                                            'selected_files':dialog.selectedFiles()}
                            dialog.accept()
                        QTimer.singleShot(200, enter_directory)
            QTimer.singleShot(150, accept_picker)
            # Emergency rejection avoids a stuck offscreen modal dialog.
            def reject_picker():
                for widget in app.topLevelWidgets():
                    if isinstance(widget, QFileDialog):
                        widget.reject()
            QTimer.singleShot(2000, reject_picker)
            window.choose_folder(window.source)
            require(Path(window.source.text()).resolve()==fixtures.resolve(), 'Folder was not selected')
        step('qt_folder_picker', choose)
        def listing():
            for name in ['2.png', '10.png']:
                Image.new('RGB', (320, 200), 'white').save(fixtures/name)
            paths = scan_images(fixtures, False)
            window.options.source = str(fixtures)
            window.handle_event({'type': 'files', 'files': [str(p) for p in paths]})
            require(window.table.rowCount()==2, 'Image table was not populated from filesystem')
        step('filesystem_image_list', listing)
        def models():
            dialog = ModelManagerDialog(window)
            QTimer.singleShot(80, dialog.reject)
            dialog.exec()
            require(dialog.table.rowCount()>0, 'Model catalog is empty')
        step('model_manager_opens', models)
        def preview():
            dialog = PreviewDialog(str(fixtures/'2.png'), str(fixtures/'10.png'), window)
            QTimer.singleShot(80, dialog.reject)
            dialog.exec()
            require(len(dialog.views)==2 and all(v.scene().items() for v in dialog.views), 'Preview has no image')
        step('preview_opens', preview)
        step('screenshot_saved', lambda: require(window.grab().save(str(path.parent/'window.png')), 'Screenshot write failed'))
        QTimer.singleShot(250, finish)

    def finish():
        step('event_loop_heartbeat', lambda: require(len(beats)>=3, 'Event loop did not respond'))
        report['heartbeat_count'] = len(beats)
        report['overall'] = 'PASS' if checks and all(c['status']=='PASS' for c in checks.values()) else 'FAIL'
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        heartbeat.stop()
        window.options = original
        window.source.setText(old_source)
        window.mode.setCurrentText(old_mode)
        window.close()
        app.exit(0 if report['overall']=='PASS' else 1)

    app.setAttribute(Qt.AA_DontUseNativeDialogs, True)
    QTimer.singleShot(0, actions)
