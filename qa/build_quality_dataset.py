"""Build a source-only split from verified existing OCR, never from model scores."""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from core.paths import ROOT
from core.storage import digest, file_digest
from core.types import Options, OCRResult
from core.ocr import PaddleOCREngine
from core.ocr_overrides import OCRRegionOverrides

SEED='stage3-source-only-families-20261108-v1'


def canonical(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKC',text).casefold()
                   if not c.isspace() and not unicodedata.category(c).startswith('P'))


def tags(row: dict) -> list[str]:
    text=row['source'];out=[]
    cjk=re.findall(r'[\u3400-\u9fff]',text)
    notice=bool(re.search(r'活动|礼包|奖|更新|关注|点赞|感谢|制作|主笔|出品|监制|编辑|勾线|分镜|上色',text))
    if cjk and not notice:out.append('long_dialogue_candidate' if len(text)>=20 else 'short_dialogue_candidate')
    if notice:out.append('announcement_or_credit')
    if re.search(r'[！!]',text):out.append('exclamation')
    if re.search(r'[？?]|吗',text):out.append('question')
    if re.search(r'[0-9]+月[0-9]+日',text):out.append('date')
    if re.search(r'(?:[0-9]+|[一二三四五六七八九十百千万两]+)(?:个|分钟|个月|天|年)',text):out.append('quantity')
    if re.search(r'(?:[0-9]+|[一二三四五六七八九十百千万]+)(?:元|两)',text):out.append('money')
    if re.search(r'(?:[0-9]+|[一二三四五六七八九十]+)岁',text):out.append('age')
    if re.search(r'千城|千雪|孙妈妈|阿彩|秦国|顾府|顾国公|王府|梁家列|井浅系|墨墨子',text):out.append('proper_name_candidate')
    if re.search(r'世子|殿下|小姐|老太爷|老爷|夫人|国公|妾',text):out.append('honorific')
    if re.search(r'美若天仙|青灯古佛|了却尘缘|养家糊口|胡说八道',text):out.append('idiom_candidate')
    if len(text.strip())<=2:out.append('one_two_characters')
    if '\n' in text:out.append('literal_multiline')
    if ' ' in text and cjk:out.append('space_joined_ocr_not_proven_multiline')
    confidence=min(p['confidence'] for p in row['occurrences'])
    out.append('ocr_low_confidence' if confidence<.75 else 'ocr_high_confidence' if confidence>=.9 else 'ocr_medium_confidence')
    if not row['should_translate']:out.append('verified_preserve_control')
    if any(x in out for x in ('date','proper_name_candidate','honorific','idiom_candidate')):out.append('pivot_sensitive_candidate')
    return out


def collect(evidence: Path) -> list[dict]:
    chapter=json.loads((evidence/'chapter-manifest-before.json').read_text(encoding='utf-8'))
    target_job=next(p['pipeline_job_id'] for p in chapter['pages'] if p.get('pipeline_job_id'))
    ocr_identity=PaddleOCREngine().identity('zh')
    from providers.offline import ArgosTranslationProvider
    provider_identity=ArgosTranslationProvider().identity
    registry=OCRRegionOverrides.load()
    rows=[]
    for label,filename in [('production','pipeline.sqlite3'),('imgtest','batch-state.sqlite3')]:
        snapshot=evidence/'snapshots'/label/filename
        db=sqlite3.connect(snapshot.resolve().as_uri()+'?mode=ro',uri=True)
        db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON')
        for job in db.execute('SELECT * FROM jobs'):
            if label=='production' and job['id']!=target_job:continue
            options=Options.from_dict(json.loads(job['options']))
            if options.language!='zh' or options.glossary:
                raise ValueError('Dataset requires verified zh input and no hidden glossary normalization')
            for item in db.execute('SELECT * FROM items WHERE job=?',(job['id'],)):
                image=Path(item['path']);sha=file_digest(image)
                key=digest([sha,ocr_identity,options.language,options.confidence,options.tile_size,options.reading_direction])
                raw=db.execute("SELECT value FROM cache WHERE kind='ocr' AND key=?",(key,)).fetchone()
                if raw is None:raise ValueError('Unmapped OCR cache: '+str(image))
                regions=[OCRResult(**r) for r in json.loads(raw[0])['regions']]
                rules=registry.for_image(sha,image)
                filtered,_=registry.apply(regions,rules)
                context=digest([r.text for r in filtered if any(c.isalpha() for c in r.text)])
                for index,region in enumerate(regions):
                    preserve=not any(c.isalpha() for c in region.text) or region not in filtered
                    oldkey=digest([region.text,region.language,'vi',provider_identity,{},context,'glossary-v3-literal-numbers'])
                    old=db.execute("SELECT value FROM cache WHERE kind='translation' AND key=?",(oldkey,)).fetchone()
                    occurrence=dict(corpus=label,job_id=job['id'],image=str(image),image_sha256=sha,
                        ocr_cache_key=key,region_index=index,confidence=float(region.confidence),
                        polygon=region.polygon,reading_order=region.reading_order,
                        historical_accepted_translation=json.loads(old[0]) if old else None,
                        preserve_basis='VERIFIED_OCR_OVERRIDE' if region not in filtered else 'NUMERIC_SYMBOL_ONLY' if preserve else None)
                    rows.append(dict(source=region.text,language=region.language,should_translate=not preserve,occurrences=[occurrence]))
        db.close()
    return rows


