"""Model preference survives an older open window. All settings/DB paths isolated."""
from unittest.mock import patch, Mock
from types import SimpleNamespace

from core.runtime import prepare_inference_runtime
prepare_inference_runtime()
from PySide6.QtWidgets import QApplication,QDialog
from core.storage import load_options,save_options
from core.types import Options
from tests.test_core import WorkspaceCase
from ui.main_window import MainWindow
from core.resume import ResumeStore
from providers.agy import MODE
from core.storage import file_digest


class ModelPreferenceTests(WorkspaceCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        folder=self.folder/'config';folder.mkdir()
        self.settings_patch=patch('core.storage.CONFIG',folder);self.settings_patch.start()
        self.ui_patch=patch('ui.main_window.CONFIG',folder);self.ui_patch.start()
        self.addCleanup(self.settings_patch.stop);self.addCleanup(self.ui_patch.stop)

    def window(self,**kwargs):
        window=MainWindow(self.cache.path,**kwargs)
        self.addCleanup(window.close)
        return window

    def test_open_medium_window_uses_latest_saved_low_on_collect_and_close(self):
        save_options(Options(agy_model='gemini-3.8-flash-medium'))
        window=self.window()
        self.assertEqual(window.options.agy_model,'gemini-3.8-flash-medium')
        save_options(Options(agy_model='gemini-3.8-flash-low'))
        self.assertEqual(window.collect_options().agy_model,'gemini-3.8-flash-low')
        window.close()
        self.assertEqual(load_options().agy_model,'gemini-3.8-flash-low')

    def test_explicit_settings_choice_can_still_change_model(self):
        save_options(Options(agy_model='gemini-3.8-flash-low'))
        window=self.window()
        class Dialog:
            def __init__(self,options,*args,**kwargs):self.options=options
            def exec(self):
                self.options.agy_model='gemini-3.8-flash-medium'
                return QDialog.Accepted
        with patch('ui.main_window.SettingsDialog',Dialog):window.show_settings()
        self.assertEqual(load_options().agy_model,'gemini-3.8-flash-medium')

    def test_nonpersistent_qa_options_do_not_sync_from_user_settings(self):
        window=self.window(persist_settings=False)
        window.options.agy_model='gemini-3.8-flash-medium'
        with patch('ui.main_window.load_options',side_effect=AssertionError('No user settings read')):
            self.assertEqual(window.collect_options().agy_model,'gemini-3.8-flash-medium')

    def test_new_options_default_to_requested_low(self):
        self.assertEqual(Options().agy_model,'gemini-3.8-flash-low')

    def prepare_paused_sonnet_window(self):
        source=self.image()
        old=Options(source=str(self.source),output=str(self.output),mode=MODE,
                    agy_model='gemini-3.8-flash-low',agy_effort='low')
        record=ResumeStore(self.cache.path).pipeline(old,[source],self.cache)
        record['state']='paused_provider';ResumeStore(self.cache.path).save(record)
        preferred=Options.from_dict(old.to_dict());preferred.agy_model='claude-sonnet-4-6';preferred.agy_effort=''
        save_options(preferred)
        window=self.window();window.resume_id=record['id']
        window.provider_paused=True;window.provider_pending=[str(source)]
        return window,record,source

    def fake_worker(self):
        return SimpleNamespace(event=Mock(),finished=Mock(),start=Mock(),isRunning=lambda:False)

    def test_start_button_uses_saved_sonnet_instead_of_old_gemini_checkpoint(self):
        window,record,_=self.prepare_paused_sonnet_window()
        with patch('ui.main_window.ProcessingWorker',return_value=self.fake_worker()) as worker, \
                patch.object(window,'check_provider_setup',return_value=True):
            window.start_button.click()
        self.assertIsNone(worker.call_args.kwargs['resume_id'])
        self.assertEqual(worker.call_args.args[0].agy_model,'claude-sonnet-4-6')
        self.assertEqual(ResumeStore(self.cache.path).read(record['id'])['state'],'paused_provider')
        self.assertEqual(load_options().agy_model,'claude-sonnet-4-6')

    def test_explicit_continue_pins_old_model_without_overwriting_saved_sonnet(self):
        window,record,_=self.prepare_paused_sonnet_window()
        with patch('ui.main_window.ProcessingWorker',return_value=self.fake_worker()) as worker, \
                patch.object(window,'check_provider_setup',return_value=True):
            window.resume()
        self.assertEqual(worker.call_args.kwargs['resume_id'],record['id'])
        self.assertEqual(worker.call_args.args[0].agy_model,'gemini-3.8-flash-low')
        self.assertEqual(worker.call_args.args[0].agy_effort,'low')
        self.assertEqual(load_options().agy_model,'claude-sonnet-4-6')
        self.assertEqual(window.options.agy_model,'claude-sonnet-4-6')

    def test_new_start_after_continue_uses_preference_not_pinned_run(self):
        window,_,_=self.prepare_paused_sonnet_window()
        with patch('ui.main_window.ProcessingWorker',side_effect=lambda *a,**k:self.fake_worker()) as worker, \
                patch.object(window,'check_provider_setup',return_value=True):
            window.resume();window.set_running(False);window.start_button.click()
        self.assertIsNone(worker.call_args.kwargs['resume_id'])
        self.assertEqual(worker.call_args.args[0].agy_model,'claude-sonnet-4-6')

    def test_new_model_does_not_relabel_or_modify_an_old_isolated_run(self):
        window,record,_=self.prepare_paused_sonnet_window()
        old=Options.from_dict(record['options'])
        isolated=window.run_registry.create(window.run_registry.plan(old),old)
        window.active_run_id=isolated['run_id'];window.active_cache_path=isolated['database']
        marker=window.run_registry.directory(isolated['run_id'])/'run.json';before=file_digest(marker)
        with patch('ui.main_window.ProcessingWorker',return_value=self.fake_worker()) as worker, \
                patch.object(window,'check_provider_setup',return_value=True):
            window.start_button.click()
        self.assertIsNone(worker.call_args.kwargs['run_id'])
        self.assertEqual(worker.call_args.kwargs['cache_path'],self.cache.path)
        self.assertEqual(file_digest(marker),before)

    def test_start_button_selection_reaches_actual_cli_argv_with_fixture_transport(self):
        from core.pipeline import ProcessingManager
        from tests.test_core import FakeOCR
        from tests.test_agy import RunnerFixture
        from providers.agy import AGYProvider
        window,old,_=self.prepare_paused_sonnet_window()
        with patch('ui.main_window.ProcessingWorker',return_value=self.fake_worker()) as worker, \
                patch.object(window,'check_provider_setup',return_value=True):
            window.start_button.click()
        opts=worker.call_args.args[0];exe=self.folder/'fake.exe';exe.write_bytes(b'NOT EXECUTED')
        opts.agy_executable=str(exe);runner=RunnerFixture()
        def provider(**kwargs):return AGYProvider(**kwargs,root=self.folder/'cli',runner=runner)
        with patch('core.pipeline.AGYProvider',side_effect=provider),patch('providers.agy.check_automatic_extensions'):
            manager=ProcessingManager(opts,self.cache,ocr=FakeOCR(),resume_id=worker.call_args.kwargs['resume_id'])
            result=manager.run()
        self.assertEqual(result['completed'],1)
        self.assertNotEqual(manager.resume_id,old['id'])
        argv=runner.calls[0][0]
        self.assertEqual(argv[argv.index('--model')+1],'claude-sonnet-4-6')
        self.assertNotIn('--effort',argv)
