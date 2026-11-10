"""Real Qt widgets, isolated filesystem, mocked processing launch (no AGY/network)."""
import time
from pathlib import Path
from unittest.mock import patch,MagicMock

from core.runtime import prepare_inference_runtime
prepare_inference_runtime()
from PySide6.QtCore import QTimer,QUrl
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialog

from core.run_cache import RunRegistry
from tests.test_core import WorkspaceCase
from ui.main_window import MainWindow
from ui.fresh_run import FreshRunDialog
from ui.cache_manager import CacheManagerDialog,open_cache_directory


class CacheWidgetsTests(WorkspaceCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def wait_for(self,predicate,timeout=3000):
        end=time.monotonic()+timeout/1000
        while not predicate() and time.monotonic()<end:QTest.qWait(10)
        self.assertTrue(predicate())

    def window(self):
        self.image();window=MainWindow(self.cache.path,persist_settings=False)
        window.source.setText(str(self.source));window.output.setText(str(self.output))
        window.mode.setCurrentIndex(window.mode.findData('Offline'));window.language.setCurrentIndex(window.language.findData('en'))
        self.addCleanup(window.close);return window

    def test_cancel_confirmation_does_not_create_namespace_or_launch_worker(self):
        window=self.window()
        def cancel():
            dialog=next(w for w in self.app.topLevelWidgets() if isinstance(w,FreshRunDialog));dialog.reject()
        QTimer.singleShot(50,cancel)
        with patch('ui.main_window.ProcessingWorker') as worker:window.start_fresh();worker.assert_not_called()
        self.assertFalse(window.run_registry.root.exists())

    def test_confirm_creates_new_run_and_passes_its_database_to_worker(self):
        window=self.window();window.skip.setChecked(False)
        worker=MagicMock();worker.isRunning.return_value=False
        def confirm_when_ready():
            dialogs=[w for w in self.app.topLevelWidgets() if isinstance(w,FreshRunDialog) and w.isVisible()]
            if not dialogs or not dialogs[0].confirm.isEnabled():QTimer.singleShot(20,confirm_when_ready);return
            dialogs[0].confirm.click()
        QTimer.singleShot(20,confirm_when_ready)
        with patch('ui.main_window.ProcessingWorker',return_value=worker) as factory:window.start_fresh()
        self.assertIsNotNone(window.active_run_id);self.assertNotEqual(window.active_cache_path,self.cache.path)
        self.assertEqual(factory.call_args.kwargs['cache_path'],window.active_cache_path)
        self.assertEqual(factory.call_args.kwargs['run_id'],window.active_run_id)
        self.assertIsNone(factory.call_args.kwargs['resume_id']);worker.start.assert_called_once()
        self.assertEqual(window.run_registry.read(window.active_run_id)['cache_policy'],'isolated-new-run')

    def test_open_cache_uses_actual_injected_or_active_database_parent(self):
        external=self.folder/'custom-cache';external.mkdir()
        with patch('ui.cache_manager.QDesktopServices.openUrl',return_value=True) as opened:
            self.assertTrue(open_cache_directory(external/'custom.sqlite3'))
        self.assertEqual(Path(opened.call_args.args[0].toLocalFile()),external)

    def test_missing_cache_directory_is_not_created(self):
        path=self.folder/'not-created'
        with patch('ui.cache_manager.QMessageBox.information'),patch('ui.cache_manager.QDesktopServices.openUrl') as opened:
            self.assertFalse(open_cache_directory(path/'state.sqlite3'));opened.assert_not_called()
        self.assertFalse(path.exists())

    def test_whole_cache_button_uses_workspace_database_not_batch_cache(self):
        from providers.agy import WHOLE_MODE
        window=self.window();workspace=self.folder/'whole-workspace';workspace.mkdir()
        window.last_whole_output=workspace/'rendered';window.mode.setCurrentIndex(window.mode.findData(WHOLE_MODE))
        self.assertEqual(window.current_cache_database(),workspace/'qa.sqlite3')
        with patch('ui.cache_manager.QDesktopServices.openUrl',return_value=True) as opened:window.open_cache()
        self.assertEqual(Path(opened.call_args.args[0].toLocalFile()),workspace)

    def test_whole_fresh_confirmation_passes_unique_workspace_without_starting_agy(self):
        from providers.agy import WHOLE_MODE
        window=self.window();window.mode.setCurrentIndex(window.mode.findData(WHOLE_MODE))
        def confirm_when_ready():
            dialogs=[w for w in self.app.topLevelWidgets() if isinstance(w,FreshRunDialog) and w.isVisible()]
            if not dialogs or not dialogs[0].confirm.isEnabled():QTimer.singleShot(20,confirm_when_ready);return
            dialogs[0].confirm.click()
        QTimer.singleShot(20,confirm_when_ready)
        with patch.object(window,'open_selected_whole') as whole,patch('ui.main_window.ProcessingWorker') as batch:
            window.start_fresh()
        batch.assert_not_called();context=whole.call_args.args[0]
        self.assertTrue(context['force_new']);self.assertEqual(len(context['fresh_plan']['run_id']),32)
        self.assertEqual(Path(context['fresh_plan']['output']).parent,Path(context['fresh_plan']['workspace']))
        self.assertFalse(Path(context['fresh_plan']['workspace']).exists())

    def test_reopened_window_binds_saved_run_database_without_starting_processing(self):
        self.image();registry=RunRegistry(self.cache.path);options=self.options()
        record=registry.create(registry.plan(options),options)
        from core.types import Options
        with patch('ui.main_window.load_options',return_value=Options.from_dict(record['options'])),patch('ui.main_window.ProcessingWorker') as worker:
            window=MainWindow(self.cache.path,persist_settings=False)
        self.assertEqual(window.active_run_id,record['run_id'])
        self.assertEqual(window.active_cache_path,Path(record['database']));worker.assert_not_called();window.close()

    def test_reopened_pending_run_restore_and_continue_keep_its_own_database(self):
        from core.resume import ResumeStore
        from core.storage import TranslationCache
        from core.types import Options
        source=self.image();registry=RunRegistry(self.cache.path);record=registry.create(registry.plan(self.options()),self.options())
        options=Options.from_dict(record['options']);cache=TranslationCache(Path(record['database']))
        store=ResumeStore(cache.path);journal=store.pipeline(options,[source.resolve()],cache)
        journal['state']='cancelled';store.save(journal);cache.job('gui-state-fixture',options,'cancelled');cache.close()
        with patch('ui.main_window.load_options',return_value=options):window=MainWindow(self.cache.path,persist_settings=False)
        window.restore_previous()
        self.assertEqual(window.active_cache_path,Path(record['database']));self.assertEqual(window.resume_id,journal['id'])
        worker=MagicMock();worker.isRunning.return_value=False
        with patch('ui.main_window.ProcessingWorker',return_value=worker) as factory:window.resume()
        self.assertEqual(factory.call_args.kwargs['cache_path'],Path(record['database']))
        self.assertEqual(factory.call_args.kwargs['resume_id'],journal['id']);self.assertEqual(factory.call_args.kwargs['run_id'],record['run_id'])
        window.close()

    def test_completed_active_run_does_not_hide_legacy_unfinished_checkpoint(self):
        from core.resume import ResumeStore
        from core.types import Options
        source=self.image();legacy=self.options();store=ResumeStore(self.cache.path)
        journal=store.pipeline(legacy,[source.resolve()],self.cache);journal['state']='cancelled';store.save(journal)
        self.cache.job('legacy-gui-fixture',legacy,'cancelled')
        registry=RunRegistry(self.cache.path);record=registry.create(registry.plan(legacy),legacy)
        with patch('ui.main_window.load_options',return_value=Options.from_dict(record['options'])):
            window=MainWindow(self.cache.path,persist_settings=False)
        self.assertEqual(window.pending_cache_path,self.cache.path)
        window.restore_previous();self.assertEqual(window.active_cache_path,self.cache.path)
        self.assertIsNone(window.active_run_id);self.assertEqual(window.resume_id,journal['id']);window.close()

    def test_repeated_fresh_action_uses_original_output_base_not_nested_runs(self):
        window=self.window();record=window.run_registry.create(window.run_registry.plan(window.collect_options()),window.collect_options())
        window.output.setText(record['output']);window.active_run_id=record['run_id'];window.active_cache_path=Path(record['database'])
        seen=[]
        def capture_cancel():
            dialogs=[w for w in self.app.topLevelWidgets() if isinstance(w,FreshRunDialog) and w.isVisible()]
            if not dialogs:QTimer.singleShot(20,capture_cancel);return
            seen.append(dialogs[0].plan['output']);dialogs[0].reject()
        QTimer.singleShot(20,capture_cancel);window.start_fresh()
        self.assertEqual(Path(seen[0]).parent,Path(record['output']).parent)

    def test_legacy_shared_database_and_render_cleanup_are_disabled(self):
        dialog=CacheManagerDialog(RunRegistry(self.cache.path),self.cache.path)
        self.wait_for(lambda:not dialog.task_pending);dialog.table.selectRow(0);self.app.processEvents()
        self.assertFalse(dialog.prune.isEnabled());self.assertFalse(dialog.render.isEnabled())
        self.assertIn(str(self.cache.path),dialog.location.text());dialog.close()

    def test_menu_and_combo_have_dark_palette_and_explicit_states(self):
        window=self.window();window.show();self.app.processEvents()
        self.assertLess(window.folder_more.menu().palette().color(QPalette.Window).lightness(),100)
        self.assertLess(window.mode.view().palette().color(QPalette.Base).lightness(),100)
        style=self.app.styleSheet()
        for selector in ('QMenu::item:selected','QMenu::item:disabled','QComboBox QAbstractItemView'):
            self.assertIn(selector,style)
        self.assertTrue(window.skip.isEnabled());self.assertTrue(window.fresh_button.isVisible())

    def test_large_inventory_is_off_ui_thread_and_event_loop_keeps_ticking(self):
        import ui.cache_manager as module
        real=module.bounded_size
        def slow(*args):time.sleep(.25);return real(*args)
        beats=[];timer=QTimer();timer.setInterval(10);timer.timeout.connect(lambda:beats.append(1));timer.start()
        with patch('ui.cache_manager.bounded_size',side_effect=slow):
            dialog=CacheManagerDialog(RunRegistry(self.cache.path),self.cache.path)
            self.wait_for(lambda:not dialog.task_pending)
        timer.stop();dialog.close();self.assertGreater(len(beats),5)
