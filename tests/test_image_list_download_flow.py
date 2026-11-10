"""Local Qt/HTTP wiring tests; no live website or real permission grant.

Image discovery is deliberately distinct from the user's download command.
"""
from dataclasses import replace
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from core.paths import ROOT
from core.types import Options
from sources.contracts import AccessStatus, ChapterImage, ChapterInfo, ComicInfo
from sources.download_policy import decide_download, DEFAULT_ALLOW_PUBLIC, VERIFIED_ONLY
from sources.states import ContentPermission, DownloadState
from tests.test_kuaikan_downloader import mocked_cdn, response


class ImageListDownloadFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from core.runtime import prepare_inference_runtime
        prepare_inference_runtime()
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'output', prefix='image-list-flow-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.chapter = ChapterInfo('42', 'Fixture chapter', '8',
            'https://www.kuaikanmanhua.com/webs/comic-next/42', AccessStatus.PUBLIC, 9)
        self.comic = ComicInfo('kuaikanmanhua', '12',
            'https://www.kuaikanmanhua.com/web/topic/12/', title='Fixture', source_kind='topic')
        self.images = [ChapterImage(1, 'https://tn1.kkmh.com/__fixture__/page.png')]

    def panel(self, *, access=AccessStatus.PUBLIC, policy=DEFAULT_ALLOW_PUBLIC, mode='Offline'):
        from sources.contracts import WebsiteAdapter
        from ui.comic_sources import ComicSourcesPanel
        owner = self

        class Adapter(WebsiteAdapter):
            site_id = 'kuaikanmanhua'
            hosts = ('www.kuaikanmanhua.com',)
            downloads = 0
            ready = False

            def normalize_url(self, url): return url
            def get_comic_info(self, url, control=None): return owner.comic
            def get_chapters(self, comic, control=None): return [owner.chapter]
            def get_chapter_images(self, chapter, control=None):
                self.ready = True
                return owner.images
            def download_decision(self, chapter):
                return decide_download(chapter, policy, images_safe=True if self.ready else None)
            def download_chapter(self, chapter, cache_dir, control=None):
                from sources.kuaikan_download import DownloadLimits, download_images
                self.downloads += 1
                return download_images(chapter, owner.images, cache_dir,
                    self.download_decision(chapter), control, getattr(self, 'download_progress', None),
                    limits=DownloadLimits(delay=0))

        adapter = Adapter()
        chapter = replace(self.chapter, access_status=access)
        panel = ComicSourcesPanel(Options(mode=mode), fixed_kind=2,
            settings_path=self.root / 'settings.json', database=self.root / 'qa.sqlite3')
        panel.output.setText(str(self.root / 'translated'))
        def cleanup():
            if panel.worker and panel.worker.isRunning():
                panel.worker.control.cancel()
                panel.worker.wait(5000)
                self.app.processEvents()
            panel.close()
        self.addCleanup(cleanup)
        panel.handle_event({'type': 'collection', 'comic': self.comic,
                            'chapters': [chapter], 'adapter': adapter})
        panel.check_all(True)
        return panel, adapter

    def discover(self, panel, adapter):
        images = adapter.get_chapter_images(panel.chapters[0])
        panel.handle_event({'type': 'images_ready', 'chapter_id': '42', 'images': images})

    def wait_worker(self, panel):
        deadline = time.monotonic() + 8
        while panel.worker.isRunning() or panel.busy:
            self.app.processEvents()
            if time.monotonic() > deadline:
                self.fail('Local worker did not finish')
            time.sleep(.005)
        self.app.processEvents()

    def test_discovery_only_never_starts_download_even_when_allowed(self):
        panel, adapter = self.panel()
        with patch.object(panel, 'launch') as launch:
            self.discover(panel, adapter)
        launch.assert_not_called()
        self.assertEqual(adapter.downloads, 0)
        self.assertTrue(panel.download.isEnabled())
        self.assertIn('chưa tải', panel.status.text())
        self.assertEqual(panel.progress.value(), 0)

    def test_content_permission_unknown_is_not_unknown_access_or_a_block(self):
        panel, adapter = self.panel()
        self.discover(panel, adapter)
        decision = panel.download_decisions['42']
        self.assertEqual(decision.content_permission, ContentPermission.UNKNOWN)
        self.assertEqual(decision.access_status, AccessStatus.PUBLIC)
        self.assertEqual(decision.state, DownloadState.ALLOWED_BY_USER_POLICY)
        self.assertTrue(panel.download.isEnabled())

    def test_unknown_access_does_not_launch_despite_safe_image_urls(self):
        panel, adapter = self.panel(access=AccessStatus.UNKNOWN)
        self.discover(panel, adapter)
        with patch.object(panel, 'launch') as launch:
            panel.begin()
        launch.assert_not_called()
        self.assertFalse(panel.download.isEnabled())
        self.assertIn('Chưa xác minh chương PUBLIC', panel.status.text())

    def test_verified_only_unknown_permission_is_explained_and_blocked(self):
        panel, adapter = self.panel(policy=VERIFIED_ONLY)
        self.discover(panel, adapter)
        panel.begin()
        self.assertIsNone(panel.worker)
        self.assertIn('verified_only', panel.status.text())

    def test_vip_or_locked_never_launches(self):
        for access in (AccessStatus.LOCKED, AccessStatus.RESTRICTED):
            with self.subTest(access=access):
                panel, adapter = self.panel(access=access)
                self.discover(panel, adapter)
                with patch.object(panel, 'launch') as launch:
                    panel.begin()
                launch.assert_not_called()
                self.assertFalse(panel.download.isEnabled())
                self.assertEqual(panel.selected(), [])

    def test_download_click_dispatches_process_for_each_translation_mode(self):
        from providers.agy import MODE
        for mode in ('Offline', 'Online Free', MODE):
            with self.subTest(mode=mode):
                panel, adapter = self.panel(mode=mode)
                self.discover(panel, adapter)
                with patch.object(panel, 'launch') as launch:
                    panel.download.click()
                self.assertEqual(launch.call_args.args[0], 'process')
                request = launch.call_args.args[1]
                self.assertEqual(request['chapters'], panel.selected())
                self.assertEqual(request['options'].mode, mode)
                self.assertIs(request['adapter'], adapter)

    def test_real_qthread_routes_explicit_download_to_bitmap_cache_and_progress(self):
        """Real Qt + downloader/bitmap, mocked HTTP and job shell; no OCR/MT claim."""
        from core.paths import CACHE
        download_temp = tempfile.TemporaryDirectory(dir=CACHE, prefix='image-list-http-')
        self.addCleanup(download_temp.cleanup)
        incoming = Path(download_temp.name) / 'incoming'
        panel, adapter = self.panel()
        self.discover(panel, adapter)
        owner = self
        class DownloadOnlyJob:
            def __init__(self, **kwargs): self.request = kwargs
            def run(self):
                request = self.request
                request['adapter'].download_progress = lambda event: request['emit'](
                    dict(event, type='download', chapter_id='42'))
                request['adapter'].download_chapter(request['chapters'][0],
                    incoming, request['control'])
        with patch('ui.comic_sources.LocalComicJob', DownloadOnlyJob), mocked_cdn([response()]) as (connection, _):
            panel.download.click()
            self.wait_worker(panel)
        self.assertEqual(adapter.downloads, 1)
        self.assertEqual(connection.request.call_count, 1)
        self.assertEqual(panel.progress.value(), 1000)
        self.assertIn('downloaded', panel.status.text())
        from sources.cache import inspect_image
        path = incoming / '0001.png'
        before = inspect_image(path)['sha256']
        # Repeating the explicit request must use the verified receipt, no HTTP.
        with patch('ui.comic_sources.LocalComicJob', DownloadOnlyJob), mocked_cdn([]) as (connection, _):
            panel.download.click()
            self.wait_worker(panel)
        connection.request.assert_not_called()
        self.assertEqual(inspect_image(path)['sha256'], before)

    def test_process_worker_startup_error_is_visible_not_image_list_success(self):
        panel, adapter = self.panel()
        self.discover(panel, adapter)
        with patch('ui.comic_sources.LocalComicJob', side_effect=RuntimeError('Fixture worker failure')):
            panel.download.click()
            self.wait_worker(panel)
        self.assertEqual(panel.last_result['state'], 'error')
        self.assertIn('Fixture worker failure', panel.status.text())
        self.assertEqual(adapter.downloads, 0)

    def test_pause_resume_cancel_controls_reach_worker_control(self):
        from ui.comic_sources import ComicSourceWorker
        panel, _ = self.panel()
        panel.worker = ComicSourceWorker('process', {}, panel)  # Not started.
        panel.set_busy(True)
        panel.pause_job()
        self.assertTrue(panel.worker.control.paused)
        self.assertTrue(panel.resume.isEnabled())
        panel.resume_job()
        self.assertFalse(panel.worker.control.paused)
        panel.cancel_job()
        self.assertTrue(panel.worker.control.cancelled)
        self.assertFalse(panel.resume.isEnabled())
        panel.set_busy(False)
