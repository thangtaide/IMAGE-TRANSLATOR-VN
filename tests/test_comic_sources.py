"""New source unit tests. HTTP responses and HTML below are explicitly synthetic.

No test in this module claims to download a Kuaikan comic.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from core.paths import ROOT
from core.pipeline import JobControl
from core.storage import file_digest
from core.types import CancelledError, Options
from sources.cache import ChapterCache, inspect_image
from sources.collection import ImageCollection, discover_local
from sources.contracts import (AccessRestricted, AccessStatus, CacheError, InvalidURL,
                               NetworkUnavailable, SourceError, StructureChanged, UnsupportedWebsite)
from sources.kuaikan import KuaikanAdapter
from sources.metadata_http import fetch_public_html
from sources.registry import resolve_adapter
from sources.security import contained, public_addresses, safe_id, safe_name
from sources.service import LocalComicJob, publish_image, validate_output


class URLSourceTests(unittest.TestCase):
    def test_build_fingerprint_includes_adapter_sources(self):
        from scripts.qa_common import source_fingerprint
        with tempfile.TemporaryDirectory(dir=ROOT / 'output', prefix='comic-fingerprint-') as folder:
            root = Path(folder)
            for name in ('main.py', 'requirements.txt', 'ImageTranslatorVN.spec'):
                (root / name).write_text('fixture')
            (root / 'sources').mkdir()
            adapter = root / 'sources' / 'adapter.py'
            adapter.write_text('old')
            before = source_fingerprint(root)
            adapter.write_text('new')
            self.assertNotEqual(before, source_fingerprint(root))

    def test_supported_urls_and_normalization(self):
        adapter = KuaikanAdapter()
        for identifier in ('6677', '15425', '3791', '98231'):
            url = f'https://www.kuaikanmanhua.com/web/topic/{identifier}/'
            self.assertEqual(resolve_adapter(url).normalize_url(url + '?tracking=a#fragment'), url)
            self.assertTrue(adapter.can_handle(url))

    def test_invalid_urls_and_unsupported_domain(self):
        adapter = KuaikanAdapter()
        invalid = ['http://www.kuaikanmanhua.com/web/topic/1/', 'https://localhost/web/topic/1/',
                   'https://127.0.0.1/', 'https://169.254.169.254/', 'https://[::1]/',
                   'https://user:secret@www.kuaikanmanhua.com/web/topic/1/',
                   'https://www.kuaikanmanhua.com:444/web/topic/1/',
                   'https://www.kuaikanmanhua.com/web/topic/1/../../',
                   'https://www.kuaikanmanhua.com/web/topic/0/',
                   'https://www.kuaikanmanhua.com.evil.example/web/topic/1/',
                   'https://www.kuaikanmanhua.com/web/topic/1/\n']
        for url in invalid:
            with self.subTest(url=url):
                self.assertFalse(adapter.can_handle(url))
        with self.assertRaises(UnsupportedWebsite):
            resolve_adapter('https://example.org/web/topic/1/')
        with self.assertRaises(InvalidURL):
            resolve_adapter('not a url')

    def test_fixture_metadata_not_live_html(self):
        # Manually authored fixture, NOT a capture of actual Kuaikan HTML.
        html = '<meta name="author" content="Fixture author"><h3>测试作品</h3><p>连载中</p><p>共4个内容</p><p>共3篇正文</p>'
        for identifier in ('12', '45'):
            comic = KuaikanAdapter().parse_topic_html(f'https://www.kuaikanmanhua.com/web/topic/{identifier}/', html)
            self.assertEqual((comic.comic_id, comic.title, comic.author, comic.chapter_count, comic.main_chapter_count),
                             (identifier, '测试作品', 'Fixture author', 4, 3))

    def test_structure_change_fails_without_inventing_chapters(self):
        adapter = KuaikanAdapter()
        with self.assertRaises(StructureChanged):
            adapter.parse_topic_html('https://www.kuaikanmanhua.com/web/topic/1/', '<script>fake data</script>')
        with self.assertRaises(StructureChanged):
            adapter.get_chapters(Mock())

    def test_download_and_image_discovery_denied_before_network(self):
        adapter = KuaikanAdapter()
        with patch('sources.kuaikan.fetch_public_html', side_effect=AssertionError('No HTTP for images')) as fetch:
            with self.assertRaises(StructureChanged):
                adapter.get_chapter_images(Mock())
            with self.assertRaises(SourceError):
                adapter.download_chapter(Mock(), ROOT / 'cache')
            fetch.assert_not_called()
        self.assertFalse(adapter.download_enabled)

    def test_dns_rejects_mixed_public_private_response(self):
        rows = [(2, 1, 6, '', (ip, 443)) for ip in ['8.8.8.8', '127.0.0.1']]
        with patch('socket.getaddrinfo', return_value=rows):
            with self.assertRaises(InvalidURL):
                public_addresses('www.kuaikanmanhua.com')

    def test_safe_windows_filename_and_boundary(self):
        for name in ('CON', 'LPT1', 'A/B:C?<>|*', '中文 / chương 1', '..'):
            result = safe_name(name, '12')
            self.assertFalse(any(char in result for char in '<>:"/\\|?*'))
            self.assertTrue(result.endswith('__12'))
        for identifier in ('../x', 'NUL', 'a/b', ''):
            with self.assertRaises(CacheError):
                safe_id(identifier)
        with self.assertRaises(CacheError):
            contained(ROOT / 'cache', '..', 'main.py')


class MetadataHTTPTests(unittest.TestCase):
    def fake_fetch(self, responses):
        connection = Mock()
        connection.getresponse.side_effect = responses
        self.connection = connection
        self.stack = []
        for context in (patch.dict(os.environ, {'CODEX_SANDBOX_NETWORK_DISABLED': '0'}),
                        patch('sources.metadata_http.getproxies', return_value={}),
                        patch('sources.metadata_http.public_addresses', return_value=['8.8.8.8']),
                        patch('sources.metadata_http._PinnedHTTPS', return_value=connection)):
            context.start()
            self.addCleanup(context.stop)
        return connection

    @staticmethod
    def response(status=200, content_type='text/html', location=None, body=b'<html>fixture</html>'):
        response = Mock(status=status)
        response.getheader.side_effect = lambda name, default=None: {'Content-Type': content_type,
            'Content-Length': str(len(body)), 'Location': location}.get(name, default)
        response.read.side_effect = [body, b'']
        return response

    def test_bounded_public_html_using_mock_http(self):
        connection = self.fake_fetch([self.response()])
        self.assertIn('fixture', fetch_public_html('https://www.kuaikanmanhua.com/web/topic/1/', KuaikanAdapter.hosts))
        self.assertEqual(connection.request.call_count, 1)
        connection.close.assert_called_once()

    def test_no_retry_on_access_and_rate_limits(self):
        self.fake_fetch([self.response(429), self.response(403), self.response(401)])
        for _ in range(3):
            with self.assertRaises(AccessRestricted):
                fetch_public_html('https://www.kuaikanmanhua.com/web/topic/1/', KuaikanAdapter.hosts)
        self.assertEqual(self.connection.request.call_count, 3)

    def test_redirect_to_internal_or_external_domain_rejected(self):
        self.fake_fetch([self.response(302, location='https://127.0.0.1/private')])
        with self.assertRaises(InvalidURL):
            fetch_public_html('https://www.kuaikanmanhua.com/web/topic/1/', KuaikanAdapter.hosts)
        self.assertEqual(self.connection.request.call_count, 1)

    def test_non_html_body_rejected(self):
        self.fake_fetch([self.response(content_type='image/jpeg')])
        with self.assertRaises(SourceError):
            fetch_public_html('https://www.kuaikanmanhua.com/web/topic/1/', KuaikanAdapter.hosts)

    def test_timeout_and_proxy_not_bypassed(self):
        connection = self.fake_fetch([])
        connection.request.side_effect = TimeoutError('fixture timeout')
        with self.assertRaises(NetworkUnavailable):
            fetch_public_html('https://www.kuaikanmanhua.com/web/topic/1/', KuaikanAdapter.hosts)
        with patch('sources.metadata_http.getproxies', return_value={'https': 'http://proxy.invalid'}):
            with self.assertRaises(NetworkUnavailable):
                fetch_public_html('https://www.kuaikanmanhua.com/web/topic/1/', KuaikanAdapter.hosts)
        self.assertEqual(connection.request.call_count, 1)

    def test_html_size_and_redirect_budget(self):
        huge = self.response()
        huge.getheader.side_effect = lambda name, default=None: {'Content-Type': 'text/html',
            'Content-Length': '2000001'}.get(name, default)
        self.fake_fetch([huge] + [self.response(302, location='/web/topic/2/') for _ in range(4)])
        with self.assertRaises(SourceError):
            fetch_public_html('https://www.kuaikanmanhua.com/web/topic/1/', KuaikanAdapter.hosts)
        with self.assertRaises(SourceError):
            fetch_public_html('https://www.kuaikanmanhua.com/web/topic/1/', KuaikanAdapter.hosts)
        self.assertEqual(self.connection.request.call_count, 5)


class LocalCollectionTests(unittest.TestCase):
    def setUp(self):
        # Temporary files stay inside the authorized workspace.
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'output', prefix='comic-unit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'nguồn ảnh có dấu'
        self.source.mkdir()
        for name in ('10.png', '2.png', '1.png'):
            Image.new('RGBA', (80, 60), (255, 255, 255, 128)).save(self.source / name)
        self.control = JobControl()
        self.comic, self.chapters = discover_local(self.source)
        self.chapter = self.chapters[0]
        self.collection = ImageCollection.discover(self.source)
        self.cache = ChapterCache(self.root / 'cache')

    def test_natural_order_and_existing_pipeline_request(self):
        self.assertEqual([p.name for p in self.collection.paths], ['1.png', '2.png', '10.png'])
        options, only = self.collection.request(Options(output='unchanged'))
        self.assertEqual(options.output, 'unchanged')
        self.assertEqual(len(only), 3)
        self.assertEqual(self.chapter.access_status, AccessStatus.LOCAL)

    def test_single_image_and_nested_chapters(self):
        _, chapters = discover_local(self.source / '2.png')
        self.assertEqual(chapters[0].image_count, 1)
        book = self.root / 'book'
        book.mkdir()
        for chapter in ('Chapter10', 'Chapter2'):
            directory = book / chapter
            directory.mkdir()
            Image.new('RGB', (30, 20)).save(directory / '1.jpg')
        _, chapters = discover_local(book)
        self.assertEqual([c.chapter_title for c in chapters], ['Chapter2', 'Chapter10'])

    def test_empty_folder_fails(self):
        path = self.root / 'empty'
        path.mkdir()
        with self.assertRaises(SourceError):
            discover_local(path)

    def test_cache_resume_without_recopy_and_original_unchanged(self):
        before = {p: file_digest(p) for p in self.collection.paths}
        cached, directory, manifest = self.cache.stage(self.comic, self.chapter, self.collection, self.control)
        times = [p.stat().st_mtime_ns for p in cached.paths]
        again, _, _ = self.cache.stage(self.comic, self.chapter, self.collection, self.control)
        self.assertEqual(times, [p.stat().st_mtime_ns for p in again.paths])
        self.assertEqual(before, {p: file_digest(p) for p in self.collection.paths})
        self.assertEqual(len(json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))['pages']), 3)

    def test_cancel_retains_manifest_and_resume_finishes(self):
        def cancel_after_first(event):
            self.control.cancel()
        with self.assertRaises(CancelledError):
            self.cache.stage(self.comic, self.chapter, self.collection, self.control, cancel_after_first)
        directory = self.cache.directory(self.comic, self.chapter)
        self.assertEqual(len(self.cache.read(directory)['pages']), 1)
        self.control = JobControl()
        _, _, manifest = self.cache.stage(self.comic, self.chapter, self.collection, self.control)
        self.assertEqual(len(manifest['pages']), 3)

    def test_corrupt_source_html_not_treated_as_image(self):
        (self.source / '1.png').write_text('<html>denied</html>')
        with self.assertRaises(CacheError):
            self.cache.stage(self.comic, self.chapter, self.collection, self.control)

    def test_cache_quota_and_tamper_detection(self):
        self.cache.quota = 1
        with self.assertRaises(CacheError):
            self.cache.stage(self.comic, self.chapter, self.collection, self.control)
        self.cache.quota = 2_000_000
        cached, _, _ = self.cache.stage(self.comic, self.chapter, self.collection, self.control)
        Image.new('RGB', (30, 20)).save(cached.paths[0])
        with self.assertRaises(CacheError):
            self.cache.stage(self.comic, self.chapter, self.collection, self.control)

    def test_changed_source_not_mixed_with_old_pages(self):
        self.cache.stage(self.comic, self.chapter, self.collection, self.control)
        Image.new('RGB', (20, 20)).save(self.source / '1.png')
        with self.assertRaises(CacheError):
            self.cache.stage(self.comic, self.chapter, self.collection, self.control)

    def test_broken_manifest_retained_and_reported(self):
        _, directory, _ = self.cache.stage(self.comic, self.chapter, self.collection, self.control)
        manifest = directory / 'manifest.json'
        for value in ('[1,2]', '{"version":1,"pages":[{}]}', '{broken'):
            manifest.write_text(value)
            with self.assertRaises(CacheError):
                self.cache.read(directory)
            self.assertEqual(manifest.read_text(), value)

    def test_publish_preserves_dimensions_alpha_and_no_overwrite(self):
        target = self.root / 'export' / '0001.png'
        publish_image(self.source / '1.png', target, self.control, (80, 60))
        self.assertEqual(Image.open(target).mode, 'RGBA')
        publish_image(self.source / '1.png', target, self.control, (80, 60))
        Image.new('RGB', (40, 20)).save(target)
        with self.assertRaises(CacheError):
            publish_image(self.source / '1.png', target, self.control, (80, 60))

    def test_cleanup_only_complete_and_verified_published_pages(self):
        cached, directory, manifest = self.cache.stage(self.comic, self.chapter, self.collection, self.control)
        with self.assertRaises(CacheError):
            self.cache.cleanup_completed(directory, manifest)
        for page, source in zip(manifest['pages'], cached.paths):
            destination = self.root / 'export' / page['file']
            checksum = publish_image(source, destination, self.control, (80, 60))
            page.update(output=str(destination), output_sha256=checksum)
        manifest['state'] = 'completed'
        self.cache.cleanup_completed(directory, manifest)
        self.assertTrue(all(p.exists() for p in self.collection.paths))
        self.assertTrue(all(not p.exists() for p in cached.paths))
        self.assertTrue((directory / 'manifest.json').exists())

    def test_pause_resume_and_cancel_waiting_checkpoint(self):
        self.control.pause()
        reached = threading.Event()
        worker = threading.Thread(target=lambda: (self.control.checkpoint(), reached.set()))
        worker.start()
        self.assertFalse(reached.wait(.05))
        self.control.resume()
        worker.join(1)
        self.assertTrue(reached.is_set())
        self.control.cancel()
        with self.assertRaises(CancelledError):
            self.control.checkpoint()

    def test_output_safety_and_offline_enforcement(self):
        for output in (self.source, self.source / 'translated', ROOT / 'models', ROOT / 'cache'):
            with self.assertRaises(CacheError):
                validate_output(output, self.chapters)
        job = LocalComicJob(self.comic, self.chapters, self.root / 'export',
                            Options(mode='Online', allow_online_fallback=True))
        self.assertEqual(job.options.mode, 'Offline')
        self.assertFalse(job.options.allow_online_fallback)

    def test_pipeline_failure_preserves_underlying_reason_and_retry_cache(self):
        result = LocalComicJob(self.comic, [self.chapter], self.root / 'export',
            Options(language='invalid'), cache=self.cache, database=self.root / 'qa.sqlite3').run()
        self.assertEqual(result['state'], 'errors')
        self.assertEqual(result['chapters_failed'], 1)
        self.assertIn('Ngôn ngữ OCR không hợp lệ', result['errors'][0]['detail'])
        self.assertEqual(result['errors'][0]['category'], 'processing')
        manifest = self.cache.read(self.cache.directory(self.comic, self.chapter))
        self.assertEqual(manifest['state'], 'error')
        self.assertTrue(all((self.cache.directory(self.comic, self.chapter) / p['file']).exists()
                            for p in manifest['pages']))


class ComicSourceGUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from core.runtime import prepare_inference_runtime
        prepare_inference_runtime()
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_selection_and_restricted_url_controls(self):
        from ui.comic_sources import ComicSourcesDialog
        from PySide6.QtCore import Qt
        with tempfile.TemporaryDirectory(dir=ROOT / 'output', prefix='comic-gui-unit-') as folder:
            path = Path(folder)
            Image.new('RGB', (50, 50)).save(path / '1.png')
            comic, chapters = discover_local(path)
            dialog = ComicSourcesDialog(Options(), settings_path=path / 'settings.json')
            dialog.show()
            dialog.handle_event({'type': 'collection', 'comic': comic, 'chapters': chapters})
            self.app.processEvents()
            self.assertFalse(dialog.start.isEnabled())
            self.assertEqual(dialog.table.item(0, 0).checkState(), Qt.Unchecked)
            dialog.check_all(True)
            self.assertTrue(dialog.start.isEnabled())
            dialog.check_all(False)
            self.assertFalse(dialog.start.isEnabled())
            dialog.kind.setCurrentIndex(2)
            self.assertFalse(dialog.download.isEnabled())
            self.assertEqual(dialog.table.rowCount(), 0)
            dialog.location.setText('https://www.kuaikanmanhua.com/web/topic/6677/')
            self.assertFalse(dialog.start.isEnabled())
            dialog.close()

    def test_cancel_before_processing_initialization_has_terminal_result(self):
        from ui.comic_sources import ComicSourceWorker
        worker = ComicSourceWorker('process', {})
        events = []
        worker.event.connect(events.append)
        worker.control.cancel()
        worker.run()
        self.assertEqual(events[-1]['type'], 'job_finished')
        self.assertEqual(events[-1]['state'], 'cancelled')
