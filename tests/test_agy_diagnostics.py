"""Manual protocol contracts + isolated QA, never an AGY/account/network call."""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from tests.image_fixtures import provider_page
from core.paths import ROOT
from core.pipeline import JobControl, ProcessingManager, TranslationService
from core.storage import TranslationCache, file_digest
from core.types import Options, CancelledError
from core.diagnostics import DiagnosticLog
from providers.agy import AGYProvider, MODE, parse_response, run_bounded, SESSION_SETTINGS, PROMPT_VERSION
from providers.agy_diagnostics import sanitize, observe
from providers.online import OnlineProviderError
from tests.test_agy import RunnerFixture, envelope
from tests.test_online_free import OCRFixture, OfflineFixture

FIXTURES = Path(__file__).parent/'fixtures/agy_protocol_manual_cases.json'


def packet(case):
    prefix = (case.get('raw_prefix','') + ''.join(json.dumps(e)+'\n' for e in case.get('prefix',[]))).encode()
    result = b'' if case.get('omit_result') else envelope(
        case.get('rows',[{'id':'r0','text':'Bản dịch 15'}]), **case.get('override',{}))
    return prefix + result*(2 if case.get('duplicate_result') else 1)


class ProtocolObservationTests(unittest.TestCase):
    def test_twenty_manual_contracts_keep_legacy_verdict(self):
        data=json.loads(FIXTURES.read_text(encoding='utf-8'))
        self.assertEqual(data['fixture_kind'],'MANUAL_CONTRACT_FIXTURES_NOT_CAPTURED_AGY')
        for case in data['cases']:
            with self.subTest(case=case['id']):
                meta={}
                if case['verdict']=='REJECT':
                    with self.assertRaises(OnlineProviderError):
                        parse_response(packet(case),case.get('expected_ids',['r0']),case.get('exit_code',0),diagnostic=meta)
                else:
                    self.assertTrue(parse_response(packet(case),['r0'],0,diagnostic=meta))
                self.assertEqual(meta['classification'],case['classification'])
                self.assertEqual(meta['guard_decision'],case['verdict'])
                self.assertFalse(meta['retry'])
                self.assertFalse(meta['translation_cached'])

    def test_untrusted_names_values_paths_and_stderr_are_not_retained(self):
        secret='PRIVATE_FIXTURE_SECRET_123'
        prefix={'event':secret+'\n\r',secret:{'tool_name':secret},'metadata':{'authorization':secret}}
        payload=json.dumps(prefix).encode()+b'\n'+envelope([{'id':'r0','text':secret}])
        with self.assertRaises(OnlineProviderError) as cm:
            parse_response(payload,['r0'],0,stderr=secret.encode())
        meta=cm.exception.agy_diagnostic
        self.assertEqual(meta['classification'],'UNKNOWN_PROTOCOL_SHAPE')
        text=json.dumps(meta)
        self.assertNotIn(secret,text)
        self.assertEqual(meta['events'][0]['event_type'],'OTHER')
        self.assertTrue(all(hit['path'].startswith('$') for hit in meta['tool_indicators']))
        self.assertEqual(meta['stderr_bytes'],len(secret))

    def test_key_type_fingerprint_has_no_values(self):
        def meta(value):
            d={};parse_response(envelope([{'id':'r0','text':value}]),['r0'],0,diagnostic=d);return d
        a,b=meta('PRIVATE_ONE'),meta('PRIVATE_TWO')
        self.assertEqual(a['schema_fingerprint'],b['schema_fingerprint'])
        self.assertNotIn('PRIVATE_',json.dumps(a))

    def test_bounded_event_path_depth_and_unknown_auxiliary_policy(self):
        prefix=b''.join(json.dumps({'event':'init','metadata':{'tool_name':'fixture'}}).encode()+b'\n' for _ in range(200))
        with self.assertRaises(OnlineProviderError) as cm:
            parse_response(prefix+envelope([{'id':'r0','text':'A'}]),['r0'],0)
        d=cm.exception.agy_diagnostic
        self.assertLessEqual(len(d['events']),128);self.assertLessEqual(len(d['tool_indicators']),32)
        self.assertTrue(d['scan_truncated'])
        self.assertLess(len(json.dumps(d)),50000)

    def test_deep_unknown_object_cannot_leak_or_change_valid_verdict(self):
        value='PRIVATE_DEEP_VALUE'
        for _ in range(40):value={'secret_key':value}
        payload=json.dumps({'event':'init','metadata':value}).encode()+b'\n'+envelope([{'id':'r0','text':'A'}])
        d={};self.assertEqual(parse_response(payload,['r0'],0,diagnostic=d),['A'])
        self.assertTrue(d['scan_truncated'])
        self.assertNotIn('secret_key',json.dumps(d))

    def test_malicious_diagnostic_dictionary_is_filtered_again(self):
        value={'classification':'PRIVATE','parser_error_code':['secret'],'timestamp':'x\nTOKEN',
            'events':[{'event_type':{'secret':'bad'},'value_type':[],'private':'secret'}],
            'tool_indicators':[{'path':'$.TOKEN_SECRET','event_type':'x','value_type':'string',
                                'evidence':{'bad':'secret'}}], 'raw_stdout':'PRIVATE',
            'schema_fingerprint':'not a hash','cli_version':'1.5.3\nSECRET'}
        safe=sanitize(value)
        self.assertNotIn('PRIVATE',json.dumps(safe));self.assertNotIn('TOKEN_SECRET',json.dumps(safe))
        self.assertNotIn('raw_stdout',safe);self.assertNotIn('cli_version',safe)


class DiagnosticPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'output',prefix='stage3c1-unit-')
        self.root=Path(self.tmp.name)
        self.cache=TranslationCache(self.root/'qa.sqlite3')
        self.exe=self.root/'fake.exe';self.exe.write_bytes(b'NEVER EXECUTED')
        self.runner=RunnerFixture()
        self.ext=patch('providers.agy.check_automatic_extensions');self.ext.start()
        self.source=self.root/'source';self.source.mkdir()
        for n in (1,2,3):provider_page((260,150),n).save(self.source/f'{n}.png')

    def tearDown(self):
        self.ext.stop();self.cache.close();self.tmp.cleanup()

    def provider(self, runner=None, **kwargs):
        return AGYProvider(str(self.exe),root=self.root/'fake-cli',runner=runner or self.runner,**kwargs)

    def manager(self, provider=None, options=None, resume_id=None):
        options=options or Options(source=str(self.source),output=str(self.root/'export'),mode=MODE)
        control=JobControl();service=TranslationService(options,self.cache,control,offline=OfflineFixture())
        service.agy=provider or self.provider()
        return ProcessingManager(options,self.cache,control,ocr=OCRFixture(),service=service,
            diagnostic_root=self.root/'diagnostics',resume_id=resume_id)

    def test_reject_diagnostic_batch_counts_no_text_no_cache_no_render(self):
        secret='PRIVATE_PROTOCOL_SECRET_123'
        def rejected(argv,payload,*args):
            result=self.runner(argv,payload,*args)
            if payload:return 0,json.dumps({'event':'tool_call','tool_name':secret,'arguments':{}}).encode()+b'\n'+result[1],secret.encode()
            return result
        provider=self.provider(rejected);before=provider.identity
        m=self.manager(provider);result=m.run()
        self.assertEqual(result['state'],'paused_provider');self.assertEqual(len(result['pending_paths']),3)
        self.assertEqual(result['completed'],0);self.assertEqual(len(self.runner.calls),1)
        self.assertEqual(provider.identity,before);self.assertEqual(provider.max_requests,64)
        self.assertEqual(len(m.journal['regions']),0)
        self.assertFalse(list((self.root/'export').glob('*')))
        self.assertEqual(self.cache.connection.execute("SELECT count(*) FROM cache WHERE kind='translation'").fetchone()[0],0)
        d=json.loads((m.diagnostics.directory/'errors.jsonl').read_text(encoding='utf-8').splitlines()[0])
        proto=d['agy_protocol']
        self.assertEqual(proto['classification'],'ACTUAL_TOOL_REQUEST')
        self.assertEqual((proto['page_count'],proto['region_count'],proto['source_characters']),(3,3,12))
        self.assertEqual(proto['request_number'],1);self.assertEqual(proto['cli_version'],'1.5.3')
        self.assertTrue(proto['pending_preserved']);self.assertFalse(proto['retry']);self.assertFalse(proto['translation_cached'])
        text=json.dumps(d,ensure_ascii=False)
        for value in [secret,'你好','Xin chào',str(self.root)]:self.assertNotIn(value,text)

    def test_unknown_tool_metadata_still_rejects_and_does_not_retry(self):
        def metadata(argv,payload,*args):
            code,out,err=self.runner(argv,payload,*args)
            if payload:out=b'{"event":"init","metadata":{"tool_name":"fixture"}}\n'+out
            return code,out,err
        m=self.manager(self.provider(metadata));result=m.run()
        self.assertEqual(result['state'],'paused_provider')
        d=json.loads(m.diagnostics.path.read_text(encoding='utf-8').splitlines()[0])
        self.assertEqual(d['agy_protocol']['classification'],'UNKNOWN_PROTOCOL_SHAPE')
        self.assertEqual(len(self.runner.calls),1)

    def test_schema_declaration_remains_rejected_even_classified_metadata(self):
        case=next(c for c in json.loads(FIXTURES.read_text(encoding='utf-8'))['cases'] if c['id']=='type_metadata')
        prefix=b''.join(json.dumps(e).encode()+b'\n' for e in case['prefix'])
        def metadata(argv,payload,*args):
            code,out,err=self.runner(argv,payload,*args);return code,prefix+out if payload else out,err
        m=self.manager(self.provider(metadata));result=m.run()
        self.assertEqual(result['state'],'paused_provider');self.assertFalse(m.journal['regions'])
        d=json.loads(m.diagnostics.path.read_text(encoding='utf-8').splitlines()[0])
        self.assertEqual(d['agy_protocol']['classification'],'TOOL_METADATA_ONLY')
        self.assertEqual(d['agy_protocol']['guard_decision'],'REJECT')

    def test_log_writer_never_persists_text_exception_or_private_paths(self):
        d=DiagnosticLog('a'*64,True,self.root/'diag')
        path=d.write(dict(job_id='a'*64,agy_protocol={'raw_stdout':'PRIVATE'},
            ocr_source_text='PRIVATE_OCR',raw_translated_target='PRIVATE_TARGET',
            image_path='C:/Users/PRIVATE',output_path='C:/Users/PRIVATE/result.png',
            error_message='PRIVATE_RAW_EXCEPTION'))
        text=Path(path).read_text(encoding='utf-8')
        self.assertNotIn('PRIVATE',text)

    def test_partial_validated_receipts_and_manual_resume_unchanged(self):
        def rejected_second(argv,payload,*args):
            index=len(self.runner.calls);code,out,err=self.runner(argv,payload,*args)
            if payload and index==1:out=b'{"event":"tool_call","tool_name":"fixture"}\n'+out
            return code,out,err
        options=Options(source=str(self.source),output=str(self.root/'export'),mode=MODE,agy_batch_regions=1)
        m=self.manager(self.provider(rejected_second),options);first=m.run()
        self.assertEqual((first['completed'],len(first['pending_paths'])),(1,2))
        self.assertEqual(len(m.journal['regions']),1)
        path=self.source/'1.png';output=m.destination(path);checksum=file_digest(output)
        receipt=self.cache.item(m.job_id,str(path))
        options.mode='Offline'
        service=TranslationService(options,self.cache,JobControl(),offline=OfflineFixture())
        with patch('core.pipeline.AGYProvider',side_effect=AssertionError('No AGY on Offline resume')):
            resumed=ProcessingManager(options,self.cache,ocr=OCRFixture(),service=service,resume_id=first['resume_id'])
            last=resumed.run()
        self.assertEqual(last['completed'],2);self.assertEqual(file_digest(output),checksum)
        self.assertEqual(receipt,self.cache.item(m.job_id,str(path)));self.assertEqual(len(self.runner.calls),2)

    def test_transport_stdout_and_stderr_limits_without_raw_capture(self):
        for script in ['import sys;sys.stdout.write("PRIVATE"*10000)',
                       'import sys;sys.stderr.write("PRIVATE"*15000)']:
            with self.assertRaises(OnlineProviderError) as cm:
                run_bounded([sys.executable,'-c',script],None,self.root,5,limit=4096)
            meta=cm.exception.agy_diagnostic
            self.assertTrue(meta['stream_limit_exceeded']);self.assertNotIn('PRIVATE',json.dumps(meta))
            self.assertEqual(meta['parser_error_code'],'INVALID_RESPONSE')

    def test_transport_timeout_and_cancel_without_agy_executable(self):
        command=[sys.executable,'-c','import time;time.sleep(10)']
        with self.assertRaises(OnlineProviderError) as cm:run_bounded(command,None,self.root,.1)
        self.assertEqual(cm.exception.agy_diagnostic['parser_error_code'],'TIMEOUT')
        with self.assertRaises(CancelledError) as cm:run_bounded(command,None,self.root,3,cancelled=lambda:True)
        self.assertEqual(cm.exception.agy_diagnostic['guard_decision'],'CANCELLED')

    def test_timeout_pipeline_still_pauses_and_records_no_payload(self):
        def timeout(argv,payload,*args):
            if payload:
                self.runner.calls.append((argv,payload,args[0],args[1]))
                raise OnlineProviderError('TIMEOUT','PRIVATE_TRANSPORT_EXCEPTION')
            return self.runner(argv,payload,*args)
        m=self.manager(self.provider(timeout));result=m.run()
        self.assertEqual(result['state'],'paused_provider');self.assertEqual(len(self.runner.calls),1)
        text=m.diagnostics.path.read_text(encoding='utf-8')
        self.assertNotIn('PRIVATE_TRANSPORT_EXCEPTION',text)
        self.assertEqual(json.loads(text)['agy_protocol']['parser_error_code'],'TIMEOUT')

    def test_online_translation_is_not_rejected_by_numeric_content(self):
        self.runner.transform=lambda text:text.replace('你好','Xin chào').replace('2','999')
        m=self.manager();result=m.run()
        self.assertEqual((result['completed'],result['fallback_original']),(3,0))
        self.assertFalse(m.diagnostics.path.exists())

    def test_request_limit_is_observed_without_an_extra_generation(self):
        provider=self.provider(max_requests=1)
        provider.translate_batch(['你好 1'],'zh')
        self.assertEqual(provider.requests_sent,1)
        with self.assertRaises(OnlineProviderError) as cm:provider.translate_batch(['你好 2'],'zh')
        self.assertEqual(cm.exception.code,'REQUEST_LIMIT')
        self.assertEqual(cm.exception.agy_diagnostic['request_number'],1)
        self.assertEqual(len(self.runner.calls),1)

    def test_cancel_pipeline_keeps_same_cancel_state_and_safe_diagnostic(self):
        def cancel(argv,payload,*args):
            if payload:raise CancelledError('PRIVATE_CANCEL_DETAIL')
            return self.runner(argv,payload,*args)
        m=self.manager(self.provider(cancel));result=m.run()
        self.assertEqual(result['state'],'cancelled');self.assertEqual(result['completed'],0)
        self.assertEqual(len(result['pending_paths']),3)
        diag=json.loads(m.diagnostics.path.read_text(encoding='utf-8'))
        self.assertEqual(diag['agy_protocol']['guard_decision'],'CANCELLED')
        self.assertNotIn('PRIVATE_CANCEL_DETAIL',json.dumps(diag))

    def test_observer_failure_cannot_change_legacy_accept_or_reject(self):
        good=envelope([{'id':'r0','text':'A'}])
        with patch('providers.agy.observe',side_effect=ValueError('PRIVATE_OBSERVER_FAILURE')):
            d={};self.assertEqual(parse_response(good,['r0'],0,diagnostic=d),['A'])
            self.assertEqual(d['guard_decision'],'ACCEPT');self.assertTrue(d['observation_failed'])
            self.assertFalse(d['pending_preserved'])
            with self.assertRaises(OnlineProviderError) as cm:parse_response(b'bad JSON',['r0'],0)
        self.assertNotIn('PRIVATE_OBSERVER_FAILURE',json.dumps(cm.exception.agy_diagnostic))

    def test_prompt_permissions_and_cache_identity_do_not_depend_on_diagnostics(self):
        provider=self.provider();identity=provider.identity
        self.assertEqual(SESSION_SETTINGS['permissions']['allow'],[])
        self.assertEqual(SESSION_SETTINGS['permissions']['ask'],[])
        self.assertIn('command(*)',SESSION_SETTINGS['permissions']['deny'])
        self.assertFalse(SESSION_SETTINGS['useG1Credits'])
        self.assertEqual(PROMPT_VERSION,'comic-vi-id-json-v1-literal-numbers-effort-medium')
        service=TranslationService(Options(mode=MODE),self.cache,JobControl());service.agy=provider
        from core.types import OCRResult
        regions=[OCRResult('你好 15',[[0,0],[10,0],[10,10],[0,10]],.99,'zh')]
        self.assertEqual(service.translate_regions(regions,'fixed-cache-context'),['Xin chào 15'])
        service.translate_regions(regions,'fixed-cache-context')
        self.assertEqual(len(self.runner.calls),1);self.assertEqual(provider.identity,identity)
        self.assertNotIn('你好',' '.join(self.runner.calls[0][0]))
        self.assertEqual(self.runner.calls[0][0][0],str(self.exe.resolve()))
