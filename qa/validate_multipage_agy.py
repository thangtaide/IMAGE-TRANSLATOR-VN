"""Prepare real OCR offline; one separate opt-in AGY batch on three QA pages."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from dataclasses import asdict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--authorized-live', action='store_true')
    args = parser.parse_args()
    from core.runtime import prepare_inference_runtime
    prepare_inference_runtime()
    from core.pipeline import ProcessingManager, TranslationService, JobControl
    from core.storage import TranslationCache, digest, file_digest
    from core.ocr import PaddleOCREngine
    from core.types import Options
    from core.paths import ROOT
    from providers.agy import AGYProvider, MODE, run_bounded
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    root = args.root.resolve()
    if not root.is_relative_to((ROOT/'output').resolve()):
        parser.error('QA phải nằm trong output, tách production')
    root.mkdir(parents=True, exist_ok=True)
    cache = TranslationCache(root/'qa.sqlite3')
    source = root/'source'
    ocr = PaddleOCREngine()
    opts = Options(source=str(source), output=str(root/'export'), mode=MODE, agy_max_requests=1)
    if not args.authorized_live:
        if source.exists(): parser.error('Không ghi đè QA đã chuẩn bị; dùng thư mục mới')
        source.mkdir()
        texts = ['活动时间', '活动时间和活动内容', '第13话']
        font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 64)
        rows = []
        for n, text in enumerate(texts, 1):
            path = source/f'{n:04d}.png'
            image = Image.new('RGB', (1600, 400), 'white')
            ImageDraw.Draw(image).text((100, 100), text, font=font, fill='black')
            image.save(path)
            regions, warnings = ocr.recognize(np.array(image), opts.language, opts.confidence,
                opts.tile_size, opts.reading_direction, lambda: None)
            if [r.text for r in regions] != [text]:
                raise ValueError('Fixture OCR khác kế hoạch; không được gửi live')
            key = digest([file_digest(path), ocr.identity(opts.language), opts.language,
                          opts.confidence, opts.tile_size, opts.reading_direction])
            cache.put('ocr', key, dict(regions=[asdict(r) for r in regions], warnings=warnings))
            rows.extend(asdict(r) for r in regions)
        plan = dict(kind='SYNTHETIC_QA_REAL_OCR', pages=3, regions=len(rows),
            characters=sum(len(r['text']) for r in rows), regions_data=rows,
            max_cli_invocations=1, retry=0, model=opts.agy_model, uses_prepared_ocr_cache=True,
            source_hashes={str(p):file_digest(p) for p in source.glob('*.png')})
        (root/'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
        cache.close()
        print(json.dumps({k:v for k,v in plan.items() if k!='regions_data'}, ensure_ascii=False))
        return 0
    plan = json.loads((root/'plan.json').read_text(encoding='utf-8'))
    if (root/'live-attempt.json').exists():
        parser.error('Đã dùng lượt QA; không tự retry')
    assert plan['pages']==3 and plan['regions']==3 and plan['characters']==17
    assert all(file_digest(Path(p))==h for p,h in plan['source_hashes'].items())
    # A durable ledger precedes invocation so a crash cannot silently reuse consent.
    ledger = root/'live-attempt.json'
    ledger.write_text(json.dumps(dict(authorized=True, requests_max=1, source_characters=17)), encoding='utf-8')
    attempts = []
    def runner(argv, payload, cwd, timeout, cancelled):
        if payload is not None:
            if attempts: raise RuntimeError('QA request budget exhausted')
            attempts.append(dict(characters=17, regions=3, pages=3))
        return run_bounded(argv, payload, cwd, timeout, cancelled)
    control = JobControl()
    service = TranslationService(opts, cache, control)
    service.agy = AGYProvider(model=opts.agy_model, max_requests=1,
        checkpoint=control.checkpoint, cancelled=lambda:control.cancelled, runner=runner, root=root/'cli')
    manager = ProcessingManager(opts, cache, control, ocr=ocr, service=service,
        diagnostic_root=root/'diagnostics')
    summary = manager.run()
    outputs = [Path(p['output']) for p in manager.journal['pages'] if p['state']=='done']
    from sources.cache import inspect_image
    report = dict(kind='LIVE_AGY' if attempts else 'CACHE_ONLY', summary=summary,
        cli_invocations=len(attempts), protocol=service.agy.last_protocol,
        output_bitmaps=[dict(path=str(p), **inspect_image(p)) for p in outputs],
        source_unchanged=all(file_digest(Path(p))==h for p,h in plan['source_hashes'].items()),
        translations=service.agy.last_targets,
        status='PASS' if summary['completed']==3 and len(attempts)==1 and summary['failed']==0 else 'FAIL')
    (root/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    cache.close()
    print(json.dumps(dict(status=report['status'], requests=len(attempts), images=len(outputs))))
    return 0 if report['status']=='PASS' else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
