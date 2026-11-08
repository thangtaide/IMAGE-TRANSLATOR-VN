"""GUI/state regression. Website responses/adapters here are explicitly fixtures."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from core.paths import ROOT
from core.types import Options
from sources.cache import ChapterCache
from sources.collection import ImageCollection
from sources.contracts import AccessStatus, ChapterInfo, ComicInfo, StructureChanged, WebsiteAdapter
from sources.service import LocalComicJob
from sources.states import AnalysisState, DownloadDecision, DownloadState, ProcessingState, chapter_access


class FixtureAdapter(WebsiteAdapter):
    """A LOCAL IO fixture, never a real website downloader or permission source."""
    site_id = 'fixture_site'
    hosts = ('fixture.example',)
    download_enabled = False  # The old global flag must not control the new UI.

    def __init__(self, decision=DownloadState.UNKNOWN, image=None):
        self.decision = decision
        self.image = image
        self.downloads = 0

    def normalize_url(self, url):
        return url

    def get_comic_info(self, url, control=None):
        return ComicInfo(self.site_id, '12', url, title='Fixture comic', chapter_count=1)

    def get_chapters(self, comic, control=None):
        return [ChapterInfo('99', 'Fixture chapter', None, 'https://fixture.example/chapter', AccessStatus.UNKNOWN, 0)]

    def get_chapter_images(self, chapter, control=None):
        return []

    def download_decision(self, chapter):
        if chapter.access_status == AccessStatus.LOCKED:
            return DownloadDecision(DownloadState.RESTRICTED, 'Fixture locked')
        return DownloadDecision(self.decision, 'Fixture decision, not live rights evidence')

    def download_chapter(self, chapter, cache_dir, control=None):
        self.downloads += 1
        cache_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.image, cache_dir / '1.png')
        return ImageCollection.discover(cache_dir)


class SourceTabsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from core.runtime import prepare_inference_runtime
        prepare_inference_runtime()
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'output', prefix='tabs-unit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.comic = FixtureAdapter().get_comic_info('https://fixture.example/topic')
        self.chapter = FixtureAdapter().get_chapters(self.comic)[0]

    def panel(self, adapter=None):
        from ui.comic_sources import ComicSourcesPanel
        panel = ComicSourcesPanel(Options(), settings_path=self.root / 'preferences.json', fixed_kind=2)
        self.addCleanup(panel.close)
        if adapter:
            panel.handle_event({'type': 'collection', 'comic': self.comic,
                                'chapters': [self.chapter], 'adapter': adapter})
        return panel

    def test_main_has_three_embedded_independent_pages_and_scroll(self):
        from ui.main_window import MainWindow
        from PySide6.QtWidgets import QScrollArea
        window = MainWindow(cache_path=self.root / 'main.sqlite3', persist_settings=False)
        self.addCleanup(window.close)
        window.show()
        self.assertIsInstance(window.centralWidget(), QScrollArea)
        self.assertEqual([window.source_tabs.tabText(i) for i in range(3)], ['Ảnh đơn', 'Thư mục ảnh', 'Link truyện online'])
        window.source.setText(str(self.root))
        # QA must not persist this temporary source when the window closes.
        from core.paths import CONFIG
        original_preferences = (CONFIG / 'settings.json').read_bytes() if (CONFIG / 'settings.json').exists() else None
        window.source_tabs.setCurrentIndex(0)
        self.assertTrue(window.image_panel.isVisible())
        self.assertFalse(window.folder_page.isVisible())
        self.assertFalse(window.url_panel.isVisible())
        self.assertFalse(window.mode.isVisible())
        window.source_tabs.setCurrentIndex(2)
        self.assertTrue(window.url_panel.isVisible())
        self.assertFalse(window.url_panel.browse.isVisible())
        self.assertFalse(window.url_panel.start.isVisible())
        window.source_tabs.setCurrentIndex(1)
        self.assertEqual(window.source.text(), str(self.root))
        self.assertTrue(window.recursive.isVisible())
        window.resize(680, 500)
        self.app.processEvents()
        self.assertGreater(window.centralWidget().verticalScrollBar().maximum(), 0)
        window.close()
        self.assertEqual((CONFIG / 'settings.json').read_bytes() if (CONFIG / 'settings.json').exists() else None,
                         original_preferences)

    def test_unknown_access_is_selectable_and_analysis_stays_enabled(self):
        panel = self.panel(FixtureAdapter())
        panel.check_all(True)
        self.assertEqual(panel.selected(), [self.chapter])
        self.assertTrue(panel.analyze.isEnabled())
        self.assertFalse(panel.download.isEnabled())
        self.assertEqual(panel.analysis_state, AnalysisState.CHAPTER_LIST_READY)
        self.assertIn('Fixture decision', panel.download_status.text())

    def test_per_chapter_verified_policy_enables_download_despite_global_false(self):
        panel = self.panel(FixtureAdapter(DownloadState.ALLOWED))
        self.assertFalse(panel.download.isEnabled())  # No auto selection.
        panel.check_all(True)
        self.assertTrue(panel.download.isEnabled())
        self.assertEqual(panel.processing_state, ProcessingState.READY)
        panel.check_all(False)
        self.assertFalse(panel.download.isEnabled())

    def test_locked_chapter_cannot_be_selected(self):
        panel = self.panel()
        locked = ChapterInfo('locked', 'Locked', None, None, AccessStatus.LOCKED, 0)
        panel.handle_event({'type': 'collection', 'comic': self.comic, 'chapters': [locked], 'adapter': FixtureAdapter()})
        panel.check_all(True)
        self.assertEqual(panel.selected(), [])
        self.assertEqual(chapter_access(locked), 'CHAPTER_ACCESS_RESTRICTED')

    def test_chapter_analysis_error_preserves_metadata_not_access_error(self):
        panel = self.panel()
        panel.handle_event({'type': 'metadata', 'comic': self.comic, 'chapters': [], 'adapter': FixtureAdapter()})
        panel.handle_event({'type': 'source_error', 'phase': 'chapters', 'category': 'analysis', 'detail': 'Fixture DOM changed'})
        self.assertIs(panel.comic, self.comic)
        self.assertIn('Fixture comic', panel.title.text())
        self.assertEqual(panel.metadata_state, AnalysisState.METADATA_READY)
        self.assertEqual(panel.chapter_state, AnalysisState.CHAPTER_LIST_ERROR)
        self.assertEqual(panel.last_error_category, 'analysis')
        self.assertTrue(panel.analyze.isEnabled())
        self.assertTrue(panel.retry_analysis.isEnabled())

    def test_error_categories_are_separate(self):
        for category, expected in [('network', AnalysisState.CONNECTION_ERROR), ('access', AnalysisState.ACCESS_ERROR),
                                   ('usage_limit', AnalysisState.USAGE_LIMIT), ('url', AnalysisState.URL_INVALID),
                                   ('source', AnalysisState.TECHNICAL_ERROR)]:
            with self.subTest(category=category):
                panel = self.panel()
                panel.handle_event({'type': 'source_error', 'phase': 'metadata', 'category': category, 'detail': 'Fixture error'})
                self.assertEqual(panel.analysis_state, expected)
                self.assertEqual(panel.last_error_category, category)
                self.assertTrue(panel.analyze.isEnabled())

    def test_retry_chapters_reuses_metadata(self):
        from ui.comic_sources import ComicSourceWorker
        adapter = FixtureAdapter()
        adapter.get_chapters = lambda *args: (_ for _ in ()).throw(StructureChanged('Fixture parse error'))
        events = []
        with patch('ui.comic_sources.resolve_adapter', return_value=adapter), patch.object(adapter, 'get_comic_info') as metadata:
            worker = ComicSourceWorker('url', {'url': self.comic.source_url, 'comic': self.comic})
            worker.event.connect(events.append)
            worker.run()
        metadata.assert_not_called()
        self.assertEqual(events[-1]['phase'], 'chapters')
        self.assertEqual(events[-1]['category'], 'analysis')

    def test_busy_blocks_other_modes_but_cancel_remains_available(self):
        from ui.main_window import MainWindow
        window = MainWindow(cache_path=self.root / 'main.sqlite3', persist_settings=False)
        self.addCleanup(window.close)
        window.source_tabs.setCurrentIndex(2)
        window.url_panel.set_busy(True)
        self.assertFalse(window.source_tabs.tabBar().isEnabled())
        self.assertFalse(window.config_panel.isEnabled())
        self.assertTrue(window.url_panel.cancel.isEnabled())
        window.url_panel.set_busy(False)
        self.assertTrue(window.source_tabs.tabBar().isEnabled())

    def test_worker_rechecks_download_policy_before_any_download(self):
        image = self.root / 'source.png'
        Image.new('RGB', (50, 50), 'white').save(image)
        adapter = FixtureAdapter(DownloadState.UNKNOWN, image)
        job = LocalComicJob(self.comic, [self.chapter], self.root / 'translated', Options(language='invalid'),
                            cache=ChapterCache(self.root / 'cache'), database=self.root / 'job.sqlite3', adapter=adapter)
        result = job.run()
        self.assertEqual(result['state'], 'errors')
        self.assertEqual(adapter.downloads, 0)
        self.assertEqual(result['errors'][0]['category'], 'download_policy')

    def test_approved_fixture_download_uses_original_pipeline_and_web_provenance(self):
        image = self.root / 'source.png'
        Image.new('RGB', (50, 50), 'white').save(image)
        adapter = FixtureAdapter(DownloadState.ALLOWED, image)
        cache = ChapterCache(self.root / 'cache')
        result = LocalComicJob(self.comic, [self.chapter], self.root / 'translated', Options(language='invalid'),
                               cache=cache, database=self.root / 'job.sqlite3', adapter=adapter).run()
        # This fixture copies locally; NOT a live web download or real OCR PASS.
        self.assertEqual(adapter.downloads, 1)
        self.assertEqual(result['state'], 'errors')
        self.assertIn('Ngôn ngữ OCR', result['errors'][0]['detail'])
        manifest = cache.read(cache.directory(self.comic, self.chapter))
        self.assertEqual(manifest['site_id'], 'fixture_site')
        self.assertEqual(manifest['provenance'], 'verified_adapter_download')
