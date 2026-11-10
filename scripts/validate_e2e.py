"""No-mock offline OCR -> MT -> inpaint -> render evidence runner.

If no source is supplied, generate a clearly labelled Chinese synthetic fixture.
Expected fixture text is never used as OCR output or as translation input.
"""
from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import os
import sys
import time
import traceback
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import ROOT
if sys.stdout is not None:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def memory() -> dict:
    if sys.platform != 'win32':
        return {'status': 'NOT MEASURED', 'reason': 'Windows working-set counters unavailable'}
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
                    ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return {'status': 'PASS', 'working_set_bytes': counters.WorkingSetSize, 'peak_working_set_bytes': counters.PeakWorkingSetSize}
    return {'status': 'FAIL', 'winerror': ctypes.get_last_error()}


def execute(source: Path | None, language: str, engine_name: str, root: Path = ROOT) -> tuple[dict, Path]:
    from scripts.qa_common import source_fingerprint

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
    destination = root/'output/e2e-validation'/stamp
    destination.mkdir(parents=True, exist_ok=False)
    stages = {name: {'status': 'SKIPPED', 'reason': 'Earlier prerequisite has not succeeded'}
              for name in ['source', 'ocr', 'translation', 'mask', 'inpaint', 'render', 'export', 'source_integrity', 'ocr_reuse']}
    report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'mock': False, 'language': language,
              'source_fingerprint': source_fingerprint(),
              'python': sys.executable, 'engine': engine_name, 'source_kind': 'user image' if source else 'synthetic Chinese fixture',
              'destination': str(destination), 'stages': stages, 'overall': 'FAIL', 'memory_before': memory(),
              'quality_observation': 'NOT TESTED; inference must complete before assessing translation quality',
              'limitations': ['Synthetic input is not evidence of accuracy on real manga/photos.',
                              'A nonempty translation alone does not establish semantic accuracy.'],
              'artifacts': {}, 'model_details': []}
    current_stage = 'source'
    started = time.monotonic()
    original_hash = None
    source_hash = None
    try:
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
        from core.imaging import TextRenderer, atomic_save, build_mask, erase_text, open_image
        from core.ocr import PaddleOCREngine
        from core.storage import file_digest
        from core.types import Options
        from providers.offline import create_offline_provider
        stage_start = time.monotonic()
        if source:
            source = source.resolve()
            original_hash = file_digest(source)
            image = open_image(source)
            image.save(destination/'source.png')
        else:
            if language != 'zh':
                raise ValueError('Default synthetic fixture is Chinese; provide --source for other languages')
            candidates = [Path('C:/Windows/Fonts/msyh.ttc'), Path('C:/Windows/Fonts/simhei.ttf'), Path('C:/Windows/Fonts/simsun.ttc')]
            fixture_font = next((p for p in candidates if p.is_file()), None)
            if fixture_font is None:
                raise FileNotFoundError('No installed Chinese font for a valid synthetic fixture; provide --source')
            image = Image.new('RGB', (1200, 430), 'white')
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((50, 45, 1150, 385), radius=35, outline='#394b60', width=3)
            font = ImageFont.truetype(str(fixture_font), 64)
            draw.text((130, 120), '你好，世界！', font=font, fill='black')
            draw.text((130, 220), '欢迎使用图像翻译。', font=font, fill='black')
            image.save(destination/'source.png')
            report['fixture'] = {'font': str(fixture_font), 'description': 'Two Chinese sentences drawn by Pillow; OCR and translation are never supplied manually'}
        source_hash = file_digest(destination/'source.png')
        report['artifacts']['source'] = 'source.png'
        report['dimensions'] = list(image.size)
        stages['source'] = {'status': 'PASS', 'seconds': time.monotonic()-stage_start, 'sha256': source_hash}

        current_stage = 'ocr'
        stage_start = time.monotonic()
        missing = [m for m in ['paddle', 'paddleocr'] if importlib.util.find_spec(m) is None]
        if missing:
            raise ModuleNotFoundError('Missing OCR dependencies: '+', '.join(missing))
        ocr = PaddleOCREngine()
        ocr.identity(language)
        rgb = np.array(image.convert('RGB'))
        regions, warnings = ocr.recognize(rgb, language)
        if not regions:
            raise RuntimeError('Real OCR returned no regions; cannot pass E2E')
        if any(not (0 <= r.confidence <= 1) or any(not (0 <= p[0] < image.width and 0 <= p[1] < image.height) for p in r.polygon) for r in regions):
            raise RuntimeError('OCR confidence/coordinates out of bounds')
        (destination/'ocr.json').write_text(json.dumps({'status': 'PASS', 'mock': False, 'regions': [asdict(r) for r in regions], 'warnings': warnings}, ensure_ascii=False, indent=2), encoding='utf-8')
        report['artifacts']['ocr'] = 'ocr.json'
        stages['ocr'] = {'status': 'PASS', 'seconds': time.monotonic()-stage_start, 'count': len(regions)}

        current_stage = 'translation'
        stage_start = time.monotonic()
        provider = create_offline_provider(engine_name)
        route = provider.route(language)
        for pair in route:
            folder, meta = provider.packages[pair]
            report['model_details'].append({'pair': list(pair), 'directory': str(folder), 'metadata': meta,
                                           'installed_bytes': sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()),
                                           'license': meta.get('license', 'MIT/CC0 per official Argos model release notice')})
        translated = provider.translate_batch([r.text for r in regions], language)
        if len(translated) != len(regions) or any(not t.strip() for t in translated):
            raise RuntimeError('MT output missing/empty')
        records = [{'ocr_text': r.text, 'vietnamese': text, 'polygon': r.polygon} for r, text in zip(regions, translated)]
        (destination/'translation.json').write_text(json.dumps({'status': 'PASS', 'mock': False, 'engine': engine_name, 'route': route, 'records': records}, ensure_ascii=False, indent=2), encoding='utf-8')
        report['artifacts']['translation'] = 'translation.json'
        stages['translation'] = {'status': 'PASS', 'seconds': time.monotonic()-stage_start, 'memory': memory(),
                                 'result': translated, 'quality': 'Requires human semantic review; real inference completed'}
        report['quality_observation'] = 'Real inference completed; semantic quality NOT YET reviewed'
        options = Options(language=language, mode='Offline')
        for current_stage, action in [
            ('mask', lambda: Image.fromarray(build_mask(rgb, regions, options.mask_expand)).save(destination/'mask.png')),
        ]:
            stage_start = time.monotonic()
            action()
            stages[current_stage] = {'status': 'PASS', 'seconds': time.monotonic()-stage_start}
        report['artifacts']['mask'] = 'mask.png'
        current_stage = 'inpaint'
        stage_start = time.monotonic()
        erased = erase_text(image, regions, options)
        erased.save(destination/'erased.png')
        stages['inpaint'] = {'status': 'PASS', 'seconds': time.monotonic()-stage_start}
        report['artifacts']['erased'] = 'erased.png'
        current_stage = 'render'
        stage_start = time.monotonic()
        rendered = TextRenderer(options).render(erased, regions, translated)
        stages['render'] = {'status': 'PASS', 'seconds': time.monotonic()-stage_start}
        current_stage = 'export'
        atomic_save(rendered, destination/'final.png')
        if open_image(destination/'final.png').size != image.size:
            raise RuntimeError('Resolution changed')
        stages['export'] = {'status': 'PASS', 'sha256': file_digest(destination/'final.png')}
        report['artifacts']['final'] = 'final.png'
        current_stage = 'ocr_reuse'
        existing_engine = ocr.engine
        stage_start = time.monotonic()
        second, _ = ocr.recognize(rgb, language)
        if ocr.engine is not existing_engine or not second:
            raise RuntimeError('OCR engine was not reused / repeat returned empty')
        stages['ocr_reuse'] = {'status': 'PASS', 'seconds': time.monotonic()-stage_start}
    except Exception as exc:
        stages[current_stage] = {'status': 'FAIL', 'error_type': type(exc).__name__, 'reason': str(exc)}
        (destination/'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
    finally:
        unchanged = source_hash is not None and file_digest(destination/'source.png') == source_hash
        if source is not None and original_hash is not None:
            unchanged = unchanged and file_digest(source) == original_hash
        stages['source_integrity'] = {'status': 'PASS' if unchanged else 'FAIL' if source_hash is not None else 'NOT TESTED', 'unchanged': unchanged}
        for name in ['ocr', 'translation']:
            path = destination/(name+'.json')
            if not path.exists():
                path.write_text(json.dumps({'mock': False, **stages[name], 'records': []}, ensure_ascii=False, indent=2), encoding='utf-8')
        report['seconds_total'] = time.monotonic()-started
        report['memory_after'] = memory()
        report['overall'] = 'PASS' if all(v['status']=='PASS' for v in stages.values()) else 'FAIL'
        (destination/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        lines = ['# E2E validation', '', 'Overall: **'+report['overall']+'**', '', 'Mock: false. Input: '+report['source_kind'], '', '| Stage | Status | Detail |', '| --- | --- | --- |']
        for name, value in stages.items():
            lines.append('| '+name+' | '+value['status']+' | '+value.get('reason', '')+' |')
        lines += ['', 'No OCR output or translation was entered manually. Missing artifacts were not fabricated.']
        (destination/'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
        (root/'output/e2e-validation/latest.json').write_text(json.dumps({'path': str(destination/'report.json'), 'overall': report['overall']}), encoding='utf-8')
    return report, destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path)
    parser.add_argument('--language', choices=['zh', 'zt', 'ko', 'en'], default='zh')
    parser.add_argument('--engine', choices=['Argos', 'CTranslate2', 'M2M100'], default='Argos')
    args = parser.parse_args()
    try:
        report, folder = execute(args.source, args.language, args.engine)
    except ImportError as exc:
        print('E2E cannot start; missing CV dependencies:', str(exc))
        return 2
    print('E2E:', report['overall'], 'Evidence:', folder)
    return 0 if report['overall']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
