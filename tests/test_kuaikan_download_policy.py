"""Historical verified_only policy regression; default-public has separate tests.

No official permission fixture is invented. Kuaikan stays UNKNOWN without an
applicable verified grant; existing generic fixture adapters test ALLOWED wiring.
"""
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from sources.contracts import AccessStatus, ChapterInfo, WebsiteAdapter
from sources.kuaikan import KuaikanAdapter
from sources.states import DownloadState
from tests.test_kuaikan_http_runtime import mocked_http, response

CHAPTER = 'https://www.kuaikanmanhua.com/webs/comic-next/281106'
FIXTURE = Path(__file__).parent / 'fixtures/kuaikan_reader_http_state_sanitized.html'


class KuaikanDownloadPolicyTests(unittest.TestCase):
    def setUp(self):
        self.adapter = KuaikanAdapter(download_policy='verified_only')
        self.chapter = ChapterInfo('281106', 'Public chapter fixture', '15', CHAPTER,
                                   AccessStatus.PUBLIC, 0)

    def test_public_reading_does_not_grant_download(self):
        decision = self.adapter.download_decision(self.chapter)
        self.assertEqual(decision.state, DownloadState.UNKNOWN)
        self.assertTrue(decision.reason)

    def test_locked_chapter_is_restricted(self):
        decision = self.adapter.download_decision(replace(self.chapter, access_status=AccessStatus.LOCKED))
        self.assertEqual(decision.state, DownloadState.BLOCKED)

    def test_restricted_chapter_stays_restricted(self):
        decision = self.adapter.download_decision(replace(self.chapter, access_status=AccessStatus.RESTRICTED))
        self.assertEqual(decision.state, DownloadState.BLOCKED)

    def test_missing_policy_source_cannot_authorize_download(self):
        self.adapter.terms_url = None
        decision = self.adapter.download_decision(self.chapter)
        self.assertEqual(decision.state, DownloadState.UNKNOWN)
        self.assertIsNone(decision.evidence_url)

    def test_policy_page_link_alone_is_not_a_verified_grant(self):
        decision = self.adapter.download_decision(self.chapter)
        self.assertEqual(decision.evidence_url, 'https://www.kuaikanmanhua.com/webs/agreement')
        self.assertEqual(decision.state, DownloadState.UNKNOWN)

    def test_legacy_enabled_flag_and_enum_cannot_bypass_missing_grant(self):
        self.adapter.download_enabled = True  # Test only; no runtime config changes.
        decision = self.adapter.download_decision(replace(self.chapter, access_status=AccessStatus.ALLOWED))
        self.assertEqual(decision.state, DownloadState.UNKNOWN)
        self.assertFalse(decision.allowed)  # Capability does not override verified_only.

    def test_captured_public_image_urls_do_not_authorize_or_trigger_download(self):
        self.adapter.load_document(CHAPTER, FIXTURE.read_text(encoding='utf-8'))
        with patch('sources.kuaikan.fetch_public_html', side_effect=AssertionError('Offline fixture must not fetch')):
            comic = self.adapter.get_comic_info(CHAPTER)
            chapter = self.adapter.get_chapters(comic)[0]
            images = self.adapter.get_chapter_images(chapter)
        self.assertTrue(images)
        self.assertTrue(all(i.local_path is None and i.download_status == 'discovered' for i in images))
        self.assertEqual(self.adapter.download_decision(chapter).state, DownloadState.UNKNOWN)

    def test_mocked_http_200_and_manifest_do_not_become_permission(self):
        with mocked_http([response(FIXTURE.read_text(encoding='utf-8'))]) as (connection, _, __):
            comic = self.adapter.get_comic_info(CHAPTER)
            chapter = self.adapter.get_chapters(comic)[0]
            images = self.adapter.get_chapter_images(chapter)
            self.assertTrue(images)
            self.assertEqual(self.adapter.download_decision(chapter).state, DownloadState.UNKNOWN)
            self.assertEqual(connection.request.call_count, 1)  # Page only, never image/CDN.
