"""Sanitized capture excerpts and full user-captured DOM, never live HTTP.

Assertions are independent observations of these captures, not parser constants.
Full captures stay in ignored output; excerpt provenance is beside the fixtures.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qsl, urlsplit

from sources.contracts import AccessRestricted, AccessStatus, StructureChanged
from sources.kuaikan import KuaikanAdapter
from sources.kuaikan_dom import Document, discover_images, image_url
from sources.kuaikan_state import decode_state, page_payload
from sources.states import DownloadState
from scripts.analyze_kuaikan_html import report_image

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / 'fixtures'
CAPTURES = ROOT / 'output/kuaikan-capture'
TOPIC = 'https://www.kuaikanmanhua.com/web/topic/6677/'
CHAPTER = 'https://www.kuaikanmanhua.com/webs/comic-next/281106'
TITLE = '\u7b2c15\u8bdd \u67e5\u51fa\u6b7b\u56e0'


def embedded(payload):
    return '<script>window.__NUXT__=(function(a){return a;}(' + json.dumps(
        {'data': [{'res': {'data': payload}}]}, ensure_ascii=True) + '));</script>'


def replace_payload(html, payload):
    start = html.index('<script>window.__NUXT__=')
    end = html.index('</script>', start) + len('</script>')
    return html[:start] + embedded(payload) + html[end:]


class NuxtDataReaderTests(unittest.TestCase):
    def test_alias_assignments_and_bounded_sparse_array(self):
        data = decode_state('window.__NUXT__=(function(a,b,c){a[0]=b;c.value=a;return {data:c};}(Array(2),{id:17},{}));')
        self.assertEqual(data, {'data': {'value': [{'id': 17}, None]}})

    def test_rejects_execution_and_unsupported_or_truncated_data(self):
        scripts = [
            'window.__NUXT__=(function(a){return a;}(fetch("https://example.com")));',
            'window.__NUXT__=(function(a){run();return a;}({}));',
            'window.__NUXT__=(function(a){return a.foo;}({foo:1}));',
            'window.__NUXT__=(function(a){return a;}(Array(9999)));',
            'window.__NUXT__=(function(a){a.__proto__={};return a;}({}));',
            'window.__NUXT__=(function(a){return {constructor:1};}({}));',
            'window.__NUXT__=(function(a){return a;}(1+2));',
            'window.__NUXT__=(function(a){return a;}());',
            'window.__NUXT__=(function(a){return a;}({}));alert(1);',
            'window.__NUXT__=(function(a){return a;',
        ]
        for script in scripts:
            with self.subTest(script=script), self.assertRaises(StructureChanged):
                decode_state(script)

    def test_wrong_page_schema_reports_structure_error(self):
        with self.assertRaises(StructureChanged):
            page_payload(Document('<script>window.__NUXT__=(function(a){return a;}({data:[{res:null}]}));</script>'))

    def test_only_whitelisted_page_fields_are_exposed(self):
        result = page_payload(Document(embedded({'topic_info': {'id': 1}, 'comments': ['private'], 'account': {'secret': 'no'}})))
        self.assertEqual(result, {'topic_info': {'id': 1}})


class CapturedExcerptTests(unittest.TestCase):
    """Sanitized excerpts DERIVED from real DOM; not a live acquisition test."""
    def setUp(self):
        self.topic = (FIXTURES / 'kuaikan_topic_captured_excerpt.html').read_text(encoding='utf-8')
        self.reader = (FIXTURES / 'kuaikan_reader_captured_excerpt.html').read_text(encoding='utf-8')
        self.adapter = KuaikanAdapter()

    def test_topic_mapping_uses_titles_not_state_array_positions(self):
        payload = page_payload(Document(self.topic))
        payload['topic_info']['comics'].reverse()
        chapters = self.adapter.parse_chapters_html(TOPIC, replace_payload(self.topic, payload), 26)
        self.assertEqual(len(chapters), 26)
        self.assertEqual(chapters.analysis['main_count'], 23)
        self.assertEqual(chapters.analysis['supplementary_count'], 3)
        self.assertEqual(chapters.analysis['literal_href_count'], 0)
        self.assertEqual(chapters.analysis['derived_url_count'], 26)
        chapter = next(c for c in chapters if c.chapter_title == TITLE)
        self.assertEqual((chapter.chapter_id, chapter.chapter_url, chapter.order_index), ('281106', CHAPTER, 17))
        self.assertTrue(all(c.url_source == 'embedded_id+verified_route' for c in chapters))
        self.assertEqual([c.order_index for c in chapters], list(range(26)))

    def test_missing_or_ambiguous_mapping_returns_partial_result(self):
        for ambiguous in (False, True):
            payload = page_payload(Document(self.topic))
            records = payload['topic_info']['comics']
            if ambiguous:
                records.append(dict(records[0], id=999999))
            else:
                records.pop(0)
            chapters = self.adapter.parse_chapters_html(TOPIC, replace_payload(self.topic, payload), 26)
            self.assertEqual(len(chapters), 25)
            self.assertEqual(chapters.analysis['missing_url_count'], 1)
            self.assertFalse(chapters.complete)
            self.assertTrue(chapters.warnings)

    def test_wrong_topic_identity_and_missing_state_are_not_empty_success(self):
        with self.assertRaises(StructureChanged):
            self.adapter.parse_chapters_html(TOPIC.replace('6677', '6678'), self.topic, 26)
        with self.assertRaises(StructureChanged):
            self.adapter.parse_chapters_html(TOPIC, self.topic.split('<script>')[0], 26)

    def test_metadata_survives_unreadable_state(self):
        broken = self.topic.replace('return a;', 'return unsupported();')
        comic = self.adapter.parse_topic_html(TOPIC, broken)
        self.assertTrue(comic.title)
        self.assertEqual(comic.chapter_count, 26)
        self.assertTrue(comic.warnings)
        with self.assertRaises(StructureChanged):
            self.adapter.parse_chapters_html(TOPIC, broken, 26)

    def test_real_reader_structure_excludes_duplicates_and_uses_metadata_dimensions(self):
        reader = self.adapter.parse_reader_html(CHAPTER, self.reader)
        self.assertEqual(reader.chapter.chapter_title, TITLE)
        images = discover_images(reader)
        self.assertEqual(len(images), 3)
        self.assertGreater(images.analysis['content_img_elements'], len(images))
        self.assertEqual(images.analysis['manifest_matched_urls'], 3)
        self.assertTrue(all(i.source_attribute == 'data-src' for i in images))
        self.assertTrue(all(i.dimensions_source == 'embedded_metadata' for i in images))
        self.assertIsNone(images.complete)
        self.assertEqual(reader.chapter.access_status, AccessStatus.PUBLIC)
        self.assertEqual(self.adapter.download_decision(reader.chapter).state, DownloadState.UNKNOWN)

    def test_reader_rejects_wrong_id_and_locked_embedded_state(self):
        with self.assertRaises(StructureChanged):
            self.adapter.parse_reader_html(CHAPTER.replace('281106', '281107'), self.reader)
        payload = page_payload(Document(self.reader))
        payload['comic_info']['locked'] = True
        with self.assertRaises(AccessRestricted):
            discover_images(self.adapter.parse_reader_html(CHAPTER, replace_payload(self.reader, payload)))

    def test_discovery_accepts_observed_signature_shape_but_report_redacts(self):
        images = discover_images(self.adapter.parse_reader_html(CHAPTER, self.reader))
        original = images[0].source_url
        self.assertEqual(image_url(original, CHAPTER), original)
        row = report_image(images[0])
        self.assertTrue(row['source_url_is_redacted'])
        self.assertEqual(row['source_url_sha256'], hashlib.sha256(original.encode()).hexdigest())
        self.assertTrue(all(v == '[REDACTED]' for _, v in parse_qsl(urlsplit(row['source_url']).query)))
        self.assertNotIn('0' * 32, json.dumps(row))
        self.assertTrue(all(i.local_path is None and i.download_status == 'discovered' for i in images))

    def test_excerpt_queries_are_dummy_not_original_signatures(self):
        for node in Document(self.reader).nodes:
            for key in ('src', 'data-src'):
                value = node.attrs.get(key, '')
                for name, content in parse_qsl(urlsplit(value).query):
                    self.assertEqual(set(content), {'0'})
        self.assertNotIn('user_id', self.topic + self.reader)
        self.assertNotIn('nickname', self.topic + self.reader)


@unittest.skipUnless((CAPTURES / 'topic-6677.dom.html').is_file() and (CAPTURES / 'chapter-281106.dom.html').is_file(),
                     'User-supplied real DOM files absent; sanitized excerpts are tested separately')
class FullCapturedDOMTests(unittest.TestCase):
    """CAPTURED REAL DOM TEST. No HTTP, image download or browser execution."""
    def setUp(self):
        self.adapter = KuaikanAdapter()

    def test_original_topic_dom(self):
        path = CAPTURES / 'topic-6677.dom.html'
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        self.adapter.load_document(TOPIC, path.read_text(encoding='utf-8-sig'))
        with patch('sources.kuaikan.fetch_public_html', side_effect=AssertionError('No HTTP in captured DOM tests')):
            comic = self.adapter.get_comic_info(TOPIC)
            chapters = self.adapter.get_chapters(comic)
        self.assertEqual(comic.title, '\u6743\u5983\u4e4b\u5e1d\u533b\u98ce\u534e')
        self.assertEqual((comic.chapter_count, comic.main_chapter_count), (26, 23))
        self.assertEqual(len(chapters), 26)
        self.assertEqual(chapters.analysis['main_count'], 23)
        self.assertEqual(chapters.analysis['supplementary_count'], 3)
        self.assertEqual(chapters.analysis['missing_url_count'], 0)
        self.assertEqual(chapters.analysis['literal_href_count'], 0)
        self.assertEqual(chapters.analysis['derived_url_count'], 26)
        self.assertTrue(chapters.complete)
        chapter = next(c for c in chapters if c.chapter_title == TITLE)
        self.assertEqual(chapter.chapter_url, CHAPTER)
        self.assertEqual(chapter.chapter_id, '281106')
        self.assertEqual([c.order_index for c in chapters], list(range(26)))
        self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_original_chapter_dom(self):
        path = CAPTURES / 'chapter-281106.dom.html'
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        self.adapter.load_document(CHAPTER, path.read_text(encoding='utf-8-sig'))
        with patch('sources.kuaikan.fetch_public_html', side_effect=AssertionError('No HTTP in captured DOM tests')):
            comic = self.adapter.get_comic_info(CHAPTER)
            chapter = self.adapter.get_chapters(comic)[0]
            images = self.adapter.get_chapter_images(chapter)
        reader = self.adapter.parse_reader_html(CHAPTER, path.read_text(encoding='utf-8-sig'))
        self.assertEqual(chapter.chapter_title, TITLE)
        self.assertEqual(chapter.chapter_id, '281106')
        self.assertEqual(reader.topic_url, TOPIC)
        self.assertTrue(reader.previous_url.endswith('/281105'))
        self.assertTrue(reader.next_url.endswith('/282537'))
        self.assertEqual(len(images), 116)
        expected = {'all_img_elements': 130, 'content_img_elements': 122, 'content_boxes': 116,
                    'duplicate_elements': 6, 'manifest_items': 116, 'manifest_matched_urls': 116}
        for key, value in expected.items():
            self.assertEqual(images.analysis[key], value, key)
        self.assertEqual(images.analysis['lazy_attribute_counts']['data-src'], 116)
        self.assertEqual(images.analysis['lazy_attribute_counts']['lazy'], 116)
        self.assertIsNone(images.complete)
        self.assertFalse(images.analysis['network_access_checked'])
        self.assertFalse(images.analysis['image_bytes_downloaded'])
        self.assertEqual(self.adapter.download_decision(chapter).state, DownloadState.ALLOWED_BY_USER_POLICY)
        self.assertEqual(self.adapter.download_decision(chapter).content_permission.value, 'UNKNOWN')
        self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())
