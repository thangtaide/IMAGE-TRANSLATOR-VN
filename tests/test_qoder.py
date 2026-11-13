"""Qoder contract fixtures and real local subprocess lifecycle; no Qoder generation."""
import copy
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from core.paths import ROOT
from core.pipeline import ProcessingManager
from core.resume import ResumeStore, work_recipe
from core.storage import TranslationCache, atomic_json, file_digest
from core.types import Options
from core.whole_chapter import QoderWholeChapterTranslator, WholeChapterJob
from providers.online import ProviderSuspended
from providers.qoder import (QoderProvider, CONTRACT, MODELS, EFFORTS, USAGE_MODEL_KEYS, find_qoder, selection,
    packet_for, parse_envelope, parse_translations, pack_rows, preflight, error_code)
from providers.qoder_process import run_process, QoderCancelled
from tests.image_fixtures import provider_page
from tests.test_whole_chapter import OCRFixture


def response(packet):
    result=copy.deepcopy(packet)
    result['images'].reverse()
    for page in result['images']:
        page['regions'].reverse()
        for row in page['regions']:row['text']='Xin chào'
    return result


class Runner:
    def __init__(self):self.calls=[];self.code=0;self.error=None;self.mutate=None
    def __call__(self,argv,payload,cwd,timeout,cancelled=lambda:False):
        self.calls.append((argv,payload,cwd))
        if self.error:raise self.error
        if self.code:return self.code,b'',b'insufficient credits'
        packet=json.loads(payload);data=response(packet)
        if self.mutate:self.mutate(data)
        model=argv[argv.index('--model')+1]
        return 0,json.dumps(dict(type='result',subtype='success',is_error=False,num_turns=1,
            stop_reason='end_turn',permission_denials=[],modelUsage={next(iter(USAGE_MODEL_KEYS[model])):{}},
            result=json.dumps(data))).encode(),b''


@pytest.fixture
def setup_qoder(tmp_path):
    exe=tmp_path/'fixture.exe';exe.write_bytes(b'NEVER EXECUTED')
    runner=Runner();probe=dict(models=['Ultimate','Sonus'],plugins={})
    def provider(**kwargs):
        return QoderProvider(str(exe),model='Ultimate',root=tmp_path/'receipts',runner=runner,probe=probe,**kwargs)
    return exe,runner,provider


def test_detection_and_exact_catalog(setup_qoder):
    exe,_,_=setup_qoder
    assert find_qoder(str(exe))==exe
    with pytest.raises(ProviderSuspended,match='Không tìm'):find_qoder(str(exe.with_name('missing.exe')))
    assert MODELS==(('Ultimate','Ultimate'),('Sonus','Sonus'))
    for _,model in MODELS:
        assert selection(model)==(model,None)
        assert EFFORTS[model]==()
        for effort in ('low','high','off'):
            with pytest.raises(ValueError):selection(model,effort)
    with pytest.raises(ValueError):selection('guessed-qwen-slug')


def test_preflight_metadata_only_and_no_secrets(setup_qoder):
    exe,_,_=setup_qoder;commands=[]
    from providers.qoder import REQUIRED_FLAGS
    def run(argv,*args):
        commands.append(argv)
        if '--version' in argv:out='1.1.89'
        elif '--help' in argv:out=' '.join(REQUIRED_FLAGS)
        elif 'status' in argv:out=json.dumps(dict(logged_in=True,token='NEVER-RETURN',email='PRIVATE'))
        elif '--list-models' in argv:out='MODEL\nUltimate\nSonus\n'
        else:out='[]'
        return 0,out.encode(),b''
    with patch.dict('os.environ',{'QODER_CONFIG_DIR':str(exe.parent/'empty-config')}):
        result=preflight(str(exe),runner=run)
    assert result['models']==['Ultimate','Sonus']
    assert 'NEVER-RETURN' not in json.dumps(result)
    assert all('--print' not in c for c in commands)


