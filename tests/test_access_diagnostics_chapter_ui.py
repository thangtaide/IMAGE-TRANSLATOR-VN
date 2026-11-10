"""Manual response/source fixtures only. No account, production job or network."""
import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from core.paths import ROOT
from core.types import Options
from providers.gemini_api import GeminiAPIProvider, MODE
from providers.gemini_diagnostics import clean, reason_from_error
from providers.online import ProviderSuspended
from tests.test_gemini_api import HTTPFixture


class AccessDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'GEMINI_API_KEY':'fake-unit-key-no-real-credential'})
        self.env.start();self.http=HTTPFixture()

    def tearDown(self):self.env.stop()

    def provider(self, **kwargs):
        return GeminiAPIProvider(client=self.http,free_tier_confirmed=True,**kwargs)

    def test_403_records_response_not_just_attempt(self):
        self.http.status=403;self.http.body={'error':{'status':'PERMISSION_DENIED','message':'PRIVATE RAW BODY'}}
        p=self.provider()
        with self.assertRaises(ProviderSuspended) as exc:p.translate('你好','zh')
        info=exc.exception.gemini_api_diagnostic
        self.assertEqual(info['request_state'],'RESPONSE_RECEIVED');self.assertEqual(info['http_status'],403)
        self.assertTrue(info['http_response_received']);self.assertEqual(info['error_reason'],'PERMISSION_DENIED')
        self.assertEqual(len(info['request_attempt_id']),32);self.assertEqual(len(self.http.calls),1)
        self.assertNotIn('PRIVATE RAW BODY',json.dumps(info));self.assertEqual(info['preflight_state'],'READY_UNVERIFIED')

    def test_key_and_free_preflight_never_attempt_http(self):
        for key,confirmed,code in [('',True,'API_KEY_MISSING'),('fake',False,'FREE_TIER_UNCONFIRMED')]:
            p=GeminiAPIProvider(client=self.http,free_tier_confirmed=confirmed)
            with patch.dict(os.environ,{'GEMINI_API_KEY':key}),self.assertRaises(ProviderSuspended) as exc:p.translate('你好','zh')
            self.assertEqual(exc.exception.code,code)
            self.assertEqual(exc.exception.gemini_api_diagnostic['request_state'],'NOT_ATTEMPTED')
        self.assertFalse(self.http.calls)

    def test_timeout_and_network_are_attempt_only_not_access_denial(self):
        for error,code in [(requests.Timeout('PRIVATE URL'),'TIMEOUT'),(requests.ConnectionError('PRIVATE URL'),'NETWORK_ERROR')]:
            self.http.error=error;p=self.provider()
            with self.assertRaises(ProviderSuspended) as exc:p.translate('你好','zh')
            info=exc.exception.gemini_api_diagnostic
            self.assertEqual(exc.exception.code,code);self.assertEqual(info['request_state'],'ATTEMPT_STARTED')
            self.assertIsNone(info['http_status']);self.assertFalse(info['http_response_received'])
            self.assertNotIn('PRIVATE URL',json.dumps(info))

    def test_body_timeout_preserves_headers_response_evidence(self):
        original=self.http.post
        def post(*a,**kw):
            r=original(*a,**kw)
            r.iter_content=Mock(side_effect=requests.Timeout('PRIVATE PAYLOAD'))
            return r
        self.http.post=post;self.http.status=403
        with self.assertRaises(ProviderSuspended) as exc:self.provider().translate('你好','zh')
        self.assertEqual(exc.exception.code,'TIMEOUT')
        self.assertEqual(exc.exception.gemini_api_diagnostic['http_status'],403)

    def test_status_mapping_and_429_not_mislabelled_403(self):
        for status,code in [(400,'INVALID_REQUEST'),(401,'AUTH_REQUIRED'),(403,'ACCESS_DENIED'),
                            (404,'MODEL_UNAVAILABLE'),(429,'RATE_LIMITED'),(503,'PROVIDER_UNAVAILABLE')]:
            self.http.status=status
            with self.subTest(status=status),self.assertRaises(ProviderSuspended) as exc:self.provider().translate('你好','zh')
            self.assertEqual(exc.exception.code,code)
            self.assertEqual(exc.exception.gemini_api_diagnostic['http_status'],status)

    def test_quota_details_and_retry_after_stay_bounded(self):
        self.http.status=429;self.http.headers['Retry-After']='45'
        self.http.body={'error':{'status':'RESOURCE_EXHAUSTED','details':[{
            '@type':'type.googleapis.com/google.rpc.QuotaFailure','violations':[{'quotaId':'RequestsPerDayPerProject'}]}]}}
        with self.assertRaises(ProviderSuspended) as exc:self.provider().translate('你好','zh')
        self.assertEqual(exc.exception.code,'QUOTA_EXCEEDED')
        self.assertEqual(exc.exception.gemini_api_diagnostic['retry_after'],45)

    def test_repeated_call_does_not_retry_switch_or_change_attempt_identity(self):
        self.http.status=403;p=self.provider();ids=[]
        for _ in range(2):
            with self.assertRaises(ProviderSuspended) as exc:p.translate('你好','zh')
            ids.append(exc.exception.gemini_api_diagnostic['request_attempt_id'])
        self.assertEqual(ids[0],ids[1]);self.assertEqual(len(self.http.calls),1)
        self.assertIn('gemini-2.5-flash:generateContent',self.http.calls[0][0])

    def test_observer_unknown_does_not_mean_not_attempted(self):
        info=clean({'request_state':'SECRET\nBAD','http_status':403,'http_attempt_started':False})
        self.assertEqual(info['request_state'],'UNKNOWN');self.assertIsNone(info['http_attempt_started'])
        self.assertIsNone(info['http_response_received']);self.assertIsNone(info['http_status'])

    def test_reason_allowlist_drops_message_metadata_and_untrusted_fields(self):
        secret='PRIVATE-CREDENTIAL\nFAKE-LOG-LINE'
        self.assertEqual(reason_from_error({'error':{'message':secret,'status':secret}}),'UNSPECIFIED')
        info=clean(dict(error_reason=secret,raw_response=secret,headers={'x-goog-api-key':secret},
            request_attempt_id=secret,model=secret,chapter_id=secret,provider=secret))
        self.assertNotIn(secret,json.dumps(info));self.assertLess(len(json.dumps(info)),2000)

    def test_diagnostic_second_boundary_omits_all_payload_and_text(self):
        from core.diagnostics import DiagnosticLog
        with tempfile.TemporaryDirectory() as tmp:
            log=DiagnosticLog('a'*64,True,Path(tmp))
            path=log.write(dict(job_id='a'*64,error_code='ACCESS_DENIED',error_message='PRIVATE',
                ocr_source_text='PRIVATE',raw_translated_target='PRIVATE',unsafe={'raw':'PRIVATE'},
                gemini_api_request={'raw':'PRIVATE','request_state':'RESPONSE_RECEIVED','http_status':403}))
            data=Path(path).read_text(encoding='utf-8')
            self.assertNotIn('PRIVATE',data);self.assertNotIn('ocr_source_text',data)
            self.assertEqual(json.loads(data)['gemini_api_request']['http_status'],403)


