"""HTTP-derived sanitized state + manual DOM skeleton tests, NOT live HTTP.

Provenance and original response hashes are in the adjacent JSON. Signature
values are dummy. Full captured DOM tests and real HTTP validation stay separate.
"""
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from sources.contracts import AccessRestricted, StructureChanged
from sources.kuaikan import KuaikanAdapter
from sources.kuaikan_dom import Document, discover_images
from sources.kuaikan_state import page_payload
from sources.states import DownloadState
from tests.test_kuaikan_captured_dom import replace_payload
from tests.test_kuaikan_http_runtime import mocked_http, response

FIXTURES = Path(__file__).parent / 'fixtures'
TOPIC = 'https://www.kuaikanmanhua.com/web/topic/6677/'
CHAPTER = 'https://www.kuaikanmanhua.com/webs/comic-next/281106'


class KuaikanSSRTests(unittest.TestCase):
    def setUp(self):
        self.adapter = KuaikanAdapter()
        self.topic = (FIXTURES / 'kuaikan_topic_http_state_sanitized.html').read_text(encoding='utf-8')
        self.reader = (FIXTURES / 'kuaikan_reader_http_state_sanitized.html').read_text(encoding='utf-8')

    def test_topic_without_rendered_items_uses_verified_state(self):
        with mocked_http([response(self.topic)]) as (connection, _, __):
            comic = self.adapter.get_comic_info(TOPIC)
            chapters = self.adapter.get_chapters(comic)
        self.assertEqual(len(chapters), 26)
        self.assertEqual(chapters.analysis['source'], 'embedded_state')
        self.assertEqual(chapters.analysis['dom_items'], 0)
        self.assertEqual(chapters.analysis['main_count'], 23)
        self.assertEqual(chapters.analysis['supplementary_count'], 3)
        self.assertEqual(chapters[17].chapter_id, '281106')
        self.assertTrue(chapters.complete)
        self.assertEqual(connection.request.call_count, 1)
        self.assertTrue(all(self.adapter.download_decision(c).state == DownloadState.UNKNOWN for c in chapters))

    def test_state_order_is_preserved_without_sorting_ids(self):
        data = page_payload(Document(self.topic))
        data['topic_info']['comics'].reverse()
        chapters = self.adapter.parse_chapters_html(TOPIC, replace_payload(self.topic, data), 26)
        self.assertEqual([c.chapter_id for c in chapters], [str(c['id']) for c in data['topic_info']['comics']])
        self.assertEqual([c.order_index for c in chapters], list(range(len(chapters))))

    def test_bad_and_duplicate_state_records_produce_partial_warning(self):
        data = page_payload(Document(self.topic))
        records = data['topic_info']['comics']
        records[0] = dict(records[1])
        records[-1] = {'id': 'not-real', 'title': 'invalid'}
        chapters = self.adapter.parse_chapters_html(TOPIC, replace_payload(self.topic, data), 26)
        self.assertEqual(len(chapters), 24)
        self.assertEqual(chapters.analysis['missing_url_count'], 2)
        self.assertFalse(chapters.complete)
        self.assertTrue(chapters.warnings)

    def test_wrong_topic_identity_or_empty_state_fails(self):
        with self.assertRaises(StructureChanged):
            self.adapter.parse_chapters_html(TOPIC.replace('6677', '6678'), self.topic, 26)
        data = page_payload(Document(self.topic))
        data['topic_info']['comics'] = []
        with self.assertRaises(StructureChanged):
            self.adapter.parse_chapters_html(TOPIC, replace_payload(self.topic, data), 26)

    def test_direct_reader_expands_only_from_this_responses_verified_manifest(self):
        with mocked_http([response(self.reader)]) as (connection, _, __):
            comic = self.adapter.get_comic_info(CHAPTER)
            chapter = self.adapter.get_chapters(comic)[0]
            images = self.adapter.get_chapter_images(chapter)
        self.assertEqual(connection.request.call_count, 1)
        self.assertEqual(len(images), 116)
        self.assertEqual(images.analysis['dom_unique_valid_urls'], 2)
        self.assertEqual(images.analysis['content_img_elements'], 4)
        self.assertEqual(images.analysis['duplicate_elements'], 2)
        self.assertEqual(images.analysis['discovery_source'], 'embedded_manifest')
        self.assertEqual(images.analysis['manifest_matched_urls'], 116)
        self.assertTrue(images.analysis['dom_manifest_consistent'])
        self.assertTrue(all(i.source_attribute == 'comic_info.comic_images.url1280' for i in images))
        manifest = page_payload(Document(self.reader))['comic_info']['comic_images']
        self.assertEqual([i.source_url for i in images], [r['url1280'] for r in manifest])
        self.assertIsNone(images.complete)
        self.assertEqual(self.adapter.download_decision(chapter).state, DownloadState.ALLOWED_BY_USER_POLICY)
        self.assertEqual(self.adapter.download_decision(chapter).content_permission.value, 'UNKNOWN')
        self.assertTrue(all(i.local_path is None and i.download_status == 'discovered' for i in images))

    def test_manifest_discovery_does_not_require_rendered_img(self):
        start = self.reader.index('<div class="comicDetails">')
        end = self.reader.index('<!-- HTTP-derived whitelisted')
        body = self.reader[:start] + self.reader[end:]
        images = discover_images(self.adapter.parse_reader_html(CHAPTER, body))
        self.assertEqual(len(images), 116)
        self.assertEqual(images.analysis['dom_unique_valid_urls'], 0)
        self.assertEqual(images.analysis['discovery_source'], 'embedded_manifest')

    def test_invalid_manifest_url_is_not_replaced_or_fetched(self):
        data = page_payload(Document(self.reader))
        record = data['comic_info']['comic_images'][-1]
        record['url'] = record['url1280'] = 'https://127.0.0.1/private'
        images = discover_images(self.adapter.parse_reader_html(CHAPTER, replace_payload(self.reader, data)))
        self.assertEqual(len(images), 115)
        self.assertEqual(images.analysis['manifest_rejected_entries'], 1)
        self.assertTrue(all(urlsplit(i.source_url).hostname == 'tn1.kkmh.com' for i in images))
        self.assertIsNone(images.complete)

    def test_conflicting_dom_order_does_not_silently_merge_manifest(self):
        data = page_payload(Document(self.reader))
        data['comic_info']['comic_images'].reverse()
        images = discover_images(self.adapter.parse_reader_html(CHAPTER, replace_payload(self.reader, data)))
        self.assertEqual(len(images), 2)
        self.assertEqual(images.analysis['discovery_source'], 'dom_elements')
        self.assertFalse(images.analysis['dom_manifest_consistent'])
        self.assertTrue(images.warnings)

    def test_wrong_chapter_id_and_locked_flags_cannot_enable_manifest_discovery(self):
        with self.assertRaises(StructureChanged):
            self.adapter.parse_reader_html(CHAPTER.replace('281106', '281107'), self.reader)
        data = page_payload(Document(self.reader))
        data['comic_info']['locked'] = True
        with self.assertRaises(AccessRestricted):
            discover_images(self.adapter.parse_reader_html(CHAPTER, replace_payload(self.reader, data)))

    def test_scaled_height_is_unknown_if_not_declared(self):
        data = page_payload(Document(self.reader))
        data['comic_info']['comic_images'][0]['width'] = 2560
        images = discover_images(self.adapter.parse_reader_html(CHAPTER, replace_payload(self.reader, data)))
        self.assertIsNone(images[0].height)
        self.assertEqual(images[0].width, 1280)
