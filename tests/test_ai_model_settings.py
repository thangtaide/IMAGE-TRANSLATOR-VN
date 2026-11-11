"""Fixed AGY model settings, exact invocation and pinned resume. No real requests."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from core.runtime import prepare_inference_runtime
prepare_inference_runtime()
from PySide6.QtWidgets import QApplication,QDialog,QMessageBox
from core.types import Options
from core.storage import save_options,load_options,file_digest
from core.pipeline import ProcessingManager,TranslationService,JobControl
from core.whole_chapter import AGYWholeChapterTranslator,WholeChapterJob
from providers.agy import AGYProvider,MODE
from providers.agy_models import MODELS,MODEL_IDS,selection,identifier,bind_run_model
from providers.online import ProviderSuspended
from tests.test_core import WorkspaceCase
from tests.test_agy import RunnerFixture,envelope
from tests.test_online_free import OCRFixture
from tests.image_fixtures import provider_page
from ui.settings_dialog import SettingsDialog


class ModelSettingsTests(WorkspaceCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp();self.exe=self.folder/'fake.exe';self.exe.write_bytes(b'NOT EXECUTED')
        self.runner=RunnerFixture()
        p=patch('providers.agy.check_automatic_extensions');p.start();self.addCleanup(p.stop)

    def provider(self,model,effort=''):
        return AGYProvider(str(self.exe),model=model,effort=effort,root=self.folder/'cli',runner=self.runner)

    def test_fixed_catalog_matches_observed_cli_and_legacy_ids(self):
        fixture=Path(__file__).parent/'fixtures/agy_models_1_5_5.txt'
        self.assertEqual(MODEL_IDS,{line.split('\t')[0] for line in fixture.read_text(encoding='utf-8').splitlines()})
        self.assertEqual(len(MODELS),4)
        for effort in ('low','medium','high'):
            model=identifier('gemini-flash',effort)
            self.assertEqual(selection(model)[1],effort)
            self.assertEqual(selection(model,effort)[1],effort)
        for choice in MODELS[1:]:self.assertIsNone(selection(choice.variants[0][1])[1])

    def test_every_model_batch_and_whole_command_has_nonconflicting_flags(self):
        for choice in MODELS:
            for effort,model in choice.variants:
                p=self.provider(model,effort)
                for whole in (False,True):
                    argv=p.command(['r0'],60,whole=whole)
                    self.assertEqual(argv[argv.index('--model')+1],model)
                    self.assertEqual(argv.count('--model'),1)
                    if effort:self.assertEqual(argv[argv.index('--effort')+1],effort)
                    else:self.assertNotIn('--effort',argv)
        self.assertFalse(self.runner.calls)

    def test_invalid_id_or_conflicting_effort_never_falls_back_or_calls_model(self):
        for model,effort in [('unknown',''),('gemini-3.8-flash-low','high'),('claude-sonnet-4-6','low'),('gpt-oss-120b-medium','high')]:
            with self.subTest(model=model),self.assertRaises(ProviderSuspended) as cm:self.provider(model,effort)
            self.assertEqual(cm.exception.code,'AGY_MODEL')
        self.assertFalse(self.runner.calls)

    def test_settings_save_cancel_and_reopen_keep_model_and_effort(self):
        opts=Options(agy_model='gemini-3.8-flash-medium');before=opts.to_dict()
        d=SettingsDialog(opts);self.addCleanup(d.close)
        self.assertEqual(d.ai_effort.currentData(),'medium')
        d.ai_model.setCurrentIndex(d.ai_model.findData('claude-opus'));d.reject()
        self.assertEqual(opts.to_dict(),before)
        for choice in MODELS:
            for effort,model in choice.variants:
                d=SettingsDialog(opts);self.addCleanup(d.close)
                d.ai_model.setCurrentIndex(d.ai_model.findData(choice.key))
                d.ai_effort.setCurrentIndex(d.ai_effort.findData(effort));d.accept()
                self.assertEqual(d.result(),QDialog.Accepted)
                self.assertEqual((opts.agy_model,opts.agy_effort),(model,effort))
                folder=self.folder/'settings';folder.mkdir(exist_ok=True)
                with patch('core.storage.CONFIG',folder):save_options(opts);loaded=load_options()
                reopened=SettingsDialog(loaded);self.addCleanup(reopened.close)
                self.assertEqual(reopened.ai_model.currentData(),choice.key)
                self.assertEqual(reopened.ai_effort.currentData(),effort)
                self.assertEqual(reopened.ai_effort.isEnabled(),choice.key=='gemini-flash')

    def test_unknown_saved_selection_requires_explicit_choice(self):
        opts=Options(agy_model='gemini-old-model')
        d=SettingsDialog(opts);self.addCleanup(d.close)
        self.assertEqual(d.ai_model.currentData(),'unsupported')
        with patch.object(QMessageBox,'warning') as warning:d.accept();warning.assert_called_once()
        self.assertEqual(opts.agy_model,'gemini-old-model')
        self.assertNotEqual(d.result(),QDialog.Accepted)

    def test_batch_settings_reach_provider_and_diagnostic(self):
        for choice in MODELS:
            for effort,model in choice.variants:
                opts=Options(mode=MODE,agy_executable=str(self.exe),agy_model=model,agy_effort=effort)
                def factory(**kwargs):return AGYProvider(**kwargs,root=self.folder/'factory',runner=self.runner)
                with patch('core.pipeline.AGYProvider',side_effect=factory):
                    service=TranslationService(opts,self.cache,JobControl());self.assertEqual(service.translate('你好','zh',model), 'Xin chào')
                p=service.agy;self.assertEqual(p.model,model)
                self.assertEqual(p.last_diagnostic['model'],model)
                self.assertEqual(p.last_diagnostic['effort'],effort or 'default')

    def test_whole_adapter_passes_exact_model_and_effort(self):
        manifest=dict(chapter_id='fixture',content_hash='a'*64,pages=[dict(page=dict(id='p0',index=1),regions=[dict(id='r0',ocr=dict(reading_order=0,text='你好',language='zh'))])])
        for choice in MODELS:
            for effort,model in choice.variants:
                opts=Options(agy_model=model,agy_effort=effort,agy_executable=str(self.exe))
                adapter=AGYWholeChapterTranslator(opts)
                observed=[]
                def response(p,packet,**kwargs):observed.append((p.model,p.effort));return ['Xin chào']
                with patch.object(AGYProvider,'translate_whole_chapter',response):
                    adapter.translate_manifest(manifest,[dict(id='r0',text='你好')],self.folder,JobControl())
                self.assertEqual(observed,[(model,effort or None)])
                self.assertEqual(adapter.descriptor['effort'],effort)

    def test_resume_binds_saved_model_and_preserves_completed_output(self):
        source=self.folder/'pages';source.mkdir()
        for n in (1,2):provider_page((260,150),n).save(source/f'{n}.png')
        opts=Options(source=str(source),output=str(self.output),mode=MODE,agy_executable=str(self.exe),agy_effort='low',agy_batch_regions=1)
        def runner(argv,payload,*args):
            if payload and len(self.runner.calls)==1:self.runner.failure=(1,envelope([],status='ERROR',error={'code':'RESOURCE_EXHAUSTED'}),b'')
            return self.runner(argv,payload,*args)
        def factory(**kwargs):return AGYProvider(**kwargs,root=self.folder/'resume-cli',runner=runner)
        with patch('core.pipeline.AGYProvider',side_effect=factory),patch('core.multipage.AGY_WAIT_SECONDS',(0,0)):
            first=ProcessingManager(opts,self.cache,ocr=OCRFixture());paused=first.run()
            self.assertEqual(paused['state'],'paused_provider');old=first.destination(source/'1.png');old_hash=file_digest(old)
            saved=self.cache.item(first.job_id,str(source/'1.png'))
            changed=Options.from_dict(opts.to_dict());changed.agy_model='claude-sonnet-4-6';changed.agy_effort=''
            self.runner.failure=None
            resumed=ProcessingManager(changed,self.cache,ocr=OCRFixture(),resume_id=paused['resume_id']);result=resumed.run()
        self.assertEqual(result['state'],'done');self.assertEqual(file_digest(old),old_hash)
        self.assertEqual(self.cache.item(first.job_id,str(source/'1.png')),saved)
        self.assertEqual(resumed.service.agy.model,'gemini-3.8-flash-low')
        self.assertEqual(len(self.runner.calls),3)

    def test_whole_resume_restores_saved_selection_before_recipe_check(self):
        from core.paths import ROOT
        from tests.test_whole_chapter import OCRFixture as WholeOCR
        source=self.folder/'whole-pages';source.mkdir();provider_page((300,150),1).save(source/'0001.png')
        old=Options(agy_model='gemini-3.8-flash-low',agy_effort='low',agy_executable=str(self.exe))
        with tempfile.TemporaryDirectory(prefix='stage3g-model-test-',dir=ROOT/'output') as folder:
            workspace=Path(folder)
            first=WholeChapterJob(source,workspace,options=old,translator=AGYWholeChapterTranslator(old),ocr=WholeOCR())
            self.assertEqual(first.run()['state'],'awaiting_translation')
            changed=Options(agy_model='claude-sonnet-4-6',agy_executable=str(self.exe))
            resumed=WholeChapterJob(source,workspace,options=changed,translator=AGYWholeChapterTranslator(changed),ocr=WholeOCR())
            self.assertEqual(resumed.translator.model,old.agy_model)
            self.assertEqual(resumed.run()['state'],'awaiting_translation')
            self.assertEqual(changed.agy_model,'claude-sonnet-4-6')

