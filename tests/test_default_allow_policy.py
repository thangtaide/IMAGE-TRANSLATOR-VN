"""Owner operating policy fixtures, not permission granted by a real website."""
from dataclasses import replace
import unittest
from sources.contracts import AccessStatus, ChapterInfo
from sources.download_policy import decide_download, DEFAULT_ALLOW_PUBLIC, VERIFIED_ONLY
from sources.states import ContentPermission, ContentPermissionEvidence, DownloadState


class DefaultAllowPolicyTests(unittest.TestCase):
    def setUp(self):
        self.chapter = ChapterInfo('12', 'Public fixture', '1', None, AccessStatus.PUBLIC, 0)

    def test_public_safe_unknown_permission_is_allowed_by_owner_only(self):
        d = decide_download(self.chapter, DEFAULT_ALLOW_PUBLIC, images_safe=True)
        self.assertEqual(d.state, DownloadState.ALLOWED_BY_USER_POLICY)
        self.assertEqual(d.content_permission, ContentPermission.UNKNOWN)
        self.assertEqual(d.basis, 'USER_POLICY_DEFAULT_ALLOW')
        self.assertIsNone(d.evidence_url)
        self.assertTrue(d.allowed)

    def test_locked_and_vip_paywall_restricted_block(self):
        for status in (AccessStatus.LOCKED, AccessStatus.RESTRICTED):
            d = decide_download(replace(self.chapter, access_status=status), DEFAULT_ALLOW_PUBLIC, images_safe=True)
            self.assertEqual(d.state, DownloadState.BLOCKED)
            self.assertFalse(d.allowed)

    def test_verified_applicable_restriction_overrides_owner_policy(self):
        evidence = ContentPermissionEvidence(ContentPermission.RESTRICTED, 'https://example.com/fixture-policy', True, True)
        d = decide_download(self.chapter, DEFAULT_ALLOW_PUBLIC, images_safe=True, evidence=evidence)
        self.assertEqual(d.state, DownloadState.BLOCKED)
        self.assertEqual(d.content_permission, ContentPermission.RESTRICTED)

    def test_unrelated_restriction_is_not_an_applicable_grant_or_restriction(self):
        evidence = ContentPermissionEvidence(ContentPermission.RESTRICTED, 'https://example.com/vip-fixture', True, False)
        d = decide_download(self.chapter, DEFAULT_ALLOW_PUBLIC, images_safe=True, evidence=evidence)
        self.assertEqual(d.state, DownloadState.ALLOWED_BY_USER_POLICY)
        self.assertEqual(d.content_permission, ContentPermission.UNKNOWN)

    def test_verified_fixture_grant_remains_separate_from_owner_policy(self):
        evidence = ContentPermissionEvidence(ContentPermission.ALLOWED, 'https://example.com/fixture-grant', True, True)
        d = decide_download(self.chapter, VERIFIED_ONLY, images_safe=True, evidence=evidence)
        self.assertEqual(d.state, DownloadState.ALLOWED_BY_VERIFIED_PERMISSION)
        self.assertEqual(d.content_permission, ContentPermission.ALLOWED)

    def test_missing_unsafe_urls_or_technical_barrier_cannot_be_overridden(self):
        for safe, barrier, expected in [(None, None, DownloadState.UNKNOWN), (False, None, DownloadState.BLOCKED),
                                         (True, 'HTTP 403', DownloadState.BLOCKED), (True, 'CAPTCHA/DRM', DownloadState.BLOCKED)]:
            self.assertEqual(decide_download(self.chapter, DEFAULT_ALLOW_PUBLIC, images_safe=safe, barrier=barrier).state, expected)

    def test_verified_only_preserves_unknown_evidence(self):
        d = decide_download(self.chapter, VERIFIED_ONLY, images_safe=True)
        self.assertEqual(d.state, DownloadState.UNKNOWN)
        self.assertFalse(d.allowed)

    def test_login_vip_paywall_captcha_and_drm_flags_are_restricted(self):
        from sources.kuaikan_dom import record_access
        for flag in ('need_login', 'need_vip', 'is_pay_comic', 'captcha', 'drm'):
            record = dict(is_free=True, locked=False, need_vip=False, is_pay_comic=False)
            record[flag] = True
            self.assertEqual(record_access(record), AccessStatus.RESTRICTED)

    def test_policy_config_is_simple_and_malformed_values_fail_closed(self):
        import tempfile
        from pathlib import Path
        from core.paths import CACHE
        from sources.download_policy import load_download_policy
        with tempfile.TemporaryDirectory(dir=CACHE) as directory:
            p = Path(directory) / 'download.json'
            self.assertEqual(load_download_policy(p), DEFAULT_ALLOW_PUBLIC)
            p.write_text('{"download_policy":"default_allow_public"}', encoding='utf-8')
            self.assertEqual(load_download_policy(p), DEFAULT_ALLOW_PUBLIC)
            p.write_text('broken', encoding='utf-8')
            self.assertEqual(load_download_policy(p), VERIFIED_ONLY)
