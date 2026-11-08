"""Real MainWindow tabs + OCR/Offline inference; no mock widgets or translations.

Website metadata/chapter success is NOT asserted when networking is restricted.
Run with --validate-source-tabs from main/EXE to validate the same packaged UI.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    from core.paths import CONFIG, ROOT
    from core.runtime import prepare_inference_runtime
    prepare_inference_runtime()
    from core.storage import file_digest
    from scripts.qa_common import source_fingerprint
    from sources.states import AnalysisState
    from PySide6.QtCore import QEventLoop, QTimer, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog
    from ui.main_window import MainWindow

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:6]
    folder = ROOT / 'output' / 'source-tabs-validation' / stamp
    folder.mkdir(parents=True, exist_ok=False)
    report = {'mock': False, 'overall': 'FAIL', 'checks': {}, 'evidence': str(folder),
              'source_fingerprint': source_fingerprint(), 'frozen': bool(getattr(sys, 'frozen', False)),
              'website_downloads': 0, 'platform': os.environ.get('QT_QPA_PLATFORM', 'windows')}
    preferences = {p: p.read_bytes() for p in CONFIG.glob('*.json')}
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    window = None
    beats = [0]
    timer = QTimer()
    timer.setInterval(20)
    timer.timeout.connect(lambda: beats.__setitem__(0, beats[0] + 1))
    timer.start()
    connections = []

    def network_audit(event, args):
        if event == 'socket.connect':
            connections.append(str(args[1]))
            raise RuntimeError('Offline validation forbids socket connections')

    sys.addaudithook(network_audit)

    def wait_until(condition, seconds=180):
        if condition():
            return
        loop = QEventLoop()
        pulse = QTimer()
        pulse.timeout.connect(lambda: loop.quit() if condition() else None)
        pulse.start(20)
        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.timeout.connect(loop.quit)
        deadline.start(seconds * 1000)
        loop.exec()
        pulse.stop()
        deadline.stop()
        if not condition():
            raise TimeoutError('Source tab validation timed out')

    try:
        source = sorted((ROOT / 'ImgTest').glob('*.jpg'))[0]
        report['source'] = str(source)
        source_hash = file_digest(source)
        inputs = folder / 'input'
        inputs.mkdir()
        copied = inputs / 'ảnh nguồn.jpg'
        shutil.copy2(source, copied)
        window = MainWindow(cache_path=folder / 'qa.sqlite3', persist_settings=False)
        window.options.output_format = 'png'
        window.language.setCurrentIndex(window.language.findData('zh'))
        window.offline_provider.setCurrentText('Argos')
        window.mode.setCurrentText('Offline')
        window.show()
        assert window.source_tabs.count() == 3
        assert not any(w.isVisible() for w in QApplication.topLevelWidgets() if isinstance(w, QDialog))
        report['checks']['three_tabs_no_source_dialog'] = True

        window.source_tabs.setCurrentIndex(0)
        panel = window.image_panel
        panel.settings_path = folder / 'single-preferences.json'
        panel.location.setText(str(copied))
        panel.output.setText(str(folder / 'single-translated'))
        QTest.mouseClick(panel.analyze, Qt.LeftButton)
        wait_until(lambda: not panel.busy)
        assert len(panel.selected()) == 1 and panel.start.isEnabled()
        assert not window.url_panel.isVisible() and not window.folder_page.isVisible()
        QTest.mouseClick(panel.start, Qt.LeftButton)
        # Pause immediately and check UI exclusion while the real QThread is running.
        QTest.mouseClick(panel.pause, Qt.LeftButton)
        assert panel.worker.control.paused
        assert not window.source_tabs.tabBar().isEnabled()
        QTimer.singleShot(150, lambda: QTest.mouseClick(panel.resume, Qt.LeftButton))
        wait_until(lambda: not panel.busy)
        assert panel.last_result['state'] == 'done', panel.last_result
        assert panel.last_result['images_exported'] == 1
        report['single_result'] = panel.last_result
        report['checks']['single_real_offline_pause_resume'] = True
        window.grab().save(str(folder / 'single-tab.png'))

        database = sqlite3.connect(folder / 'qa.sqlite3')
        metadata = [json.loads(row[0]) for row in database.execute("SELECT value FROM cache WHERE kind='metadata'")]
        database.close()
        regions = sum(len(value['regions']) for value in metadata)
        translations = sum(len(value['translations']) for value in metadata)
        assert regions and translations, 'No text translated from the supplied comic page'
        report['actual_ocr_regions'] = regions
        report['actual_translations'] = translations
        (folder / 'ocr-translation.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')

        window.source_tabs.setCurrentIndex(1)
        window.source.setText(str(inputs))
        window.output.setText(str(folder / 'folder-translated'))
        QTest.mouseClick(window.start_button, Qt.LeftButton)
        wait_until(lambda: window.worker and not window.worker.isRunning())
        app.processEvents()
        assert len(window.outputs) == 1 and not window.failed
        assert window.progress.value() == 1000
        report['checks']['folder_real_pipeline_preserved'] = True
        window.grab().save(str(folder / 'folder-tab.png'))

        window.source_tabs.setCurrentIndex(2)
        panel = window.url_panel
        panel.settings_path = folder / 'url-preferences.json'
        panel.location.setText('not-a-url')
        QTest.mouseClick(panel.analyze, Qt.LeftButton)
        wait_until(lambda: not panel.busy)
        assert panel.analysis_state == AnalysisState.URL_INVALID
        assert panel.analyze.isEnabled()
        report['checks']['invalid_url_retry_available'] = True
        if os.environ.get('CODEX_SANDBOX_NETWORK_DISABLED') == '1':
            panel.location.setText('https://www.kuaikanmanhua.com/web/topic/6677/')
            QTest.mouseClick(panel.analyze, Qt.LeftButton)
            wait_until(lambda: not panel.busy)
            assert panel.analysis_state == AnalysisState.CONNECTION_ERROR
            assert panel.last_error_category == 'network'
            assert panel.analyze.isEnabled() and not panel.download.isEnabled()
            report['checks']['connection_failure_not_permission_failure'] = True
        else:
            report['live_metadata'] = 'NOT TESTED (offline validation; separate permitted live run needed)'
        assert not window.folder_page.isVisible() and not window.image_panel.isVisible()
        window.grab().save(str(folder / 'url-tab.png'))
        window.resize(680, 500)
        app.processEvents()
        assert window.centralWidget().verticalScrollBar().maximum() > 0
        report['checks']['small_window_scroll'] = True
        assert file_digest(source) == source_hash and file_digest(copied) == source_hash
        assert not connections
        report['checks']['original_unchanged_no_network'] = True
        assert beats[0] > 10
        report['checks']['responsive_gui'] = True
        report['overall'] = 'PASS'
    except Exception:
        report['failure'] = traceback.format_exc()
    finally:
        if window:
            for worker in (window.worker, window.image_panel.worker, window.url_panel.worker):
                if worker and worker.isRunning():
                    worker.control.cancel()
                    wait_until(lambda: not worker.isRunning(), seconds=90)
            window.close()
        report['preferences_unchanged'] = all(p.is_file() and p.read_bytes() == value for p, value in preferences.items())
        if not report['preferences_unchanged']:
            report['overall'] = 'FAIL'
        report['heartbeats'] = beats[0]
        report['network_attempts'] = connections
        (folder / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'overall': report['overall'], 'evidence': str(folder), 'failure': report.get('failure')}, ensure_ascii=False))
    return 0 if report['overall'] == 'PASS' else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    raise SystemExit(main())
