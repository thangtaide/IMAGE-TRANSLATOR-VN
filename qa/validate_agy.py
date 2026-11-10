"""One explicitly authorized batch: real PaddleOCR -> real AGY -> guarded export."""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--authorized-three-development-samples', action='store_true')
    parser.add_argument('--additional-approved-attempt', action='store_true')
    parser.add_argument('--stage3-evidence', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    if not args.authorized_three_development_samples:
        parser.error('Cần người dùng duyệt AGY/3 mẫu/300ký tự/1lượt không retry trước khi dùng opt-in.')
    from core.runtime import prepare_inference_runtime
    prepare_inference_runtime()
    from core.paths import ROOT
    from core.ocr import PaddleOCREngine
    from core.pipeline import JobControl, ProcessingManager, TranslationService, NUMBER_PATTERN
    from core.storage import TranslationCache, digest, file_digest
    from core.types import Options
    from providers.agy import AGYProvider, MODE, run_bounded, strict_json, protocol_metadata
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    folder = ROOT / 'output' / 'agy-validation' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder.mkdir(parents=True, exist_ok=False)
    pointer = args.evidence / 'live-qa-location.json'
    ledger_path = args.evidence / 'live-qa-attempts.json'
    ledger = json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else []
    if pointer.exists():
        previous = json.loads(pointer.read_text(encoding='utf-8'))
        if previous not in ledger:
            ledger.append(previous)
    current = {'root': str(folder)}
    ledger.append(current)
    ledger_path.write_text(json.dumps(ledger, indent=2), encoding='utf-8')
    pointer.write_text(json.dumps(current), encoding='utf-8')
    rows = json.loads((args.stage3_evidence / 'dataset-manifest.json').read_text(encoding='utf-8'))['rows']
    wanted = ['活动时间', '活动时间和活动内容', '第13话']
    selected = [next(r for r in rows if r['source'] == text and r['split'] == 'development') for text in wanted]
    assert len(selected) == 3 and sum(len(r['source']) for r in selected) <= 300
    plan = {'authorization': 'Explicit user approval in Stage3B conversation',
            'additional_explicitly_approved_attempt': args.additional_approved_attempt,
            'max_model_requests': 1, 'max_ocr_characters': 300, 'max_regions': 3, 'retry': 0,
            'samples': [{'id': r['id'], 'source': r['source'], 'split': r['split']} for r in selected],
            'image_fixture': 'SYNTHETIC, with source strings taken from development set; not real comic acceptance'}
    (folder / 'approved-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    source = folder / 'source'
    source.mkdir()
    image = Image.new('RGB', (1600, 1000), 'white')
    draw = ImageDraw.Draw(image)
    for index, text in enumerate(wanted):
        draw.text((80, 70+index*300), text, font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 64), fill='black')
    path = source / 'development-fixture.png'
    image.save(path)
    original = file_digest(path)
    report = {'status': 'NOT_TESTED', 'mock': False, 'model_requests': 0, 'retries': 0,
              'independent_verified_references': 0, 'fixture': plan['image_fixture']}
    cache = TranslationCache(folder / 'qa.sqlite3')
    provider = None
    try:
        engine = PaddleOCREngine()
        identity = engine.identity('zh')
        regions, warnings = engine.recognize(np.array(image), 'zh')
        (folder / 'ocr.json').write_text(json.dumps({'regions': [asdict(r) for r in regions], 'warnings': warnings},
            ensure_ascii=False, indent=2), encoding='utf-8')
        actual = [r.text for r in regions]
        if actual != wanted:
            report.update(status='OCR_SCOPE_MISMATCH_NO_AGY_REQUEST', actual_ocr=actual)
            return 1
        options = Options(source=str(source), output=str(folder / 'export'), mode=MODE, agy_max_requests=1)
        key = digest([original, identity, 'zh', options.confidence, options.tile_size, options.reading_direction])
        cache.put('ocr', key, {'regions': [asdict(r) for r in regions], 'warnings': warnings})
        control = JobControl()
        def capture_runner(argv, payload, cwd, timeout, cancelled):
            result = run_bounded(argv, payload, cwd, timeout, cancelled)
            if payload is not None:
                code, stdout, stderr = result
                candidates = []
                seen = set()
                def visit(value, depth=0):
                    if depth > 8 or len(candidates) >= 5:
                        return
                    if isinstance(value, str):
                        try:
                            visit(strict_json(value), depth+1)
                        except ValueError:
                            pass
                    if isinstance(value, dict):
                        if set(value) == {'translations'} and isinstance(value['translations'], list):
                            items = value['translations']
                            if (len(items) == 3 and all(isinstance(r, dict) and set(r) == {'id', 'text'}
                                    and isinstance(r['id'], str) and isinstance(r['text'], str) and len(r['text']) <= 4000 for r in items)
                                    and {r['id'] for r in items} == {'r0000', 'r0001', 'r0002'}):
                                fingerprint = json.dumps(value, sort_keys=True)
                                if fingerprint not in seen:
                                    seen.add(fingerprint)
                                    candidates.append(value)
                        for child in value.values():
                            visit(child, depth+1)
                    if isinstance(value, list):
                        for child in value:
                            visit(child, depth+1)
                for line in stdout.decode('utf-8', errors='replace').splitlines():
                    try:
                        visit(strict_json(line))
                    except ValueError:
                        pass
                (folder / 'protocol.json').write_text(json.dumps({'metadata': protocol_metadata(stdout, stderr, code),
                    'translation_payload_candidates': candidates,
                    'notice': 'Candidates are not accepted output; terminal state/tools/IDs/numeric guard must still pass.'},
                    ensure_ascii=False, indent=2), encoding='utf-8')
            return result
        provider = AGYProvider(max_requests=1, root=folder / 'agy', checkpoint=control.checkpoint,
                               cancelled=lambda: control.cancelled, runner=capture_runner)
        service = TranslationService(options, cache, control)
        service.agy = provider
        events = []
        manager = ProcessingManager(options, cache, control, events.append, ocr=engine, service=service,
                                    diagnostic_root=folder / 'diagnostics')
        summary = manager.run()
        report.update(pipeline=summary, model_requests=provider.requests_sent, model=provider.model,
                      protocol=provider.last_protocol,
                      provider_identity=provider.identity, cli_version=provider.version,
                      transmitted_source_characters=sum(len(r.text) for r in regions),
                      rows=[{'source': r.text, 'raw_target': target,
                             'numeric_source': re.findall(NUMBER_PATTERN, r.text),
                             'numeric_target': re.findall(NUMBER_PATTERN, target),
                             'numeric_pass': re.findall(NUMBER_PATTERN, r.text) == re.findall(NUMBER_PATTERN, target)}
                            for r, target in zip(regions, provider.last_targets)])
        if summary['state'] == 'done':
            result = manager.destination(path)
            with Image.open(result) as bitmap:
                assert bitmap.size == image.size
                bitmap.verify()
            assert file_digest(path) == original and provider.requests_sent == 1
            report.update(status='REAL_AGY_OCR_TO_IMAGE_QA_PASS', output=str(result),
                          source_hash_unchanged=True, bitmap_valid=True)
            return 0
        report['status'] = 'AGY_QA_NOT_COMPLETE'
        return 1
    except Exception as exc:
        report.update(status='AGY_QA_ERROR', code=getattr(exc, 'code', type(exc).__name__))
        return 1
    finally:
        report['model_requests'] = provider.requests_sent if provider else 0
        cache.close()
        (folder / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
