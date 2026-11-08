"""Independent typed fixtures for QA parser robustness; not human translation GT."""
from __future__ import annotations

import calendar
import json
import random
from pathlib import Path

from core.storage import digest
from qa.translation_quality import parse_date_range,date_integrity


def generate(evidence: Path) -> dict:
    rng=random.Random(202611080317)
    rows=[]
    separators=['—','–','-','至','到','~','～']
    def positive(y1,m1,d1,y2,m2,d2,sep):
        source=(f'{y1}年' if y1 else '')+f'{m1}月{d1}日'+sep+(f'{y2}年' if y2 else '')+f'{m2}月{d2}日'
        start=f'{d1}/{m1}'+(f'/{y1}' if y1 else '')
        end=f'{d2}/{m2}'+(f'/{y2}' if y2 else '')
        rows.append(dict(id=f'positive-{len(rows):03}',source=source,should_parse=True,
                         expected_vi=f'Từ ngày {start} đến ngày {end}',typed_endpoints=[[y1,m1,d1],[y2,m2,d2]]))
    for i in range(32):
        year=2024+i%3 if i%3==0 else None
        month=rng.randint(1,12);maximum=calendar.monthrange(year or 2001,month)[1]
        start=rng.randint(1,maximum-1);end=rng.randint(start+1,maximum)
        positive(year,month,start,year,month,end,separators[i%7])
    for i in range(16):
        month=rng.randint(1,11);year=2024 if i%2 else None
        positive(year,month,25,year,month+1,3,separators[i%7])
    for i in range(8):
        year=2024 if i%2 else None
        positive(year,12,24+i%5,2025 if year else None,1,1+i%7,separators[i%7])
    for i,year in enumerate([2000,2004,2012,2016,2020,2024,2028,2032]):
        positive(year,2,29,year,3,1,separators[i%7])
    negatives=['5月20日5月30日','6月1日6月10日','12月28日1月3日',
        '2024年5月20日—5月30日','2月29日—3月1日','1900年2月29日—1900年3月1日',
        '5月30日—5月20日','2025年5月20日—2024年5月30日',
        '0月20日—5月30日','13月20日—5月30日','5月0日—5月30日','4月31日—5月2日',
        '活动时间：5月20日—5月30日','5月20日—5月30日（节假日除外）',
        '农历5月20日—5月30日','５月２０日—５月３０日']
    for i in range(8):
        negatives.extend([f'{10+i}:00—{11+i}:30',f'{20+i}-{30+i}元',
                          f'{3+i}—{5+i}个',f'13800138{i:03}',f'QA-ID-{202400+i}',f'-{15+i}'])
    for i,source in enumerate(negatives):rows.append(dict(id=f'negative-{i:03}',source=source,should_parse=False,expected_vi=None))
    result=dict(seed=202611080317,kind='SYNTHETIC_TYPED_CONSTRAINT_FIXTURES_NOT_NATURAL_HOLDOUT',
                human_translation_ground_truth=False,materialized_before_evaluation=True,rows=rows,sha256=digest(rows))
    path=evidence/'structural-fixtures.json'
    if path.exists():raise FileExistsError('Frozen fixture data must not be replaced')
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def evaluate(evidence: Path) -> dict:
    data=json.loads((evidence/'structural-fixtures.json').read_text(encoding='utf-8'))
    assert digest(data['rows'])==data['sha256']
    results=[];tamper_count=0
    for row in data['rows']:
        value=parse_date_range(row['source'])
        passed=(value is not None)==row['should_parse']
        target=value.vi() if value else None
        if row['should_parse']:
            passed=passed and target==row['expected_vi'] and date_integrity(row['source'],target)
            start,end=row['typed_endpoints']
            # Wrong day, swapped endpoints, added clock: independent mutations of expected target.
            tampered=[target.replace(f'{start[2]}/{start[1]}',f'{start[2]+1}/{start[1]}',1),
                      target.replace('Từ ngày ','Lúc ',1)]
            left,right=target.removeprefix('Từ ngày ').split(' đến ngày ')
            tampered.append(f'Từ ngày {right} đến ngày {left}')
            for bad in tampered:
                if bad!=target:
                    tamper_count+=1
                    passed=passed and not date_integrity(row['source'],bad)
        results.append(dict(id=row['id'],parsed=value is not None,output=target,passed=passed))
    report=dict(total=len(results),positive=sum(r['should_parse'] for r in data['rows']),
                negative=sum(not r['should_parse'] for r in data['rows']),
                passed=sum(r['passed'] for r in results),tamper_rejections_checked=tamper_count,
                results=results,semantic_accuracy_measured=False)
    (evidence/'structural-evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report
