"""MOCKED HTTP TESTS, never LIVE_HTTP_PASS.

Exercise the real transport -> adapter -> parser (and QThread/panel) path.
Only DNS and the HTTPS connection are simulated. Payloads are sanitized capture
excerpts or deliberately malformed responses, not new captures from HTTP.
The environment patches below apply only inside unit tests; real probes never
remove sandbox/proxy configuration.
"""
from __future__ import annotations

import os
import socket
import tempfile
import threading
import unittest
from contextlib import contextmanager, ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

from sources.contracts import AccessRestricted, NetworkUnavailable, SourceError, StructureChanged, UsageLimited
from sources.kuaikan import KuaikanAdapter
from sources.metadata_http import fetch_public_html
from sources.states import AnalysisState, DownloadState

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / 'fixtures'
TOPIC = 'https://www.kuaikanmanhua.com/web/topic/6677/'
CHAPTER = 'https://www.kuaikanmanhua.com/webs/comic-next/281106'


def excerpt(name):
    return (FIXTURES / ('kuaikan_' + name + '_captured_excerpt.html')).read_text(encoding='utf-8')


def response(body='', status=200, content_type='text/html; charset=utf-8', location=None):
    payload = body.encode('utf-8')
    result = Mock(status=status)
    headers = {'Content-Type': content_type, 'Content-Length': str(len(payload)), 'Location': location}
    result.getheader.side_effect = lambda name, default=None: headers.get(name, default)
    result.read.side_effect = [payload, b'']
    return result


@contextmanager
def mocked_http(responses):
    """No real socket or DNS; keep fetch_public_html itself unmodified."""
    connection = Mock()
    connection.getresponse.side_effect = responses
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {'CODEX_SANDBOX_NETWORK_DISABLED': '0'}))
        stack.enter_context(patch('sources.metadata_http.getproxies', return_value={}))
        dns = stack.enter_context(patch('sources.metadata_http.public_addresses', return_value=['8.8.8.8']))
        factory = stack.enter_context(patch('sources.metadata_http._PinnedHTTPS', return_value=connection))
        yield connection, dns, factory


