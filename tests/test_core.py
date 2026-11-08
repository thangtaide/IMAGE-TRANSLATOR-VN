from __future__ import annotations

import io
import json
import socket
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont

from core.imaging import TextRenderer, atomic_save, build_mask, default_font, erase_text, open_image
from core.models import extract_archive, safe_member, verify_installation
from core.ocr import PaddleOCREngine, deduplicate, group_lines, local_models_only, reading_order
from core.paths import ROOT
from core.pipeline import JobControl, ProcessingManager, TranslationService, scan_images
from core.storage import TranslationCache, atomic_json, digest, file_digest
from core.types import CancelledError, LayoutError, MissingModelError, OCRResult, Options
from providers.offline import ArgosTranslationProvider
from providers.online import LibreTranslateProvider, MyMemoryProvider, ProviderError


def region(text='Hello world', box=(25, 25, 450, 125), language='en'):
    x0, y0, x1, y1 = box
    return OCRResult(text, [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], .99, language)


class FakeOCR:
    """Unit-test fixture; never used by production code or real integration tests."""
    def __init__(self, regions=None):
        self.calls = 0
        self.regions = [region()] if regions is None else regions

    def identity(self, language):
        return 'UNIT-TEST-OCR'

    def recognize(self, *args):
        self.calls += 1
        return self.regions, []


class FakeProvider:
    online = False
    identity = 'UNIT-TEST-TRANSLATOR'

    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def translate(self, text, source, target='vi'):
        self.calls += 1
        if self.fail:
            raise ProviderError('UNIT-TEST provider failure')
        return text.replace('Hello world', 'Xin chào thế giới').replace('Hello', 'Xin chào')


class WorkspaceCase(unittest.TestCase):
    def setUp(self):
        base = ROOT / 'output' / 'test-runs'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.folder = Path(self.temp.name)
        self.source = self.folder / 'nguồn ảnh có dấu'
        self.source.mkdir()
        self.output = self.folder / 'kết quả'
        self.cache = TranslationCache(self.folder / 'state.sqlite3')

    def tearDown(self):
        self.cache.close()
        self.temp.cleanup()

    def image(self, name='1.png', mode='RGBA'):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new(mode, (480, 160), (255, 255, 255, 190) if mode == 'RGBA' else 'white')
        draw = ImageDraw.Draw(image)
        draw.text((32, 40), 'Hello world', fill='black', font=ImageFont.truetype(str(default_font()), 28))
        image.save(path)
        return path

    def options(self, **kwargs):
        return Options(source=str(self.source), output=str(self.output), language='en', **kwargs)

    def manager(self, options=None, provider=None, ocr=None, control=None, events=None):
        options = options or self.options()
        control = control or JobControl()
        service = TranslationService(options, self.cache, control, offline=provider or FakeProvider())
        return ProcessingManager(options, self.cache, control, (events.append if events is not None else lambda _: None),
                                 ocr or FakeOCR(), service)


class FilesAndStorageTests(WorkspaceCase):
    def test_unicode_natural_scan_and_output_exclusion(self):
        for name in ['10.png', '2.png', '1.png', 'thư mục/3.png']:
            self.image(name)
        self.assertEqual([p.name for p in scan_images(self.source, False)], ['1.png', '2.png', '10.png'])
        self.assertEqual(len(scan_images(self.source, True)), 4)
        nested_output = self.source / 'export'
        nested_output.mkdir()
        Image.new('RGB', (10, 10)).save(nested_output / 'skip.png')
        self.assertEqual(len(scan_images(self.source, True, nested_output)), 4)

    def test_missing_folder(self):
        with self.assertRaises(FileNotFoundError):
            scan_images(self.folder / 'missing', True)

    def test_cache_unicode_and_identity(self):
        first = digest(['你好', 'zh', 'vi', 'providerA', {'张三': 'Trương Tam'}])
        self.cache.put('translation', first, 'Xin chào')
        self.assertEqual(self.cache.get('translation', first), 'Xin chào')
        self.assertIsNone(self.cache.get('translation', digest(['你好', 'providerB'])))

    def test_checkpoint_persistence(self):
        opts = self.options()
        self.cache.job('a', opts, 'cancelled')
        self.cache.checkpoint('a', 'tệp.png', 'done', 'kết quả.png', 'hash')
        another = TranslationCache(self.folder / 'state.sqlite3')
        try:
            self.assertEqual(another.pending_job().source, opts.source)
            self.assertEqual(another.item('a', 'tệp.png')['status'], 'done')
        finally:
            another.close()

    def test_atomic_json(self):
        path = self.folder / 'cấu hình.json'
        atomic_json(path, {'a': 'Việt'})
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'a': 'Việt'})
        self.assertFalse(path.with_suffix('.json.tmp').exists())

    def test_forbid_source_overwrite_and_output_escape(self):
        self.image()
        for target in [self.source, ROOT.parent / 'unsafe-export', ROOT / 'models/unsafe']:
            opts = self.options()
            opts.output = str(target)
            with self.assertRaises(ValueError):
                self.manager(opts).validate()


