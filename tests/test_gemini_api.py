"""Manual official REST fixtures; no Gemini API, AGY CLI or production data I/O."""
import json
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import requests
from PIL import Image

from core.pipeline import JobControl, ProcessingManager, TranslationService, NumericMismatchError
from core.paths import ROOT
from core.resume import ResumeStore, work_recipe
from core.storage import TranslationCache, file_digest
from core.types import Options, OCRResult, CancelledError
from providers.gemini_api import GeminiAPIProvider, MODE, MODEL, ENDPOINT, key_available
from providers.online import ProviderSuspended

CANARY = 'unit-test-secret-never-a-real-key'


def response(rows, **kwargs):
    return dict(candidates=[dict(finishReason='STOP', content=dict(role='model',
        parts=[dict(text=json.dumps(dict(translations=rows), ensure_ascii=False))]))],
        usageMetadata=dict(promptTokenCount=25, candidatesTokenCount=15, totalTokenCount=40), **kwargs)


class HTTPFixture:
    def __init__(self):
        self.calls = []
        self.status = 200
        self.body = None
        self.transform = lambda t: t.replace('你好', 'Xin chào')
        self.headers = {'Content-Type': 'application/json'}
        self.error = None

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        packet = json.loads(kwargs['json']['contents'][0]['parts'][0]['text'])
        data = self.body if self.body is not None else response(
            [dict(id=i['id'], text=self.transform(i['text'])) for i in reversed(packet['regions'])])
        r = requests.Response()
        r.status_code = self.status
        r.headers.update(self.headers)
        r._content = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
        r._content_consumed = True
        return r

    def close(self):
        pass


