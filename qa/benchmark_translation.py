"""Offline, isolated two-leg benchmark. No production cache/job/setting writes."""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from core.paths import ROOT
from core.storage import digest,file_digest
from core.pipeline import NUMBER_PATTERN
from core.diagnostics import VALIDATOR_VERSION
from providers.offline import ArgosTranslationProvider
from qa.translation_quality import normalize_source,split_sentences,parse_date_range,date_integrity,DATE_POLICY_VERSION

CANDIDATES=('nfc_trim_v1','sentence_split_v1','length_penalty_1_0',DATE_POLICY_VERSION)


class ObservedArgos(ArgosTranslationProvider):
    """Observation only; underlying Argos decoder and settings unchanged."""
    def __init__(self):
        super().__init__();self.trace=[]

    def _decode(self,tokenizer,tokens):
        output=super()._decode(tokenizer,tokens)
        pair=next(pair for pair,(path,meta) in self.packages.items()
                  if str(path) in self.loaded and self.loaded[str(path)][1] is tokenizer)
        self.trace.append(dict(source_language=pair[0],target_language=pair[1],output=output.strip()))
        return output


class PenaltyProxy:
    def __init__(self,translator):self.translator=translator
    def translate_batch(self,*args,**kwargs):
        kwargs=dict(kwargs,length_penalty=1.0)
        return self.translator.translate_batch(*args,**kwargs)


class QAPenaltyArgos(ObservedArgos):
    def _load(self,pair):
        translator,tokenizer,prefix=super()._load(pair)
        return PenaltyProxy(translator),tokenizer,prefix


def infer(provider,text: str) -> tuple[str,str,list]:
    provider.trace=[]
    target=provider.translate(text,'zh','vi')
    trace=list(provider.trace)
    if len(trace)!=2 or [(r['source_language'],r['target_language']) for r in trace]!=[('zh','en'),('en','vi')]:
        raise RuntimeError('Unexpected provider route')
    return trace[0]['output'],target,trace


def evaluate(row: dict, candidate: str, baseline: ObservedArgos, penalty: QAPenaltyArgos) -> dict:
    source=row['source'];started=time.perf_counter();cpu=time.process_time()
    result=dict(id=row['id'],source_zh=source,split=row['split'],candidate=candidate,
        model_identity=baseline.identity,source_numeric_tokens=re.findall(NUMBER_PATTERN,source),
        validator_version=VALIDATOR_VERSION,reference_status=row['reference_status'],human_verified=False,
        intermediate_en=None,final_vi=None,traces=[],provider_input=source,error=None,
        production_literal_guard_pass=False,structured_date_integrity_pass=False,qa_policy_pass=False)
    try:
        if not row['should_translate']:
            result.update(final_vi=source,preserved_control=True,qa_policy_pass=True,engine='NO_MT_PRESERVED_CONTROL')
        else:
            result['preserved_control']=False
            dates=parse_date_range(source) if candidate==DATE_POLICY_VERSION else None
            if dates is not None:
                target=dates.vi()
                assert date_integrity(source,target)
                result.update(final_vi=target,engine='QA_TYPED_DATE_RECONSTRUCTION',
                              structured_date_integrity_pass=True,date_proof=asdict(dates),traces=[])
            else:
                result['engine']='REAL_ARGOS_PIVOT'
                if candidate=='sentence_split_v1':
                    parts=split_sentences(source)
                    mids=[];targets=[];traces=[]
                    for part in parts:
                        mid,target,trace=infer(baseline,part)
                        mids.append(mid);targets.append(target);traces.extend(trace)
                    result.update(intermediate_en=' | '.join(mids),final_vi=' '.join(targets),traces=traces,segments=parts)
                else:
                    text=normalize_source(source) if candidate=='nfc_trim_v1' else source
                    provider=penalty if candidate=='length_penalty_1_0' else baseline
                    mid,target,trace=infer(provider,text)
                    result.update(provider_input=text,intermediate_en=mid,final_vi=target,traces=trace)
            result['target_numeric_tokens']=re.findall(NUMBER_PATTERN,result['final_vi'])
            result['production_literal_guard_pass']=bool(result['final_vi'].strip()) and result['target_numeric_tokens']==result['source_numeric_tokens']
            result['qa_policy_pass']=result['production_literal_guard_pass'] or result['structured_date_integrity_pass']
            result['placeholder_like_output']=bool(re.search(r'ZX[QN][A-Z]{2}[QN]XZ',result['final_vi'],re.I))
    except Exception as exc:
        result.update(error=dict(type=type(exc).__name__,message=str(exc)[:1000]),qa_policy_pass=False)
    result.update(seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,
                  decode_settings=dict(beam_size=4,length_penalty=1.0 if candidate=='length_penalty_1_0' else .2,
                                       max_decoding_length=768,replace_unknowns=True,device='cpu',compute_type='int8',intra_threads=2))
    return result