class MockedKuaikanHTTPTests(unittest.TestCase):
    def test_200_utf8_topic_through_real_adapter_and_transport_reuses_one_request(self):
        with mocked_http([response(excerpt('topic'))]) as (connection, dns, factory):
            adapter = KuaikanAdapter()  # No load_document and no DOM preloading.
            comic = adapter.get_comic_info(TOPIC)
            chapters = adapter.get_chapters(comic)
            self.assertEqual(len(chapters), 26)
            self.assertEqual(chapters.analysis['main_count'], 23)
            self.assertEqual(next(c.chapter_id for c in chapters if c.chapter_number == '15'), '281106')
            self.assertEqual(connection.request.call_count, 1)
            self.assertEqual(connection.request.call_args.args, ('GET', '/web/topic/6677/'))
            headers = connection.request.call_args.kwargs['headers']
            self.assertNotIn('Cookie', headers)
            self.assertNotIn('Authorization', headers)
            factory.assert_called_once_with('www.kuaikanmanhua.com', '8.8.8.8')
            connection.close.assert_called_once()

    def test_allowed_relative_redirect_gets_only_allowlisted_page(self):
        with mocked_http([response(status=302, location='/web/topic/6677/'), response(excerpt('topic'))]) as (connection, dns, factory):
            comic = KuaikanAdapter().get_comic_info(TOPIC)
            self.assertTrue(comic.title)
            self.assertEqual(connection.request.call_count, 2)
            self.assertEqual(dns.call_count, 2)  # Every hop is validated/pinned.
            self.assertEqual(connection.close.call_count, 2)

    def test_timeout_keeps_network_cause_closes_connection_and_never_retries(self):
        with mocked_http([]) as (connection, _, __):
            connection.request.side_effect = TimeoutError('simulated timeout')
            with self.assertRaises(NetworkUnavailable) as caught:
                fetch_public_html(TOPIC, KuaikanAdapter.hosts)
            self.assertIsInstance(caught.exception.__cause__, TimeoutError)
            self.assertEqual(connection.request.call_count, 1)
            connection.close.assert_called_once()

    def test_dns_failure_never_constructs_https_connection(self):
        with mocked_http([]) as (connection, dns, factory):
            dns.side_effect = socket.gaierror('simulated DNS failure')
            with self.assertRaises(NetworkUnavailable) as caught:
                fetch_public_html(TOPIC, KuaikanAdapter.hosts)
            self.assertIsInstance(caught.exception.__cause__, socket.gaierror)
            factory.assert_not_called()
            connection.request.assert_not_called()

    def test_configured_proxy_is_not_bypassed(self):
        with mocked_http([]) as (connection, dns, factory):
            with patch('sources.metadata_http.getproxies', return_value={'https': 'http://proxy.invalid'}):
                with self.assertRaises(NetworkUnavailable):
                    fetch_public_html(TOPIC, KuaikanAdapter.hosts)
            dns.assert_not_called()
            factory.assert_not_called()

    def test_sandbox_guard_stops_before_dns_even_without_proxy(self):
        with mocked_http([]) as (connection, dns, factory):
            with patch.dict(os.environ, {'CODEX_SANDBOX_NETWORK_DISABLED': '1'}):
                with self.assertRaises(NetworkUnavailable):
                    fetch_public_html(TOPIC, KuaikanAdapter.hosts)
            dns.assert_not_called()
            factory.assert_not_called()

    def test_401_403_429_keep_exact_category_and_do_not_read_or_retry(self):
        for status, error, category in [(401, AccessRestricted, 'access'), (403, AccessRestricted, 'access'), (429, UsageLimited, 'usage_limit')]:
            with self.subTest(status=status):
                item = response(status=status)
                with mocked_http([item]) as (connection, _, __):
                    with self.assertRaises(error) as caught:
                        fetch_public_html(TOPIC, KuaikanAdapter.hosts)
                    self.assertEqual(type(caught.exception), error)
                    self.assertEqual(caught.exception.category, category)
                    self.assertEqual(connection.request.call_count, 1)
                    item.read.assert_not_called()
                    connection.close.assert_called_once()

    def test_non_html_rejected_before_body_read(self):
        item = response('not an HTML response', content_type='application/json')
        with mocked_http([item]) as (connection, _, __):
            with self.assertRaises(SourceError):
                fetch_public_html(TOPIC, KuaikanAdapter.hosts)
            item.read.assert_not_called()
            connection.close.assert_called_once()

    def test_missing_state_retains_metadata_but_reports_chapter_structure_error(self):
        body = excerpt('topic').split('<script>')[0]
        with mocked_http([response(body)]) as (connection, _, __):
            adapter = KuaikanAdapter()
            comic = adapter.get_comic_info(TOPIC)
            self.assertTrue(comic.title)
            with self.assertRaises(StructureChanged) as caught:
                adapter.get_chapters(comic)
            self.assertEqual(caught.exception.category, 'analysis')
            self.assertEqual(connection.request.call_count, 1)

    def test_changed_topic_structure_is_not_network_or_permission_error(self):
        with mocked_http([response('<html><title>Unrecognized layout</title></html>')]) as (connection, _, __):
            with self.assertRaises(StructureChanged):
                KuaikanAdapter().get_comic_info(TOPIC)
            self.assertEqual(connection.request.call_count, 1)

    def test_direct_chapter_http_does_not_fetch_topic_or_any_image(self):
        with mocked_http([response(excerpt('reader'))]) as (connection, _, __):
            adapter = KuaikanAdapter()
            comic = adapter.get_comic_info(CHAPTER)
            chapter = adapter.get_chapters(comic)[0]
            images = adapter.get_chapter_images(chapter)
            self.assertEqual(chapter.chapter_id, '281106')
            self.assertEqual(len(images), 3)  # Sanitized excerpt, not full DOM/live count.
            self.assertEqual(connection.request.call_count, 1)
            self.assertEqual(connection.request.call_args.args, ('GET', '/webs/comic-next/281106'))
            self.assertEqual(adapter.download_decision(chapter).state, DownloadState.ALLOWED_BY_USER_POLICY)
            self.assertEqual(adapter.download_decision(chapter).content_permission.value, 'UNKNOWN')
            self.assertTrue(all(i.local_path is None and i.download_status == 'discovered' for i in images))