def test_three_images_one_invocation_and_receipt_reordered_resume(setup_qoder):
    _,runner,provider=setup_qoder
    ids=['p1_r00000','p2_r00000','p3_r00000']
    assert provider().translate_batch(['你好']*3,'zh',item_ids=ids)==['Xin chào']*3
    assert len(runner.calls)==1
    argv,payload,cwd=runner.calls[0]
    assert len(json.loads(payload)['images'])==3
    assert not cwd.is_relative_to(ROOT)
    assert argv[argv.index('--tools')+1]=='' and '--strict-mcp-config' in argv
    assert '--reasoning-effort' not in argv and '--yolo' not in argv
    # Different pending subset must replay the old full response without another subprocess.
    assert provider().translate_batch(['你好'],'zh',item_ids=[ids[1]])==['Xin chào']
    assert len(runner.calls)==1


@pytest.mark.parametrize('kind',['batch','image_missing','image_extra','image_duplicate','region_missing',
    'region_extra','region_duplicate','wrong_image','wrong_type','text_type'])
def test_invalid_id_contract(kind):
    rows=[dict(image_id='a',region_id='a_r0',text='你好'),dict(image_id='b',region_id='b_r0',text='你好')]
    packet=packet_for(rows,'fixture');data=response(packet)
    if kind=='batch':data['batch_id']='wrong'
    elif kind=='image_missing':data['images'].pop()
    elif kind=='image_extra':data['images'].append(dict(image_id='x',regions=[]))
    elif kind=='image_duplicate':data['images'][1]=copy.deepcopy(data['images'][0])
    elif kind=='region_missing':data['images'][0]['regions']=[]
    elif kind=='region_extra':data['images'][0]['regions'].append(dict(region_id='extra',text='x'))
    elif kind=='region_duplicate':data['images'][0]['regions']*=2
    elif kind=='wrong_image':data['images'][0]['regions'],data['images'][1]['regions']=data['images'][1]['regions'],data['images'][0]['regions']
    elif kind=='wrong_type':data['images'][0]['image_id']=[]
    else:data['images'][0]['regions'][0]['text']=False
    with pytest.raises(ProviderSuspended) as exc:parse_translations(data,packet)
    assert exc.value.code=='INVALID_RESPONSE'


@pytest.mark.parametrize('stdout',[b'{}',b'{"type":"result","type":"result"}',b'```json\n{}\n```',b'{}\n{}',b'\xff'])
def test_envelope_rejects_invalid_stdout(stdout):
    with pytest.raises(ProviderSuspended):parse_envelope(stdout,b'not a translation',0,dict(batch_id='x',images=[]))


def test_duplicate_inner_json_and_nonterminal_response(setup_qoder):
    packet=dict(batch_id='x',images=[])
    for content,stop in [(' {"batch_id":"x","batch_id":"x","images":[]}', 'end_turn'),('{}','max_tokens')]:
        raw=json.dumps(dict(type='result',subtype='success',is_error=False,num_turns=1,
            stop_reason=stop,permission_denials=[],result=content)).encode()
        with pytest.raises(ProviderSuspended) as exc:parse_envelope(raw,b'',0,packet)
        assert exc.value.code=='INVALID_RESPONSE'


def test_large_batches_split_without_cutting_regions(setup_qoder):
    _,runner,provider=setup_qoder
    ids=[f'p{i}_r0' for i in range(21)]
    assert len(provider().translate_batch(['你好']*21,'zh',item_ids=ids))==21
    assert [len(json.loads(c[1])['images']) for c in runner.calls]==[20,1]
    rows=[dict(image_id='p',region_id=f'p_r{i}',text='中'*300) for i in range(5)]
    batches=list(pack_rows(rows));assert len(batches)>1
    assert [r for b in batches for r in b]==rows


@pytest.mark.parametrize('message,code',[(b'insufficient credits','QUOTA_OR_CREDITS_EXCEEDED'),
    (b'not logged in','AUTH_REQUIRED'),(b'model not found','MODEL_UNAVAILABLE'),(b'other','PROVIDER_ERROR')])
def test_error_classification(message,code):assert error_code(b'',message)==code


def test_quota_latches_and_never_retries(setup_qoder):
    _,runner,provider=setup_qoder;runner.code=1;p=provider()
    for _ in range(2):
        with pytest.raises(ProviderSuspended) as exc:p.translate('你好','zh')
        assert exc.value.code=='QUOTA_OR_CREDITS_EXCEEDED'
    assert len(runner.calls)==1


