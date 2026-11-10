"""Export measured constraints and blind human-reference forms, not semantic scores."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from qa.benchmark_translation import CANDIDATES,metrics

TAXONOMY=['OCR_ERROR','ZH_EN_SEMANTIC_ERROR','EN_VI_SEMANTIC_ERROR','NUMERIC_ERROR',
    'DATE_TIME_ERROR','ENTITY_NAME_ERROR','CONTEXT_LOSS','UNNATURAL_VIETNAMESE',
    'HALLUCINATED_CONTENT','OMITTED_CONTENT','POSTPROCESSING_ERROR','INSUFFICIENT_EVIDENCE']


def export(evidence: Path):
    dataset=json.loads((evidence/'dataset-manifest.json').read_text(encoding='utf-8'))
    rows={r['id']:r for r in dataset['rows']}
    all_outputs={name:[] for name in ('baseline',*CANDIDATES)}
    for phase in ('development','holdout'):
        for name in all_outputs:
            all_outputs[name].extend(json.loads((evidence/phase/(name+'.json')).read_text(encoding='utf-8')))
    baseline=all_outputs['baseline'];old={r['id']:r for r in baseline}
    aggregate={name:metrics(records,baseline if name!='baseline' else None) for name,records in all_outputs.items()}
    comparisons=[]
    for name,records in all_outputs.items():
        if name=='baseline':continue
        for record in records:
            previous=old[record['id']]
            comparisons.append(dict(id=record['id'],split=record['split'],candidate=name,
                output_changed=record['final_vi']!=previous['final_vi'],
                integrity_gain=record['qa_policy_pass'] and not previous['qa_policy_pass'],
                integrity_regression=not record['qa_policy_pass'] and previous['qa_policy_pass'],
                verified_semantic_improvement=None,verified_semantic_regression=None))
    known=[]
    for record in baseline:
        source=record['source_zh'];labels=[];basis=None
        if source in ('活动时间','活动时间和活动内容') and (record['final_vi'] or '').casefold()=='name':
            labels=['ZH_EN_SEMANTIC_ERROR' if (record['intermediate_en'] or '').casefold()=='name' else 'EN_VI_SEMANTIC_ERROR','OMITTED_CONTENT']
            basis='User-reported issue reproduced; no independent full reference translation.'
        elif source=='5月20日—5月30日' and 'giờ' in (record['final_vi'] or ''):
            labels=['EN_VI_SEMANTIC_ERROR','DATE_TIME_ERROR','NUMERIC_ERROR']
            basis='Stage2/user-confirmed date-to-clock meaning failure reproduced.'
        elif source=='3子' and record.get('preserved_control'):
            labels=['OCR_ERROR'];basis='User-confirmed decorative false positive; skipped, not an MT defect.'
        known.append(dict(id=record['id'],source=source,labels=labels or ['INSUFFICIENT_EVIDENCE'],
                         evidence=basis,independent_human_verified_reference=False,
                         literal_guard_rejected=not record['production_literal_guard_pass'] if not record.get('preserved_control') else None))
    (evidence/'baseline.json').write_text(json.dumps(baseline,ensure_ascii=False,indent=2),encoding='utf-8')
    (evidence/'candidate-results.json').write_text(json.dumps({k:v for k,v in all_outputs.items() if k!='baseline'},ensure_ascii=False,indent=2),encoding='utf-8')
    (evidence/'benchmark-metrics.json').write_text(json.dumps(dict(aggregate=aggregate,comparisons=comparisons,
        independent_human_references=0,semantic_metrics='NOT_MEASURED',
        timings='single ordered runs; warm model; not statistically controlled speed rankings'),ensure_ascii=False,indent=2),encoding='utf-8')
    (evidence/'error-analysis.json').write_text(json.dumps(dict(taxonomy=TAXONOMY,records=known,
        note='Unreviewed samples stay INSUFFICIENT_EVIDENCE; numeric regex is not semantic quality.'),ensure_ascii=False,indent=2),encoding='utf-8')
    with (evidence/'human-reference-template.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['id','split','source_zh','source_image','ocr_confidence','reference_vi','accepted_variants','verified_by','verified_at','status']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in dataset['rows']:
            writer.writerow(dict(id=row['id'],split=row['split'],source_zh=row['source'],
                source_image=row['occurrences'][0]['image'],ocr_confidence=row['occurrences'][0]['confidence'],
                reference_vi='',accepted_variants='',verified_by='',verified_at='',status='UNVERIFIED_REFERENCE'))
    with (evidence/'outputs-for-review.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['id','split','source','English baseline','Vietnamese baseline',*CANDIDATES])
        by_candidate={name:{r['id']:r for r in records} for name,records in all_outputs.items()}
        for row in dataset['rows']:
            b=old[row['id']]
            writer.writerow([row['id'],row['split'],row['source'],b['intermediate_en'],b['final_vi'],
                             *(by_candidate[n][row['id']]['final_vi'] for n in CANDIDATES)])
    return aggregate