class GeminiAPITests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GEMINI_API_KEY': CANARY})
        self.env.start()
        self.http = HTTPFixture()

    def tearDown(self):
        self.env.stop()

    def provider(self, **kwargs):
        return GeminiAPIProvider(client=self.http, free_tier_confirmed=True, **kwargs)

    def test_official_request_header_only_schema_and_no_tools(self):
        p = self.provider()
        self.assertEqual(p.translate_batch(['你好 1', '你好 2'], 'zh', item_ids=['page1_r0', 'page2_r0']), ['Xin chào 1', 'Xin chào 2'])
        url, kw = self.http.calls[0]
        self.assertEqual(url, ENDPOINT + MODEL + ':generateContent')
        self.assertNotIn(CANARY, url + json.dumps(kw['json']) + p.identity + repr(p.__dict__.keys()))
        self.assertEqual(kw['headers']['x-goog-api-key'], CANARY)
        self.assertTrue(kw['verify']); self.assertFalse(kw['allow_redirects'])
        self.assertNotIn('tools', kw['json']); self.assertNotIn('toolConfig', kw['json'])
        self.assertEqual(kw['json']['generationConfig']['responseMimeType'], 'application/json')
        self.assertEqual(kw['json']['generationConfig']['responseJsonSchema']['required'], ['translations'])

    def test_free_tier_confirmation_required_before_network(self):
        p = GeminiAPIProvider(client=self.http)
        with self.assertRaises(ProviderSuspended) as exc: p.translate('你好', 'zh')
        self.assertEqual(exc.exception.code, 'FREE_TIER_UNCONFIRMED'); self.assertFalse(self.http.calls)

    def test_missing_key_no_network_no_key_in_options(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': ''}):
            self.assertFalse(key_available())
            with self.assertRaises(ProviderSuspended) as exc: self.provider().translate('你好', 'zh')
        self.assertEqual(exc.exception.code, 'API_KEY_MISSING'); self.assertFalse(self.http.calls)
        self.assertNotIn(CANARY, json.dumps(Options().to_dict()))

    def test_model_does_not_silently_switch(self):
        with self.assertRaises(ProviderSuspended): self.provider(model='gemini-paid-other')
        self.assertFalse(self.http.calls)

    def test_all_http_errors_are_safe_pauses_no_retry(self):
        for status, code in [(400,'INVALID_REQUEST'),(401,'AUTH_REQUIRED'),(403,'ACCESS_DENIED'),
                             (404,'MODEL_UNAVAILABLE'),(429,'RATE_LIMITED'),(500,'PROVIDER_UNAVAILABLE'),
                             (503,'PROVIDER_UNAVAILABLE'),(302,'PROVIDER_UNAVAILABLE')]:
            with self.subTest(status=status):
                self.http.status = status; self.http.body = {'error': {'message': CANARY}}
                p = self.provider(); before = len(self.http.calls)
                for _ in range(2):
                    with self.assertRaises(ProviderSuspended) as exc: p.translate('你好', 'zh')
                    self.assertEqual(exc.exception.code, code); self.assertEqual(exc.exception.status, status)
                    self.assertNotIn(CANARY, str(exc.exception))
                self.assertEqual(len(self.http.calls), before + 1)

    def test_daily_quota_only_from_structured_details_and_retry_after(self):
        self.http.status = 429
        self.http.headers['Retry-After'] = '30'
        self.http.body = dict(error=dict(details=[{'@type':'type.googleapis.com/google.rpc.QuotaFailure',
            'violations':[{'quotaId':'GenerateRequestsPerDayPerProject'}]}]))
        with self.assertRaises(ProviderSuspended) as exc: self.provider().translate('你好', 'zh')
        self.assertEqual(exc.exception.code, 'QUOTA_EXCEEDED'); self.assertEqual(exc.exception.retry_after,30)

    def test_timeout_and_network_errors_do_not_leak_exception_or_retry(self):
        for err, code in [(requests.Timeout(CANARY),'TIMEOUT'),(requests.ConnectionError(CANARY),'NETWORK_ERROR')]:
            self.http.error = err; before = len(self.http.calls)
            with self.assertRaises(ProviderSuspended) as exc: self.provider().translate('你好', 'zh')
            self.assertEqual(exc.exception.code, code); self.assertNotIn(CANARY,str(exc.exception))
            self.assertEqual(len(self.http.calls), before+1)

    def test_budget_does_not_claim_google_quota(self):
        p = self.provider(max_requests=1); p.translate('你好', 'zh')
        with self.assertRaises(ProviderSuspended) as exc: p.translate('你好', 'zh')
        self.assertEqual(exc.exception.code,'REQUEST_BUDGET'); self.assertEqual(len(self.http.calls),1)

    def test_cancel_before_network(self):
        control = JobControl(); control.cancel()
        with self.assertRaises(CancelledError): self.provider(checkpoint=control.checkpoint).translate('你好','zh')
        self.assertFalse(self.http.calls)

    def test_cancel_while_reading_response(self):
        calls=[]
        def checkpoint():
            calls.append(True)
            if len(calls)>1: raise CancelledError('QA cancel')
        with self.assertRaises(CancelledError): self.provider(checkpoint=checkpoint).translate('你好','zh')
        self.assertEqual(len(self.http.calls),1)

    def test_wall_clock_limit_checked_while_streaming(self):
        with patch('providers.gemini_api.time.monotonic',side_effect=[0,1000]):
            with self.assertRaises(ProviderSuspended) as exc:self.provider().translate('你好','zh')
        self.assertEqual(exc.exception.code,'TIMEOUT');self.assertEqual(len(self.http.calls),1)

    def test_exact_ids_missing_duplicate_unknown_wrong_types(self):
        for rows in [[],[dict(id='r0',text='a')]*2,[dict(id='alien',text='a')],
                     [dict(id=1,text='a')],[dict(id='r0',text=42)],[dict(id='r0',text='a',extra=1)]]:
            self.http.body = response(rows)
            with self.subTest(rows=rows), self.assertRaises(ProviderSuspended): self.provider().translate('你好','zh')

    def test_malformed_json_duplicate_keys_and_ndjson(self):
        for raw in [b'bad',b'{}\n{}',b'{"candidates":[],"candidates":[]}', b'[]']:
            self.http.body=raw
            with self.subTest(raw=raw), self.assertRaises(ProviderSuspended): self.provider().translate('你好','zh')

    def test_tool_function_and_thought_parts_rejected_without_execution(self):
        for part in [{'functionCall':{'name':'shell','args':{}}}, {'text':'{}','functionCall':{}},
                     {'text':CANARY,'thought':True}, {'inlineData':{}}]:
            self.http.body=response([]); self.http.body['candidates'][0]['content']['parts']=[part]
            with self.assertRaises(ProviderSuspended) as exc: self.provider().translate('你好','zh')
            self.assertEqual(exc.exception.code,'UNEXPECTED_TOOL_USE'); self.assertNotIn(CANARY,str(exc.exception))

    def test_tool_names_in_normal_text_not_invocations(self):
        self.http.body=response([dict(id='r0',text='Không dùng shell hoặc web')])
        self.assertEqual(self.provider().translate('你好','zh'),'Không dùng shell hoặc web')

    def test_truncated_and_safety_blocked_response_not_accepted(self):
        for reason in ['MAX_TOKENS','SAFETY',None]:
            self.http.body=response([dict(id='r0',text='Xin chào')]);self.http.body['candidates'][0]['finishReason']=reason
            with self.assertRaises(ProviderSuspended):self.provider().translate('你好','zh')

    def test_mime_size_and_payload_limits(self):
        self.http.headers['Content-Type']='text/html'
        with self.assertRaises(ProviderSuspended):self.provider().translate('你好','zh')
        self.http.headers['Content-Type']='application/json';self.http.body=b' '*1_000_001
        with self.assertRaises(ProviderSuspended):self.provider().translate('你好','zh')
        count=len(self.http.calls)
        for texts in [['中']*61,['中'*6001],['中'*6000]*3]:
            with self.assertRaises(ProviderSuspended):self.provider().translate_batch(texts,'zh')
        self.assertEqual(len(self.http.calls),count)

    def test_sixty_regions_unicode_and_context_reference_only(self):
        p=self.provider()
        values=p.translate_batch(['你好']*60,'zh',context=[dict(id='old',source='你好',target='Xin chào')])
        self.assertEqual(len(values),60)
        packet=json.loads(self.http.calls[0][1]['json']['contents'][0]['parts'][0]['text'])
        self.assertEqual(len(packet['regions']),60);self.assertEqual(len(packet['reference_only']),1)

    def test_usage_allowlist_does_not_echo_response_metadata(self):
        self.http.body=response([dict(id='r0',text='Xin chào')]);self.http.body['usageMetadata']['secret']=CANARY
        events=[];self.provider(emit=events.append).translate('你好','zh')
        self.assertEqual(events[0]['usage']['totalTokenCount'],40)
        self.assertNotIn(CANARY,json.dumps(events))

    def test_invalid_ids_and_context_fail_before_network(self):
        for ids in [['same','same'], ['x/y','z'], ['x']]:
            with self.assertRaises(ProviderSuspended):
                self.provider().translate_batch(['你好','你好'],'zh',item_ids=ids)
        for context in [[dict(id='x',source='中'*1601,target='v')], [dict(id='x',source='a',target='b',tool='shell')]]:
            with self.assertRaises(ProviderSuspended):self.provider().translate_batch(['你好'],'zh',context=context)
        self.assertFalse(self.http.calls)


class GeminiPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'output',prefix='stage3d-')
        self.root=Path(self.temp.name);self.source=self.root/'source';self.source.mkdir()
        for n in (1,2,3):Image.new('RGB',(500,200),(n,n,n)).save(self.source/f'{n}.png')
        self.cache=TranslationCache(self.root/'qa.sqlite3');self.http=HTTPFixture()
        self.env=patch.dict(os.environ,{'GEMINI_API_KEY':CANARY});self.env.start()
        self.ocr_calls=[];owner=self
        class OCR:
            def identity(self,language):return 'stage3d-fake-ocr'
            def recognize(self,image,*args):
                n=int(image[0,0,0]);owner.ocr_calls.append(n)
                return [OCRResult(f'你好 {n}',[[10,10],[400,10],[400,70],[10,70]],.99,'zh')],[]
        self.ocr=OCR()

    def tearDown(self):
        self.env.stop();self.cache.close();self.temp.cleanup()

    def options(self, **kw):
        return Options(source=str(self.source),output=str(self.root/'export'),mode=MODE,
                       gemini_api_free_tier_confirmed=True,**kw)

    def manager(self, opts=None, resume_id=None, emit=lambda _:None):
        opts=opts or self.options();control=JobControl();service=TranslationService(opts,self.cache,control)
        service.gemini_api=GeminiAPIProvider(client=self.http,checkpoint=control.checkpoint,free_tier_confirmed=True)
        return ProcessingManager(opts,self.cache,control,emit,ocr=self.ocr,service=service,
                                 resume_id=resume_id,diagnostic_root=self.root/'diagnostics')

    def test_three_pages_one_api_request_correct_mapping_and_usage(self):
        events=[];m=self.manager(emit=events.append);result=m.run()
        self.assertEqual(result['completed'],3);self.assertEqual(len(self.http.calls),1)
        for n in (1,2,3):
            item=self.cache.item(m.job_id,str(self.source/f'{n}.png'))
            self.assertEqual(self.cache.get('metadata',item['fingerprint'])['translations'],[f'Xin chào {n}'])
        self.assertTrue(any(e.get('type')=='gemini_api_usage' for e in events))
        self.assertNotIn(CANARY,json.dumps(m.journal))

    def test_numeric_reject_not_cached_fallback_only_affected_page(self):
        self.http.transform=lambda t:'Xin chào 9' if '2' in t else t.replace('你好','Xin chào')
        m=self.manager();r=m.run()
        self.assertEqual(r['fallback_original'],1);self.assertEqual(r['completed'],2)
        fallback=Path(r['review_pages'][0]['output_path'])
        self.assertEqual(file_digest(fallback),file_digest(self.source/'2.png'))
        self.assertNotIn('Xin chào 9',json.dumps(m.journal))

    def test_quota_pause_restart_switch_offline_preserves_published_receipt(self):
        opts=self.options(agy_batch_regions=1)
        original=self.http.post
        def post(*a,**kw):
            if self.http.calls:self.http.status=429
            return original(*a,**kw)
        self.http.post=post
        m=self.manager(opts);r=m.run();self.assertEqual(r['state'],'paused_provider')
        self.assertEqual(r['completed'],1);self.assertEqual(len(r['pending_paths']),2)
        old=file_digest(m.destination(self.source/'1.png'));old_receipt=deepcopy(m.journal['pages'][0])
        self.cache.close();self.cache=TranslationCache(self.root/'qa.sqlite3')
        offline_opts=self.options();offline_opts.mode='Offline';control=JobControl()
        class Offline:
            online=False;identity='stage3d-offline-fixture'
            def translate(self,text,*args):return text.replace('你好','Xin chào')
        service=TranslationService(offline_opts,self.cache,control,offline=Offline())
        count=len(self.http.calls)
        m2=ProcessingManager(offline_opts,self.cache,control,ocr=self.ocr,service=service,
            resume_id=r['resume_id'],diagnostic_root=self.root/'diagnostics')
        r2=m2.run();self.assertEqual(r2['completed'],2);self.assertEqual(len(self.http.calls),count)
        self.assertEqual(file_digest(m.destination(self.source/'1.png')),old)
        self.assertEqual(m2.journal['pages'][0],old_receipt);self.assertEqual(self.ocr_calls,[1,2,3])

    def test_invalid_response_does_not_render_or_cache_pending(self):
        self.http.body=response([]);m=self.manager();r=m.run()
        self.assertEqual(r['state'],'paused_provider');self.assertEqual(r['completed'],0)
        self.assertFalse(list((self.root/'export').glob('*.png')))
        self.assertFalse(m.journal['regions']);self.assertEqual(len(self.http.calls),1)

    def test_provider_cache_namespace_and_numeric_guard_unchanged(self):
        service=self.manager().service;p=service._gemini_api()
        with self.assertRaises(NumericMismatchError):
            service._translate_using(p,'15','zh','qa',raw_target='16')
        self.assertEqual(service._translate_using(p,'15','zh','qa',raw_target='15'),'15')
        class Other:
            online=True;identity='other-provider'
            def translate(self,*args):return 'other 15'
        self.assertEqual(service._translate_using(Other(),'15','zh','qa'),'other 15')

    def test_options_provider_switch_does_not_change_work_recipe(self):
        opts=self.options();before=work_recipe(opts)
        opts.mode='Offline';opts.gemini_api_timeout=20;opts.gemini_api_free_tier_confirmed=False
        self.assertEqual(work_recipe(opts),before)

    def test_restart_same_api_reuses_ocr_and_completed_output(self):
        opts=self.options(agy_batch_regions=1);original=self.http.post
        def stop(*a,**kw):
            if self.http.calls:self.http.status=429
            return original(*a,**kw)
        self.http.post=stop
        m=self.manager(opts);r=m.run();self.assertEqual(r['completed'],1)
        old=file_digest(m.destination(self.source/'1.png'));old_receipt=deepcopy(m.journal['pages'][0])
        self.cache.close();self.cache=TranslationCache(self.root/'qa.sqlite3');self.ocr_calls.clear()
        self.http=HTTPFixture()
        m2=self.manager(opts,resume_id=r['resume_id']);r2=m2.run()
        self.assertEqual(r2['completed'],2);self.assertEqual(len(self.http.calls),2)
        self.assertEqual(file_digest(m.destination(self.source/'1.png')),old)
        self.assertEqual(m2.journal['pages'][0],old_receipt);self.assertFalse(self.ocr_calls)

    def test_error_diagnostic_and_sqlite_never_store_key_or_server_message(self):
        self.http.status=403;self.http.body=dict(error=dict(message=CANARY))
        m=self.manager();r=m.run();self.assertEqual(r['state'],'paused_provider')
        self.cache.close();self.cache=TranslationCache(self.root/'qa.sqlite3')
        for p in self.root.rglob('*'):
            if p.is_file():self.assertNotIn(CANARY.encode(),p.read_bytes(),str(p))

    def test_offline_never_constructs_api_provider(self):
        from tests.test_online_free import OfflineFixture
        opts=self.options();opts.mode='Offline';control=JobControl()
        service=TranslationService(opts,self.cache,control,offline=OfflineFixture())
        with patch('core.pipeline.GeminiAPIProvider',side_effect=AssertionError('No API in Offline')):
            self.assertEqual(service.translate('你好','zh','fixture'),'Xin chào')
        self.assertFalse(self.http.calls)

    def test_source_job_preserves_api_selection_without_running(self):
        from sources.service import LocalComicJob
        from sources.contracts import ComicInfo
        from sources.cache import ChapterCache
        job=LocalComicJob(ComicInfo('local','qa',None),[],self.root/'export',self.options(),
            cache=ChapterCache(self.root/'chapter-cache'),database=self.root/'source.sqlite3')
        self.assertEqual(job.options.mode,MODE)
        self.assertFalse(job.options.allow_online_fallback);self.assertFalse(self.http.calls)

    def test_glossary_guard_still_rejects_lost_markers(self):
        opts=self.options();opts.glossary={'名字':'Tên'}
        service=self.manager(opts).service
        from providers.online import ProviderError
        with self.assertRaises(ProviderError):
            service._translate_using(service._gemini_api(),'名字 15','zh','qa',raw_target='Name 15')

    def test_api_batch_recipe_changes_output_identity_while_ocr_is_reused(self):
        m=self.manager();m.run();first_job=m.job_id;self.ocr_calls.clear()
        opts=self.options(agy_context=False)
        # A separate QA journal is intentional: test recipe isolation, not rewriting receipts.
        m2=self.manager(opts);m2.run()
        self.assertNotEqual(m2.job_id,first_job);self.assertFalse(self.ocr_calls)

    def test_gui_four_modes_key_presence_no_network_and_usage_notice(self):
        from PySide6.QtWidgets import QApplication
        from ui.main_window import MainWindow
        from ui.settings_dialog import SettingsDialog
        app=QApplication.instance() or QApplication([])
        # Test the new-install default, independent of the user's saved selection.
        with patch('ui.main_window.load_options',return_value=Options()):
            window=MainWindow(cache_path=self.root/'gui.sqlite3',persist_settings=False)
        with patch('requests.Session.post',side_effect=AssertionError('GUI must not request')):
            self.assertEqual(window.mode.currentText(),'Offline')
            for mode in ['Offline','Online Free','AI Gemini AGY',MODE]:
                self.assertGreaterEqual(window.mode.findData(mode),0)
            window.mode.setCurrentText(MODE);self.assertIn('GEMINI_API_KEY',window.privacy.text())
            self.assertNotIn(CANARY,window.privacy.text())
            settings=SettingsDialog(self.options(),window)
            self.assertTrue(settings.gemini_api_model.isReadOnly());settings.close()
            window.handle_event(dict(type='gemini_api_usage',model=MODEL,requests=1,request_limit=64,
                usage={'totalTokenCount':40}))
            self.assertIn('40',window.privacy.text())
        window.close();app.processEvents()