def test_unknown_attempt_blocks_resume_until_explicit_authorization(setup_qoder):
    exe,runner,provider=setup_qoder;runner.error=ProviderSuspended('TIMEOUT','fixture')
    with pytest.raises(ProviderSuspended):provider().translate('你好','zh')
    runner.error=None
    with pytest.raises(ProviderSuspended) as exc:provider().translate('你好','zh')
    assert exc.value.code=='QODER_RESULT_UNKNOWN';assert len(runner.calls)==1
    receipt=next((exe.parent/'receipts').glob('*.json'));data=json.loads(receipt.read_text(encoding='utf-8'));data['state']='retry_authorized';atomic_json(receipt,data)
    assert provider().translate('你好','zh')=='Xin chào';assert len(runner.calls)==2


def test_local_subprocess_timeout_and_cancel(tmp_path):
    argv=[sys.executable,'-c','import time;time.sleep(30)']
    with pytest.raises(ProviderSuspended) as exc:run_process(argv,None,tmp_path,.1)
    assert exc.value.code=='TIMEOUT'
    with pytest.raises(QoderCancelled):run_process(argv,None,tmp_path,10,cancelled=lambda:True)
    code,out,err=run_process([sys.executable,'-c','import sys;print("stdout");print("stderr",file=sys.stderr)'],None,tmp_path,10)
    assert code==0 and out.strip()==b'stdout' and err.strip()==b'stderr'


def test_settings_save_cancel_reopen_and_effort(setup_qoder):
    from PySide6.QtWidgets import QApplication
    from ui.settings_dialog import SettingsDialog
    app=QApplication.instance() or QApplication([])
    opts=Options();dialog=SettingsDialog(opts);dialog.ai_source.setCurrentIndex(dialog.ai_source.findData('qoder'))
    dialog.qoder_model.setCurrentIndex(dialog.qoder_model.findData('Ultimate'));dialog.reject()
    assert opts.ai_provider=='agy' and not opts.qoder_model
    dialog=SettingsDialog(opts);dialog.ai_source.setCurrentIndex(dialog.ai_source.findData('qoder'))
    dialog.qoder_model.setCurrentIndex(dialog.qoder_model.findData('Sonus'));dialog.accept()
    reopened=SettingsDialog(Options.from_dict(opts.to_dict()))
    assert reopened.ai_source.currentData()=='qoder' and reopened.qoder_model.currentData()=='Sonus'
    assert not reopened.qoder_effort.isEnabled();assert opts.agy_model==Options().agy_model


@pytest.mark.parametrize('model',['Ultimate','Sonus'])
def test_pipeline_resume_and_provider_pin(setup_qoder,model):
    exe,runner,provider=setup_qoder
    source=exe.parent/'source';source.mkdir();output=exe.parent/'output'
    for i in range(3):provider_page((300,150),i+1).save(source/f'{i}.png')
    opts=Options(source=str(source),output=str(output),mode='AI Gemini AGY',ai_provider='qoder',
        qoder_executable=str(exe),qoder_model=model)
    events=[];cache=TranslationCache(exe.parent/'state.sqlite3')
    with patch('providers.qoder.run_process',runner),patch('providers.qoder.preflight',return_value=dict(models=['Ultimate','Sonus'],plugins={})),patch('providers.qoder.QoderProvider',side_effect=lambda **kw:QoderProvider(**kw,runner=runner,probe=dict(models=['Ultimate','Sonus'],plugins={}))):
        first=ProcessingManager(opts,cache=cache,ocr=OCRFixture(),emit=events.append).run()
        assert first['state']=='done',first
        resume_id=next(e['resume_id'] for e in events if e.get('type')=='resume_ready')
        opts.qoder_model='Sonus' if model=='Ultimate' else 'Ultimate'
        second=ProcessingManager(opts,cache=cache,ocr=OCRFixture(),resume_id=resume_id).run()
        assert second['skipped']==3 and len(runner.calls)==1
        assert opts.qoder_model==model
    cache.close()


