"""Routing uses a user-verified URL; DOM fixtures are MANUAL, not live/captured HTML."""
from __future__ import annotations

import os
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from sources.contracts import AccessRestricted, AccessStatus, InvalidURL, NetworkUnavailable, StructureChanged
from sources.kuaikan import KuaikanAdapter
from sources.kuaikan_dom import chapter_number, discover_images, image_url
from sources.registry import resolve_adapter
from sources.states import AnalysisState, DownloadState

FIXTURES = Path(__file__).parent / 'fixtures'
TOPIC = 'https://www.kuaikanmanhua.com/web/topic/6677/'
CHAPTER = 'https://www.kuaikanmanhua.com/webs/comic-next/281106'


class KuaikanDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.adapter = KuaikanAdapter()
        self.topic_html = (FIXTURES / 'kuaikan_topic_manual.html').read_text(encoding='utf-8')
        self.reader_html = (FIXTURES / 'kuaikan_reader_manual.html').read_text(encoding='utf-8')

    def test_topic_and_chapter_route_without_specific_id_hardcode(self):
        for identifier in ('281106', '378923', '920001'):
            url = 'https://www.kuaikanmanhua.com/webs/comic-next/' + identifier
            self.assertTrue(resolve_adapter(url).can_handle(url))
            self.assertEqual(self.adapter.chapter_id_from_url(url + '/?tracking=1#x'), identifier)
            self.assertEqual(self.adapter.normalize_url(url), url)
        self.assertEqual(self.adapter.url_kind(TOPIC), 'topic')
        self.assertEqual(self.adapter.url_kind(CHAPTER), 'chapter')

    def test_invalid_routes_and_private_urls(self):
        for url in ('https://www.kuaikanmanhua.com/webs/comic-next/0',
                    'https://www.kuaikanmanhua.com/webs/comic-next/281106/extra',
                    'https://www.kuaikanmanhua.com/webs/comic-next/../281106',
                    'https://127.0.0.1/webs/comic-next/281106'):
            with self.subTest(url=url):
                self.assertFalse(self.adapter.can_handle(url))
        with self.assertRaises(InvalidURL):
            self.adapter.chapter_id_from_url(TOPIC)

    def test_manual_reader_title_id_parent_and_navigation(self):
        reader = self.adapter.parse_reader_html(CHAPTER, self.reader_html)
        self.assertEqual(reader.chapter.chapter_id, '281106')
        self.assertEqual(reader.chapter.chapter_title, '第15话 查出死因')
        self.assertEqual(reader.chapter.chapter_number, '15')
        self.assertEqual(reader.topic_url, TOPIC)
        self.assertTrue(reader.previous_url.endswith('/920001'))
        self.assertTrue(reader.next_url.endswith('/930002'))
        self.assertEqual(reader.chapter.access_status, AccessStatus.UNKNOWN)

    def test_actual_href_values_from_manual_fixture_and_partial_list(self):
        chapters = self.adapter.parse_chapters_html(TOPIC, self.topic_html, 26)
        self.assertEqual([c.chapter_id for c in chapters], ['900001', '281106', '900002'])
        self.assertEqual([c.order_index for c in chapters], [0, 1, 2])
        self.assertEqual(chapters[1].chapter_url, CHAPTER)
        self.assertFalse(chapters.complete)
        self.assertTrue(any('từng phần' in warning for warning in chapters.warnings))
        self.assertEqual(chapters[0].content_kind, 'supplementary')
        self.assertEqual(chapters[1].content_kind, 'main')
        self.assertEqual(chapters[2].access_status, AccessStatus.LOCKED)

    def test_missing_rendered_links_is_parser_error_not_empty_success(self):
        with self.assertRaises(StructureChanged):
            self.adapter.parse_chapters_html(TOPIC, '<h2>章节列表</h2><p>共26个内容</p>', 26)

    def test_chinese_and_fullwidth_numbers(self):
        self.assertEqual(chapter_number('第十五话 Fixture'), '15')
        self.assertEqual(chapter_number('第１５话 Fixture'), '15')
        self.assertIsNone(chapter_number('公告'))

    def test_reader_heading_and_access_ignore_ui_notice_and_footer(self):
        html = '<header><h1>公告 需付费</h1></header><h1>第15话 查出死因</h1><footer>登录后阅读</footer>'
        reader = self.adapter.parse_reader_html(CHAPTER, html)
        self.assertEqual(reader.chapter.chapter_title, '第15话 查出死因')
        self.assertEqual(reader.chapter.access_status, AccessStatus.UNKNOWN)

    def test_branded_document_title_uses_matching_literal_image_name(self):
        html = '<title>Fixture comic - 第15话 查出死因 | Fixture site</title><img alt="第15话 查出死因" src="https://tn1.kkmh.com/__fixture__/page.jpg">'
        reader = self.adapter.parse_reader_html(CHAPTER, html)
        self.assertEqual(reader.chapter.chapter_title, '第15话 查出死因')
        self.assertEqual(len(discover_images(reader)), 1)

    def test_direct_chapter_does_not_require_topic_list(self):
        self.adapter.load_document(CHAPTER, self.reader_html)
        with patch('sources.kuaikan.fetch_public_html', side_effect=AssertionError('No network from saved HTML')):
            comic = self.adapter.get_comic_info(CHAPTER)
            chapters = self.adapter.get_chapters(comic)
            images = self.adapter.get_chapter_images(chapters[0])
        self.assertEqual(comic.source_kind, 'chapter')
        self.assertEqual(comic.comic_id, '6677')
        self.assertIsNone(comic.chapter_count)  # No invented full-comic count.
        self.assertEqual(len(chapters), 1)
        self.assertEqual(len(images), 2)
        self.assertIsNone(images.complete)
        self.assertEqual(self.adapter.download_decision(chapters[0]).state, DownloadState.UNKNOWN)

    def test_unidentified_parent_remains_null_not_fake_comic_id(self):
        html = self.reader_html.replace('<a href="/web/topic/6677/">Fixture parent comic</a>', '')
        self.adapter.load_document(CHAPTER, html)
        comic = self.adapter.get_comic_info(CHAPTER)
        self.assertIsNone(comic.comic_id)
        self.assertIsNone(comic.topic_url)
        self.assertEqual(len(self.adapter.get_chapters(comic)), 1)

    def test_content_images_lazy_srcset_order_and_placeholder_exclusion(self):
        images = discover_images(self.adapter.parse_reader_html(CHAPTER, self.reader_html))
        self.assertEqual([image.image_index for image in images], [1, 2])
        self.assertTrue(images[0].source_url.endswith('/page-one.jpg'))
        self.assertTrue(images[1].source_url.endswith('/page-two.webp'))
        self.assertEqual(images[0].source_attribute, 'data-src')
        self.assertEqual(images[1].source_attribute, 'srcset')
        self.assertEqual((images[0].width, images[0].height), (1280, 2400))
        self.assertEqual(images[0].dimensions_source, 'html_attributes')
        self.assertTrue(all(image.local_path is None and image.download_status == 'discovered' for image in images))

    def test_other_lazy_attributes_and_data_srcset(self):
        for key, value in [('data-original', 'https://tn1.kkmh.com/__fixture__/one.jpg'),
                           ('data-lazy-src', 'https://tn1.kkmh.com/__fixture__/one.jpg'),
                           ('data-srcset', 'https://tn1.kkmh.com/__fixture__/one.jpg 1x')]:
            html = '<h1>第9话 Fixture</h1><img alt="第9话 Fixture" src="data:image/gif;base64,AA" ' + key + '="' + value + '">'
            images = discover_images(self.adapter.parse_reader_html(CHAPTER, html))
            self.assertEqual(len(images), 1)
            self.assertEqual(images[0].source_attribute, key)

    def test_invalid_image_urls_and_credentials_are_not_exposed(self):
        for url in ('http://tn1.kkmh.com/page.jpg', 'https://localhost/page.jpg',
                    'https://tn1.kkmh.com/__fixture__/page.jpg?token=NEVER_LOG_THIS',
                    'https://tn1.kkmh.com/__fixture__/page.jpg?sig=NEVER_LOG_THIS',
                    'https://tn1.kkmh.com/__fixture__/page.jpg?auth_key=NEVER_LOG_THIS',
                    'https://user:password@tn1.kkmh.com/page.jpg', 'data:image/png;base64,AAA'):
            self.assertIsNone(image_url(url, CHAPTER))

    def test_locked_chapter_is_not_probed(self):
        self.adapter.load_document(CHAPTER, self.reader_html)
        chapter = self.adapter.parse_reader_html(CHAPTER, self.reader_html).chapter
        with patch('sources.kuaikan.fetch_public_html', side_effect=AssertionError('No network for locked chapter')):
            with self.assertRaises(AccessRestricted):
                self.adapter.get_chapter_images(replace(chapter, access_status=AccessStatus.LOCKED))
        reader = self.adapter.parse_reader_html(CHAPTER, self.reader_html.replace('<main>', '<main><p>此章节需要付费</p>'))
        with self.assertRaises(AccessRestricted):
            discover_images(reader)

    def test_network_failure_not_permission_failure(self):
        with patch('sources.kuaikan.fetch_public_html', side_effect=NetworkUnavailable('fixture network error')):
            with self.assertRaises(NetworkUnavailable):
                self.adapter.get_comic_info(CHAPTER)

    def test_no_ui_images_guessed_when_name_is_missing(self):
        with self.assertRaises(StructureChanged):
            reader = self.adapter.parse_reader_html(CHAPTER, '<h1>第15话 查出死因</h1><img alt="avatar" src="https://tn1.kkmh.com/__fixture__/avatar.jpg">')
            discover_images(reader)


class KuaikanWorkerFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from core.runtime import prepare_inference_runtime
        prepare_inference_runtime()
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_direct_url_discovers_images_without_topic_fetch_or_download(self):
        from ui.comic_sources import ComicSourceWorker, ComicSourcesPanel
        from core.types import Options
        adapter = KuaikanAdapter()
        adapter.load_document(CHAPTER, (FIXTURES / 'kuaikan_reader_manual.html').read_text(encoding='utf-8'))
        panel = ComicSourcesPanel(Options(), fixed_kind=2)
        events = []
        worker = ComicSourceWorker('url', {'url': CHAPTER})
        worker.event.connect(events.append)
        worker.event.connect(panel.handle_event)
        with patch('ui.comic_sources.resolve_adapter', return_value=adapter), \
                patch('sources.kuaikan.fetch_public_html', side_effect=AssertionError('No network in manual fixture test')), \
                patch.object(adapter, 'download_chapter', side_effect=AssertionError('Discovery must not download')):
            worker.run()
        self.assertEqual(events[-1]['type'], 'images_ready')
        self.assertEqual(panel.metadata_state, AnalysisState.METADATA_READY)
        self.assertEqual(panel.chapter_state, AnalysisState.CHAPTER_LIST_READY)
        self.assertEqual(panel.analysis_state, AnalysisState.IMAGE_LIST_READY)
        self.assertEqual(panel.table.item(0, 4).text(), '2')
        self.assertIn('2 URL ảnh', panel.title.text())
        self.assertFalse(panel.download.isEnabled())
        self.assertEqual(panel.selected(), [])
        panel.close()


    def test_image_error_does_not_clear_comic_or_chapter_metadata(self):
        from ui.comic_sources import ComicSourcesPanel
        from core.types import Options
        adapter = KuaikanAdapter()
        adapter.load_document(CHAPTER, (FIXTURES / 'kuaikan_reader_manual.html').read_text(encoding='utf-8'))
        comic = adapter.get_comic_info(CHAPTER)
        chapters = adapter.get_chapters(comic)
        panel = ComicSourcesPanel(Options(), fixed_kind=2)
        panel.handle_event({'type': 'collection', 'comic': comic, 'chapters': chapters, 'adapter': adapter})
        panel.handle_event({'type': 'source_error', 'phase': 'images', 'category': 'analysis',
                            'chapter_id': '281106', 'detail': 'Fixture lazy DOM missing'})
        self.assertIs(panel.comic, comic)
        self.assertEqual(len(panel.chapters), 1)
        self.assertEqual(panel.chapter_state, AnalysisState.CHAPTER_LIST_READY)
        self.assertEqual(panel.image_states['281106'], AnalysisState.IMAGE_LIST_ERROR)
        self.assertTrue(panel.analyze.isEnabled())
        panel.close()


