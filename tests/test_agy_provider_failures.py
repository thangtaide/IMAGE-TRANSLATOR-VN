"""Sanitized provider errors. Never call AGY or expose raw error text in UI."""
import json
from pathlib import Path
from unittest.mock import patch

from providers.agy import AGYProvider,parse_response
from providers.agy_diagnostics import sanitize
from providers.online import ProviderSuspended,OnlineProviderError
from tests.test_agy import envelope,RunnerFixture
from tests.test_core import WorkspaceCase

FIXTURE=json.loads((Path(__file__).parent/'fixtures/agy_provider_failures.json').read_text(encoding='utf-8'))


class ProviderFailureTests(WorkspaceCase):
    def test_captured_shapes_are_classified_in_batch_and_whole(self):
        for name in ('server_shutdown','content_filter'):
            case=FIXTURE[name];raw=(json.dumps({'event':'result','result':case['result']})+'\n').encode()
            for whole in (False,True):
                with self.subTest(name=name,whole=whole),self.assertRaises(ProviderSuspended) as cm:
                    parse_response(raw,['r0'],case['exit_code'],whole=whole)
                self.assertEqual(cm.exception.code,case['expected'])
                safe=sanitize(cm.exception.agy_diagnostic)
                self.assertEqual(safe['parser_error_code'],case['expected'])
                self.assertEqual(safe['guard_decision'],'REJECT')
                self.assertNotIn('Synthetic candidate',json.dumps(safe))

    def test_errors_latch_even_if_cli_suggests_retries_or_returns_candidates(self):
        executable=self.folder/'fake.exe';executable.write_bytes(b'NOT EXECUTED')
        for name in ('server_shutdown','content_filter'):
            runner=RunnerFixture();case=FIXTURE[name]
            runner.failure=(case['exit_code'],(json.dumps({'event':'result','result':case['result']})+'\n').encode(),b'')
            with patch('providers.agy.check_automatic_extensions'):
                provider=AGYProvider(str(executable),root=self.folder/name,runner=runner)
                for _ in range(2):
                    with self.assertRaises(ProviderSuspended) as cm:provider.translate('你好','zh')
                    self.assertEqual(cm.exception.code,case['expected'])
                self.assertEqual(len(runner.calls),1)
                self.assertEqual(provider.last_targets,[])
                self.assertEqual(provider.last_diagnostic['parser_error_code'],case['expected'])
                self.assertEqual(provider._error_source(cm.exception),'CLI_EXIT' if case['exit_code'] else 'CLI_RESPONSE')

    def test_successful_translation_mentions_do_not_trigger_provider_classification(self):
        for phrase in ('blocked by content safety filters','http2: GOAWAY server_shutting_down'):
            self.assertEqual(parse_response(envelope([{'id':'r0','text':phrase}]),['r0'],0),[phrase])
        with self.assertRaises(OnlineProviderError) as cm:
            parse_response(envelope([],status='ERROR',error='Unknown unrelated error'),['r0'],3)
        self.assertEqual(cm.exception.code,'PROVIDER_UNAVAILABLE')

    def test_ui_explains_provider_block_without_raw_text(self):
        from core.runtime import prepare_inference_runtime
        prepare_inference_runtime()
        from PySide6.QtWidgets import QApplication
        from ui.provider_notice import ProviderNotice
        app=QApplication.instance() or QApplication([])
        notice=ProviderNotice();self.addCleanup(notice.close)
        notice.show_error(dict(code='RESPONSE_BLOCKED',provider='AGY Gemini',detail='PRIVATE_ERROR',image_index=112))
        self.assertIn('bộ lọc',notice.message.text().lower())
        self.assertIn('bộ lọc',notice.log.toPlainText().lower())
        self.assertNotIn('PRIVATE_ERROR',notice.log.toPlainText())