class ImagingTests(WorkspaceCase):
    def test_inpaint_glyph_mask_is_local(self):
        image = open_image(self.image())
        rgb = np.array(image.convert('RGB'))
        mask = build_mask(rgb, [region()])
        self.assertGreater(np.count_nonzero(mask), 20)
        self.assertLess(np.count_nonzero(mask), 425*100/2)
        self.assertTrue(np.all(mask[140:, :] == 0))
        restored = erase_text(image, [region()], self.options())
        self.assertEqual(restored.size, image.size)
        self.assertTrue(np.array_equal(np.array(restored.getchannel('A')), np.array(image.getchannel('A'))))
        self.assertTrue(np.array_equal(np.array(restored)[140:], np.array(image)[140:]))

    def test_no_regions_keeps_pixels(self):
        image = open_image(self.image())
        self.assertTrue(np.array_equal(np.array(image), np.array(erase_text(image, [], self.options()))))

    def test_vietnamese_render_and_png_alpha(self):
        image = open_image(self.image())
        rendered = TextRenderer(self.options()).render(image, [region()], ['Tiếng Việt: Nguyễn Ánh, ạ ễ ự'])
        self.assertFalse(np.array_equal(np.array(image), np.array(rendered)))
        target = self.folder / 'xuất ảnh.png'
        atomic_save(rendered, target)
        reopened = open_image(target)
        self.assertEqual(reopened.size, (480, 160))
        self.assertEqual(reopened.mode, 'RGBA')
        self.assertTrue(np.array_equal(np.array(image.getchannel('A')), np.array(reopened.getchannel('A'))))

    def test_text_overflow_raises_without_truncating(self):
        image = Image.new('RGB', (20, 20), 'white')
        with self.assertRaises(LayoutError):
            TextRenderer(self.options()).render(image, [region(box=(1, 1, 4, 4))], ['Không được cắt mất chữ Việt'])

    def test_jpeg_and_webp_outputs(self):
        image = open_image(self.image())
        for extension in ['jpg', 'webp', 'bmp']:
            target = self.folder / f'kết quả.{extension}'
            warnings = atomic_save(image, target, 90)
            self.assertEqual(open_image(target).size, image.size)
            if extension != 'webp':
                self.assertTrue(warnings)

    def test_save_failure_cleans_temp(self):
        with patch('core.imaging.os.replace', side_effect=PermissionError('UNIT-TEST')):
            with self.assertRaises(PermissionError):
                atomic_save(Image.new('RGB', (20, 20)), self.folder / 'target.png')
        self.assertFalse(list(self.folder.glob('.itvn-*')))

    def test_custom_mask_size_error(self):
        mask = self.folder / 'mask.png'
        Image.new('L', (2, 2)).save(mask)
        opts = self.options(erase_mode='custom', mask_path=str(mask))
        with self.assertRaises(ValueError):
            erase_text(open_image(self.image()), [region()], opts)

    def test_corrupt_image(self):
        path = self.source / 'hỏng.png'
        path.write_bytes(b'not an image')
        with self.assertRaises(OSError):
            open_image(path)