def test_whole_automatic_batches_and_resume(setup_qoder):
    exe,runner,_=setup_qoder
    with tempfile.TemporaryDirectory(dir=ROOT/'output',prefix='stage3g-qoder-test-') as name:
        root=Path(name);source=root/'source';source.mkdir();work=root/'work'
        for i in range(21):provider_page((300,150),i+1).save(source/f'{i:03d}.png')
        opts=Options(qoder_executable=str(exe),qoder_model='Ultimate',ai_provider='qoder')
        def adapter():return QoderWholeChapterTranslator(opts,runner=runner,probe=dict(models=['Ultimate'],plugins={}))
        def job():return WholeChapterJob(source,work,options=opts,translator=adapter(),ocr=OCRFixture())
        prepared=job().run();assert prepared['state']=='awaiting_translation'
        first=job().run(allow_translation=True,confirmed_manifest_hash=prepared['manifest_hash'])
        assert first['state']=='done',first
        counts=[len(json.loads(c[1])['images']) for c in runner.calls]
        assert len(counts)>1 and sum(counts)==21 and all(1<n<=20 for n in counts)
        second=job().run();assert second['state']=='done' and second['skipped']==21
        assert len(runner.calls)==2


def test_qoder_fields_do_not_change_legacy_recipe():
    old=Options();new=Options(qoder_model='Sonus',qoder_effort='ignored',qoder_executable='unused.exe')
    assert work_recipe(old)==work_recipe(new)


def test_invalid_batch_is_not_committed(setup_qoder):
    exe,runner,provider=setup_qoder
    runner.mutate=lambda data:data['images'][0]['regions'].clear()
    with pytest.raises(ProviderSuspended) as exc:provider().translate('你好','zh')
    assert exc.value.code=='INVALID_RESPONSE'
    assert all(json.loads(p.read_text(encoding='utf-8'))['state']=='unknown' for p in (exe.parent/'receipts').glob('*.json'))


def test_whole_quota_preserves_completed_batches(setup_qoder):
    exe,runner,_=setup_qoder
    with tempfile.TemporaryDirectory(dir=ROOT/'output',prefix='stage3g-qoder-quota-') as name:
        root=Path(name);source=root/'source';source.mkdir();work=root/'work'
        for i in range(21):provider_page((300,150),i+1).save(source/f'{i:03d}.png')
        opts=Options(qoder_executable=str(exe),qoder_model='Ultimate',ai_provider='qoder')
        def quota_runner(*args):
            runner.code=1 if len(runner.calls)==1 else 0
            return runner(*args)
        def job():
            adapter=QoderWholeChapterTranslator(opts,runner=quota_runner,probe=dict(models=['Ultimate'],plugins={}))
            return WholeChapterJob(source,work,options=opts,translator=adapter,ocr=OCRFixture())
        prepared=job().run();hash_value=prepared['manifest_hash']
        failed=job().run(allow_translation=True,confirmed_manifest_hash=hash_value)
        first_count=len(json.loads(runner.calls[0][1])['images'])
        assert failed['error_code']=='QUOTA_OR_CREDITS_EXCEEDED' and failed['validated_regions']==first_count
        assert len(runner.calls)==2
        resumed=job().run(allow_translation=True,confirmed_manifest_hash=hash_value)
        assert resumed['state']=='done' and resumed['completed']==21
        assert len(runner.calls)==3 and len(json.loads(runner.calls[-1][1])['images'])==21-first_count


def test_unrelated_qoder_fields_keep_groq_job_fingerprint(setup_qoder):
    from tests.test_groq_api import HTTP
    exe,_,_=setup_qoder;source=exe.parent/'input';source.mkdir()
    provider_page((300,150),1).save(source/'01.png')
    opts=Options(source=str(source),output=str(exe.parent/'export'),mode='AI Gemini AGY',ai_provider='groq')
    cache=TranslationCache(exe.parent/'state.sqlite3');http=HTTP()
    try:
        with patch('providers.groq_api.requests.Session',return_value=http),patch('providers.groq_api.read_key',return_value='fixture'):
            first=ProcessingManager(opts,cache=cache,ocr=OCRFixture()).run()
            assert first['state']=='done'
            opts.qoder_model='Sonus';opts.qoder_executable='unrelated.exe'
            second=ProcessingManager(opts,cache=cache,ocr=OCRFixture()).run()
            assert second['skipped']==1 and first['job_id']==second['job_id']
            assert len(http.calls)==1
    finally:cache.close()


