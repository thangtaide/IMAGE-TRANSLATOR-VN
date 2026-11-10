"""Mock adapter-contract tests; real-model integration is separately skipped."""
import json
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.paths import ROOT
from core.storage import atomic_json, file_digest
from core.types import MissingModelError
from providers.m2m100 import M2M100TranslationProvider, MODEL_DIRECTORY, validate_package
from providers.offline import create_offline_provider


class M2MContractTests(unittest.TestCase):
    def provider(self):
        provider=M2M100TranslationProvider(ROOT/'output/nonexistent-m2m-unit')
        provider._meta={'format':'UNIT-TEST ONLY'}
        tokenizer=Mock()
        tokenizer.encode.return_value=['piece']
        tokenizer.decode.return_value='UNIT-TEST translation'
        translator=Mock()
        translator.translate_batch.return_value=[SimpleNamespace(hypotheses=[['__vi__','piece','</s>']])]
        provider.loaded=translator,tokenizer
        return provider,translator,tokenizer

    def test_source_language_eos_target_prefix_and_reuse_contract(self):
        provider,translator,tokenizer=self.provider()
        for _ in range(2):
            self.assertEqual(provider.translate('UNIT INPUT','zh'),'UNIT-TEST translation')
        args,kwargs=translator.translate_batch.call_args
        self.assertEqual(args[0],[['__zh__','piece','</s>']])
        self.assertEqual(kwargs['target_prefix'],[['__vi__']])
        self.assertEqual(translator.translate_batch.call_count,2)
        tokenizer.decode.assert_called_with(['piece'])

    def test_missing_model_does_not_open_network(self):
        with patch.object(socket,'create_connection',side_effect=AssertionError('Network forbidden')):
            with self.assertRaises(MissingModelError):
                M2M100TranslationProvider(ROOT/'output/absent-m2m-model').translate('INPUT','zh')

    def test_factory_keeps_argos_and_rejects_unknown_provider(self):
        self.assertEqual(create_offline_provider('Argos').engine_name,'Argos')
        self.assertIsInstance(create_offline_provider('M2M100'),M2M100TranslationProvider)
        with self.assertRaises(ValueError):create_offline_provider('unrecognized')

    def test_wrong_prefix_and_decoder_limit_fail_safely(self):
        provider,translator,_=self.provider()
        for tokens in [['__en__','piece'],['__vi__']+['piece']*768,['__vi__','<unk>']]:
            translator.translate_batch.return_value=[SimpleNamespace(hypotheses=[tokens])]
            with self.assertRaises(RuntimeError):provider.translate('INPUT','zh')

    def test_long_input_never_silently_truncates(self):
        provider,translator,tokenizer=self.provider()
        tokenizer.encode.return_value=['piece']*511
        with self.assertRaises(ValueError):provider.translate('INPUT','zh')
        translator.translate_batch.assert_not_called()

    def test_corrupt_package_rejected_by_hash(self):
        base=ROOT/'output/test-runs';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temporary:
            folder=Path(temporary);(folder/'model').mkdir()
            for name in ['model/model.bin','model/config.json','sentencepiece.bpe.model']:
                (folder/name).write_bytes(b'UNIT TEST NOT REAL MODEL')
            atomic_json(folder/'m2m100.json',{'model_id':'facebook/m2m100_418M','license':'MIT','format':'m2m100-ct2-v1'})
            atomic_json(folder/'model/shared_vocabulary.json',['__zh__','__vi__','</s>'])
            atomic_json(folder/'integrity.json',{'files':{
                str(p.relative_to(folder)).replace('\\','/'):file_digest(p) for p in folder.rglob('*') if p.is_file()}})
            (folder/'model/model.bin').write_bytes(b'CHANGED')
            with self.assertRaises(MissingModelError):validate_package(folder)


class M2MRealIntegration(unittest.TestCase):
    @unittest.skipUnless((MODEL_DIRECTORY/'integrity.json').is_file(),'No local M2M100 model; real inference NOT TESTED')
    def test_real_cpu_inference(self):
        provider=M2M100TranslationProvider()
        output=provider.translate('欢迎使用图像翻译。','zh')
        self.assertTrue(output.strip())
        # Nonempty output is technical inference evidence, not semantic acceptance.
