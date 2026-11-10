"""Stage 1 contracts: mock inference, real bitmap/cache/publish/Qt behavior."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.diagnostics import DiagnosticLog, FALLBACK_ORIGINAL, TRANSLATED_SUCCESS, FAILED_NO_OUTPUT
from core.imaging import atomic_save
from core.pipeline import JobControl, ProcessingManager, TranslationService
from core.storage import TranslationCache, file_digest
from core.types import MissingModelError, Options
from tests.test_core import WorkspaceCase, FakeOCR, FakeProvider, region


class FallbackTests(WorkspaceCase):
    def manager_for(self, provider=None, ocr=None, options=None, events=None):
        manager = self.manager(options=options, provider=provider, ocr=ocr, events=events)
        manager.diagnostic_root = self.folder / 'diagnostics'
        return manager

    def numeric_failure(self):
        provider = Mock(online=False, identity='numeric-mock', engine_name='MockOffline')
        provider.translate.return_value = 'Ngày 21/5'
        return provider

    def test_numeric_error_records_raw_target_and_original_output(self):
        source = self.image()
        manager = self.manager_for(self.numeric_failure(), FakeOCR([region('5月20日')]))
        result = manager.run()
        self.assertEqual(result['state'], 'completed_with_warnings')
        self.assertEqual(result['translated_success'], 0)
        self.assertEqual(result['fallback_original'], 1)
        review = result['review_pages'][0]
        self.assertEqual(file_digest(Path(review['output_path'])), file_digest(source))
        self.assertFalse(manager.destination(source).exists())
        record = json.loads(Path(review['diagnostic_path']).read_text(encoding='utf-8'))
        self.assertEqual(record['raw_translated_target'], 'Ngày 21/5')
        self.assertEqual(record['source_numeric_tokens'], ['5', '20'])
        self.assertEqual(record['target_numeric_tokens'], ['21/5'])
        self.assertEqual(record['error_code'], 'NUMERIC_MISMATCH')
        self.assertEqual(record['stage'], 'VALIDATION')
        self.assertEqual(record['provider'], 'MockOffline')
        self.assertEqual(record['ocr_region_index'], 0)
        self.assertEqual(self.cache.item(manager.job_id, str(source))['status'], 'fallback_original')
        self.assertEqual(self.cache.connection.execute("SELECT count(*) FROM cache WHERE kind='translation'").fetchone()[0], 0)

    def test_failed_later_region_never_inpaints_any_region(self):
        source = self.image()
        provider = self.numeric_failure()
        provider.translate.side_effect = ['Xin chào', 'Ngày 21']
        manager = self.manager_for(provider, FakeOCR([region('你好'), region('第20日')]))
        with patch('core.pipeline.erase_text') as erase:
            result = manager.run()
        erase.assert_not_called()
        self.assertEqual(result['partial_translation'], 0)
        self.assertEqual(file_digest(Path(result['review_pages'][0]['output_path'])), file_digest(source))
        self.assertEqual(self.cache.connection.execute("SELECT count(*) FROM cache WHERE kind='translation'").fetchone()[0], 1)

    def test_retry_keeps_success_and_old_fallback_uses_cached_ocr(self):
        good, bad = self.image('1.png'), self.image('2.png')
        from PIL import Image
        with Image.open(bad) as image:
            image.putpixel((0, 0), (0, 0, 0, 255))
            image.save(bad)
        class PerImage(FakeOCR):
            def recognize(self, *args, **kwargs):
                self.calls += 1
                return [region('第' + str(self.calls) + '话')], []
        provider = Mock(online=False, identity='stable', engine_name='MockOffline')
        provider.translate.side_effect = ['Chương 1', 'Sai số']
        ocr = PerImage()
        manager = self.manager_for(provider, ocr)
        first = manager.run()
        completed = manager.destination(good)
        good_hash = file_digest(completed)
        fallback = Path(first['review_pages'][0]['output_path'])
        fallback_hash = file_digest(fallback)
        provider.translate.side_effect = None
        provider.translate.return_value = 'Chương 2'
        retry = self.manager_for(provider, ocr)
        second = retry.run(only=first['needs_retry'])
        self.assertEqual(second['total'], 1)
        self.assertEqual(second['completed'], 1)
        self.assertEqual(retry.job_id, manager.job_id)
        self.assertEqual(ocr.calls, 2)
        self.assertEqual(file_digest(completed), good_hash)
        self.assertEqual(file_digest(fallback), fallback_hash)
        self.assertEqual(self.cache.item(retry.job_id, str(bad))['status'], 'done')

    def test_corrupt_source_never_exports_fake_bitmap(self):
        (self.source / 'bad.png').write_bytes(b'not an image')
        result = self.manager_for().run()
        self.assertEqual(result['failed_no_output'], 1)
        self.assertEqual(result['files_exported'], 0)
        self.assertEqual(result['review_pages'][0]['output_status'], FAILED_NO_OUTPUT)

    def test_ocr_failure_exports_original(self):
        source = self.image()
        ocr = FakeOCR()
        ocr.recognize = Mock(side_effect=RuntimeError('OCR runtime error'))
        result = self.manager_for(ocr=ocr).run()
        self.assertEqual(result['fallback_original'], 1)
        self.assertEqual(result['review_pages'][0]['stage'], 'OCR')
        self.assertEqual(file_digest(source), file_digest(Path(result['review_pages'][0]['output_path'])))

    def test_missing_model_still_falls_back_valid_sources(self):
        self.image()
        ocr = FakeOCR()
        ocr.identity = Mock(side_effect=MissingModelError('Missing OCR model'))
        result = self.manager_for(ocr=ocr).run()
        self.assertEqual(result['fallback_original'], 1)
        self.assertEqual(result['review_pages'][0]['provider'], 'PaddleOCR')

    def test_render_failure_falls_back_source_not_erased_image(self):
        source = self.image()
        with patch('core.pipeline.TextRenderer.render', side_effect=RuntimeError('render failed')):
            result = self.manager_for().run()
        self.assertEqual(result['review_pages'][0]['stage'], 'RENDER')
        self.assertEqual(file_digest(Path(result['review_pages'][0]['output_path'])), file_digest(source))

    def test_inpaint_failure_falls_back(self):
        self.image()
        with patch('core.pipeline.erase_text', side_effect=RuntimeError('inpaint failed')):
            result = self.manager_for().run()
        self.assertEqual(result['fallback_original'], 1)
        self.assertEqual(result['review_pages'][0]['stage'], 'INPAINT')

    def test_export_failure_falls_back_when_other_file_can_be_written(self):
        self.image()
        with patch('core.pipeline.atomic_save', side_effect=OSError('write failed')):
            result = self.manager_for().run()
        self.assertEqual(result['fallback_original'], 1)
        self.assertEqual(result['review_pages'][0]['stage'], 'EXPORT')

    def test_fallback_write_failure_is_real_no_output(self):
        self.image()
        manager = self.manager_for(FakeProvider(fail=True))
        with patch.object(manager, 'fallback_original', side_effect=PermissionError('no permission')):
            result = manager.run()
        self.assertEqual(result['failed_no_output'], 1)
        self.assertEqual(result['fallback_original'], 0)
        self.assertIn('no permission', result['review_pages'][0]['fallback_error'])

    def test_modified_fallback_is_never_overwritten(self):
        self.image()
        first = self.manager_for(FakeProvider(fail=True)).run()
        output = Path(first['review_pages'][0]['output_path'])
        output.write_bytes(b'user data')
        second = self.manager_for(FakeProvider(fail=True)).run()
        self.assertEqual(second['failed_no_output'], 1)
        self.assertEqual(output.read_bytes(), b'user data')

    def test_logging_failure_does_not_prevent_fallback(self):
        self.image()
        with patch.object(DiagnosticLog, 'write', return_value=None):
            result = self.manager_for(FakeProvider(fail=True)).run()
        self.assertEqual(result['fallback_original'], 1)

    def test_sensitive_diagnostics_can_be_disabled_without_job_id_change(self):
        self.image()
        provider = self.numeric_failure()
        first = self.manager_for(provider, FakeOCR([region('第20日')]))
        first.run()
        second = self.manager_for(provider, FakeOCR(), self.options(diagnostic_text=False))
        result = second.run()
        self.assertEqual(first.job_id, second.job_id)
        record = json.loads(Path(result['review_pages'][0]['diagnostic_path']).read_text(encoding='utf-8').splitlines()[-1])
        self.assertIsNone(record['raw_translated_target'])
        self.assertIsNone(record['ocr_source_text'])
        self.assertIsNone(record['source_numeric_tokens'])

    def test_valid_success_is_preserved_and_skip_off_creates_a_new_result(self):
        source = self.image()
        manager = self.manager_for()
        manager.run()
        dest = manager.destination(source)
        before = (file_digest(dest), dest.stat().st_mtime_ns)
        result = self.manager_for(options=self.options(skip_success=False)).run()
        self.assertEqual(result['skipped'], 0)
        self.assertEqual(result['completed'], 1)
        self.assertEqual((file_digest(dest), dest.stat().st_mtime_ns), before)

    def test_atomic_save_no_clobber(self):
        from PIL import Image
        path = self.output / 'keep.png'
        path.parent.mkdir()
        path.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            atomic_save(Image.new('RGB', (10, 10)), path, overwrite=False)
        self.assertEqual(path.read_bytes(), b'keep')


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        from core.paths import ROOT
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'output', prefix='diag-unit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_redaction_limits_and_complete_json_line(self):
        log = DiagnosticLog('a'*64, root=self.root)
        path = log.write({'raw_translated_target': 'https://tn1.kkmh.com/a?sign=SECRET token=SECRET ' + 'x'*6000})
        data = Path(path).read_text(encoding='utf-8')
        self.assertNotIn('SECRET', data)
        self.assertLessEqual(len(json.loads(data)['raw_translated_target']), 2048)
        self.assertTrue(data.endswith('\n'))

    def test_torn_tail_preserved_and_new_file_used(self):
        log = DiagnosticLog('a'*64, root=self.root)
        log.directory.mkdir()
        log.path.write_bytes(b'{"incomplete":')
        old = log.path
        new = log.write({'error_code': 'TEST'})
        self.assertNotEqual(new, str(old))
        self.assertEqual(old.read_bytes(), b'{"incomplete":')
        self.assertEqual(json.loads(Path(new).read_text())['error_code'], 'TEST')

    def test_record_and_byte_caps(self):
        log = DiagnosticLog('a'*64, root=self.root, max_records=1)
        self.assertIsNotNone(log.write({'error_code': 'ONE'}))
        self.assertIsNone(log.write({'error_code': 'TWO'}))
        self.assertIn('limit', log.error)
        other = DiagnosticLog('b'*64, root=self.root, max_bytes=10)
        self.assertIsNone(other.write({'error_code': 'TOO LARGE'}))

    def test_unsafe_job_id_rejected(self):
        with self.assertRaises(ValueError):
            DiagnosticLog('../outside', root=self.root)


class ChapterFallbackTests(WorkspaceCase):
    def test_publish_conflict_preserves_user_file_and_exports_original_separately(self):
        from sources.collection import discover_local
        from sources.cache import ChapterCache
        from sources.service import LocalComicJob, publish_image
        source = self.image()
        comic, chapters = discover_local(self.source)
        conflicts = []
        def publish(src, target, control, size):
            if 'original' not in target.parts:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'USER DATA')
                conflicts.append(target)
            return publish_image(src, target, control, size)
        with patch('sources.service.publish_image', side_effect=publish), \
             patch('sources.service.PaddleOCREngine', return_value=FakeOCR([])), \
             patch('core.pipeline.create_offline_provider', return_value=FakeProvider()):
            result = LocalComicJob(comic, chapters, self.output, Options(),
                cache=ChapterCache(self.folder/'chapters'), database=self.folder/'job.sqlite3').run()
        self.assertEqual(result['state'], 'completed_with_warnings')
        self.assertEqual(result['translated_success'], 0)
        self.assertEqual(result['fallback_original'], 1)
        self.assertEqual(result['images_exported'], 1)
        self.assertEqual(conflicts[0].read_bytes(), b'USER DATA')
        self.assertEqual(file_digest(Path(result['outputs'][0])), file_digest(source))
        self.assertEqual(result['review_pages'][0]['stage'], 'EXPORT')

    def test_download_failure_record_has_known_index_and_no_signed_url(self):
        from sources.service import LocalComicJob
        from sources.cache import ChapterCache
        from sources.states import DownloadState
        from tests.test_source_tabs import FixtureAdapter
        source = self.image()
        adapter = FixtureAdapter(DownloadState.ALLOWED, source)
        comic = adapter.get_comic_info('https://fixture.example/topic')
        chapters = adapter.get_chapters(comic)
        def failure(*args):
            adapter.download_progress({'index': 2, 'stage': 'downloading'})
            raise RuntimeError('CDN https://tn1.kkmh.com/a.jpg?sign=SECRET')
        adapter.download_chapter = failure
        result = LocalComicJob(comic, chapters, self.output, Options(),
            cache=ChapterCache(self.folder / 'chapter'), database=self.folder / 'job.sqlite3', adapter=adapter).run()
        self.assertEqual(result['state'], 'errors')
        record = result['review_pages'][0]
        self.assertEqual(record['stage'], 'DOWNLOAD')
        self.assertEqual(record['image_index'], 2)
        self.assertIsNone(record['image_filename'])
        self.assertNotIn('SECRET', Path(record['diagnostic_path']).read_text(encoding='utf-8'))
        self.assertNotIn('SECRET', result['errors'][0]['detail'])

    def test_chapter_counts_retry_from_cache_preserve_success_and_fallback(self):
        from PIL import Image
        from sources.collection import discover_local
        from sources.cache import ChapterCache
        from sources.service import LocalComicJob
        self.image('1.png')
        second = self.image('2.png')
        with Image.open(second) as image:
            image.putpixel((0, 0), (0, 0, 0, 255))
            image.save(second)
        comic, chapters = discover_local(self.source)
        cache = ChapterCache(self.folder / 'chapters')
        provider = Mock(online=False, identity='mock-stable', engine_name='MockOffline')
        provider.translate.side_effect = ['Chương 1', 'Chương 21']
        class SequenceOCR(FakeOCR):
            def recognize(self, *args):
                self.calls += 1
                return [region('第1话' if self.calls == 1 else '第20话')], []
        ocr = SequenceOCR()
        kwargs = dict(comic=comic, chapters=chapters, output=self.output, options=Options(),
                      cache=cache, database=self.folder / 'comic.sqlite3', keep_cached=False)
        with patch('sources.service.PaddleOCREngine', return_value=ocr), patch('core.pipeline.create_offline_provider', return_value=provider):
            first = LocalComicJob(**kwargs).run()
            self.assertEqual(first['state'], 'completed_with_warnings')
            self.assertEqual(first['images_exported'], 2)
            self.assertEqual(first['translated_success'], 1)
            self.assertEqual(first['fallback_original'], 1)
            self.assertEqual(first['images_failed'], 0)
            self.assertEqual(first['chapters_completed'], 0)
            self.assertEqual(first['chapters_with_warnings'], 1)
            directory = cache.directory(comic, chapters[0])
            manifest = cache.read(directory)
            self.assertEqual(manifest['needs_retry'], [2])
            self.assertTrue(all((directory / p['file']).exists() for p in manifest['pages']))
            good_path = Path(manifest['pages'][0]['output'])
            fallback_path = Path(manifest['pages'][1]['output'])
            before = {str(p):file_digest(p) for p in (good_path, fallback_path)}
            provider.translate.side_effect = None
            provider.translate.return_value = 'Chương 20'
            # A web download implementation must never be touched in this retry branch.
            with patch('sources.service.ImageCollection.discover', side_effect=AssertionError('Do not rediscover sources')):
                retry = LocalComicJob(**dict(kwargs, retry_only=True, keep_cached=True)).run()
        self.assertEqual(retry['state'], 'done')
        self.assertEqual(retry['translated_success'], 2)
        self.assertEqual(ocr.calls, 2)
        self.assertEqual(provider.translate.call_count, 3)
        self.assertEqual(retry['chapters_completed'], 1)
        self.assertTrue(all(file_digest(Path(p)) == h for p,h in before.items()))
        updated = cache.read(directory)
        self.assertEqual(updated['needs_retry'], [])
        self.assertEqual(updated['pages'][1]['output_status'], TRANSLATED_SUCCESS)
        self.assertEqual(Path(updated['pages'][1]['output']).name, '0002.png')
        self.assertNotIn('original', Path(updated['pages'][1]['output']).parts)


class FallbackGUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from core.runtime import prepare_inference_runtime
        prepare_inference_runtime()
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_review_and_retry_only_request(self):
        from core.paths import ROOT
        from sources.collection import discover_local
        from ui.comic_sources import ComicSourcesPanel
        from sources.states import ProcessingState
        from PIL import Image
        with tempfile.TemporaryDirectory(dir=ROOT / 'output', prefix='fallback-gui-') as tmp:
            root = Path(tmp)
            Image.new('RGB', (30, 30), 'white').save(root / '1.png')
            comic, chapters = discover_local(root / '1.png')
            panel = ComicSourcesPanel(Options(), settings_path=root / 'preferences.json', fixed_kind=0)
            panel.handle_event(dict(type='collection', comic=comic, chapters=chapters))
            panel.failed_ids = {chapters[0].chapter_id}
            panel.handle_event(dict(type='job_finished', state='completed_with_warnings', images_total=1,
                images_exported=1, images_failed=0, translated_success=0, partial_translation=0,
                fallback_original=1, failed_no_output=0, skipped=0, chapters_completed=0,
                chapters_failed=0, errors=[], review_pages=[dict(image_filename='0001.png')]))
            self.assertEqual(panel.processing_state, ProcessingState.COMPLETED_WITH_WARNINGS)
            self.assertTrue(panel.review_button.isEnabled())
            self.assertIn('Dịch hoàn chỉnh: 0', panel.status.text())
            self.assertIn('Ảnh gốc dự phòng: 1', panel.status.text())
            with patch.object(panel, 'launch') as launch:
                panel.retry_failed()
                self.assertTrue(launch.call_args.args[1]['retry_only'])
            panel.close()

    def test_review_dialog_lists_error_and_log_metadata(self):
        from ui.review_dialog import ReviewDialog
        record = dict(image_index=111, image_filename='0111.jpg', stage='VALIDATION', provider='Argos',
                      error_code='NUMERIC_MISMATCH', output_status=FALLBACK_ORIGINAL,
                      error_message='Cần xem lại', diagnostic_path=None)
        dialog = ReviewDialog([record])
        dialog.show()
        self.app.processEvents()
        self.assertEqual(dialog.table.item(0, 1).text(), '0111.jpg')
        self.assertEqual(dialog.table.item(0, 3).text(), 'Argos')
        self.assertEqual(dialog.table.item(0, 4).text(), 'NUMERIC_MISMATCH')
        self.assertFalse(dialog.open_log.isEnabled())
        dialog.close()