class ControlTests(unittest.TestCase):
    def test_pause_resume(self):
        control = JobControl()
        control.pause()
        reached = threading.Event()
        thread = threading.Thread(target=lambda: (control.checkpoint(), reached.set()))
        thread.start()
        self.assertFalse(reached.wait(.08))
        control.resume()
        self.assertTrue(reached.wait(1))
        thread.join(1)

    def test_cancel_wakes_pause(self):
        control = JobControl()
        control.pause()
        cancelled = threading.Event()
        def run():
            try:
                control.checkpoint()
            except CancelledError:
                cancelled.set()
        thread = threading.Thread(target=run)
        thread.start()
        control.cancel()
        self.assertTrue(cancelled.wait(1))
        thread.join(1)


class OCRStructureTests(unittest.TestCase):
    def test_conservative_paragraph_grouping(self):
        first = region('First', (10, 10, 210, 40))
        second = region('Second', (12, 50, 210, 80))
        image = np.full((200, 500, 3), 255, np.uint8)
        self.assertEqual(group_lines([first, second], image, 'ltr')[0].text, 'First Second')
        image[43:48, 10:210] = 0
        self.assertEqual(len(group_lines([first, second], image, 'ltr')), 2)

    def test_framework_autodownload_is_disabled(self):
        with self.assertRaises(MissingModelError):
            local_models_only(str(ROOT / 'output/no-such-model'), 'https://example.com/model.tar')

    def test_deduplicate_overlapping_tiles(self):
        a = region(box=(10, 10, 150, 80))
        b = region(box=(12, 12, 148, 78))
        b.confidence = .7
        c = region(box=(300, 10, 400, 80))
        self.assertEqual(len(deduplicate([a, b, c])), 2)

    def test_reading_order(self):
        a, b = region(box=(200, 0, 300, 100)), region(box=(10, 0, 100, 100))
        self.assertIs(reading_order([a, b], 'ltr')[0], b)
        self.assertIs(reading_order([a, b], 'rtl')[0], a)

    def test_tile_coordinates_return_to_original(self):
        # Adapter unit test with synthetic engine output, not real OCR accuracy.
        class Engine:
            def ocr(self, tile, cls):
                return [[[[[10, 10], [100, 10], [100, 40], [10, 40]], ('Hello', .98)]]]
        ocr = PaddleOCREngine()
        with patch.object(ocr, '_load', return_value=Engine()):
            results, _ = ocr.recognize(np.zeros((2500, 500, 3), np.uint8), 'en', tile_size=1000)
        self.assertGreater(len(results), 1)
        self.assertGreater(max(r.box[1] for r in results), 1000)

    def test_missing_models_dont_import_paddle_or_network(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'output') as tmp, patch('socket.socket.connect', side_effect=AssertionError('NETWORK')):
            with self.assertRaises(MissingModelError):
                PaddleOCREngine(Path(tmp)).identity('zh')


