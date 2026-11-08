"""MOCKED_DOWNLOADER tests: generated bitmap fixtures, dummy signed URLs, no CDN."""
import io
import json
import os
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image
from core.paths import CACHE
from core.pipeline import JobControl
from core.types import CancelledError
from sources.contracts import AccessRestricted, AccessStatus, CacheError, ChapterImage, ChapterInfo, InvalidURL, NetworkUnavailable, UsageLimited
from sources.download_policy import decide_download, DEFAULT_ALLOW_PUBLIC
from sources.kuaikan_download import DownloadLimits, download_images


def png(color='red'):
    stream = io.BytesIO()
    Image.new('RGB', (32, 48), color).save(stream, 'PNG')
    return stream.getvalue()


def response(payload=None, status=200, mime='image/png', location=None, length=True):
    payload = png() if payload is None else payload
    stream = io.BytesIO(payload)
    item = Mock(status=status)
    item.getheader.side_effect = lambda key, default=None: {'Content-Type': mime,
        'Content-Length': str(len(payload)) if length else None, 'Location': location}.get(key, default)
    item.read.side_effect = stream.read
    return item


@contextmanager
def mocked_cdn(responses):
    connection = Mock()
    connection.getresponse.side_effect = responses
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {'CODEX_SANDBOX_NETWORK_DISABLED': '0'}))
        stack.enter_context(patch('sources.kuaikan_download.getproxies', return_value={}))
        stack.enter_context(patch('sources.kuaikan_download.public_addresses', return_value=['8.8.8.8']))
        factory = stack.enter_context(patch('sources.kuaikan_download._PinnedHTTPS', return_value=connection))
        stack.enter_context(patch('sources.kuaikan_download._pause', side_effect=lambda seconds, checkpoint: checkpoint()))
        yield connection, factory


