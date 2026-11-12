"""Official HTTP fixtures only. Never use the real key, API, CLI or user DB."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch,Mock
from types import SimpleNamespace

import requests
from PIL import Image
from core.runtime import prepare_inference_runtime
prepare_inference_runtime()
from PySide6.QtWidgets import QApplication,QDialog
from core.paths import ROOT
from core.types import Options
from core.storage import save_options,load_options,file_digest
from core.resume import ResumeStore,work_recipe
from core.pipeline import ProcessingManager
from core.whole_chapter import WholeChapterJob,GroqWholeChapterTranslator
from providers.agy import AGYProvider,MODE
from providers.groq_api import GroqProvider,MODELS,MODEL,BASE_URL,key_available,retry_delay
from providers.online import ProviderSuspended
from tests.test_core import WorkspaceCase,FakeOCR
from tests.image_fixtures import provider_page
from ui.settings_dialog import SettingsDialog
from ui.main_window import MainWindow

CANARY='unit-test-groq-secret-not-a-real-key'


class HTTP:
    def __init__(self):
        self.calls=[];self.status=200;self.body=None;self.headers={'Content-Type':'application/json'}
        self.fail_after=None;self.exception=None
    def post(self,url,**kwargs):
        self.calls.append((url,kwargs))
        if self.exception:raise self.exception
        body=json.loads(kwargs['json']['messages'][1]['content'])
        data=self.body if self.body is not None else dict(model=kwargs['json']['model'],choices=[dict(finish_reason='stop',
            message=dict(content=json.dumps(dict(translations=[dict(id=r['id'],text=r['text'].replace('你好','Xin chào').replace('Hello world','Xin chào thế giới')) for r in reversed(body['regions'])]))))])
        r=requests.Response();r.status_code=429 if self.fail_after is not None and len(self.calls)>self.fail_after else self.status
        r.headers.update(self.headers);r._content=data if isinstance(data,bytes) else json.dumps(data).encode();r._content_consumed=True
        return r
    def close(self):pass


class GroqTests(WorkspaceCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        super().setUp();self.http=HTTP()
        for p in (patch.dict(os.environ,{'GROQ_API_KEY':CANARY}),patch('providers.groq_api.requests.Session',return_value=self.http),
                  patch.object(AGYProvider,'_invoke',side_effect=AssertionError('Groq must never invoke AGY'))):
            p.start();self.addCleanup(p.stop)
    def provider(self,**kwargs):return GroqProvider(client=self.http,**kwargs)
    def options(self,**kwargs):return Options(source=str(self.source),output=str(self.output),mode=MODE,ai_provider='groq',**kwargs)

    def test_environment_key_and_options_never_store_credentials(self):
        self.assertTrue(key_available())
        with patch.dict(os.environ,{'GROQ_API_KEY':''}):
            self.assertFalse(key_available())
            with self.assertRaises(ProviderSuspended) as e:self.provider().translate('你好','zh')
            self.assertEqual(e.exception.code,'API_KEY_MISSING')
        self.assertEqual(self.http.calls,[])
        self.assertNotIn(CANARY,json.dumps(self.options().to_dict()))

    def test_three_fixed_models_request_schema_and_id_mapping(self):
        self.assertEqual(len(MODELS),3)
        for _,model in MODELS:
            self.assertEqual(self.provider(model=model).translate_batch(['你好','你好！'],'zh',item_ids=['a','b']),['Xin chào','Xin chào！'])
            url,args=self.http.calls[-1]
            self.assertEqual(url,BASE_URL+'/chat/completions');self.assertEqual(args['json']['model'],model)
            self.assertEqual(args['headers']['Authorization'],'Bearer '+CANARY)
            self.assertTrue(args['json']['response_format']['json_schema']['strict'])
            self.assertEqual(args['json']['max_completion_tokens'],512)
            self.assertNotIn('reasoning_effort',args['json']);self.assertFalse(args['allow_redirects'])

    def test_invalid_model_never_falls_back(self):
        with self.assertRaises(ProviderSuspended):self.provider(model='unknown')
        self.assertFalse(self.http.calls)

    def test_http_errors_are_safe_and_latched_without_retry(self):
        for status,code in [(400,'INVALID_REQUEST'),(401,'AUTH_REQUIRED'),(403,'ACCESS_DENIED'),(404,'MODEL_UNAVAILABLE'),(429,'RATE_LIMITED'),(500,'PROVIDER_UNAVAILABLE'),(503,'PROVIDER_UNAVAILABLE')]:
            self.http.status=status;self.http.headers['Retry-After']='12'
            p=self.provider();before=len(self.http.calls)
            for _ in range(2):
                with self.assertRaises(ProviderSuspended) as e:p.translate('你好','zh')
                self.assertEqual(e.exception.code,code);self.assertNotIn(CANARY,str(e.exception))
            self.assertEqual(len(self.http.calls)-before,1)
        self.assertEqual(retry_delay('12'),12)

    def test_timeout_and_network_do_not_expose_exception_or_key(self):
        for kind,code in [(requests.Timeout,'TIMEOUT'),(requests.ConnectionError,'NETWORK_ERROR')]:
            self.http.exception=kind(CANARY)
            with self.assertRaises(ProviderSuspended) as e:self.provider().translate('你好','zh')
            self.assertEqual(e.exception.code,code);self.assertNotIn(CANARY,str(e.exception))

    def test_json_shape_duplicate_missing_tool_or_truncated_response_rejected(self):
        cases=[b'not JSON',dict(model=MODEL,choices=[])]
        for rows in ([dict(id='a',text='Một'),dict(id='a',text='Hai')],[dict(id='wrong',text='Một')]):
            cases.append(dict(model=MODEL,choices=[dict(finish_reason='stop',message=dict(content=json.dumps(dict(translations=rows))))]))
        cases.append(dict(model=MODEL,choices=[dict(finish_reason='length',message=dict(content='{}'))]))
        cases.append(dict(model=MODEL,choices=[dict(finish_reason='stop',message=dict(content='{}',tool_calls=[{}]))]))
        for body in cases:
            self.http.body=body
            with self.assertRaises(ProviderSuspended) as e:self.provider().translate_batch(['你好'],'zh',item_ids=['a'])
            self.assertEqual(e.exception.code,'INVALID_RESPONSE')

    def test_settings_save_cancel_and_restore_preserve_agy_selection(self):
        opts=Options(agy_model='claude-sonnet-4-6');d=SettingsDialog(opts)
        d.ai_source.setCurrentIndex(d.ai_source.findData('groq'));d.reject();self.assertEqual(opts.ai_provider,'agy')
        for _,model in MODELS:
            d=SettingsDialog(opts);d.ai_source.setCurrentIndex(d.ai_source.findData('groq'))
            d.groq_model.setCurrentIndex(d.groq_model.findData(model));d.accept()
            self.assertEqual(d.result(),QDialog.Accepted);self.assertEqual(opts.ai_provider,'groq');self.assertEqual(opts.groq_model,model)
            self.assertEqual(opts.agy_model,'claude-sonnet-4-6')
            config=self.folder/'config';config.mkdir(exist_ok=True)
            with patch('core.storage.CONFIG',config):save_options(opts);loaded=load_options()
            self.assertEqual(loaded.groq_model,model);self.assertEqual(loaded.ai_provider,'groq')
            self.assertNotIn(CANARY,(config/'settings.json').read_text())
            d.close()

    def test_batch_reuses_cache_and_does_not_call_agy(self):
        self.image();opts=self.options();events=[];first=ProcessingManager(opts,self.cache,ocr=FakeOCR(),emit=events.append).run()
        second=ProcessingManager(opts,self.cache,ocr=FakeOCR()).run()
        self.assertEqual(first['completed'],1);self.assertEqual(second['skipped'],1);self.assertEqual(len(self.http.calls),1)
        self.assertTrue(any(e.get('type')=='groq_batch' for e in events))
        self.assertFalse(any(e.get('type') in ('gemini_api_batch','agy_batch') for e in events))

    def test_main_start_uses_latest_saved_groq_without_overwriting_agy_preference(self):
        self.image();config=self.folder/'config';config.mkdir()
        with patch('core.storage.CONFIG',config),patch('ui.main_window.CONFIG',config):
            original=Options(source=str(self.source),output=str(self.output),mode=MODE,agy_model='claude-sonnet-4-6')
            save_options(original);window=MainWindow(self.cache.path)
            try:
                saved=Options.from_dict(original.to_dict());saved.ai_provider='groq';save_options(saved)
                worker=SimpleNamespace(event=Mock(),finished=Mock(),start=Mock(),isRunning=lambda:False)
                with patch('ui.main_window.ProcessingWorker',return_value=worker) as factory:
                    window.start_button.click()
                queued=factory.call_args.args[0]
                self.assertEqual((queued.ai_provider,queued.groq_model),('groq',MODEL))
                self.assertEqual(queued.agy_model,'claude-sonnet-4-6')
                self.assertFalse(self.http.calls)
            finally:window.timer.stop();window.close()

    def test_resume_pins_provider_and_model_and_preserves_finished_image(self):
        for n in (1,2):provider_page((480,160),n).save(self.source/f'{n}.png')
        opts=self.options(agy_batch_regions=1);self.http.fail_after=1
        manager=ProcessingManager(opts,self.cache,ocr=FakeOCR());first=manager.run()
        self.assertEqual(first['state'],'paused_provider');old=next(self.output.glob('*.png'));h=file_digest(old)
        changed=Options.from_dict(opts.to_dict());changed.ai_provider='agy';changed.groq_model=MODELS[2][1]
        self.http.fail_after=None
        resumed=ProcessingManager(changed,self.cache,ocr=FakeOCR(),resume_id=first['resume_id']);result=resumed.run()
        self.assertEqual(result['state'],'done');self.assertEqual(file_digest(old),h)
        self.assertEqual(resumed.options.ai_provider,'groq');self.assertEqual(resumed.service.agy.model,MODEL)
        self.assertEqual(len(self.http.calls),3)

    def test_retry_after_blocks_resume_before_transport(self):
        self.image();self.http.status=429;self.http.headers['Retry-After']='120'
        opts=self.options();first=ProcessingManager(opts,self.cache,ocr=FakeOCR()).run()
        self.assertEqual(first['state'],'paused_provider');self.assertEqual(len(self.http.calls),1)
        self.http.status=200
        result=ProcessingManager(opts,self.cache,ocr=FakeOCR(),resume_id=first['resume_id']).run()
        self.assertEqual(result['state'],'paused_provider');self.assertEqual(len(self.http.calls),1)

    def test_models_do_not_share_identity_or_change_ocr_render_recipe(self):
        self.assertEqual(len({self.provider(model=m).identity for _,m in MODELS}),3)
        opts=self.options();before=work_recipe(opts);opts.ai_provider='agy';opts.groq_model=MODELS[2][1]
        self.assertEqual(work_recipe(opts),before)

    def test_settings_connection_worker_and_retry_after_do_not_auto_repeat(self):
        from ui.settings_dialog import GroqConnectionWorker
        worker=GroqConnectionWorker(MODEL);results=[];worker.result.connect(results.append);worker.run()
        self.assertEqual(results,[dict(ok=True,code='SUCCESS')]);self.assertEqual(len(self.http.calls),1)
        dialog=SettingsDialog(self.options())
        dialog.groq_connection_result(dict(code='RATE_LIMITED',retry_after=120))
        dialog.check_groq_connection();self.assertEqual(len(self.http.calls),1);dialog.close()

    def test_whole_chapter_one_request_and_resume_uses_saved_translation(self):
        from tests.test_whole_chapter import OCRFixture
        provider_page((480,160),1).save(self.source/'0001.png');opts=self.options()
        with tempfile.TemporaryDirectory(prefix='stage3g-groq-test-',dir=ROOT/'output') as name:
            workspace=Path(name);adapter=GroqWholeChapterTranslator(opts,client=self.http)
            job=WholeChapterJob(self.source,workspace,options=opts,translator=adapter,ocr=OCRFixture())
            prepared=job.run();self.assertEqual(prepared['state'],'awaiting_translation');self.assertEqual(len(self.http.calls),0)
            result=job.run(allow_translation=True,confirmed_manifest_hash=prepared['manifest_hash'])
            self.assertEqual(result['state'],'done');self.assertEqual(len(self.http.calls),1)
            result=job.run();self.assertEqual(result['state'],'done');self.assertEqual(len(self.http.calls),1)
            changed=self.options(groq_model=MODELS[2][1]);changed.ai_provider='agy'
            resumed=WholeChapterJob(self.source,workspace,options=changed,
                translator=GroqWholeChapterTranslator(changed,client=self.http),ocr=OCRFixture())
            self.assertEqual(resumed.translator.model,MODEL);self.assertEqual(resumed.run()['state'],'done')
            self.assertEqual(len(self.http.calls),1)