class TranslationTests(WorkspaceCase):
    def test_offline_no_network_or_online_construction(self):
        options = self.options(mode='Offline')
        with patch('socket.socket.connect', side_effect=AssertionError('NETWORK')), \
             patch('core.pipeline.MyMemoryProvider', side_effect=AssertionError('ONLINE CREATED')):
            service = TranslationService(options, self.cache, JobControl(), offline=FakeProvider())
            self.assertEqual(service.translate('Hello world', 'en', 'context'), 'Xin chào thế giới')

    def test_missing_offline_models_no_fallback(self):
        options = self.options(mode='Offline', allow_online_fallback=True)
        with tempfile.TemporaryDirectory(dir=self.folder) as tmp, patch('socket.socket.connect', side_effect=AssertionError('NETWORK')):
            provider = ArgosTranslationProvider(Path(tmp))
            service = TranslationService(options, self.cache, JobControl(), offline=provider, online=Mock())
            with self.assertRaises(MissingModelError):
                service.translate('你好', 'zh', 'context')
            service.online.translate.assert_not_called()

    def test_pivot_requires_both_models(self):
        provider = ArgosTranslationProvider(self.folder / 'missing')
        provider.packages = {('zh', 'en'): (self.folder, {})}
        with self.assertRaises(MissingModelError):
            provider.route('zh')
        provider.packages[('en', 'vi')] = (self.folder, {})
        self.assertEqual(provider.route('zh'), [('zh', 'en'), ('en', 'vi')])

    def test_cache_context_and_provider_separation(self):
        provider = FakeProvider()
        service = TranslationService(self.options(), self.cache, JobControl(), offline=provider)
        service.translate('Hello', 'en', 'one')
        service.translate('Hello', 'en', 'one')
        self.assertEqual(provider.calls, 1)
        service.translate('Hello', 'en', 'two')
        self.assertEqual(provider.calls, 2)
        provider.identity = 'different-model-version'
        service.translate('Hello', 'en', 'one')
        self.assertEqual(provider.calls, 3)

    def test_glossary_and_numbers_roundtrip(self):
        service = TranslationService(self.options(glossary={'张三': 'Trương Tam'}), self.cache, JobControl(), offline=FakeProvider())
        translated = service.translate('Hello 张三 123,45%', 'zh', 'context')
        self.assertEqual(translated, 'Xin chào Trương Tam 123,45%')

    def test_changed_markers_fail_safely(self):
        provider = Mock(online=False, identity='broken-marker')
        provider.translate.return_value = 'Xin chào'
        service = TranslationService(self.options(), self.cache, JobControl(), offline=provider)
        with self.assertRaises(ProviderError):
            service.translate('Hello 123', 'en', 'context')

    def test_fallback_needs_consent(self):
        for consent in [False, True]:
            opts = self.options(mode='Auto Fallback', allow_online_fallback=consent)
            online = Mock(online=True, identity='mock-online')
            online.translate.return_value = 'Xin chào'
            service = TranslationService(opts, self.cache, JobControl(), offline=FakeProvider(fail=True), online=online)
            if consent:
                self.assertEqual(service.translate('Hello', 'en', str(consent)), 'Xin chào')
            else:
                with self.assertRaises(ProviderError):
                    service.translate('Hello', 'en', str(consent))
                online.translate.assert_not_called()

    def test_online_mock_success(self):
        session = Mock()
        session.request.return_value.status_code = 200
        session.request.return_value.json.return_value = {'responseStatus': 200, 'responseData': {'translatedText': 'Xin chào &amp; bạn'}}
        self.assertEqual(MyMemoryProvider(client=session).translate('Hello', 'en'), 'Xin chào & bạn')
        self.assertNotIn('key', session.request.call_args.kwargs['params'])

    def test_online_quota_not_retried(self):
        session = Mock()
        session.request.return_value.status_code = 429
        with self.assertRaises(ProviderError):
            MyMemoryProvider(client=session).translate('Hello', 'en')
        self.assertEqual(session.request.call_count, 1)

    def test_online_timeout_bounded_retry(self):
        session = Mock()
        session.request.side_effect = requests.Timeout('secret URL should not appear')
        provider = MyMemoryProvider(client=session)
        # Replace monotonic/sleep to exercise retry without waiting seconds.
        tick = iter(range(1000))
        with patch('providers.online.time.monotonic', side_effect=lambda: next(tick)), patch('providers.online.time.sleep'):
            with self.assertRaisesRegex(ProviderError, '3 lần'):
                provider.translate('Hello', 'en')
        self.assertEqual(session.request.call_count, 3)

    def test_libre_secure_endpoint_and_mock(self):
        for bad in ['http://external.example', 'https://user:password@example.com', 'https://example.com?key=secret']:
            with self.assertRaises(ProviderError):
                LibreTranslateProvider(bad)
        session = Mock()
        session.request.return_value.status_code = 200
        session.request.return_value.json.return_value = {'translatedText': 'Xin chào'}
        provider = LibreTranslateProvider('http://127.0.0.1:5000', client=session)
        self.assertEqual(provider.translate('Hello', 'en'), 'Xin chào')