def test_unknown_authorization_is_explicit_and_one_time(setup_qoder):
    from PySide6.QtWidgets import QApplication,QMessageBox
    from ui.qoder_retry import confirm_unknown_receipts
    app=QApplication.instance() or QApplication([])
    exe,runner,provider=setup_qoder;runner.error=ProviderSuspended('TIMEOUT','fixture')
    with pytest.raises(ProviderSuspended):provider().translate('你好','zh')
    root=exe.parent/'receipts';receipt=next(root.glob('*.json'))
    with patch.object(QMessageBox,'question',return_value=QMessageBox.No):assert not confirm_unknown_receipts(root,None)
    assert json.loads(receipt.read_text(encoding='utf-8'))['state']=='unknown'

    with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):assert confirm_unknown_receipts(root,None)
    assert json.loads(receipt.read_text(encoding='utf-8'))['state']=='retry_authorized'
    # A second timed-out attempt consumes the authorization and becomes uncertain again.
    with pytest.raises(ProviderSuspended):provider().translate('你好','zh')
    assert json.loads(receipt.read_text(encoding='utf-8'))['state']=='unknown'


def test_cli_binary_change_does_not_resend_uncertain_pipeline(setup_qoder):
    exe,runner,_=setup_qoder;source=exe.parent/'input';source.mkdir()
    provider_page((300,150),1).save(source/'01.png')
    opts=Options(source=str(source),output=str(exe.parent/'export'),mode='AI Gemini AGY',ai_provider='qoder',
        qoder_executable=str(exe),qoder_model='Ultimate')
    cache=TranslationCache(exe.parent/'state.sqlite3');events=[]
    runner.error=ProviderSuspended('TIMEOUT','fixture')
    try:
        with patch('providers.qoder.QoderProvider',side_effect=lambda **kw:QoderProvider(**kw,runner=runner,probe=dict(models=['Ultimate'],plugins={}))):
            first=ProcessingManager(opts,cache=cache,ocr=OCRFixture(),emit=events.append).run()
            assert first['state']=='paused_provider'
            resume_id=next(e['resume_id'] for e in events if e.get('type')=='resume_ready')
            exe.write_bytes(b'NEW CLI IDENTITY');runner.error=None
            second=ProcessingManager(opts,cache=cache,ocr=OCRFixture(),resume_id=resume_id).run()
            assert second['state']=='paused_provider' and len(runner.calls)==1
    finally:cache.close()


def test_captured_sonus_envelope_has_real_internal_model_alias():
    fixture=json.loads((Path(__file__).parent/'fixtures/qoder_sonus_1_1_89.json').read_text(encoding='utf-8'))
    envelope=fixture['envelope'];packet=fixture['packet']
    assert 'smodel' in envelope['modelUsage'] and 'sonus' not in envelope['modelUsage']
    mapped,_=parse_envelope(json.dumps(envelope).encode(),b'',0,packet)
    assert set(mapped)=={r['region_id'] for p in packet['images'] for r in p['regions']}
    assert len(mapped)==3


def test_sonus_real_response_metadata_is_accepted_and_receipted(setup_qoder):
    exe,_,_=setup_qoder
    fixture=json.loads((Path(__file__).parent/'fixtures/qoder_sonus_1_1_89.json').read_text(encoding='utf-8'))
    rows=[(p['image_id'],r['region_id'],r['text']) for p in fixture['packet']['images'] for r in p['regions']]
    calls=[]
    def replay(argv,payload,*args):
        calls.append(argv);assert argv[argv.index('--model')+1]=='Sonus'
        packet=json.loads(payload);assert packet['images']==fixture['packet']['images']
        envelope=copy.deepcopy(fixture['envelope']);data=json.loads(envelope['result'])
        data['batch_id']=packet['batch_id'];envelope['result']=json.dumps(data)
        return 0,json.dumps(envelope).encode(),b''
    def provider():return QoderProvider(str(exe),model='Sonus',runner=replay,root=exe.parent/'sonus-receipts',probe=dict(models=['Sonus'],plugins={}))
    kwargs=dict(item_ids=[r[1] for r in rows],image_ids=[r[0] for r in rows])
    first=provider().translate_batch([r[2] for r in rows],'zh',**kwargs)
    second=provider().translate_batch([r[2] for r in rows],'zh',**kwargs)
    assert len(first)==3 and second==first and len(calls)==1
    assert all(json.loads(p.read_text(encoding='utf-8'))['state']=='done' for p in (exe.parent/'sonus-receipts').glob('*.json'))