class MockedHTTPQThreadTests(unittest.TestCase):
    """Real Qt event loop/worker, simulated HTTPS response bytes, no live site."""
    @classmethod
    def setUpClass(cls):
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from core.runtime import prepare_inference_runtime
        prepare_inference_runtime()
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def run_panel(self, url, body):
        from PySide6.QtCore import QEventLoop, QTimer, Qt
        from PySide6.QtTest import QTest
        from core.types import Options
        from ui.comic_sources import ComicSourcesPanel

        temporary = tempfile.TemporaryDirectory(dir=ROOT / 'output', prefix='mock-http-worker-')
        self.addCleanup(temporary.cleanup)
        panel = ComicSourcesPanel(Options(), fixed_kind=2, settings_path=Path(temporary.name) / 'prefs.json')
        self.addCleanup(panel.close)
        panel.location.setText(url)
        entered, release = threading.Event(), threading.Event()
        beats = [0]
        def delayed_request(*args, **kwargs):
            entered.set()
            if not release.wait(4):
                raise TimeoutError('mock latency barrier was not released')
        loop = QEventLoop()
        timer, deadline = QTimer(), QTimer()
        timer.setInterval(10)
        def pulse():
            beats[0] += 1
            if beats[0] >= 3 and entered.is_set():
                release.set()
            if panel.worker and not panel.worker.isRunning() and not panel.busy:
                loop.quit()
        timer.timeout.connect(pulse)
        deadline.setSingleShot(True)
        deadline.timeout.connect(loop.quit)
        with mocked_http([response(body)]) as (connection, _, __), patch('sources.registry.ADAPTERS', (KuaikanAdapter(),)):
            connection.request.side_effect = delayed_request
            try:
                timer.start()
                deadline.start(6000)
                QTest.mouseClick(panel.analyze, Qt.LeftButton)
                loop.exec()
                self.assertIsNotNone(panel.worker)
                self.assertFalse(panel.worker.isRunning(), 'HTTP worker exceeded test deadline')
                self.assertFalse(panel.busy)
                self.assertGreaterEqual(beats[0], 3)
                self.assertTrue(entered.is_set())
                self.assertEqual(connection.request.call_count, 1)
                self.assertFalse(panel.download.isEnabled())
            finally:
                release.set()
                timer.stop()
                deadline.stop()
                if panel.worker and panel.worker.isRunning():
                    panel.worker.control.cancel()
                    panel.worker.wait(5000)
        return panel

    def test_topic_url_button_runs_http_in_qthread_and_displays_chapters(self):
        panel = self.run_panel(TOPIC, excerpt('topic'))
        self.assertEqual(panel.metadata_state, AnalysisState.METADATA_READY)
        self.assertEqual(panel.chapter_state, AnalysisState.CHAPTER_LIST_READY)
        self.assertEqual(panel.table.rowCount(), 26)
        self.assertEqual(panel.selected(), [])
        panel.check_all(True)
        self.assertEqual(len(panel.selected()), 26)
        # Existing discovery worker accepts at most10 chapters per explicit action.
        self.assertFalse(panel.analyze_images.isEnabled())
        self.assertIn('1–10', panel.analyze_images.toolTip())
        panel.check_all(False)
        from PySide6.QtCore import Qt
        panel.table.item(0, 0).setCheckState(Qt.Checked)
        self.assertTrue(panel.analyze_images.isEnabled())
        self.assertFalse(panel.download.isEnabled())

    def test_chapter_url_button_discovers_images_without_topic_or_download(self):
        panel = self.run_panel(CHAPTER, excerpt('reader'))
        self.assertEqual(panel.analysis_state, AnalysisState.IMAGE_LIST_READY)
        self.assertEqual(panel.table.item(0, 4).text(), '3')
        self.assertEqual(panel.selected(), [])
        self.assertEqual(panel.download_decisions['281106'].state, DownloadState.ALLOWED_BY_USER_POLICY)
        self.assertEqual(panel.download_decisions['281106'].content_permission.value, 'UNKNOWN')

    def test_missing_state_error_keeps_metadata_and_retry_without_access_error(self):
        panel = self.run_panel(TOPIC, excerpt('topic').split('<script>')[0])
        self.assertEqual(panel.metadata_state, AnalysisState.METADATA_READY)
        self.assertEqual(panel.chapter_state, AnalysisState.CHAPTER_LIST_ERROR)
        self.assertEqual(panel.last_error_category, 'analysis')
        self.assertTrue(panel.comic.title)
        self.assertTrue(panel.retry_analysis.isEnabled())
        self.assertTrue(panel.analyze.isEnabled())

    def test_default_policy_enables_explicit_selection_without_auto_download(self):
        panel = self.run_panel(CHAPTER, excerpt('reader'))
        self.assertFalse(panel.download.isEnabled())
        with patch.object(panel.adapter, 'download_chapter', side_effect=AssertionError('No download without click')) as download:
            panel.check_all(True)
            self.assertTrue(panel.download.isEnabled())
            self.assertEqual(panel.download_decisions['281106'].content_permission.value, 'UNKNOWN')
            self.app.processEvents()
            download.assert_not_called()
