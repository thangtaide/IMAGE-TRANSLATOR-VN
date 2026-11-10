"""Stage3A local/mock contracts. No live HTTP or production databases."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from PIL import Image

from core.paths import ROOT
from core.pipeline import JobControl, NumericMismatchError, ProcessingManager, TranslationService
from core.storage import TranslationCache, file_digest
from core.types import CancelledError, OCRResult, Options
from providers.online import MyMemoryProvider, OnlineProviderError, ProviderSuspended


def response(data=None, status=200, mime='application/json', body=None, headers=None):
    r = requests.Response()
    r.status_code = status
    r.headers.update({'Content-Type': mime, **(headers or {})})
    r._content = body if body is not None else json.dumps(data or {}, ensure_ascii=False).encode('utf-8')
    r._content_consumed = True
    return r


def translated(text):
    return response({'responseStatus': 200, 'responseData': {'translatedText': text}})


class OCRFixture:
    def identity(self, language):
        return 'mock-ocr-stage3a'

    def recognize(self, image, *args):
        value = int(image[0, 0, 0])
        return [OCRResult(f'你好 {value}', [[20, 20], [240, 20], [240, 125], [20, 125]], .99, 'zh')], []


class OfflineFixture:
    identity, online = 'mock-offline-stage3a', False

    def translate(self, text, source, target='vi'):
        return text.replace('你好', 'Xin chào')


class OnlineFreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'output', prefix='qa-online-free-')
        self.root = Path(self.temp.name)
        self.cache = TranslationCache(self.root / 'qa.sqlite3')
        self.session = Mock()
        self.provider = MyMemoryProvider(self.session)
        self.provider.wait = lambda seconds: self.provider.checkpoint()

    def tearDown(self):
        self.cache.close()
        self.temp.cleanup()

    def service(self, provider=None):
        return TranslationService(Options(mode='Online Free'), self.cache, JobControl(), online=provider or self.provider)

    def test_official_request_unicode_no_keys_redirect_or_billing(self):
        self.session.request.return_value = translated('Xin chào &amp; bạn')
        self.assertEqual(self.provider.translate('你好', 'zh'), 'Xin chào & bạn')
        args, kw = self.session.request.call_args
        self.assertEqual(args, ('GET', 'https://api.mymemory.translated.net/get'))
        self.assertEqual(kw['params'], {'q': '你好', 'langpair': 'zh-CN|vi', 'mt': 1})
        self.assertTrue(kw['verify'])
        self.assertFalse(kw['allow_redirects'])
        self.assertEqual(kw['timeout'], (8, 25))

    def test_500_byte_limit_uses_utf8(self):
        with self.assertRaises(OnlineProviderError):
            self.provider.translate('中' * 161, 'zh')
        self.session.request.assert_not_called()

    def test_chunks_preserve_unicode_and_do_not_merge_paragraphs(self):
        service = self.service()
        text = '中' * 350
        chunks = service._chunks(text)
        self.assertEqual(''.join(chunks), text)
        self.assertTrue(all(len(c.encode('utf-8')) <= 450 for c in chunks))
        self.assertEqual(service._chunks('第一段\n第二段'), ['第一段', '第二段'])

    def test_rate_limit_latches_and_does_not_guess_daily_quota(self):
        self.session.request.return_value = response(status=429, headers={'Retry-After': '60'})
        for _ in range(2):
            with self.assertRaises(ProviderSuspended) as cm:
                self.provider.translate('你好', 'zh')
            self.assertEqual(cm.exception.code, 'RATE_LIMITED')
            self.assertEqual(cm.exception.retry_after, 60)
        self.assertEqual(self.session.request.call_count, 1)

    def test_quota_in_http_200_suspends_without_retry(self):
        self.session.request.return_value = response({'responseStatus': 403, 'quotaFinished': True})
        with self.assertRaises(ProviderSuspended) as cm:
            self.provider.translate('你好', 'zh')
        self.assertEqual(cm.exception.code, 'QUOTA_EXCEEDED')
        self.assertIsNone(cm.exception.retry_after)
        self.assertEqual(self.session.request.call_count, 1)

    def test_authentication_stops_without_new_identity(self):
        for status in (401, 403):
            provider = MyMemoryProvider(self.session)
            provider.wait = lambda _: None
            self.session.request.return_value = response(status=status)
            with self.assertRaises(ProviderSuspended) as cm:
                provider.translate('你好', 'zh')
            self.assertEqual(cm.exception.code, 'AUTH_REQUIRED')

    def test_redirect_is_not_followed(self):
        self.session.request.return_value = response(status=302, headers={'Location': 'https://other.example/'})
        with self.assertRaises(OnlineProviderError):
            self.provider.translate('你好', 'zh')
        self.assertEqual(self.session.request.call_count, 1)

    def test_invalid_mime_json_shape_missing_target_and_oversize(self):
        bad = [response(mime='text/html', body=b'<html>error</html>'),
               response(body=b'not JSON'), response(body=b'[]'), response({'responseStatus': 200}),
               response({'responseStatus': 200, 'responseData': {'translatedText': 123}}),
               response(body=b' ' * 1_000_001)]
        for r in bad:
            self.session.request.return_value = r
            with self.assertRaises(OnlineProviderError) as cm:
                self.provider.translate('你好', 'zh')
            self.assertEqual(cm.exception.code, 'INVALID_RESPONSE')

    def test_timeout_retry_is_bounded_and_redacted(self):
        self.session.request.side_effect = requests.Timeout('https://secret.example/?q=private')
        with self.assertRaises(OnlineProviderError) as cm:
            self.provider.translate('你好', 'zh')
        self.assertEqual(cm.exception.code, 'TIMEOUT')
        self.assertNotIn('private', str(cm.exception))
        self.assertEqual(self.session.request.call_count, 3)
        self.assertEqual(self.provider.retry_count, 2)

    def test_dns_failure_is_network_error(self):
        self.session.request.side_effect = requests.ConnectionError('DNS/proxy private value')
        with self.assertRaises(OnlineProviderError) as cm:
            self.provider.translate('你好', 'zh')
        self.assertEqual(cm.exception.code, 'NETWORK_ERROR')
        self.assertNotIn('private', str(cm.exception))

    def test_temporary_server_error_retries(self):
        self.session.request.side_effect = [response(status=503), translated('Xin chào')]
        self.assertEqual(self.provider.translate('你好', 'zh'), 'Xin chào')
        self.assertEqual(self.session.request.call_count, 2)

    def test_cancel_before_request_has_no_network(self):
        control = JobControl()
        control.cancel()
        self.provider.checkpoint = control.checkpoint
        with self.assertRaises(CancelledError):
            self.provider.translate('你好', 'zh')
        self.session.request.assert_not_called()

    def test_numeric_rejection_retains_target_and_does_not_cache(self):
        self.session.request.return_value = translated('Xin chào 16')
        service = self.service()
        for _ in range(2):
            with self.assertRaises(NumericMismatchError):
                service.translate('你好 15', 'zh', 'context')
        self.assertEqual(self.session.request.call_count, 2)
        self.assertEqual(service.last_attempt['raw_translated_target'], 'Xin chào 16')
        self.assertEqual(service.last_attempt['target_numeric_tokens'], ['16'])

    def test_valid_cache_and_provider_isolation(self):
        offline = TranslationService(Options(), self.cache, JobControl(), offline=OfflineFixture())
        offline.translate('你好 15', 'zh', 'context')
        self.session.request.return_value = translated('Chào bạn 15')
        online = self.service()
        self.assertEqual(online.translate('你好 15', 'zh', 'context'), 'Chào bạn 15')
        self.assertEqual(online.translate('你好 15', 'zh', 'context'), 'Chào bạn 15')
        self.assertEqual(self.session.request.call_count, 1)
        self.assertNotEqual(offline.identity(), online.identity())

    def test_offline_does_not_construct_or_call_online(self):
        with patch('core.pipeline.MyMemoryProvider', side_effect=AssertionError('Online construction')):
            service = TranslationService(Options(), self.cache, JobControl(), offline=OfflineFixture())
            self.assertEqual(service.translate('你好 15', 'zh', 'test'), 'Xin chào 15')

    def test_quota_preserves_done_and_resume_only_pending_under_new_recipe(self):
        src, dst = self.root / 'source', self.root / 'export'
        src.mkdir()
        for n in (1, 2, 3):
            Image.new('RGB', (260, 150), (n, n, n)).save(src / f'{n}.png')
        self.session.request.side_effect = [translated('Xin chào 1'), response({'responseStatus': 403, 'quotaFinished': True})]
        opts = Options(source=str(src), output=str(dst), mode='Online Free')
        events = []
        manager = ProcessingManager(opts, self.cache, ocr=OCRFixture(), service=self.service(), emit=events.append,
                                    diagnostic_root=self.root / 'diagnostics')
        result = manager.run()
        self.assertEqual(result['state'], 'paused_provider')
        self.assertEqual(result['completed'], 1)
        self.assertEqual(result['failed'], 0)
        self.assertEqual([Path(p).name for p in result['pending_paths']], ['2.png', '3.png'])
        self.assertEqual(self.session.request.call_count, 2)
        first = manager.destination(src / '1.png')
        before = file_digest(first)
        receipt = self.cache.item(manager.job_id, str(src / '1.png'))
        self.assertEqual(receipt['status'], 'done')
        self.assertEqual(self.cache.item(manager.job_id, str(src / '2.png'))['status'], 'paused_provider')
        opts.mode = 'Offline'
        resumed = ProcessingManager(opts, self.cache, ocr=OCRFixture(),
            service=TranslationService(opts, self.cache, JobControl(), offline=OfflineFixture()))
        done = resumed.run(result['pending_paths'])
        self.assertEqual(done['completed'], 2)
        self.assertNotEqual(done['job_id'], result['job_id'])
        self.assertEqual(file_digest(first), before)
        self.assertEqual(receipt, self.cache.item(manager.job_id, str(src / '1.png')))
        self.assertEqual(self.session.request.call_count, 2)

    def test_local_comic_accepts_explicit_online_free_without_fallback(self):
        from sources.collection import discover_local
        from sources.service import LocalComicJob
        source = self.root / 'image.png'
        Image.new('RGB', (260, 150), 'white').save(source)
        comic, chapters = discover_local(source)
        job = LocalComicJob(comic, chapters, self.root / 'export', Options(mode='Online Free', allow_online_fallback=True))
        self.assertEqual(job.options.mode, 'Online Free')
        self.assertFalse(job.options.allow_online_fallback)

    def test_chapter_quota_resume_from_cache_without_download_or_overwriting_success(self):
        from sources.cache import ChapterCache
        from sources.collection import discover_local
        from sources.service import LocalComicJob
        src = self.root / 'chapter'
        src.mkdir()
        for n in (1, 2, 3):
            Image.new('RGB', (260, 150), (n, n, n)).save(src / f'{n}.png')
        comic, chapters = discover_local(src)
        chapter_cache = ChapterCache(self.root / 'chapter-cache')
        self.session.request.side_effect = [translated('Xin chào 1'), response({'responseStatus': 403, 'quotaFinished': True})]
        def service(opts, db, control):
            return TranslationService(opts, db, control, online=self.provider, offline=OfflineFixture())
        with patch('sources.service.PaddleOCREngine', return_value=OCRFixture()), \
             patch('sources.service.TranslationService', side_effect=service), \
             patch('sources.service.ROOT', self.root), \
             patch('socket.socket.connect', side_effect=AssertionError('NETWORK')):
            first = LocalComicJob(comic, chapters, self.root / 'export', Options(mode='Online Free'),
                cache=chapter_cache, database=self.root / 'chapter.sqlite3').run()
            self.assertEqual(first['state'], 'paused_provider', first)
            directory = chapter_cache.directory(comic, chapters[0])
            manifest = chapter_cache.read(directory)
            old = dict(manifest['pages'][0])
            old_hash = file_digest(Path(old['output']))
            final = LocalComicJob(comic, chapters, self.root / 'export', Options(),
                cache=chapter_cache, database=self.root / 'chapter.sqlite3', retry_only=True).run()
            self.assertEqual(final['state'], 'done', final)
            self.assertEqual(final['images_exported'], 3)
            after = chapter_cache.read(directory)
            self.assertEqual(old, after['pages'][0])
            self.assertEqual(old_hash, file_digest(Path(old['output'])))
            self.assertEqual(self.session.request.call_count, 2)

    def test_cancel_after_response_does_not_cache_target(self):
        control = JobControl()
        provider = MyMemoryProvider(self.session, checkpoint=control.checkpoint)
        provider.wait = lambda _: control.checkpoint()
        def respond(*args, **kwargs):
            control.cancel()
            return translated('Xin chào')
        self.session.request.side_effect = respond
        with self.assertRaises(CancelledError):
            TranslationService(Options(mode='Online Free'), self.cache, control, online=provider).translate('你好', 'zh', 'cancel')
        self.assertEqual(self.cache.connection.execute("SELECT count(*) FROM cache WHERE kind='translation'").fetchone()[0], 0)

    def test_gui_notice_dismiss_does_not_resume_or_change_provider(self):
        from PySide6.QtWidgets import QApplication
        from ui.main_window import MainWindow
        app = QApplication.instance() or QApplication([])
        window = MainWindow(cache_path=self.root / 'gui.sqlite3', persist_settings=False)
        window.show()
        window.mode.setCurrentText('Online Free')
        window.source_tabs.setCurrentIndex(0)
        self.assertTrue(window.mode.isVisible())
        for obj, event in [(window, {'type': 'provider_paused', 'code': 'QUOTA_EXCEEDED', 'detail': 'Quota',
                                     'pending_paths': ['remaining.png'], 'retry_after': None})]:
            obj.handle_event(event)
        app.processEvents()
        self.assertTrue(window.provider_paused)
        window.provider_notice.dismiss.click()
        self.assertTrue(window.provider_paused)
        self.assertEqual(window.mode.currentText(), 'Online Free')
        self.assertFalse(window.provider_notice.isVisible())
        self.assertIn('Chưa xác định', window.provider_notice.message.text())
        window.close()
