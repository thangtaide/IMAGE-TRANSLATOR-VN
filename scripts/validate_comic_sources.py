"""Real Qt/QThread + real local comic pages + original offline inference.

No website image is downloaded. No OCR/translation text is supplied by this test.
All fixtures/evidence are separate copies under output/comic-source-validation.
"""
from __future__ import annotations

import json
import faulthandler
import os
import shutil
import sqlite3
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import ROOT
from core.storage import configure_logging, file_digest


def main() -> int:
    from core.runtime import prepare_inference_runtime
    prepare_inference_runtime()
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtCore import QEventLoop, QTimer, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from core.types import Options
    from sources.cache import ChapterCache, inspect_image
    from ui.comic_sources import ComicSourcesDialog
    from ui.fonts import configure_ui_font
    from ui.main_window import MainWindow
    from scripts.qa_common import source_fingerprint

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:6]
    folder = ROOT / 'output' / 'comic-source-validation' / stamp
    folder.mkdir(parents=True, exist_ok=False)
    stack_log = (folder / 'runtime-stacks.log').open('w', encoding='utf-8')
    faulthandler.dump_traceback_later(60, repeat=True, file=stack_log)
    report = {'mock': False, 'website_downloads': 0, 'overall': 'FAIL', 'checks': {},
              'platform': os.environ.get('QT_QPA_PLATFORM'), 'evidence': str(folder),
              'source_fingerprint': source_fingerprint()}
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    configure_ui_font()
    beat = [0]
    timer = QTimer()
    timer.setInterval(20)
    timer.timeout.connect(lambda: beat.__setitem__(0, beat[0] + 1))
    timer.start()
    dialog = None
    main_window = None
    events = []
    network_attempts = []

    def audit(event, args):
        if event == 'socket.connect':
            network_attempts.append(str(args[1]))
            raise RuntimeError('OFFLINE QA: network connection forbidden')

    sys.addaudithook(audit)

    def record_event(event):
        events.append(event)
        with (folder / 'events-live.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + '\n')

    def wait_until(condition, timeout=240):
        if condition():
            return
        loop = QEventLoop()
        pulse = QTimer()
        pulse.setInterval(20)
        pulse.timeout.connect(lambda: loop.quit() if condition() else None)
        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.timeout.connect(loop.quit)
        pulse.start()
        deadline.start(timeout * 1000)
        loop.exec()
        pulse.stop()
        deadline.stop()
        if not condition():
            raise TimeoutError('Qt chapter workflow timeout')

    try:
        # Select TWO actual user-supplied pages whose previous real OCR found letters.
        # Selection uses prior evidence only to avoid empty pages, never as inference input.
        inventory = ROOT / 'output' / 'real-image-validation-20261106-numeric-fix'
        samples = []
        if inventory.is_dir():
            for path in sorted(inventory.glob('image-*/report.json')):
                data = json.loads(path.read_text(encoding='utf-8'))
                source = data.get('source') or data.get('original_source')
                if isinstance(source, str) and Path(source).is_file():
                    samples.append(Path(source))
                if len(samples) == 2:
                    break
        if len(samples) < 2:
            samples = sorted((ROOT / 'ImgTest').glob('*.jpg'))[:2]
        if len(samples) < 2:
            raise FileNotFoundError('Need two user-supplied real pages in ImgTest; not replacing with mock images.')
        before = {str(p): file_digest(p) for p in samples}
        report['source_kind'] = 'real user supplied comic pages (not verified as Kuaikan provenance)'
        report['originals'] = before
        book = folder / 'nguồn truyện có dấu'
        for index, sample in enumerate(samples):
            chapter = book / ('Chapter2' if index == 0 else 'Chapter10')
            chapter.mkdir(parents=True)
            shutil.copy2(sample, chapter / ('1' + sample.suffix))

        main_window = MainWindow(cache_path=folder / 'main-qa.sqlite3', persist_settings=False)
        main_window.show()
        report['checks']['embedded_source_tabs'] = main_window.source_tabs.count() == 3
        dialog = ComicSourcesDialog(Options(mode='Offline', language='zh', output_format='png'),
                                    main_window, settings_path=folder / 'source-settings.json',
                                    database=folder / 'pipeline-qa.sqlite3')
        dialog.show()
        dialog.location.setText(str(book))
        QTest.mouseClick(dialog.analyze, Qt.LeftButton)
        wait_until(lambda: not dialog.busy)
        assert [c.chapter_title for c in dialog.chapters] == ['Chapter2', 'Chapter10']
        assert len(dialog.selected()) == 0 and not dialog.start.isEnabled()
        report['checks']['analyze_without_auto_selection'] = True
        QTest.mouseClick(dialog.select_all, Qt.LeftButton)
        assert len(dialog.selected()) == 2
        dialog.output.setText(str(folder / 'translated'))
        QTest.mouseClick(dialog.start, Qt.LeftButton)
        dialog.worker.event.connect(record_event)
        QTest.mouseClick(dialog.pause, Qt.LeftButton)
        QTest.qWait(180)
        assert dialog.worker.control.paused and dialog.resume.isEnabled()
        report['checks']['pause_safe_checkpoint'] = True
        QTest.mouseClick(dialog.resume, Qt.LeftButton)
        wait_until(lambda: not dialog.busy)
        assert dialog.last_result and dialog.last_result['state'] == 'done', dialog.last_result
        assert dialog.last_result['images_exported'] == 2
        assert dialog.progress.value() == 1000
        report['first_run'] = dialog.last_result
        report['checks']['real_chapter_offline_export'] = True
        first_outputs = dialog.last_result['outputs'][:]
        first_hashes = {p: file_digest(Path(p)) for p in first_outputs}
        first_worker = dialog.worker

        # New worker, same recipe: genuine checkpoints should skip successful pages.
        QTest.mouseClick(dialog.start, Qt.LeftButton)
        dialog.worker.event.connect(record_event)
        assert dialog.worker is not first_worker
        wait_until(lambda: not dialog.busy)
        assert dialog.last_result['state'] == 'done'
        assert any(event.get('stage') == 'Bỏ qua' for event in events)
        assert all(file_digest(Path(p)) == sha for p, sha in first_hashes.items())
        report['checks']['new_worker_resume_uses_checkpoint'] = True

        # Cancel immediately while paused; retry uses the same selected chapters/cache.
        QTest.mouseClick(dialog.start, Qt.LeftButton)
        QTest.mouseClick(dialog.pause, Qt.LeftButton)
        QTest.mouseClick(dialog.cancel, Qt.LeftButton)
        wait_until(lambda: not dialog.busy)
        assert dialog.last_result['state'] == 'cancelled', dialog.last_result
        assert dialog.retry.isEnabled()
        QTest.mouseClick(dialog.retry, Qt.LeftButton)
        wait_until(lambda: not dialog.busy)
        assert dialog.last_result['state'] == 'done', dialog.last_result
        report['checks']['cancel_retry_preserves_results'] = True

        # Retain chapter manifests and actual OCR/translation data as JSON evidence.
        database = sqlite3.connect(folder / 'pipeline-qa.sqlite3')
        actual_regions = actual_translations = 0
        for chapter in dialog.chapters:
            cache = ChapterCache()
            directory = cache.directory(dialog.comic, chapter)
            manifest = cache.read(directory)
            shutil.copy2(directory / 'manifest.json', folder / ('chapter-' + chapter.chapter_id + '.json'))
            page = manifest['pages'][0]
            item = database.execute('SELECT fingerprint FROM items WHERE job=? AND path=?',
                                    (page['pipeline_job_id'], str(directory / page['file']))).fetchone()
            assert item
            raw = database.execute("SELECT value FROM cache WHERE kind='metadata' AND key=?", (item[0],)).fetchone()
            assert raw
            metadata = json.loads(raw[0])
            (folder / ('ocr-translation-' + chapter.chapter_id + '.json')).write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
            actual_regions += len(metadata['regions'])
            actual_translations += len(metadata['translations'])
            info = inspect_image(Path(page['output']))
            assert (info['width'], info['height']) == (page['width'], page['height'])
        database.close()
        report['actual_ocr_regions'] = actual_regions
        report['actual_translations'] = actual_translations
        assert actual_regions > 0 and actual_translations > 0, 'Selected real pages contained no translated text'
        report['checks']['dimensions_order_and_inference_evidence'] = True
        assert all(file_digest(Path(p)) == sha for p, sha in before.items())
        assert not network_attempts
        report['checks']['source_integrity_and_no_network'] = True
        report['checks']['heartbeat_responsive'] = beat[0] > 10
        dialog.grab().save(str(folder / 'chapter-dialog.png'))

        # Exercise the single-file source UI too, with the same original pipeline.
        dialog.kind.setCurrentIndex(0)
        dialog.location.setText(str(samples[0]))
        QTest.mouseClick(dialog.analyze, Qt.LeftButton)
        wait_until(lambda: not dialog.busy)
        assert len(dialog.chapters) == 1 and dialog.chapters[0].image_count == 1
        QTest.mouseClick(dialog.select_all, Qt.LeftButton)
        dialog.output.setText(str(folder / 'single-image-translated'))
        QTest.mouseClick(dialog.start, Qt.LeftButton)
        wait_until(lambda: not dialog.busy)
        assert dialog.last_result['state'] == 'done' and dialog.last_result['images_exported'] == 1, dialog.last_result
        report['checks']['single_image_gui_offline'] = True

        # Validate domain errors in an actual QThread; no real HTTP is needed.
        dialog.kind.setCurrentIndex(2)
        dialog.location.setText('https://example.org/web/topic/1/')
        QTest.mouseClick(dialog.analyze, Qt.LeftButton)
        wait_until(lambda: not dialog.busy)
        assert 'website' in dialog.status.text() and not dialog.download.isEnabled()
        report['checks']['unsupported_website_gui_error'] = True
        if os.environ.get('CODEX_SANDBOX_NETWORK_DISABLED') == '1':
            dialog.location.setText('https://www.kuaikanmanhua.com/web/topic/6677/')
            QTest.mouseClick(dialog.analyze, Qt.LeftButton)
            wait_until(lambda: not dialog.busy)
            assert 'network' in dialog.status.text() and dialog.table.rowCount() == 0
            assert not network_attempts
            report['checks']['managed_network_limit_reported_without_bypass'] = True
            dialog.grab().save(str(folder / 'url-access-status.png'))
        report['overall'] = 'PASS' if all(report['checks'].values()) else 'FAIL'
    except Exception:
        report['failure'] = traceback.format_exc()
    finally:
        if dialog and dialog.worker and dialog.worker.isRunning():
            dialog.worker.control.cancel()
            try:
                wait_until(lambda: not dialog.worker.isRunning(), timeout=90)
            except TimeoutError:
                report['shutdown'] = 'FAIL: worker did not stop within deadline'
                report['overall'] = 'FAIL'
        if dialog:
            dialog.close()
        if main_window:
            main_window.close()
        report['heartbeats'] = beat[0]
        report['network_attempts'] = network_attempts
        faulthandler.cancel_dump_traceback_later()
        stack_log.close()
        (folder / 'events.json').write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding='utf-8')
        (folder / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'overall': report['overall'], 'evidence': str(folder), 'failure': report.get('failure')}, ensure_ascii=False))
    return 0 if report['overall'] == 'PASS' else 1


if __name__ == '__main__':
    configure_logging()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    raise SystemExit(main())