class ModelIntegrityTests(WorkspaceCase):
    def test_path_traversal_rejected(self):
        for name in ['../evil', '/absolute', 'C:/outside', '..\\evil']:
            with self.assertRaises(ValueError):
                safe_member(name)

    def test_bad_archive_rejected(self):
        path = self.folder / 'bad.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('../outside.txt', 'unsafe')
        with self.assertRaises(ValueError):
            extract_archive(path, self.folder / 'extracted')
        self.assertFalse((self.folder / 'outside.txt').exists())

    def test_corrupted_model_hash_detected(self):
        model = self.folder / 'model'
        model.mkdir()
        binary = model / 'model.bin'
        binary.write_bytes(b'synthetic model fixture')
        atomic_json(model / 'integrity.json', {'files': {'model.bin': file_digest(binary)}})
        verify_installation(model)
        binary.write_bytes(b'corrupted')
        with self.assertRaises(MissingModelError):
            verify_installation(model)


class PipelineTests(WorkspaceCase):
    def test_mock_pipeline_real_cv_export_and_resume(self):
        path = self.image()
        before = file_digest(path)
        ocr, provider, events = FakeOCR(), FakeProvider(), []
        manager = self.manager(provider=provider, ocr=ocr, events=events)
        result = manager.run()
        self.assertEqual(result['completed'], 1)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(file_digest(path), before)
        destination = manager.destination(path)
        self.assertEqual(open_image(destination).size, (480, 160))
        self.assertTrue({'OCR', 'Dịch', 'Xóa chữ', 'Chèn chữ', 'Đang lưu', 'Hoàn thành'}.issubset({e.get('stage') for e in events}))
        manager2 = self.manager(provider=provider, ocr=ocr)
        result = manager2.run()
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(ocr.calls, 1)
        self.assertEqual(provider.calls, 1)

    def test_translation_failure_exports_verified_original_not_translation(self):
        source = self.image()
        result = self.manager(provider=FakeProvider(fail=True)).run()
        self.assertEqual(result['failed'], 1)
        self.assertEqual(result['state'], 'completed_with_warnings')
        self.assertEqual(result['translated_success'], 0)
        self.assertEqual(result['fallback_original'], 1)
        output = Path(result['review_pages'][0]['output_path'])
        self.assertEqual(file_digest(output), file_digest(source))

    def test_batch_continues_on_corruption_and_retries_only_error(self):
        good = self.image('1.png')
        bad = self.source / '2.png'
        bad.write_bytes(b'corrupt')
        result = self.manager().run()
        self.assertEqual(result['completed'], 1)
        self.assertEqual(result['failed'], 1)
        self.image('2.png')
        result2 = self.manager().run(only=result['errors'])
        self.assertEqual(result2['total'], 1)
        self.assertEqual(result2['completed'], 1)

    def test_cancel_at_checkpoint_never_saves_current_image(self):
        self.image()
        control = JobControl()
        events = []
        manager = self.manager(control=control)
        def emit(event):
            events.append(event)
            if event.get('stage') == 'Dịch':
                control.cancel()
        manager.emit = emit
        result = manager.run()
        self.assertEqual(result['state'], 'cancelled')
        self.assertFalse(list(self.output.rglob('*.png')))

    def test_empty_ocr_preserves_pixels(self):
        path = self.image()
        manager = self.manager(ocr=FakeOCR([]))
        result = manager.run()
        self.assertEqual(result['completed'], 1)
        self.assertTrue(np.array_equal(np.array(open_image(path)), np.array(open_image(manager.destination(path)))))

    def test_modified_output_is_not_overwritten(self):
        path = self.image()
        manager = self.manager()
        manager.run()
        dest = manager.destination(path)
        dest.write_bytes(b'user modified file')
        result = self.manager().run()
        self.assertEqual(result['failed'], 1)
        self.assertEqual(dest.read_bytes(), b'user modified file')

    def test_flatten_name_collisions_are_unique(self):
        self.image('a/1.png')
        self.image('b/1.png')
        manager = self.manager(self.options(preserve_structure=False))
        result = manager.run()
        self.assertEqual(result['completed'], 2)
        self.assertEqual(len(list(self.output.glob('*.png'))), 2)

    def test_no_images_reports_fatal(self):
        events = []
        result = self.manager(events=events).run()
        self.assertEqual(result['state'], 'error')
        self.assertTrue(any(e.get('type') == 'fatal' for e in events))


if __name__ == '__main__':
    unittest.main()