@unittest.skipUnless(os.environ.get('ITVN_KUAIKAN_LIVE') == '1' and os.environ.get('CODEX_SANDBOX_NETWORK_DISABLED') != '1',
                     'Live Kuaikan HTTP not run: opt-in required and sandbox network currently restricted; no mock substitute')
class KuaikanLiveTests(unittest.TestCase):
    """Public HTML only. Even these tests NEVER download image files."""
    def test_live_topic_metadata(self):
        comic = KuaikanAdapter().get_comic_info(TOPIC)
        self.assertEqual(comic.comic_id, '6677')
        self.assertTrue(comic.title)

    def test_live_chapter_metadata(self):
        adapter = KuaikanAdapter()
        comic = adapter.get_comic_info(CHAPTER)
        chapters = adapter.get_chapters(comic)
        self.assertEqual(len(chapters), 1)
        self.assertEqual(chapters[0].chapter_id, '281106')
        self.assertEqual(chapters[0].chapter_title, '第15话 查出死因')

    def test_live_image_discovery_without_download(self):
        adapter = KuaikanAdapter()
        comic = adapter.get_comic_info(CHAPTER)
        chapter = adapter.get_chapters(comic)[0]
        images = adapter.get_chapter_images(chapter)
        self.assertTrue(images)
        self.assertTrue(all(image.local_path is None and image.download_status == 'discovered' for image in images))
