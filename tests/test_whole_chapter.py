"""Synthetic local bitmaps and manual whole-response fixtures; never real AGY."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from tests.image_fixtures import provider_page
from core.paths import ROOT
from core.pipeline import JobControl, NUMBER_PATTERN
from core.storage import file_digest
from core.types import OCRResult, Options, CancelledError
from core.whole_chapter import (WholeChapterJob, MockWholeChapterTranslator, ChapterError,
    assemble_manifest, read_json, verify, seal, parse_response)


def complete(packet):
    return json.dumps(dict(manifest_hash=packet['manifest_hash'], translations=[
        dict(id=r['id'], text=r['text'].replace('你好', 'Xin chào')) for r in packet['regions']]), ensure_ascii=False)


class OCRFixture:
    def __init__(self, regions=1): self.calls = []; self.count = regions
    def identity(self, language): return 'whole-ocr-manual-v1'
    def recognize(self, image, *args):
        n = int(image[0, 0, 0]); self.calls.append(n)
        return [OCRResult(f'你好 {n}', [[10, 15+i*50], [260, 15+i*50],
            [260, 50+i*50], [10, 50+i*50]], .99, 'zh', i, i) for i in range(self.count)], []


class WholeChapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'output', prefix='stage3f-test-')
        self.root = Path(self.temp.name); self.source = self.root/'source'; self.source.mkdir()
        self.work = self.root/'run'; self.ocr = OCRFixture(); self.adapter = MockWholeChapterTranslator(complete)
        self.offline = patch('requests.sessions.Session.request', side_effect=AssertionError('NO NETWORK'))
        self.offline.start()

    def tearDown(self):
        self.offline.stop(); self.temp.cleanup()

    def images(self, count):
        for n in range(1, count+1): provider_page((300, 150),n).save(self.source/f'{n:04d}.png')

    def job(self, **kwargs):
        return WholeChapterJob(self.source, self.work, translator=self.adapter, ocr=self.ocr, **kwargs)

    def run_pages(self, count):
        self.images(count); result = self.job().run(allow_translation=True)
        self.assertEqual(result['state'], 'done', result)
        self.assertEqual(result['completed'], count)
        self.assertEqual(self.adapter.calls, 1)
        self.assertEqual(len(self.ocr.calls), count)
        manifest = read_json(self.work/'chapter-ocr-manifest.json')
        self.assertEqual([p['page']['index'] for p in manifest['pages']], list(range(1, count+1)))
        self.assertEqual(len(list((self.work/'rendered').glob('*.png'))), count)

    def test_1_page(self): self.run_pages(1)
    def test_16_pages(self): self.run_pages(16)
    def test_100_pages(self): self.run_pages(100)
    def test_120_pages(self): self.run_pages(120)

    def test_zero_ocr_original_bytes_not_translation(self):
        self.images(2); self.ocr.count = 0
        result = self.job().run(allow_translation=True)
        self.assertEqual(result['state'], 'done', result); self.assertEqual(self.adapter.calls, 0)
        self.assertEqual(result['regions'], 0)
        for path in (self.work/'rendered').glob('*.png'):
            self.assertEqual(file_digest(path), file_digest(self.source/(path.stem.split('.vi-')[0]+'.png')))

    def test_multiple_regions_unique_stable_ids_and_original_text(self):
        self.images(2); self.ocr.count = 2
        result = self.job().run(allow_translation=True); self.assertEqual(result['state'], 'done', result)
        before = read_json(self.work/'chapter-ocr-manifest.json')
        ids = [r['id'] for p in before['pages'] for r in p['regions']]
        self.assertEqual(len(set(ids)), 4)
        self.assertEqual(before['pages'][0]['raw_ocr']['regions'][0]['text'], '你好 1')
        result = self.job().run(); self.assertEqual(result['skipped'], 2, result)
        self.assertEqual(read_json(self.work/'chapter-ocr-manifest.json'), before)

    def invalid_response(self, transform):
        self.images(2)
        self.adapter.response_factory = lambda packet: transform(json.loads(complete(packet)))
        result = self.job().run(allow_translation=True)
        self.assertEqual(result['state'], 'blocked', result); self.assertEqual(self.adapter.calls, 1)
        self.assertFalse(self.work.joinpath('validated-translations.json').exists())
        self.assertFalse(self.work.joinpath('rendered').exists())
        return result

    def test_malformed_json(self): self.invalid_response(lambda data: '{broken')
    def test_truncated_json(self): self.invalid_response(lambda data: json.dumps(data)[:-8])
    def test_missing_id(self):
        self.invalid_response(lambda d: json.dumps(dict(d, translations=d['translations'][:-1])))
    def test_duplicate_id(self):
        self.invalid_response(lambda d: json.dumps(dict(d, translations=[d['translations'][0]]*2)))
    def test_unknown_id(self):
        self.invalid_response(lambda d: json.dumps(dict(d, translations=[dict(id='alien', text='Xin chào')]*2)))
    def test_empty_target(self):
        self.invalid_response(lambda d: json.dumps(dict(d, translations=[dict(r, text=' ') for r in d['translations']])))
    def test_numeric_rejected_no_render(self):
        result = self.invalid_response(lambda d: json.dumps(dict(d, translations=[dict(r, text='Xin chào 999') for r in d['translations']])))
        self.assertEqual(result['error_code'], 'NUMERIC_MISMATCH')

    def test_reversed_response_maps_correctly(self):
        self.adapter.response_factory = lambda p: json.dumps(dict(manifest_hash=p['manifest_hash'],
            translations=list(reversed(json.loads(complete(p))['translations']))))
        self.run_pages(3)
        accepted = read_json(self.work/'validated-translations.json')
        manifest = read_json(self.work/'chapter-ocr-manifest.json')
        for p in manifest['pages']:
            self.assertEqual(accepted['regions'][p['regions'][0]['id']]['target'], f"Xin chào {p['page']['index']}")

    def test_out_of_order_ocr_completion_manifest_order(self):
        self.images(3); self.job().run()
        manifest = read_json(self.work/'chapter-ocr-manifest.json')
        records = {p['page']['id']: p for p in reversed(manifest['pages'])}
        rebuilt = assemble_manifest(manifest['chapter_id'], [p['page'] for p in manifest['pages']], records, manifest['ocr_identity'])
        self.assertEqual(rebuilt, manifest)
        records.pop(next(iter(records)))
        with self.assertRaises(ChapterError):
            assemble_manifest(manifest['chapter_id'], [p['page'] for p in manifest['pages']], records, manifest['ocr_identity'])

    def test_manifest_duplicate_region_rejected(self):
        self.images(1); self.ocr.count = 2; self.job().run()
        data = read_json(self.work/'chapter-ocr-manifest.json'); row = data['pages'][0]
        row['regions'][1]['id'] = row['regions'][0]['id']
        with self.assertRaises(ChapterError):
            assemble_manifest(data['chapter_id'], [row['page']], {row['page']['id']: row}, data['ocr_identity'])

    def test_missing_source_during_resume(self):
        self.images(2); self.job().run(); (self.source/'0002.png').unlink()
        result = self.job().run(allow_translation=True)
        self.assertEqual(result['error_code'], 'WHOLE_RECIPE_OR_SOURCE_CHANGED'); self.assertEqual(self.adapter.calls, 0)

    def test_corrupt_page_never_calls_translation(self):
        self.images(2); (self.source/'0002.png').write_bytes(b'not a bitmap')
        self.assertEqual(self.job().run(allow_translation=True)['state'], 'blocked')
        self.assertEqual(self.adapter.calls, 0)

    def test_cancel_ocr_resume_without_reocr(self):
        self.images(3); control = JobControl()
        def event(e):
            if e.get('phase') == 'OCR' and e['completed'] == 1: control.cancel()
        self.assertEqual(self.job(control=control, emit=event).run()['state'], 'cancelled')
        self.assertEqual(self.ocr.calls, [1])
        self.assertEqual(self.job().run(allow_translation=True)['state'], 'done')
        self.assertEqual(self.ocr.calls, [1, 2, 3])

    def test_resume_does_not_implicitly_translate(self):
        self.images(2); first = self.job().run()
        self.assertEqual(first['state'], 'awaiting_translation')
        self.assertEqual(self.job().run()['state'], 'awaiting_translation')
        self.assertEqual(self.adapter.calls, 0); self.assertEqual(len(self.ocr.calls), 2)
        self.assertEqual(self.job().run(allow_translation=True)['state'], 'done')

    def test_resume_after_translation_before_render_no_retranslate(self):
        self.images(2); control = JobControl()
        def event(e):
            if e.get('phase') == 'RENDER': control.cancel()
        self.assertEqual(self.job(control=control, emit=event).run(allow_translation=True)['state'], 'cancelled')
        self.assertTrue(self.work.joinpath('validated-translations.json').exists())
        self.assertEqual(self.job().run()['state'], 'done'); self.assertEqual(self.adapter.calls, 1)

    def test_fresh_process_resume_validated_chapter_no_mt_or_ocr(self):
        self.images(2); control = JobControl()
        def event(e):
            if e.get('phase') == 'RENDER': control.cancel()
        self.job(control=control, emit=event).run(allow_translation=True)
        code = '''
import sys,json
def guard(event,args):
 if event in ('socket.connect','socket.getaddrinfo'):raise AssertionError('NO NETWORK')
sys.addaudithook(guard)
from core.runtime import prepare_inference_runtime
prepare_inference_runtime()
from tests.test_whole_chapter import OCRFixture
from core.whole_chapter import WholeChapterJob,MockWholeChapterTranslator
ocr=OCRFixture()
def fail(packet):raise AssertionError('NO REPLAY')
t=MockWholeChapterTranslator(fail)
r=WholeChapterJob(sys.argv[1],sys.argv[2],ocr=ocr,translator=t).run()
print('RESULT '+json.dumps(dict(state=r['state'],completed=r.get('completed'),ocr_calls=len(ocr.calls),mt_calls=t.calls)))
'''
        p = subprocess.run([sys.executable, '-c', code, str(self.source), str(self.work)], cwd=ROOT,
            capture_output=True, text=True, encoding='utf-8', timeout=90,
            env=dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONIOENCODING='utf-8'))
        self.assertEqual(p.returncode, 0, p.stderr)
        line = next(s for s in p.stdout.splitlines() if s.startswith('RESULT '))
        self.assertEqual(json.loads(line[7:]), dict(state='done', completed=2, ocr_calls=0, mt_calls=0))

    def test_crash_after_atomic_accepted_before_journal_commit_recovers(self):
        from sources.cache import atomic_json
        self.images(2)
        def crash(path, data):
            atomic_json(path, data)
            if path.name == 'validated-translations.json': raise SystemExit('simulated process death')
        with patch('sources.cache.atomic_json', side_effect=crash):
            with self.assertRaises(SystemExit): self.job().run(allow_translation=True)
        self.assertTrue((self.work/'validated-translations.json').exists())
        result = self.job().run()
        self.assertEqual(result['state'], 'done', result); self.assertEqual(self.adapter.calls, 1)

    def test_corrupt_output_receipt_does_not_overwrite(self):
        self.images(1); self.job().run(allow_translation=True)
        path = next((self.work/'rendered').glob('*.png')); path.write_bytes(b'USER DATA')
        result = self.job().run()
        self.assertEqual(result['state'], 'error', result)
        self.assertEqual(path.read_bytes(), b'USER DATA'); self.assertEqual(self.adapter.calls, 1)

    def test_glossary_uses_existing_marker_guard(self):
        self.images(1)
        self.adapter.response_factory = lambda p: json.dumps(dict(manifest_hash=p['manifest_hash'],
            translations=[dict(id=r['id'], text=r['text']) for r in p['regions']]))
        result = self.job(options=Options(glossary={'你好':'Xin chào'})).run(allow_translation=True)
        self.assertEqual(result['state'], 'done', result)
        value = next(iter(read_json(self.work/'validated-translations.json')['regions'].values()))
        self.assertEqual(value['target'], 'Xin chào 1'); self.assertIn('ZXQ', value['raw'])

    def test_missing_argos_model_blocks_without_network(self):
        from core.whole_chapter import ArgosWholeChapterTranslator
        self.images(1); translator = ArgosWholeChapterTranslator(); translator.provider.packages = {}
        result = WholeChapterJob(self.source,self.work,ocr=self.ocr,translator=translator).run(allow_translation=True)
        self.assertEqual(result['error_code'], 'MISSING_MODEL')
        self.assertFalse((self.work/'validated-translations.json').exists())

    def test_resume_partial_render_immutable_receipts(self):
        self.images(3); control = JobControl()
        def event(e):
            if e.get('stage') == 'Hoàn thành' and e['index'] == 1: control.cancel()
        self.assertEqual(self.job(control=control, emit=event).run(allow_translation=True)['state'], 'cancelled')
        exported = next((self.work/'rendered').glob('*.png')); before = file_digest(exported)
        journal = read_json(self.work/'chapter-journal.json')
        from core.resume import ResumeStore
        store = ResumeStore(self.work/'qa.sqlite3'); receipt = deepcopy(store.read(journal['render_resume_id'])['pages'][0])
        result = self.job().run(); self.assertEqual(result['state'], 'done', result)
        self.assertEqual(result['skipped'], 1); self.assertEqual(file_digest(exported), before)
        self.assertEqual(store.read(journal['render_resume_id'])['pages'][0], receipt)
        self.assertEqual(self.adapter.calls, 1)

    def test_timeout_no_auto_retry(self):
        self.images(2)
        def fail(packet): raise TimeoutError()
        self.adapter.response_factory = fail
        self.assertEqual(self.job().run(allow_translation=True)['error_code'], 'TimeoutError')
        self.assertEqual(self.job().run()['state'], 'awaiting_translation'); self.assertEqual(self.adapter.calls, 1)

    def test_manifest_changed_during_translation(self):
        self.images(2)
        def change(packet):
            data = read_json(self.work/'chapter-ocr-manifest.json'); data['chapter_id'] = 'tampered'
            (self.work/'chapter-ocr-manifest.json').write_text(json.dumps(seal({k:v for k,v in data.items() if k!='content_hash'})))
            return complete(packet)
        self.adapter.response_factory = change
        result = self.job().run(allow_translation=True)
        self.assertEqual(result['error_code'], 'WHOLE_MANIFEST_CHANGED')
        self.assertFalse((self.work/'validated-translations.json').exists())

    def test_source_changed_during_translation(self):
        self.images(2)
        def change(packet):
            Image.new('RGB', (300, 150), 'red').save(self.source/'0002.png'); return complete(packet)
        self.adapter.response_factory = change
        self.assertEqual(self.job().run(allow_translation=True)['error_code'], 'WHOLE_SOURCE_CHANGED')
        self.assertFalse((self.work/'validated-translations.json').exists())

    def test_source_changed_at_render_boundary_is_blocked(self):
        self.images(1)
        def event(e):
            if e.get('phase') == 'RENDER':
                path = self.source/'0001.png'
                with Image.open(path) as image:
                    image.putpixel((299,149), (40,40,40)); image.save(path)
        result = self.job(emit=event).run(allow_translation=True)
        self.assertEqual(result['error_code'], 'WHOLE_SOURCE_CHANGED')
        self.assertFalse((self.work/'rendered').exists())

    def test_manifest_changed_before_publication_never_publishes_translation(self):
        self.images(1)
        def event(e):
            if e.get('stage') == 'Đang lưu':
                path = self.work/'chapter-ocr-manifest.json'; data = read_json(path)
                data.pop('content_hash'); data['chapter_id'] = 'changed-before-publish'
                path.write_text(json.dumps(seal(data)), encoding='utf-8')
        result = self.job(emit=event).run(allow_translation=True)
        self.assertEqual(result['error_code'], 'WHOLE_MANIFEST_CHANGED')
        self.assertTrue(all('fallback-original' in p.name for p in (self.work/'rendered').glob('*.png')))
        self.assertFalse(list((self.work/'rendered').glob('*.part')))

    def test_accepted_changed_before_publication_never_used(self):
        self.images(1)
        def event(e):
            if e.get('stage') == 'Đang lưu':
                path = self.work/'validated-translations.json'; data = read_json(path)
                data.pop('content_hash'); next(iter(data['regions'].values()))['target'] = 'bad target 999'
                path.write_text(json.dumps(seal(data)), encoding='utf-8')
        result = self.job(emit=event).run(allow_translation=True)
        self.assertEqual(result['error_code'], 'WHOLE_TRANSLATION_RECEIPT_CHANGED')
        self.assertTrue(all('fallback-original' in p.name for p in (self.work/'rendered').glob('*.png')))

    def test_manifest_hash_wrong_response(self):
        self.invalid_response(lambda d: json.dumps(dict(d, manifest_hash='0'*64)))

    def test_accepted_result_tamper_rejected(self):
        self.images(1); self.job().run(allow_translation=True)
        p = self.work/'validated-translations.json'; data = read_json(p)
        next(iter(data['regions'].values()))['target'] = 'tampered'
        p.write_text(json.dumps(seal({k:v for k,v in data.items() if k!='content_hash'})))
        self.assertEqual(self.job().run()['error_code'], 'WHOLE_TRANSLATION_RECEIPT_CHANGED')

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ChapterError): parse_response('{"manifest_hash":1,"manifest_hash":2}', {}, set())

    def test_response_size_limit(self):
        with self.assertRaises(ChapterError): parse_response(' '*16000001, {}, set())

    def test_qa_workspace_and_offline_mode_forced(self):
        with self.assertRaises(ChapterError): WholeChapterJob(self.source, ROOT/'cache')
        options = Options(mode='AI Gemini API', allow_online_fallback=True)
        job = self.job(options=options)
        self.assertEqual(job.options.mode, 'Offline'); self.assertFalse(job.options.allow_online_fallback)
        self.assertEqual(options.mode, 'AI Gemini API')

    def test_one_active_whole_job(self):
        from core.whole_chapter import _active
        self.images(1)
        with _active:
            self.assertEqual(self.job().run(allow_translation=True)['error_code'], 'WHOLE_JOB_ACTIVE')
        self.assertEqual(self.adapter.calls, 0)

    def test_cancel_inside_mock_before_output(self):
        self.images(1); control = JobControl()
        def cancel(packet): control.cancel(); return complete(packet)
        self.adapter.response_factory = cancel
        self.assertEqual(self.job(control=control).run(allow_translation=True)['state'], 'cancelled')
        self.assertFalse((self.work/'validated-translations.json').exists())

    def test_guard_version_and_pattern_unchanged(self):
        from core.diagnostics import VALIDATOR_VERSION
        self.assertEqual(VALIDATOR_VERSION, 'literal-numbers-v2-signed')
        self.assertIn('[+\\-', NUMBER_PATTERN)


class WholeChapterQtTests(unittest.TestCase):
    def test_dialog_is_offline_and_does_not_start_on_open(self):
        from PySide6.QtWidgets import QApplication
        from ui.whole_chapter import WholeChapterDialog
        app = QApplication.instance() or QApplication([])
        with patch('ui.whole_chapter.WholeChapterWorker.start') as start:
            options = Options(mode='AI Gemini API')
            dialog = WholeChapterDialog(options); dialog.show(); app.processEvents()
            self.assertFalse(dialog.allow.isChecked()); self.assertFalse(dialog.resume.isEnabled())
            start.assert_not_called(); self.assertEqual(options.mode, 'AI Gemini API')
            dialog.close()

    def test_real_qthread_mock_pipeline_keeps_gui_responsive(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from ui.whole_chapter import WholeChapterDialog
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(dir=ROOT/'output', prefix='stage3f-gui-') as folder:
            root = Path(folder); source = root/'source'; source.mkdir()
            for n in range(1, 6): provider_page((300, 150),n).save(source/f'{n:04d}.png')
            class SlowOCR(OCRFixture):
                def recognize(self, *args):
                    time.sleep(.08)
                    return super().recognize(*args)
            adapter = MockWholeChapterTranslator(complete)
            def job(source, workspace, **kwargs):
                self.assertIsNone(kwargs.pop('translator', None))
                return WholeChapterJob(source, workspace, translator=adapter, ocr=SlowOCR(), **kwargs)
            dialog = WholeChapterDialog(Options(source=str(source)))
            dialog.workspace = root/'run'; dialog.allow.setChecked(True); dialog.show()
            ticks = []; timer = QTimer(); timer.timeout.connect(lambda:ticks.append(1)); timer.start(10)
            try:
                with patch('core.whole_chapter.WholeChapterJob', side_effect=job):
                    dialog.begin(); deadline = time.monotonic()+40
                    while dialog.worker.isRunning() and time.monotonic()<deadline:
                        app.processEvents(); time.sleep(.005)
                    self.assertFalse(dialog.worker.isRunning())
                    app.processEvents()
                self.assertGreaterEqual(len(ticks), 5)
                self.assertEqual(adapter.calls, 1)
                self.assertIn('done', dialog.status.text())
                self.assertEqual(dialog.progress.value(), 100)
                self.assertTrue(dialog.resume.isEnabled()); self.assertFalse(dialog.allow.isChecked())
            finally:
                if dialog.worker and dialog.worker.isRunning():
                    dialog.cancel_job(); dialog.worker.wait(30000)
                timer.stop(); dialog.close()