def metrics(records: list[dict],baseline: list[dict] | None=None) -> dict:
    eligible=[r for r in records if not r.get('preserved_control')]
    result=dict(samples=len(records),mt_eligible=len(eligible),preserved_controls=len(records)-len(eligible),
        inference_errors=sum(r['error'] is not None for r in eligible),
        production_literal_guard_pass=sum(r['production_literal_guard_pass'] for r in eligible),
        production_literal_guard_reject=sum(not r['production_literal_guard_pass'] for r in eligible),
        structured_date_pass=sum(r['structured_date_integrity_pass'] for r in eligible),
        qa_policy_pass=sum(r['qa_policy_pass'] for r in eligible),
        mean_seconds=statistics.mean(r['seconds'] for r in eligible) if eligible else 0,
        total_cpu_seconds=sum(r['cpu_seconds'] for r in records),
        literal_name_outputs=sum((r['final_vi'] or '').strip().casefold()=='name' for r in eligible),
        independent_verified_semantic_improvements=None,independent_verified_semantic_regressions=None,
        accuracy_bleu_comet=None)
    if baseline is not None:
        old={r['id']:r for r in baseline}
        result.update(outputs_changed=sum(r['final_vi']!=old[r['id']]['final_vi'] for r in records),
            outputs_unchanged=sum(r['final_vi']==old[r['id']]['final_vi'] for r in records),
            integrity_gain=sum(r['qa_policy_pass'] and not old[r['id']]['qa_policy_pass'] for r in eligible),
            integrity_regression=sum(not r['qa_policy_pass'] and old[r['id']]['qa_policy_pass'] for r in eligible))
    return result


def run(evidence: Path,phase: str):
    from core.runtime import prepare_inference_runtime
    prepare_inference_runtime()
    from scripts.validate_e2e import memory
    dataset=json.loads((evidence/'dataset-manifest.json').read_text(encoding='utf-8'))
    assert digest(dataset['rows'])==dataset['dataset_sha256']
    assert file_digest(ROOT/'qa/translation_quality.py')==dataset['candidate_module_sha256']
    freeze=evidence/'candidates-frozen.json'
    if phase=='holdout':
        f=json.loads(freeze.read_text(encoding='utf-8'))
        assert f['module_sha256']==file_digest(ROOT/'qa/translation_quality.py')
        assert f['runner_sha256']==file_digest(Path(__file__)) and f['candidates']==list(CANDIDATES)
    rows=[row for row in dataset['rows'] if row['split']==phase]
    assert rows
    destination=evidence/phase;destination.mkdir(exist_ok=False)
    offline=[]
    def audit(event,args):
        if event in ('socket.connect','socket.getaddrinfo'):
            offline.append(event);raise RuntimeError('Quality benchmark is strictly offline')
    sys.addaudithook(audit)
    provider=ObservedArgos();penalty=QAPenaltyArgos();penalty.loaded=provider.loaded
    started=time.perf_counter()
    for pair in provider.route('zh','vi'):provider._load(pair)
    cold=time.perf_counter()-started
    # Verify observer against the unmodified provider on development-only inputs.
    equivalence=[]
    if phase=='development':
        original=ArgosTranslationProvider();original.loaded=provider.loaded
        for row in [r for r in rows if r['should_translate']][:3]:
            output=original.translate(row['source'],'zh','vi')
            _,observed,_=infer(provider,row['source'])
            equivalence.append(output==observed)
        assert all(equivalence)
    outputs={}
    for candidate in ('baseline',*CANDIDATES):
        records=[]
        for n,row in enumerate(rows,1):
            records.append(evaluate(row,candidate,provider,penalty))
            if n%25==0:print(phase,candidate,n,'/',len(rows),flush=True)
        outputs[candidate]=records
        (destination/(candidate+'.json')).write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    measured={name:metrics(records,outputs['baseline'] if name!='baseline' else None) for name,records in outputs.items()}
    result=dict(phase=phase,metrics=measured,cold_load_seconds=cold,observer_equivalence=equivalence,
                memory_after=memory(),model_identity=provider.identity,network_attempts=offline,
                candidate_code_sha256=file_digest(ROOT/'qa/translation_quality.py'),
                python=sys.executable,model_changed=False,production_cache_access=False)
    (destination/'metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if phase=='development':
        freeze.write_text(json.dumps(dict(module_sha256=file_digest(ROOT/'qa/translation_quality.py'),
            runner_sha256=file_digest(Path(__file__)),candidates=CANDIDATES,dataset_sha256=dataset['dataset_sha256'],
            rule='All four predeclared candidates; no tuning after holdout'),indent=2),encoding='utf-8')
    assert not offline
    print(json.dumps(measured,ensure_ascii=False,indent=2))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--phase',choices=['development','holdout'],required=True)
    args=parser.parse_args();folder=args.evidence.resolve()
    if not folder.is_relative_to((ROOT/'logs').resolve()):parser.error('QA only inside project logs')
    run(folder,args.phase)
