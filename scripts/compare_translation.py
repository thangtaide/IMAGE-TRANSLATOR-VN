"""Same 24 inputs, actual Argos inference, optional actual local M2M100 inference."""
from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding='utf-8')


def main() -> int:
    from scripts.evaluate_translation import CORPUS
    from scripts.validate_e2e import memory
    from core.types import MissingModelError
    from providers.offline import ArgosTranslationProvider
    from providers.m2m100 import M2M100TranslationProvider
    folder = ROOT / 'output/translation-comparison' / (
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:6])
    folder.mkdir(parents=True, exist_ok=False)
    report = {'mock': False, 'count': len(CORPUS), 'engines': {}, 'records': [],
              'quality_status': 'NOT ACCEPTED; human semantic review required'}
    outputs = {}
    for name, provider in [('Argos', ArgosTranslationProvider()), ('M2M100', M2M100TranslationProvider())]:
        start = time.perf_counter()
        try:
            if name == 'Argos':
                english = provider.translate_batch(CORPUS, 'zh', 'en')
                outputs['english'] = english
                outputs[name] = provider.translate_batch(english, 'en', 'vi')
            else:
                outputs[name] = provider.translate_batch(CORPUS, 'zh', 'vi')
            report['engines'][name] = {'status': 'PASS inference', 'seconds': time.perf_counter()-start,
                                      'memory': memory(), 'identity': provider.identity}
        except MissingModelError as exc:
            report['engines'][name] = {'status': 'SKIPPED', 'reason': str(exc)}
        except Exception as exc:
            report['engines'][name] = {'status': 'FAIL', 'error': type(exc).__name__+': '+str(exc)}
    for i, source in enumerate(CORPUS):
        report['records'].append({'id': i+1, 'source_zh': source,
            **{name: values[i] for name, values in outputs.items()}})
    report['comparison_status'] = 'RECORDED' if 'M2M100' in outputs else 'SKIPPED'
    (folder / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# Same 24-sentence comparison', '', 'M2M100: '+report['engines']['M2M100']['status'],
             '', '| # | Chinese | English pivot | Argos Vietnamese | M2M100 Vietnamese |',
             '| --- | --- | --- | --- | --- |']
    for record in report['records']:
        lines.append('| '+str(record['id'])+' | '+record['source_zh']+' | '+
                     record.get('english','NOT RUN')+' | '+record.get('Argos','NOT RUN')+' | '+
                     record.get('M2M100','SKIPPED: model missing')+' |')
    (folder / 'results.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('Comparison:', report['comparison_status'], 'Evidence:', folder)
    return 0 if report['comparison_status'] == 'RECORDED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