class KuaikanDownloaderTests(unittest.TestCase):
    def setUp(self):
        CACHE.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=CACHE, prefix='mock-downloader-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'chapter'
        self.chapter = ChapterInfo('fixture', 'Fixture', '1', 'https://www.kuaikanmanhua.com/webs/comic-next/42', AccessStatus.PUBLIC, 0)
        self.images = [ChapterImage(i, 'https://tn1.kkmh.com/__fixture__/page-' + str(i) + '.png?sign=' + 'a'*32 + '&t=12345678') for i in (1, 2)]
        self.decision = decide_download(self.chapter, DEFAULT_ALLOW_PUBLIC, images_safe=True)
        self.limits = DownloadLimits(delay=0)

    def run_download(self, images=None, **kwargs):
        return download_images(self.chapter, self.images if images is None else images, self.root,
                               self.decision, limits=kwargs.pop('limits', self.limits), **kwargs)

    def manifest(self):
        return json.loads((self.root / 'download-manifest.json').read_text(encoding='utf-8'))

    def test_bitmap_decode_hash_order_and_signature_preservation(self):
        with mocked_cdn([response(png('red')), response(png('blue'))]) as (connection, _):
            collection = self.run_download()
        self.assertEqual([p.name for p in collection.paths], ['0001.png', '0002.png'])
        self.assertEqual(Image.open(collection.paths[0]).size, (32, 48))
        self.assertNotEqual(self.manifest()['pages'][0]['sha256'], self.manifest()['pages'][1]['sha256'])
        for call, image in zip(connection.request.call_args_list, self.images):
            self.assertEqual(call.args[1], image.source_url.split('tn1.kkmh.com', 1)[1])
            self.assertNotIn('Cookie', call.kwargs['headers'])
            self.assertNotIn('Referer', call.kwargs['headers'])
        text = (self.root/'download-manifest.json').read_text(encoding='utf-8')
        self.assertNotIn('sign=', text)
        self.assertNotIn('https://tn1.', text)
        self.assertEqual(self.manifest()['decision']['content_permission'], 'UNKNOWN')

    def test_401_403_429_stop_without_body_retry_or_second_image(self):
        for status, error in [(401, AccessRestricted), (403, AccessRestricted), (429, UsageLimited)]:
            with self.subTest(status=status):
                self.root = Path(self.temp.name) / str(status)
                item = response(status=status)
                with mocked_cdn([item]) as (connection, _):
                    with self.assertRaises(error): self.run_download()
                    self.assertEqual(connection.request.call_count, 1)
                    item.read.assert_not_called()
                self.assertEqual(self.manifest()['state'], 'restricted')

    def test_html_or_captcha_mime_stops_without_retry(self):
        with mocked_cdn([response(b'<html>captcha</html>', mime='text/html')]) as (connection, _):
            with self.assertRaises(AccessRestricted): self.run_download()
            self.assertEqual(connection.request.call_count, 1)

    def test_html_disguised_as_image_fails_magic(self):
        with mocked_cdn([response(b'<html>not bitmap</html>')]) as (connection, _):
            with self.assertRaises(CacheError): self.run_download()
            self.assertEqual(connection.request.call_count, 1)
        self.assertFalse(list(self.root.glob('*.png')))
        self.assertTrue(list(self.root.glob('*.part')))

    def test_corrupt_png_and_mime_mismatch_do_not_publish(self):
        for payload, mime in [(b'\x89PNG\r\n\x1a\ntruncated', 'image/png'), (png(), 'image/jpeg')]:
            self.root = Path(self.temp.name) / ('bad-' + mime.split('/')[-1])
            with mocked_cdn([response(payload, mime=mime)]):
                with self.assertRaises(CacheError): self.run_download()
            self.assertFalse(list(self.root.glob('*.png')))

    def test_header_and_stream_size_limits(self):
        for known in (True, False):
            self.root = Path(self.temp.name) / str(known)
            with mocked_cdn([response(length=known)]):
                with self.assertRaises(CacheError):
                    self.run_download(limits=replace(self.limits, max_image_bytes=10))

    def test_redirect_outside_allowlist_stops(self):
        with mocked_cdn([response(status=302, location='https://127.0.0.1/private')]) as (connection, _):
            with self.assertRaises(InvalidURL): self.run_download()
            self.assertEqual(connection.request.call_count, 1)

    def test_valid_redirect_remains_bounded_and_validates_bitmap(self):
        with mocked_cdn([response(status=302, location=self.images[0].source_url), response()]) as (connection, _):
            collection = self.run_download(limit=1)
            self.assertEqual(len(collection.paths), 1)
            self.assertEqual(connection.request.call_count, 2)
            self.assertEqual(self.manifest()['state'], 'sample_complete')
            self.assertTrue(self.manifest()['sample'])

    def test_bad_host_or_dns_cannot_start_image_request(self):
        with mocked_cdn([]) as (connection, factory):
            with self.assertRaises(InvalidURL):
                self.run_download(images=[ChapterImage(1, 'https://other.example/page.png')])
            factory.assert_not_called()
        with mocked_cdn([]) as (connection, _), patch('sources.kuaikan_download.public_addresses', side_effect=InvalidURL('private DNS fixture')):
            with self.assertRaises(InvalidURL): self.run_download()
            connection.request.assert_not_called()

    def test_proxy_not_bypassed(self):
        with mocked_cdn([]) as (connection, factory), patch('sources.kuaikan_download.getproxies', return_value={'https': 'http://proxy.invalid'}):
            with self.assertRaises(NetworkUnavailable): self.run_download()
            factory.assert_not_called()

    def test_temporary_timeout_retry_is_finite(self):
        with mocked_cdn([response()]) as (connection, _):
            connection.request.side_effect = [TimeoutError('fixture'), None]
            self.assertEqual(len(self.run_download(limit=1).paths), 1)
            self.assertEqual(connection.request.call_count, 2)
        self.root = Path(self.temp.name) / 'always-timeout'
        with mocked_cdn([]) as (connection, _):
            connection.request.side_effect = TimeoutError('fixture')
            with self.assertRaises(NetworkUnavailable): self.run_download()
            self.assertEqual(connection.request.call_count, 2)

    def test_cancel_retains_partial_then_resume_and_cache_hit(self):
        control = JobControl()
        with mocked_cdn([response()]):
            with self.assertRaises(CancelledError):
                self.run_download(control=control, progress=lambda _: control.cancel())
        self.assertEqual(self.manifest()['state'], 'cancelled')
        self.assertTrue(list(self.root.glob('*.part')))
        with mocked_cdn([response(), response()]): self.run_download(control=JobControl())
        with mocked_cdn([]) as (connection, _):
            collection = self.run_download()
            self.assertEqual(len(collection.paths), 2)
            connection.request.assert_not_called()

    def test_cache_corruption_is_preserved_not_overwritten(self):
        with mocked_cdn([response()]): result = self.run_download(limit=1)
        result.paths[0].write_bytes(b'corrupt fixture')
        with mocked_cdn([]) as (connection, _):
            with self.assertRaises(CacheError): self.run_download(limit=1)
            connection.request.assert_not_called()
        self.assertEqual(result.paths[0].read_bytes(), b'corrupt fixture')

    def test_manifest_traversal_and_unowned_existing_files_rejected(self):
        self.root.mkdir()
        (self.root/'0001.png').write_bytes(b'existing data')
        with mocked_cdn([]):
            with self.assertRaises(CacheError): self.run_download()
        self.assertEqual((self.root/'0001.png').read_bytes(), b'existing data')
        self.root = Path(self.temp.name) / 'manifest'
        with mocked_cdn([response()]): self.run_download(limit=1)
        m = self.manifest();m['pages'][0]['file'] = '../outside.png'
        (self.root/'download-manifest.json').write_text(json.dumps(m), encoding='utf-8')
        with mocked_cdn([]) as (connection, _):
            with self.assertRaises(CacheError): self.run_download()
            connection.request.assert_not_called()

    def test_quota_and_image_count_limit(self):
        with mocked_cdn([response()]):
            with self.assertRaises(CacheError): self.run_download(limits=replace(self.limits, max_chapter_bytes=1))
        with mocked_cdn([]) as (connection, _):
            with self.assertRaises(CacheError): self.run_download(limits=replace(self.limits, max_images=1))
            connection.request.assert_not_called()

    def test_adapter_stops_after_cdn_403_without_another_request(self):
        from sources.kuaikan import KuaikanAdapter
        from sources.states import DownloadState
        url = 'https://www.kuaikanmanhua.com/webs/comic-next/281106'
        adapter = KuaikanAdapter()
        fixture = Path(__file__).parent/'fixtures/kuaikan_reader_http_state_sanitized.html'
        adapter.load_document(url, fixture.read_text(encoding='utf-8'))
        comic = adapter.get_comic_info(url)
        chapter = adapter.get_chapters(comic)[0]
        adapter.get_chapter_images(chapter)
        with mocked_cdn([response(status=403)]) as (connection, _):
            with self.assertRaises(AccessRestricted): adapter.download_chapter(chapter, self.root, limit=1)
            with self.assertRaises(AccessRestricted): adapter.download_chapter(chapter, self.root, limit=1)
            self.assertEqual(connection.request.call_count, 1)
        self.assertEqual(adapter.download_decision(chapter).state, DownloadState.BLOCKED)
        self.assertEqual(adapter.download_decision(chapter).content_permission.value, 'UNKNOWN')

    def test_oversized_receipt_is_not_read_or_overwritten(self):
        self.root.mkdir()
        receipt = self.root/'download-manifest.json'
        receipt.write_bytes(b'x'*1_000_001)
        with mocked_cdn([]) as (connection, _):
            with self.assertRaises(CacheError): self.run_download()
            connection.request.assert_not_called()
        self.assertEqual(receipt.stat().st_size, 1_000_001)
