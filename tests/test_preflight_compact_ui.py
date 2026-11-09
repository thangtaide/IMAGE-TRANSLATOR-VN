"""Stage3D.1 local state/layout contracts; fake providers and independent QA data."""
import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

from core.paths import ROOT
from core.provider_preflight import check_configuration
from core.storage import load_options, save_options
from core.types import Options
from providers.gemini_api import GeminiAPIProvider, MODE
from providers.online import ProviderSuspended


class PreflightTests(unittest.TestCase):
    def test_missing_key_is_not_remote_auth_failure(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': ''}):
            result = check_configuration(Options(mode=MODE))
        self.assertEqual(result.code, 'API_KEY_MISSING'); self.assertFalse(result.ready)

    def test_key_present_unconfirmed_stops_before_any_request(self):
        client = Mock()
        with patch.dict(os.environ, {'GEMINI_API_KEY':'fake-key-for-unit-tests'}):
            result = check_configuration(Options(mode=MODE))
            self.assertEqual(result.code, 'FREE_TIER_UNCONFIRMED')
            provider = GeminiAPIProvider(client=client)
            with self.assertRaises(ProviderSuspended) as exc: provider.translate('你好', 'zh')
        self.assertFalse(exc.exception.request_sent)
        self.assertEqual(exc.exception.phase, 'provider_preflight')
        self.assertEqual(provider.requests, 0); client.post.assert_not_called()

    def test_ready_is_local_only_not_verified_key_or_billing(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':'fake-key-for-unit-tests'}), patch('requests.Session.post') as post:
            result = check_configuration(Options(mode=MODE, gemini_api_free_tier_confirmed=True))
        self.assertEqual(result.code,'READY_UNVERIFIED'); self.assertTrue(result.ready)
        post.assert_not_called()

    def test_offline_does_not_need_key(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':''}):
            self.assertTrue(check_configuration(Options()).ready)

    def test_confirmation_roundtrip_is_explicit_and_key_never_saved(self):
        with tempfile.TemporaryDirectory() as tmp, patch('core.storage.CONFIG', Path(tmp)):
            options=Options(mode=MODE)
            save_options(options); self.assertFalse(load_options().gemini_api_free_tier_confirmed)
            options.gemini_api_free_tier_confirmed=True
            save_options(options); self.assertTrue(load_options().gemini_api_free_tier_confirmed)
            self.assertNotIn('api_key',json.dumps(options.to_dict()).lower())


class CompactUITests(unittest.TestCase):
    def setUp(self):
        from PySide6.QtWidgets import QApplication
        self.app=QApplication.instance() or QApplication([])
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'output',prefix='stage3d1-')
        self.root=Path(self.tmp.name); self.config=self.root/'config';self.config.mkdir()
        self.stack=ExitStack()
        self.stack.enter_context(patch('ui.main_window.CONFIG',self.config))
        self.stack.enter_context(patch.dict(os.environ,{'GEMINI_API_KEY':'fake-key-for-unit-tests'}))
        self.windows=[]

    def tearDown(self):
        for window in self.windows:window.close()
        self.app.processEvents();self.stack.close();self.tmp.cleanup()

    def window(self, options=None):
        from ui.main_window import MainWindow
        with patch('ui.main_window.load_options',return_value=options or Options()):
            w=MainWindow(cache_path=self.root/f'qa-{len(self.windows)}.sqlite3',persist_settings=False)
        self.windows.append(w);w.show();self.app.processEvents()
        return w

    def fill(self, panel):
        from sources.contracts import ComicInfo, ChapterInfo, AccessStatus
        panel.handle_event(dict(type='collection',comic=ComicInfo('fixture','qa',None,title='Truyện QA'),
            chapters=[ChapterInfo(str(n),'Chương QA '+str(n),str(n),None,AccessStatus.LOCAL,n)
                      for n in range(3)]))
        return panel

    def test_start_blocked_does_not_start_worker_write_journal_or_request(self):
        w=self.window(Options(mode=MODE));w.source.setText(str(self.root));w.output.setText(str(self.root/'export'))
        with patch('ui.main_window.ProcessingWorker') as worker,patch('requests.Session.post') as post:
            w.start()
        worker.assert_not_called();post.assert_not_called()
        self.assertEqual(w.ui_job_state,'CONFIGURATION_BLOCKED')
        self.assertIn('FREE_TIER_UNCONFIRMED',w.provider_notice.title.text())
        self.assertIn('chưa gửi OCR',w.provider_notice.message.text())
        self.assertFalse(list(self.root.glob('*resume-v1/*.json')))

    def test_local_panel_preflight_keeps_selection_and_no_launch(self):
        w=self.window(Options(mode=MODE));panel=self.fill(w.image_panel)
        before=panel.selected()
        with patch.object(panel,'launch') as launch,patch('requests.Session.post') as post:panel.begin()
        launch.assert_not_called();post.assert_not_called()
        self.assertEqual(panel.selected(),before);self.assertEqual(panel.ui_job_state,'CONFIGURATION_BLOCKED')

    def test_existing_source_restore_blocked_before_launch(self):
        w=self.window(Options(mode=MODE));panel=w.url_panel
        panel.restorable={'output':str(self.root/'export')}
        with patch.object(panel,'launch') as launch:panel.restore_cached_job()
        launch.assert_not_called();self.assertEqual(panel.ui_job_state,'CONFIGURATION_BLOCKED')

    def test_settings_action_targets_gemini_without_confirmation_or_network(self):
        from ui.settings_dialog import SettingsDialog
        w=self.window(Options(mode=MODE));w.start()
        with patch.object(w,'show_settings') as settings:w.provider_notice.settings.click()
        settings.assert_called_once_with('gemini_api')
        d=SettingsDialog(w.options,w,focus_section='gemini_api')
        self.assertFalse(d.gemini_api_free.isChecked());d.reject()
        self.assertFalse(w.options.gemini_api_free_tier_confirmed)

    def test_accept_settings_reads_latest_hidden_provider_controls(self):
        w=self.window(Options(mode=MODE))
        def accept(dialog):
            dialog.gemini_api_free.setChecked(True)
            dialog.allow_fallback.setChecked(False)
            dialog.combos['online_provider'].setCurrentText('LibreTranslate')
            dialog.accept();return 1
        with patch('ui.settings_dialog.SettingsDialog.exec',accept),patch('requests.Session.post') as post:w.show_api_settings()
        self.assertTrue(w.collect_options().gemini_api_free_tier_confirmed)
        self.assertEqual(w.collect_options().online_provider,'LibreTranslate');post.assert_not_called()
        self.assertEqual(w.mode.currentText(),MODE);self.assertFalse(w.allow_fallback.isChecked())

    def test_confirmation_does_not_automatically_resume(self):
        w=self.window(Options(mode=MODE));w.provider_paused=True;w.provider_pending=['qa']
        with patch.object(w,'start') as start:
            w.options.gemini_api_free_tier_confirmed=True;w.update_mode()
            start.assert_not_called()
            w.resume();start.assert_called_once_with(['qa'])

    def test_resolved_preflight_hides_stale_notice_without_resuming_or_erasing_history(self):
        w=self.window(Options(mode=MODE));w.start()
        self.assertTrue(w.provider_notice.isVisible())
        before=w.provider_notice.log.toPlainText()
        with patch.object(w,'start') as start:
            w.options.gemini_api_free_tier_confirmed=True;w.update_mode()
            start.assert_not_called()
        self.assertFalse(w.provider_notice.isVisible())
        self.assertEqual(w.provider_notice.log.toPlainText(),before)
        self.assertEqual(w.ui_job_state,'READY_UNVERIFIED')

    def test_restore_does_not_overwrite_new_confirmation_or_selected_provider(self):
        w=self.window(Options(mode=MODE,gemini_api_free_tier_confirmed=True))
        old=Options(mode=MODE,gemini_api_free_tier_confirmed=False,source=str(self.root),output=str(self.root/'export'))
        w.pending_options=old
        w.pending_journal={'id':'a'*32,'pages':[{'path':str(self.root/'pending.png'),'state':'pending'}]}
        with patch('ui.main_window.ProcessingWorker') as worker:w.restore_previous()
        self.assertTrue(w.options.gemini_api_free_tier_confirmed)
        self.assertEqual(w.mode.currentText(),MODE);worker.assert_not_called()
        self.assertTrue(w.continue_button.isEnabled())

    def test_remote_error_never_claims_request_unsent_without_evidence(self):
        w=self.window();notice=w.provider_notice
        for code in ['AUTH_REQUIRED','ACCESS_DENIED','MODEL_UNAVAILABLE','RATE_LIMITED','QUOTA_EXCEEDED',
                     'NETWORK_ERROR','TIMEOUT','INVALID_RESPONSE']:
            notice.show_error(dict(code=code,detail='private raw body',provider=MODE))
            self.assertIn(code,notice.title.text())
            self.assertIn('Chưa xác minh',notice.message.text())
            self.assertNotIn('private raw body',notice.message.text())

    def test_agy_guard_is_not_mislabelled_as_quota_or_proven_invocation(self):
        w=self.window();w.provider_notice.show_error(dict(code='INVALID_RESPONSE',detail='Unexpected tool use'))
        text=w.provider_notice.message.text()
        self.assertIn('Guard AGY',w.provider_notice.title.text())
        self.assertIn('không phải lỗi quota',text);self.assertIn('chưa đủ bằng chứng',text)

    def test_notice_dismiss_does_not_resume_or_switch_provider(self):
        w=self.window(Options(mode=MODE));w.provider_notice.show_error(dict(code='RATE_LIMITED'))
        with patch.object(w,'resume') as resume:w.provider_notice.dismiss.click()
        resume.assert_not_called();self.assertEqual(w.mode.currentText(),MODE)

    def test_notice_filters_secrets_raw_detail_unknown_fields_and_log_injection(self):
        w=self.window();secret='DO-NOT-LOG-THIS-SECRET'
        event=dict(code=secret+'\nFAKE',detail=secret,provider=secret,diagnostic_path=secret,image_index=secret)
        w.provider_notice.show_error(event)
        text=w.provider_notice.title.text()+w.provider_notice.message.text()+w.provider_notice.log.toPlainText()+w.provider_notice.toolTip()
        self.assertNotIn(secret,text);self.assertIn('UNKNOWN_ERROR',text)

    def test_chapter_columns_keep_data_selection_and_order_when_expanded(self):
        w=self.window();panel=self.fill(w.url_panel);panel.check_all(True)
        selected=panel.selected();data=[[panel.table.item(r,c).text() for c in range(7)] for r in range(3)]
        self.assertEqual([c for c in range(7) if not panel.table.isColumnHidden(c)],[0,1,2,5])
        panel.technical_columns.setChecked(True);panel.technical_columns.setChecked(False)
        self.assertEqual(panel.selected(),selected)
        self.assertEqual([[panel.table.item(r,c).text() for c in range(7)] for r in range(3)],data)
        self.assertIn(panel.table.item(0,3).text(),panel.table.item(0,2).toolTip())

    def test_collapsed_advanced_keeps_control_capability_after_worker_finishes(self):
        w=self.window();panel=self.fill(w.url_panel)
        w.source_tabs.setCurrentIndex(2)
        panel.set_busy(True);panel.set_busy(False)
        self.assertFalse(panel.advanced.isChecked())
        self.assertTrue(panel.retry_analysis.isEnabled())
        panel.advanced.setChecked(True);self.app.processEvents()
        self.assertTrue(panel.retry_analysis.isEnabled())
        self.assertTrue(panel.advanced_body.isVisible())

    def test_analysis_only_launches_discovery_not_process(self):
        w=self.window();p=w.url_panel;p.location.setText('https://www.kuaikanmanhua.com/web/topic/6677/')
        with patch.object(p,'launch') as launch,patch.object(p,'begin') as begin:p.analyze_source()
        self.assertEqual(launch.call_args.args[0],'url');begin.assert_not_called()

    def test_four_methods_layout_preserves_values_and_fallback_off(self):
        w=self.window()
        for mode in ['Offline','Online Free','AI Gemini AGY',MODE]:
            w.mode.setCurrentIndex(w.mode.findData(mode));self.app.processEvents()
            self.assertEqual(w.collect_options().mode,mode)
            self.assertFalse(w.online_provider.isVisible());self.assertFalse(w.offline_provider.isVisible())
            self.assertFalse(w.allow_fallback.isVisible());self.assertFalse(w.collect_options().allow_online_fallback)

    def test_user_pause_is_distinct_from_provider_pause(self):
        w=self.window();w.worker=Mock();w.pause()
        self.assertEqual(w.ui_job_state,'PAUSED_BY_USER');w.worker.control.pause.assert_called_once()
        w.worker=None

    def test_main_controls_fit_target_logical_sizes_and_remain_scroll_reachable(self):
        from PySide6.QtWidgets import QScrollArea
        w=self.window();w.source_tabs.setCurrentIndex(2)
        for physical in [(1366,768),(1600,900),(1920,1080)]:
            for scale in (1,1.25,1.5):
                w.resize(int(physical[0]/scale),int(physical[1]/scale));self.app.processEvents()
                scroll=w.centralWidget();self.assertIsInstance(scroll,QScrollArea)
                for button in [w.settings_button,w.url_panel.download,w.url_panel.pause,w.url_panel.resume,w.url_panel.cancel,w.url_panel.open_output]:
                    scroll.ensureWidgetVisible(button);self.app.processEvents()
                    self.assertTrue(button.isVisible());self.assertGreaterEqual(button.width(),button.minimumSizeHint().width())
                    self.assertGreaterEqual(button.height(),button.minimumSizeHint().height())
                    pos=button.mapTo(scroll.viewport(),button.rect().center())
                    self.assertTrue(scroll.viewport().rect().contains(pos))

    def test_api_settings_buttons_fit_small_logical_height(self):
        from PySide6.QtWidgets import QDialogButtonBox
        from ui.settings_dialog import SettingsDialog
        w=self.window();d=SettingsDialog(w.options,w,focus_section='gemini_api')
        d.resize(620,490);d.show();self.app.processEvents()
        box=d.findChild(QDialogButtonBox)
        self.assertTrue(d.rect().contains(box.geometry()))
        self.assertTrue(d.api_group.isVisible());d.reject()

    def test_explicit_start_after_confirmation_launches_once_without_switch(self):
        w=self.window(Options(mode=MODE));w.source.setText(str(self.root));w.output.setText(str(self.root/'export'))
        w.options.gemini_api_free_tier_confirmed=True
        with patch('ui.main_window.ProcessingWorker') as factory:
            w.start()
            factory.return_value.start.assert_called_once()
            self.assertEqual(factory.call_args.args[0].mode,MODE)
        w.worker=None;w.timer.stop()

    def test_preflight_repair_resume_keeps_real_qa_receipt(self):
        from copy import deepcopy
        from PIL import Image
        from core.pipeline import JobControl, TranslationService, ProcessingManager
        from core.storage import TranslationCache, file_digest
        from core.types import OCRResult
        from tests.test_gemini_api import HTTPFixture
        source=self.root/'source';source.mkdir()
        for n in (1,2):Image.new('RGB',(500,200),(n,n,n)).save(source/f'{n}.png')
        class OCR:
            def identity(self,*args):return 'ocr-preflight-qa'
            def recognize(self,image,*args):
                return [OCRResult('你好',[[10,10],[200,10],[200,70],[10,70]],.99,'zh')],[]
        class Offline:
            online=False;identity='offline-preflight-fixture'
            def translate(self,*args):return 'Xin chào'
        cache=TranslationCache(self.root/'recovery.sqlite3');self.stack.callback(cache.close)
        control=JobControl();opts=Options(source=str(source),output=str(self.root/'export'))
        def stop(event):
            if event.get('completed')==1:control.cancel()
        service=TranslationService(opts,cache,control,offline=Offline())
        first=ProcessingManager(opts,cache,control,stop,ocr=OCR(),service=service,diagnostic_root=self.root/'diag')
        first.run();receipt=deepcopy(first.journal['pages'][0]);checksum=file_digest(Path(receipt['output']))
        opts.mode=MODE;http=HTTPFixture();control=JobControl()
        service=TranslationService(opts,cache,control)
        service.gemini_api=GeminiAPIProvider(client=http,free_tier_confirmed=False)
        second=ProcessingManager(opts,cache,control,ocr=OCR(),service=service,resume_id=first.resume_id,diagnostic_root=self.root/'diag')
        self.assertEqual(second.run()['state'],'paused_provider');self.assertFalse(http.calls)
        for path in (self.root/'diag').rglob('*.jsonl'):
            self.assertNotIn('你好',path.read_text(encoding='utf-8'))
        opts.gemini_api_free_tier_confirmed=True;control=JobControl();service=TranslationService(opts,cache,control)
        service.gemini_api=GeminiAPIProvider(client=http,free_tier_confirmed=True)
        third=ProcessingManager(opts,cache,control,ocr=OCR(),service=service,resume_id=first.resume_id,diagnostic_root=self.root/'diag')
        self.assertEqual(third.run()['completed'],1);self.assertEqual(len(http.calls),1)
        self.assertEqual(third.journal['pages'][0],receipt)
        self.assertEqual(file_digest(Path(receipt['output'])),checksum)
