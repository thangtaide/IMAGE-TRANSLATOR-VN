"""Windows GUI export from the successful real AGY QA cache; no new generation."""
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


def main(evidence: Path):
    from core.runtime import prepare_inference_runtime
    prepare_inference_runtime()
    from core.paths import ROOT, CONFIG
    from core.storage import file_digest
    from core.types import Options
    from providers.agy import AGYProvider, MODE, run_bounded
    from PySide6.QtCore import Qt, QTimer, QEventLoop
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow
    from PIL import Image

    previous = Path(json.loads((evidence / 'live-qa-location.json').read_text())['root'])
    live = json.loads((previous / 'report.json').read_text(encoding='utf-8'))
    assert live['status'] == 'REAL_AGY_OCR_TO_IMAGE_QA_PASS'
    root = ROOT / 'output' / 'agy-gui-cache-validation' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    root.mkdir(parents=True, exist_ok=False)
    cache = root / 'qa.sqlite3'
    with sqlite3.connect((previous / 'qa.sqlite3').resolve().as_uri()+'?mode=ro', uri=True) as src:
        with sqlite3.connect(cache) as dst:
            src.backup(dst)
    hashes = {str(p): file_digest(p) for p in (previous / 'source').glob('*.png')}
    settings = {str(p): file_digest(p) for p in CONFIG.glob('*.json')}
    calls = []
    def metadata_only(argv, payload, cwd, timeout, cancelled):
        if payload is not None:
            calls.append('BLOCKED_UNAUTHORIZED_GENERATION')
            raise AssertionError('This GUI cache replay must not generate any new AGY turn')
        return run_bounded(argv, payload, cwd, timeout, cancelled)
    class CachedAGY(AGYProvider):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, root=root / 'agy', runner=metadata_only)
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow(cache_path=cache, persist_settings=False)
    window.options = Options(mode=MODE, agy_max_requests=1)
    window.source.setText(str(previous / 'source'))
    window.output.setText(str(root / 'export'))
    window.language.setCurrentIndex(window.language.findData('zh'))
    window.mode.setCurrentText(MODE)
    window.offline_provider.setCurrentText('Argos')
    window.allow_fallback.setChecked(False)
    window.recursive.setChecked(True)
    window.structure.setChecked(True)
    window.show()
    report = {'status': 'FAIL', 'transport': 'CACHED_REAL_AGY_RESPONSE', 'new_model_requests': 0,
              'platform': os.environ.get('QT_QPA_PLATFORM'), 'provenance': str(previous)}
    beats = []
    pulse = QTimer()
    pulse.setInterval(20)
    pulse.timeout.connect(lambda: beats.append(1))
    pulse.start()
    try:
        with patch('core.pipeline.AGYProvider', CachedAGY):
            QTest.mouseClick(window.start_button, Qt.LeftButton)
            loop = QEventLoop()
            poll = QTimer()
            poll.setInterval(20)
            poll.timeout.connect(lambda: loop.quit() if window.worker and not window.worker.isRunning() else None)
            poll.start()
            deadline = QTimer()
            deadline.setSingleShot(True)
            deadline.timeout.connect(loop.quit)
            deadline.start(60_000)
            loop.exec()
            poll.stop()
            deadline.stop()
            app.processEvents()
            assert not window.worker.isRunning()
            assert not calls and not window.failed and len(window.outputs) == 1
            for output in window.outputs.values():
                with Image.open(output) as im:
                    assert im.size == (1600, 1000)
                    im.verify()
            assert all(file_digest(Path(p)) == h for p, h in hashes.items())
            assert all(file_digest(Path(p)) == h for p, h in settings.items())
            window.grab().save(str(root / 'window.png'))
            report.update(status='PASS', images_exported=1, source_unchanged=True,
                          settings_unchanged=True, heartbeats=len(beats), generation_attempts=calls)
    finally:
        pulse.stop()
        if window.worker and window.worker.isRunning():
            window.worker.control.cancel()
            window.worker.wait(10000)
        window.close()
        (root / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        (evidence / 'gui-cache-location.json').write_text(json.dumps({'root': str(root)}), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main(Path(sys.argv[1]).resolve()))