def build(evidence: Path) -> dict:
    raw=collect(evidence)
    merged={}
    for row in raw:
        key=(row['source'],row['should_translate'])
        if key in merged:merged[key]['occurrences'].extend(row['occurrences'])
        else:merged[key]=row
    rows=list(merged.values())
    for row in rows:
        row['id']=digest([row['source'],row['should_translate']])[:20]
        row['tags']=tags(row)
        row.update(reference_vi=None,reference_status='UNVERIFIED_REFERENCE',human_verified=False,
                   tags_status='SOURCE_HEURISTICS_NOT_SEMANTIC_GROUND_TRUTH')
    parent=list(range(len(rows)))
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]];x=parent[x]
        return x
    norms=[canonical(r['source']) for r in rows]
    for i in range(len(rows)):
        for j in range(i):
            if norms[i]==norms[j] or (min(len(norms[i]),len(norms[j]))>=4 and SequenceMatcher(None,norms[i],norms[j]).ratio()>=.88):
                parent[find(i)]=find(j)
    groups={}
    for i,row in enumerate(rows):groups.setdefault(find(i),[]).append(row)
    # Known Stage2/user issues must not be disguised as independent holdout.
    known={'3子','活动时间和活动内容','活动时间','5月20日—5月30日'}
    for group in groups.values():
        group_id=digest(sorted(r['id'] for r in group))[:20]
        forced=any(r['source'] in known for r in group)
        split='development' if forced or int(digest([SEED,group_id])[:8],16)%10>=3 else 'holdout'
        for row in group:
            row.update(group_id=group_id,split=split,known_issue_family=forced)
            if row['source']=='5月20日—5月30日':
                row.update(user_expected_vi='Từ ngày 20/5 đến ngày 30/5',
                           expectation_status='USER_TASK_EXPECTATION_NOT_INDEPENDENT_CORPUS_GT')
    frequencies=Counter(tag for row in rows for tag in row['tags'])
    common={'short_dialogue_candidate','long_dialogue_candidate','ocr_high_confidence','ocr_medium_confidence','pivot_sensitive_candidate'}
    def priority(row):
        must=row['source'] in known or not row['should_translate']
        coverage=sum(1/frequencies[tag] for tag in row['tags'] if tag not in common)
        return (not must,-coverage,digest([SEED,row['id']]))
    selected=sorted(rows,key=priority)[:150]
    selected=sorted(selected,key=lambda r:r['id'])
    assert len({r['group_id'] for r in selected if r['split']=='development'} &
               {r['group_id'] for r in selected if r['split']=='holdout'})==0
    counts=dict(raw_region_instances=len(raw),unique_text_policy_rows=len(rows),selected=len(selected),
                omitted=len(rows)-len(selected),split=dict(Counter(r['split'] for r in selected)),
                tags=dict(Counter(t for r in selected for t in r['tags'])),
                source_corpus=dict(Counter(o['corpus'] for r in selected for o in r['occurrences'])),
                independent_human_verified_references=0,
                user_task_expectations=sum('user_expected_vi' in r for r in selected))
    manifest=dict(schema=1,seed=SEED,selection='source-only coverage; no target/model score used',
        dedup='exact text+preserve policy; near families NFKC/punctuation/whitespace + similarity>=.88',
        split_frozen_before_inference=True,known_issues_forced_development=True,
        candidate_module_sha256=file_digest(ROOT/'qa/translation_quality.py'),
        dataset_sha256=digest(selected),counts=counts,rows=selected)
    target=evidence/'dataset-manifest.json'
    if target.exists():raise FileExistsError('Do not replace a frozen dataset')
    target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',required=True,type=Path)
    args=parser.parse_args();folder=args.evidence.resolve()
    if not folder.is_relative_to((ROOT/'logs').resolve()):parser.error('QA evidence must be in project logs')
    print(json.dumps(build(folder)['counts'],ensure_ascii=False,indent=2))