@pytest.mark.parametrize('model,metadata_key',[('Sonus','ultimate'),('Sonus','sonus'),('Ultimate','smodel')])
def test_wrong_or_unverified_metadata_alias_remains_rejected(setup_qoder,model,metadata_key):
    exe,runner,_=setup_qoder
    def wrong_metadata(*args):
        code,out,err=runner(*args);data=json.loads(out);data['modelUsage']={metadata_key:{}}
        return code,json.dumps(data).encode(),err
    provider=QoderProvider(str(exe),model=model,runner=wrong_metadata,root=exe.parent/'wrong-model',probe=dict(models=[model],plugins={}))
    with pytest.raises(ProviderSuspended) as exc:provider.translate('你好','zh')
    assert exc.value.code=='MODEL_UNAVAILABLE' and len(runner.calls)==1


def test_qoder_budget_is_independent_from_agy_and_stops_before_next_request(setup_qoder):
    exe,runner,_=setup_qoder
    from core.pipeline import TranslationService,JobControl
    opts=Options(ai_provider='qoder',qoder_executable=str(exe),qoder_model='Ultimate',agy_max_requests=1)
    cache=TranslationCache(exe.parent/'budget.sqlite3')
    try:
        with patch('providers.qoder.QoderProvider',side_effect=lambda **kw:QoderProvider(**kw,runner=runner,probe=dict(models=['Ultimate'],plugins={}))):
            p=TranslationService(opts,cache,JobControl())._agy()
        assert p.max_requests==128
        p.requests=64
        assert p.translate('你好','zh')=='Xin chào' and len(runner.calls)==1
        p.requests=128
        with pytest.raises(ProviderSuspended) as exc:p.translate('谢谢','zh')
        assert exc.value.code=='REQUEST_BUDGET' and exc.value.request_sent is False
        assert len(runner.calls)==1
    finally:cache.close()


def test_budget_setting_save_cancel_and_notice(setup_qoder):
    from PySide6.QtWidgets import QApplication
    from ui.settings_dialog import SettingsDialog
    from ui.provider_notice import ProviderNotice
    app=QApplication.instance() or QApplication([])
    opts=Options(ai_provider='qoder',qoder_model='Sonus');dialog=SettingsDialog(opts)
    dialog.qoder_budget.setValue(77);dialog.reject();assert opts.qoder_max_requests==128
    dialog=SettingsDialog(opts);dialog.qoder_budget.setValue(77);dialog.accept()
    assert opts.qoder_max_requests==77
    notice=ProviderNotice();notice.show_error(dict(provider='Qoder CLI',code='REQUEST_BUDGET'))
    assert notice.last_code=='REQUEST_BUDGET' and 'cục bộ' in notice.summary.text()


def test_budget_and_new_style_do_not_change_existing_qoder_run(setup_qoder):
    exe,runner,_=setup_qoder;source=exe.parent/'input';source.mkdir();output=exe.parent/'export'
    for i in range(2):provider_page((300,150),i+1).save(source/f'{i}.png')
    opts=Options(source=str(source),output=str(output),mode='AI Gemini AGY',ai_provider='qoder',
        qoder_executable=str(exe),qoder_model='Ultimate',foreground='black',qoder_max_requests=1)
    cache=TranslationCache(exe.parent/'state.sqlite3');events=[]
    try:
        with patch('providers.qoder.QoderProvider',side_effect=lambda **kw:QoderProvider(**kw,runner=runner,probe=dict(models=['Ultimate'],plugins={}))):
            first=ProcessingManager(opts,cache=cache,ocr=OCRFixture(),emit=events.append).run()
            assert first['state']=='done';old_hashes={p.name:file_digest(p) for p in output.glob('*.png')}
            resume_id=next(e['resume_id'] for e in events if e.get('type')=='resume_ready')
            store=ResumeStore(exe.parent/'state.sqlite3');legacy=store.read(resume_id)
            legacy['options'].pop('qoder_max_requests');store.save(legacy)
            opts.foreground='white';opts.qoder_max_requests=128
            second=ProcessingManager(opts,cache=cache,ocr=OCRFixture(),resume_id=resume_id).run()
            assert second['skipped']==2 and second['job_id']==first['job_id'] and len(runner.calls)==1
            assert opts.foreground=='black' and old_hashes=={p.name:file_digest(p) for p in output.glob('*.png')}
        assert work_recipe(Options(qoder_max_requests=1))==work_recipe(Options(qoder_max_requests=128))
    finally:cache.close()
