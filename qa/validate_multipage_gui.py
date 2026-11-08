"""Windows Qt restart/resume QA. Fake OCR/CLI/MT, real workers/cache/render/output."""
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch


def main():
    from core.runtime import prepare_inference_runtime
    prepare_inference_runtime()
    from core.paths import ROOT, CONFIG
    from core.storage import TranslationCache, file_digest
    from providers.agy import AGYProvider, MODE
    from tests.test_agy import RunnerFixture, envelope
    from tests.test_online_free import OCRFixture, OfflineFixture
    from ui.main_window import MainWindow
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QEventLoop, QTimer
    from PIL import Image
    root = ROOT/'output'/'stage3c-windows-gui'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    root.mkdir(parents=True)
    source = root/'source';source.mkdir()
    for n in (1,2,3): Image.new('RGB',(500,300),(n,n,n)).save(source/f'{n}.png')
    exe = root/'fake.exe';exe.write_bytes(b'NEVER EXECUTED')
    profile = {str(p):file_digest(p) for p in CONFIG.glob('*.json')}
    source_hashes = {str(p):file_digest(p) for p in source.glob('*.png')}
    fake = RunnerFixture()
    def runner(argv,payload,*args):
        if payload and len(fake.calls)==1:
            fake.failure = (1,envelope([],status='ERROR',error={'code':'RESOURCE_EXHAUSTED'}),b'')
        return fake(argv,payload,*args)
    with patch('providers.agy.check_automatic_extensions'):
        provider = AGYProvider(str(exe),root=root/'fake-cli',runner=runner)
    app = QApplication.instance() or QApplication([])
    beats = [0]
    timer = QTimer();timer.setInterval(20);timer.timeout.connect(lambda:beats.__setitem__(0,beats[0]+1));timer.start()
    def wait(window):
        loop = QEventLoop();deadline = QTimer();deadline.setSingleShot(True)
        deadline.timeout.connect(loop.quit);window.worker.finished.connect(loop.quit)
        deadline.start(60000);loop.exec()
        if window.worker.isRunning():
            window.worker.control.cancel();window.worker.wait(10000);raise RuntimeError('GUI QA timeout')
        app.processEvents()
    with patch('core.pipeline.AGYProvider',return_value=provider), \
            patch('core.pipeline.PaddleOCREngine',side_effect=OCRFixture), \
            patch('core.pipeline.create_offline_provider',return_value=OfflineFixture()):
        window = MainWindow(cache_path=root/'qa.sqlite3',persist_settings=False)
        window.show();window.source.setText(str(source));window.output.setText(str(root/'export'))
        window.options.agy_batch_regions=1;window.mode.setCurrentText(MODE)
        window.start();wait(window)
        assert window.provider_paused and len(window.provider_pending)==2
        identifier = window.resume_id
        window.provider_notice.dismiss.click()
        assert window.provider_paused and not window.worker.isRunning()
        from core.resume import ResumeStore
        store = ResumeStore(root/'qa.sqlite3');saved=store.read(identifier)
        first = saved['pages'][0];checksum=file_digest(Path(first['output']))
        with_cache = TranslationCache(root/'qa.sqlite3')
        receipt=with_cache.item(first['job_id'],first['path']);with_cache.close()
        window.close();app.processEvents()
        restored = MainWindow(cache_path=root/'qa.sqlite3',persist_settings=False)
        restored.show();restored.restore_previous();app.processEvents()
        assert restored.resume_id==identifier and restored.worker is None
        restored.mode.setCurrentText('Offline');restored.resume();wait(restored)
        assert store.read(identifier)['state']=='done'
        assert file_digest(Path(first['output']))==checksum
        with_cache=TranslationCache(root/'qa.sqlite3')
        assert with_cache.item(first['job_id'],first['path'])==receipt
        with_cache.close()
        restored.grab().save(str(root/'window.png'))
        restored.close()
    # Source jobs wrap pipeline events; exercise their multi-page event route too.
    from ui.comic_sources import ComicSourcesPanel
    from core.types import Options
    from sources.cache import ChapterCache
    source_fake = RunnerFixture()
    with patch('providers.agy.check_automatic_extensions'):
        source_provider = AGYProvider(str(exe),root=root/'source-cli',runner=source_fake)
    with patch('core.pipeline.AGYProvider',return_value=source_provider), \
            patch('sources.service.PaddleOCREngine',side_effect=OCRFixture), \
            patch('sources.service.ChapterCache',side_effect=lambda:ChapterCache(root/'source-cache')):
        panel=ComicSourcesPanel(Options(mode=MODE),fixed_kind=1,database=root/'source.sqlite3',
            settings_path=root/'source-settings.json')
        panel.show();panel.location.setText(str(source));panel.output.setText(str(root/'published'))
        panel.analyze_source();wait(panel);panel.check_all(True);panel.begin();wait(panel)
        assert panel.last_result['state']=='done' and panel.last_result['images_exported']==3
        assert len(source_fake.calls)==1
        panel.grab().save(str(root/'source-window.png'));panel.close()
    timer.stop()
    report=dict(status='PASS',platform=os.environ.get('QT_QPA_PLATFORM'),mocked_ocr_cli_mt=True,
        live_model_requests=0,fake_cli_requests=len(fake.calls),restart_restored=True,
        previous_output_receipt_unchanged=True,provider_switched_only_on_user_action=True,
        heartbeats=beats[0],settings_unchanged=all(file_digest(Path(p))==h for p,h in profile.items()),
        source_panel_multipage_export=True,source_fake_cli_requests=len(source_fake.calls),
        source_unchanged=all(file_digest(Path(p))==h for p,h in source_hashes.items()))
    assert report['settings_unchanged'] and report['source_unchanged'] and beats[0]>0
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(root=str(root),**report)))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
