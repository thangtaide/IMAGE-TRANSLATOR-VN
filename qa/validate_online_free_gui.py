"""Windows Qt + real OCR/Argos; Online transport deliberately MOCKED for quota QA."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
import faulthandler
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch


def main(evidence: Path) -> int:
    from core.runtime import prepare_inference_runtime
    prepare_inference_runtime()
    from core.storage import file_digest
    from core.paths import CONFIG, ROOT
    from PIL import Image, ImageDraw, ImageFont
    from PySide6.QtCore import Qt, QTimer, QEventLoop
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow
    from providers.online import MyMemoryProvider
    import requests

    root = ROOT / 'output' / 'online-free-validation' / (evidence.name + '-' + datetime.now(timezone.utc).strftime('%H%M%S%f'))
    root.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir(exist_ok=False)
    trace = (root / 'trace.txt').open('w', encoding='utf-8')
    faulthandler.dump_traceback_later(20, file=trace)
    source = root / 'source'
    source.mkdir()
    for index, text in enumerate(('你好世界', '你好朋友'), 1):
        image = Image.new('RGB', (900, 180), 'white')
        ImageDraw.Draw(image).text((25, 40), text, font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 48), fill='black')
        image.save(source / f'{index}.png')
    original = {str(p): file_digest(p) for p in source.glob('*.png')}
    settings = {str(p): file_digest(p) for p in CONFIG.glob('*.json')}
    requests_made, connections, beats = [], [], []
    def audit(event, args):
        if event in ('socket.connect', 'socket.getaddrinfo'):
            connections.append(event)
            raise RuntimeError('This GUI QA must not send OCR over network')
    sys.addaudithook(audit)
    def request(*args, **kwargs):
        requests_made.append(kwargs['params']['q'])
        response = requests.Response()
        response.status_code = 200
        response.headers['Content-Type'] = 'application/json'
        response._content_consumed = True
        data = ({'responseStatus': 200, 'responseData': {'translatedText': 'Xin chào thế giới'}}
                if len(requests_made) == 1 else {'responseStatus': 403, 'quotaFinished': True})
        response._content = json.dumps(data).encode('utf-8')
        return response
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    report = {'status': 'FAIL', 'platform': os.environ.get('QT_QPA_PLATFORM'),
              'online_transport': 'MOCKED_HTTP', 'ocr': 'REAL_PADDLEOCR', 'resume': 'REAL_ARGOS_OFFLINE'}
    class QAWindow(MainWindow):
        def handle_event(self, event):
            # A bound QObject method preserves Qt's queued cross-thread delivery.
            if event.get('type') == 'fatal':
                report['pipeline_fatal'] = event['detail']
                if self.worker:
                    self.worker.control.cancel()
                return
            super().handle_event(event)
    window = QAWindow(cache_path=root / 'gui.sqlite3', persist_settings=False)
    pulse = QTimer()
    pulse.setInterval(10)
    pulse.timeout.connect(lambda: beats.append(time.monotonic()))
    pulse.start()
    (evidence / 'windows-online-quota-location.json').write_text(json.dumps({'root': str(root)}), encoding='utf-8')
    def until(predicate):
        if predicate():
            return
        loop = QEventLoop()
        poll = QTimer()
        poll.timeout.connect(lambda: loop.quit() if predicate() else None)
        poll.start(20)
        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.timeout.connect(loop.quit)
        deadline.start(90_000)
        loop.exec()
        poll.stop()
        deadline.stop()
        if not predicate():
            raise TimeoutError('GUI QA timeout')
    try:
        window.source.setText(str(source))
        window.output.setText(str(root / 'export'))
        window.language.setCurrentIndex(window.language.findData('zh'))
        window.mode.setCurrentText('Online Free')
        window.online_provider.setCurrentText('MyMemory')
        window.offline_provider.setCurrentText('Argos')
        window.show()
        # Keep isinstance checks valid with an actual provider subclass.
        class GUIProvider(MyMemoryProvider):
            def __init__(self, **kwargs):
                client = Mock()
                client.request.side_effect = request
                super().__init__(client=client, **kwargs)
        with patch('core.pipeline.MyMemoryProvider', GUIProvider):
            QTest.mouseClick(window.start_button, Qt.LeftButton)
            until(lambda: window.worker is not None and not window.worker.isRunning() and window.continue_button.isEnabled())
            assert window.provider_paused and len(requests_made) == 2
            assert len(window.provider_pending) == 1
            success = next(Path(p) for p in window.outputs.values())
            successful_hash = file_digest(success)
            window.grab().save(str(root / 'quota-notice.png'))
            QTest.mouseClick(window.provider_notice.dismiss, Qt.LeftButton)
            assert window.provider_paused and window.mode.currentText() == 'Online Free'
            window.mode.setCurrentText('Offline')
            QTest.mouseClick(window.continue_button, Qt.LeftButton)
            until(lambda: not window.worker.isRunning() and window.start_button.isEnabled())
            assert not window.failed and len(window.outputs) == 1
            assert file_digest(success) == successful_hash
            assert len(requests_made) == 2
            assert all(file_digest(Path(p)) == h for p,h in original.items())
            assert all(file_digest(Path(p)) == h for p,h in settings.items())
            assert not connections and len(beats) > 5
            report.update(status='PASS', requests=len(requests_made), online_provider_switched_automatically=False,
                          output_before_quota=1, offline_resume_outputs=1, original_output_unchanged=True,
                          settings_unchanged=True, network_attempts=connections, heartbeats=len(beats),
                          ocr_texts=requests_made, native_guard_unchanged=True)
    except Exception:
        report['failure'] = traceback.format_exc()
    finally:
        if window.worker and window.worker.isRunning():
            window.worker.control.cancel()
            until(lambda: not window.worker.isRunning())
        pulse.stop()
        window.close()
        faulthandler.cancel_dump_traceback_later()
        trace.close()
        (root / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main(Path(sys.argv[1]).resolve()))
