"""Explicitly authorized, bounded MyMemory QA. Never run from application startup."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from core.pipeline import JobControl, TranslationService
from core.storage import TranslationCache
from core.types import Options
from providers.online import MyMemoryProvider, OnlineProviderError, ProviderSuspended
import requests


class BudgetSession(requests.Session):
    def __init__(self):
        super().__init__()
        self.requests_sent, self.characters_sent = 0, 0

    def request(self, method, url, **kwargs):
        text = kwargs.get('params', {}).get('q', '')
        if (method != 'GET' or url != 'https://api.mymemory.translated.net/get'
                or kwargs.get('allow_redirects') is not False):
            raise OnlineProviderError('QA_SCOPE', 'Request ngoài phạm vi QA đã duyệt.')
        if self.requests_sent >= 8 or self.characters_sent + len(text) > 1000:
            raise ProviderSuspended('QA_BUDGET', 'Đã đạt giới hạn QA cục bộ đã duyệt.')
        self.requests_sent += 1
        self.characters_sent += len(text)
        return super().request(method, url, **kwargs)


def select_rows(dataset):
    rows = [r for r in dataset['rows'] if r['split'] == 'development' and r['should_translate']]
    preferred = ['5月20日—5月30日', '活动时间', '活动时间和活动内容', '回去！', '父亲大人，']
    selected = []
    for text in preferred:
        match = next((r for r in rows if r['source'] == text), None)
        if match:
            selected.append(match)
    for row in rows:
        if len(selected) >= 6:
            break
        if row not in selected and len(row['source'].encode('utf-8')) <= 450:
            selected.append(row)
    assert len(selected) <= 6 and sum(len(r['source']) for r in selected) <= 1000
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--authorized-mymemory-six-development-samples', action='store_true')
    parser.add_argument('--stage3-evidence', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    if not args.authorized_mymemory_six_development_samples:
        parser.error('Cần chấp thuận rõ provider/phạm vi trước khi dùng flag opt-in.')
    output = args.evidence / 'live-online'
    output.mkdir(exist_ok=False)
    data = json.loads((args.stage3_evidence / 'dataset-manifest.json').read_text(encoding='utf-8'))
    baseline = {r['id']: r for r in json.loads((args.stage3_evidence / 'baseline.json').read_text(encoding='utf-8'))}
    selected = select_rows(data)
    (output / 'approved-plan.json').write_text(json.dumps({
        'authorization': 'Explicit user approval in Stage3A conversation',
        'provider': 'MyMemory anonymous official GET', 'max_samples': 6,
        'max_total_transmitted_characters_including_retries': 1000, 'max_requests_including_retries': 8,
        'rows': [{'id': r['id'], 'source': r['source'], 'split': r['split']} for r in selected]},
        ensure_ascii=False, indent=2), encoding='utf-8')
    session = BudgetSession()
    provider = MyMemoryProvider(client=session)
    cache = TranslationCache(output / 'online-qa.sqlite3')
    service = TranslationService(Options(mode='Online Free'), cache, JobControl(), online=provider)
    results = []
    try:
        for row in selected:
            start = time.monotonic()
            before = session.requests_sent
            item = {'id': row['id'], 'source': row['source'], 'split': row['split'],
                    'reference_status': 'UNVERIFIED_REFERENCE', 'baseline': baseline.get(row['id'])}
            try:
                item.update(target=service.translate(row['source'], row['language'], 'stage3a-approved-qa'),
                            status='LIVE_TRANSLATION_NUMERIC_PASS')
            except OnlineProviderError as exc:
                item.update(status='LIVE_ERROR', code=exc.code, detail=str(exc))
            except Exception as exc:
                item.update(status='LIVE_ERROR', code=getattr(exc, 'code', type(exc).__name__))
            item.update(attempt=service.last_attempt, seconds=time.monotonic()-start,
                        requests=session.requests_sent-before, retries=provider.retry_count)
            results.append(item)
            if provider.blocked_error is not None or item.get('code') == 'QA_BUDGET':
                break
    finally:
        service.close()
        cache.close()
        summary = {'provider_identity': provider.identity, 'requests_sent': session.requests_sent,
                   'characters_sent_including_retries': session.characters_sent,
                   'selected': len(selected), 'attempted_samples': len(results),
                   'numeric_pass': sum(r['status'] == 'LIVE_TRANSLATION_NUMERIC_PASS' for r in results),
                   'errors': sum(r['status'] == 'LIVE_ERROR' for r in results),
                   'semantic_accuracy_measured': False, 'independent_verified_references': 0,
                   'results': results}
        (output / 'results.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k: v for k,v in summary.items() if k != 'results'}, ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
