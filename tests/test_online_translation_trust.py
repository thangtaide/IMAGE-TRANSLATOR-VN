"""User policy: trust online content, retain protocol and offline guards. No network."""
from unittest.mock import Mock

from core.pipeline import TranslationService, JobControl, NumericMismatchError
from core.types import Options
from core.whole_chapter import AGYWholeChapterTranslator
from providers.online import ProviderError
from tests.test_core import WorkspaceCase


class OnlineTrustTests(WorkspaceCase):
    def test_all_online_engines_accept_written_zero_and_changed_numbers(self):
        for engine in ('AGY', 'Gemini API', 'MyMemory', 'LibreTranslate'):
            provider = Mock(online=True, identity='fixture-'+engine, engine_name=engine)
            provider.translate.side_effect = AssertionError('No transport')
            service = TranslationService(self.options(), self.cache, JobControl())
            self.assertEqual(service._translate_using(provider,'生命值归零24H','zh','zero',raw_target='Máu về 0, ngủ 24H'),'Máu về 0, ngủ 24H')
            self.assertEqual(service._translate_using(provider,'15','zh','changed',raw_target='16'),'16')
            self.assertFalse(service.last_attempt['content_validation_applied'])
            provider.translate.assert_not_called()

    def test_online_glossary_paraphrases_and_markers_are_not_revalidated(self):
        provider = Mock(online=True, identity='trusted-glossary')
        service = TranslationService(self.options(glossary={'名字':'Tên'}), self.cache, JobControl())
        for i,target in enumerate(['Một cách gọi khác 0','ZXQZZQXZ']):
            self.assertEqual(service._translate_using(provider,'名字 24','zh',str(i),raw_target=target),target)
        self.assertEqual(service._translate_using(provider,'名字 24','zh','restore',raw_target='ZXQAAQXZ 24'),'Tên 24')

    def test_trusted_online_signed_target_is_reused_without_a_second_request(self):
        provider=Mock(online=True,identity='trusted-signed-target')
        provider.translate.return_value='-16'
        service=TranslationService(self.options(),self.cache,JobControl())
        for _ in range(2):
            self.assertEqual(service._translate_using(provider,'15','zh','cached'),'-16')
        provider.translate.assert_called_once()

    def test_offline_numeric_and_glossary_guards_remain(self):
        provider = Mock(online=False, identity='strict-offline')
        service = TranslationService(self.options(glossary={'名字':'Tên'}), self.cache, JobControl())
        with self.assertRaises(NumericMismatchError):
            service._translate_using(provider,'生命值归零24H','zh','zero',raw_target='Máu về 0, ngủ 24H')
        with self.assertRaises(ProviderError):
            service._translate_using(provider,'名字 24','zh','name',raw_target='Cách gọi khác 24')

    def test_empty_online_response_still_cannot_be_rendered(self):
        service = TranslationService(self.options(), self.cache, JobControl())
        with self.assertRaises(ProviderError):
            service._translate_using(Mock(online=True,identity='empty'),'文本','zh','empty',raw_target=' ')

    def test_actual_agy_whole_adapter_trusts_online_even_with_offline_render_options(self):
        executable = self.folder/'fake-agy.exe'
        executable.write_bytes(b'NOT EXECUTED: file lookup/hash only')
        adapter = AGYWholeChapterTranslator(Options(agy_executable=str(executable),agy_model='gemini-3.8-flash-low'))
        service = TranslationService(Options(mode='Offline'),self.cache,JobControl(),offline=adapter.provider)
        self.assertTrue(adapter.provider.online)
        self.assertEqual(service._translate_using(adapter.provider,'归零24H','zh','whole',raw_target='Về 0 trong 24H'),'Về 0 trong 24H')