class ChapterWorkflowTests(unittest.TestCase):
    def setUp(self):
        from PySide6.QtWidgets import QApplication
        from ui.main_window import MainWindow
        self.app=QApplication.instance() or QApplication([])
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'output',prefix='stage3d2-')
        self.root=Path(self.tmp.name);self.config=self.root/'config';self.config.mkdir()
        self.stack=ExitStack();self.stack.enter_context(patch('ui.main_window.CONFIG',self.config))
        self.stack.enter_context(patch.dict(os.environ,{'GEMINI_API_KEY':'fake-unit-key'}))
        with patch('ui.main_window.load_options',return_value=Options()):
            self.window=MainWindow(cache_path=self.root/'qa.sqlite3',persist_settings=False)
        self.window.source_tabs.setCurrentIndex(2);self.window.show();self.app.processEvents()
        self.panel=self.window.url_panel

    def tearDown(self):
        self.window.close();self.app.processEvents();self.stack.close();self.tmp.cleanup()

    def fill(self,count=3):
        from tests.test_source_tabs import FixtureAdapter
        from sources.contracts import ComicInfo, ChapterInfo, AccessStatus
        from sources.states import DownloadState
        self.adapter=FixtureAdapter(decision=DownloadState.ALLOWED_BY_USER_POLICY)
        chapters=[ChapterInfo(str(n),f'Chương QA {n}',str(n),f'https://fixture.example/chapter/{n}',AccessStatus.PUBLIC,n)
            for n in range(count)]
        self.panel.handle_event(dict(type='collection',comic=ComicInfo('fixture','12',None,title='QA comic'),
            chapters=chapters,adapter=self.adapter))

    def test_analysis_button_is_visible_without_advanced_options(self):
        self.fill();self.app.processEvents()
        self.assertFalse(self.panel.advanced.isChecked());self.assertTrue(self.panel.analyze_images.isVisible())
        self.assertIn('Phân tích chương',self.panel.analyze_images.text())
        self.assertFalse(self.panel.analyze_images.isEnabled());self.assertIn('Chọn',self.panel.analyze_images.toolTip())

    def test_selection_enables_analysis_without_changing_order(self):
        self.fill();before=[c.chapter_id for c in self.panel.chapters]
        self.panel.select_all.click();self.assertTrue(self.panel.analyze_images.isEnabled())
        self.assertEqual([c.chapter_id for c in self.panel.selected()],before)
        self.panel.select_none.click();self.assertFalse(self.panel.selected());self.assertFalse(self.panel.analyze_images.isEnabled())

    def test_discovery_only_no_download_translation_or_selection_change(self):
        from ui.comic_sources import ComicSourceWorker
        from sources.contracts import ChapterImage
        self.fill(1);self.panel.check_all(True);selection=self.panel.selected()
        self.adapter.get_chapter_images=Mock(return_value=[ChapterImage(1,'https://fixture.example/qa-image.png')])
        self.adapter.download_chapter=Mock(side_effect=AssertionError('No download during discovery'))
        with patch.object(self.panel,'launch') as launch,patch.object(self.panel,'begin') as begin:
            self.panel.analyze_images.click()
        self.assertEqual(launch.call_args.args[0],'images');begin.assert_not_called()
        worker=ComicSourceWorker('images',launch.call_args.args[1]);worker.event.connect(self.panel.handle_event)
        worker.run();self.adapter.download_chapter.assert_not_called()
        self.assertEqual([c.chapter_id for c in self.panel.selected()],[c.chapter_id for c in selection])
        self.assertEqual(self.panel.table.item(0,4).text(),'1')

    def test_analysis_limit_unchanged_and_explained_before_worker(self):
        self.fill(11);self.panel.check_all(True)
        self.assertFalse(self.panel.analyze_images.isEnabled());self.assertIn('1–10',self.panel.analyze_images.toolTip())
        with patch.object(self.panel,'launch') as launch:self.panel.discover_selected_images()
        launch.assert_not_called()

    def test_locked_chapter_cannot_be_selected_for_analysis(self):
        from dataclasses import replace
        from sources.contracts import AccessStatus
        self.fill(1);self.panel.chapters[0]=replace(self.panel.chapters[0],access_status=AccessStatus.LOCKED)
        self.panel.check_all(True);self.assertFalse(self.panel.selected())

    def test_source_access_failure_is_not_gemini_failure(self):
        self.fill()
        self.panel.handle_event(dict(type='source_error',category='access',phase='images',chapter_id='0',detail='Fixture restricted'))
        text=self.panel.provider_notice.title.text()+self.panel.provider_notice.message.text()
        self.assertIn('SOURCE_ACCESS_DENIED',text);self.assertIn('không phải Gemini API',text)
        self.assertNotIn('HTTP 403',text)

    def test_link_and_enter_only_dispatch_url_discovery(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        p=self.panel;p.location.setText('https://fixture.example/topic')
        with patch.object(p,'launch') as launch,patch.object(p,'begin') as begin:
            QTest.keyClick(p.location,Qt.Key_Return)
        self.assertEqual(launch.call_args.args[0],'url');begin.assert_not_called()

    def test_download_requires_explicit_click_and_keeps_provider(self):
        self.fill(1);self.panel.check_all(True)
        self.window.mode.setCurrentText('Offline')
        with patch.object(self.panel,'launch') as launch:
            self.panel.refresh_start();launch.assert_not_called()
            self.panel.download.click()
        self.assertEqual(launch.call_args.args[0],'process')
        self.assertEqual(launch.call_args.args[1]['options'].mode,'Offline')

    def test_unknown_access_does_not_claim_403_or_google_response(self):
        notice=self.panel.provider_notice;notice.show_error(dict(code='ACCESS_DENIED'))
        self.assertIn('chưa thể tiếp tục',notice.title.text())
        self.assertNotIn('HTTP 403',notice.title.text());self.assertIn('Chưa xác định',notice.message.text())

    def test_local_denial_with_not_attempted_metadata_does_not_claim_remote_403(self):
        notice=self.panel.provider_notice;notice.show_error(dict(code='ACCESS_DENIED',
            gemini_api_request=dict(request_state='NOT_ATTEMPTED')))
        self.assertNotIn('HTTP 403',notice.title.text())
        self.assertIn('chưa gọi HTTP',notice.message.text())

    def test_confirmed_http_403_has_specific_title_and_evidence(self):
        notice=self.panel.provider_notice;notice.show_error(dict(code='ACCESS_DENIED',
            gemini_api_request=dict(request_state='RESPONSE_RECEIVED',http_status=403)))
        self.assertIn('HTTP 403',notice.title.text());self.assertIn('đã nhận HTTP 403',notice.message.text())
        self.assertFalse(notice.details.isVisible())

    def test_stored_error_is_historical_even_with_old_403_metadata(self):
        notice=self.panel.provider_notice;notice.show_error(dict(code='ACCESS_DENIED',origin='journal',
            gemini_api_request=dict(request_state='RESPONSE_RECEIVED',http_status=403)))
        self.assertIn('lỗi đã lưu',notice.title.text());self.assertNotIn('HTTP 403',notice.title.text())
        self.assertIn('lần chạy trước',notice.message.text())

    def test_default_banner_is_compact_and_expansion_is_explicit(self):
        notice=self.panel.provider_notice;notice.show_error(dict(code='ACCESS_DENIED'));self.app.processEvents()
        self.assertFalse(notice.details.isVisible());self.assertLessEqual(notice.sizeHint().height(),120)
        notice.log_toggle.click();self.app.processEvents();self.assertTrue(notice.details.isVisible())

    def test_table_precedes_translation_controls_and_analysis_precedes_table(self):
        p=self.panel;self.fill();self.app.processEvents()
        self.assertLess(p.analyze_images.mapTo(p,p.analyze_images.rect().topLeft()).y(),p.table.y())
        self.assertLess(p.table.geometry().bottom(),p.download.mapTo(p,p.download.rect().topLeft()).y())
        self.assertLess(p.table.y(),p.source_options.y())

    def test_resume_disabled_without_current_checkpoint(self):
        p=self.panel;p.provider_paused=True;p.paused_chapter='0';p.source_resume_id=None;p.set_busy(False)
        self.assertFalse(p.resume.isEnabled())
        p.source_resume_id='a'*32;p.set_busy(False);self.assertTrue(p.resume.isEnabled())

    def test_only_one_banner_visible_when_switching_tabs(self):
        w=self.window;w.source_tabs.setCurrentIndex(1)
        w.provider_notice.show_error(dict(code='ACCESS_DENIED'))
        self.panel.provider_notice.show_error(dict(code='ACCESS_DENIED'))
        w.source_tabs.setCurrentIndex(2);self.app.processEvents()
        self.assertFalse(w.provider_notice.isVisible());self.assertTrue(self.panel.provider_notice.isVisible())

    def test_pipeline_api_metadata_is_safe_and_reaches_ui(self):
        from PIL import Image
        from core.pipeline import JobControl,TranslationService,ProcessingManager
        from core.types import OCRResult
        from core.storage import TranslationCache
        source=self.root/'source';source.mkdir();Image.new('RGB',(500,200),'white').save(source/'1.png')
        class OCR:
            def identity(self,*args):return 'fixture-stage3d2'
            def recognize(self,*args):return [OCRResult('你好',[[10,10],[300,10],[300,70],[10,70]],.99,'zh')],[]
        cache=TranslationCache(self.root/'pipeline.sqlite3');self.stack.callback(cache.close)
        options=Options(source=str(source),output=str(self.root/'export'),mode=MODE,gemini_api_free_tier_confirmed=True)
        control=JobControl();service=TranslationService(options,cache,control);http=HTTPFixture();http.status=403
        service.gemini_api=GeminiAPIProvider(client=http,free_tier_confirmed=True)
        events=[];manager=ProcessingManager(options,cache,control,events.append,ocr=OCR(),service=service,diagnostic_root=self.root/'diag')
        result=manager.run();self.assertEqual(result['state'],'paused_provider')
        event=next(e for e in events if e.get('type')=='provider_paused')
        info=event['gemini_api_request'];self.assertEqual(info['http_status'],403)
        self.assertEqual(len(info['batch_id']),64);self.assertEqual(info['pending_page_count'],1)
        data=json.loads(next((self.root/'diag').rglob('*.jsonl')).read_text(encoding='utf-8'))
        self.assertNotIn('ocr_source_text',data);self.assertNotIn('你好',json.dumps(data,ensure_ascii=False))
        self.panel.handle_event(dict(event,type='pipeline',pipeline_event_type='provider_paused'))
        self.assertIn('HTTP 403',self.panel.provider_notice.title.text())
