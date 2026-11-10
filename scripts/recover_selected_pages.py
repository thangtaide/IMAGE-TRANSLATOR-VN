"""Offline recovery from an authorized DPAPI capture and a read-only cache snapshot.

This forensic helper never opens the production database or writes translations.
Use only after obtaining permission for the specified capture. Plaintext stays in
process memory; the requested rendered images are the only textual output.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=True, indent=2)


def decrypt_verified(folder):
    """Current Windows user only, matching the project's no-entropy DPAPI policy."""
    metadata = load(folder / 'metadata.json')
    artifact = next(a for a in metadata['artifacts'] if a['stream'] == 'stdout')
    if artifact['file'] != 'stdout.raw.dpapi' or artifact['partial']:
        raise ValueError('Complete authorized stdout capture required')
    ciphertext = (folder / artifact['file']).read_bytes()
    if hashlib.sha256(ciphertext).hexdigest() != artifact['encrypted_sha256']:
        raise ValueError('Encrypted capture checksum mismatch')

    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]

    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(Blob), wintypes.LPVOID,
        ctypes.POINTER(Blob), wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(Blob)]
    crypt.CryptUnprotectData.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [wintypes.LPVOID]
    kernel.LocalFree.restype = wintypes.LPVOID
    buffer = ctypes.create_string_buffer(ciphertext)
    source = Blob(len(ciphertext), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    if not crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise OSError('DPAPI decryption unavailable for current Windows user')
    try:
        raw = ctypes.string_at(target.data, target.size)
    finally:
        ctypes.memset(target.data, 0, target.size)
        kernel.LocalFree(ctypes.cast(target.data, wintypes.LPVOID))
    if len(raw) != artifact['captured_bytes'] or hashlib.sha256(raw).hexdigest() != artifact['captured_sha256']:
        raise ValueError('Decrypted capture checksum mismatch')
    return raw, metadata


def recover(run, attempt):
    from PIL import Image, ImageDraw
    import numpy as np
    from core.imaging import TextRenderer, TextLayoutError, build_mask, erase_text, open_image, atomic_save
    from core.ocr import PaddleOCREngine
    from core.pipeline import TranslationService, JobControl, NUMBER_PATTERN, numeric_tokens
    from core.storage import digest, file_digest
    from core.types import Options, OCRResult
    from providers.agy import AGYProvider, parse_response

    if not re.fullmatch(r'[0-9a-f]{32}', attempt):
        raise ValueError('Invalid attempt ID')
    folder = ROOT / 'logs/diagnostics/agy_errors' / attempt
    job = load(folder / 'metadata.json')['job_id']
    locations = load(run / 'job-locations.json')
    pages = load(run / 'cached-pages.json')
    if len(locations) != 1 or set(pages) != {'0014', '0029', '0085'}:
        raise ValueError('This recovery requires the reviewed three-page snapshot')
    opts = Options.from_dict(locations[0]['options'])
    records = [json.loads(line) for line in
        (ROOT / 'logs/diagnostics' / job / 'errors.jsonl').read_text(encoding='utf-8').splitlines() if line]
    if len(records) != 3 or {r['image_filename'] for r in records} != {p + '.jpg' for p in pages}:
        raise ValueError('Unexpected job scope')
    if {r['agy_attempt_id'] for r in records if r['agy_attempt_id']} != {attempt}:
        raise ValueError('Attempt does not match the reviewed job')
    if folder.resolve().parent != (ROOT / 'logs/diagnostics/agy_errors').resolve():
        raise ValueError('Invalid attempt directory')
    destination = run / 'recovered'
    destination.mkdir(exist_ok=False)
    requests = []

    def forbidden(*args, **kwargs):
        requests.append('blocked')
        raise AssertionError('Recovery must not invoke OCR, AGY or network transport')

    class MemoryCache:
        def __init__(self): self.values = {}
        def get(self, kind, key): return self.values.get((kind, key))
        def put(self, kind, key, value): self.values[kind, key] = value

    provider = types.SimpleNamespace(online=True, engine_name='AGY saved response',
        identity=next(r['model_identity'] for r in records if r['model_identity']),
        retry_count=0, translate=forbidden)
    service = TranslationService(opts, MemoryCache(), JobControl())
    # Load the reviewed baseline for before/after behavior, never mutate Git.
    baseline_head = load(run / 'baseline.json')['head']
    if not re.fullmatch(r'[0-9a-f]{40}', baseline_head):
        raise ValueError('Invalid reviewed baseline')
    old_source = subprocess.run(['git', 'show', baseline_head + ':core/imaging.py'], cwd=ROOT,
        capture_output=True, check=True).stdout.decode('utf-8')
    baseline = types.ModuleType('reviewed_baseline_imaging')
    exec(compile(old_source, '<reviewed HEAD imaging>', 'exec'), baseline.__dict__)
    expected = []
    for case, page in pages.items():
        for i, region in enumerate(page['active_regions']):
            expected.append(f'j{job[:12]}_c{digest(None)[:8]}_p{int(case):06d}'
                f'_h{page["source_sha256"][:12]}_r{i:04d}_o{region["reading_order"]:04d}')

    with ExitStack() as stack:
        for obj, method in [(AGYProvider, '_invoke'), (PaddleOCREngine, 'recognize'),
                            (socket.socket, 'connect'), (socket.socket, 'connect_ex')]:
            stack.enter_context(patch.object(obj, method, forbidden))
        raw, metadata = decrypt_verified(folder)
        if metadata['job_id'] != job:
            raise ValueError('Capture job mismatch')
        protocol = {}
        targets = parse_response(raw, expected, 0, diagnostic=protocol)
        if len(targets) != len(expected):
            raise ValueError('Incomplete saved response')
        summary = dict(job=job, attempt=attempt, parser=protocol['guard_decision'],
            source='authorized DPAPI capture + saved OCR; no new inference', pages={},
            agy_calls=0, ocr_calls=0, transport_attempts=requests)
        offset = 0
        for case, page in pages.items():
            regions = [OCRResult(**r) for r in page['active_regions']]
            values = targets[offset:offset + len(regions)]
            offset += len(regions)
            if file_digest(Path(page['source'])) != page['source_sha256']:
                raise ValueError('Source image checksum changed')
            cached = 0
            for i, (region, target) in enumerate(zip(regions, values)):
                candidates = page['target_candidates'][i]
                if candidates:
                    if not any(c['text'] == target for c in candidates):
                        raise ValueError('Saved response and cached target differ')
                    cached += 1
                checked = service._translate_using(provider, region.text, region.language,
                    'offline-selected-' + case, raw_target=target)
                if checked != target:
                    raise ValueError('Validation changed translation content')
            image = open_image(Path(page['source']))
            case_dir = destination / case
            case_dir.mkdir()
            image.save(case_dir / 'original.png')
            before = next(Path(item[2]) for item in locations[0]['items'] if Path(item[0]).stem == case)
            if before.is_file():
                open_image(before).save(case_dir / 'before.png')
            mask = build_mask(np.array(image.convert('RGB')), regions, opts.mask_expand)
            Image.fromarray(mask).save(case_dir / 'mask.png')
            cleaned = erase_text(image, regions, opts)
            cleaned.save(case_dir / 'inpainted.png')
            renderer = TextRenderer(opts)
            final = renderer.render(cleaned, regions, values)
            atomic_save(final, case_dir / 'final.jpg', opts.quality, overwrite=False)
            final.save(case_dir / 'final.png')
            overlay = image.copy()
            draw = ImageDraw.Draw(overlay)
            for i, r in enumerate(regions):
                draw.rectangle(r.box, outline='red', width=2)
                draw.text((r.box[0], r.box[1]), str(i), fill='cyan')
            overlay.save(case_dir / 'ocr.png')
            layout = final.copy()
            draw = ImageDraw.Draw(layout)
            for p in renderer.last_layout:
                draw.rectangle(p['box'], outline='cyan', width=1)
                draw.rectangle(p['paint_box'], outline='red', width=1)
            layout.save(case_dir / 'layout.png')
            comparison = Image.new('RGB', (image.width * 2, image.height + 24), 'white')
            comparison.paste(image.convert('RGB'), (0, 24))
            comparison.paste(open_image(case_dir / 'final.jpg'), (image.width, 24))
            draw = ImageDraw.Draw(comparison)
            draw.text((8, 4), 'BEFORE (fallback original)', fill='black')
            draw.text((image.width + 8, 4), 'AFTER (saved AGY response, current code)', fill='black')
            comparison.save(case_dir / 'comparison.jpg', quality=95)
            audit = []
            for n, p in enumerate(renderer.last_layout):
                assert ''.join(p['text'].split()) == ''.join(p['wrapped'].split())
                x0, y0, x1, y1 = p['paint_box']
                assert 0 <= x0 <= x1 <= image.width and 0 <= y0 <= y1 <= image.height
                assert not any(renderer._intersects(p['paint_box'], q['paint_box']) for q in renderer.last_layout[n+1:])
                safe = {k: v for k, v in p.items() if k not in ('text', 'wrapped')}
                safe.update(lines=len(p['wrapped'].splitlines()), content_preserved=True,
                    target_sha256=hashlib.sha256(p['text'].encode()).hexdigest())
                audit.append(safe)
            assert sorted(i for p in renderer.last_layout for i in p['region_indices'] + p['duplicate_indices']) == list(range(len(regions)))
            old_numeric_failures = [i for i,(r,t) in enumerate(zip(regions,values))
                if re.findall(NUMBER_PATTERN, r.text) != re.findall(NUMBER_PATTERN, t)]
            try:
                old_plans = baseline.TextRenderer(opts).plan_layout(image.size, regions, values)
                old_layout = 'PASS'
                unchanged = old_plans == renderer.last_layout
            except baseline.TextLayoutError:
                old_layout = 'LAYOUT_UNFIT'
                unchanged = False
            summary['pages'][case] = dict(regions=len(regions), cached_targets_verified=cached,
                baseline_numeric_failures=old_numeric_failures, baseline_layout=old_layout,
                accepted_layout_unchanged=unchanged, layout=audit,
                validated_numbers=[dict(index=i, source=numeric_tokens(r.text), target=numeric_tokens(t))
                    for i,(r,t) in enumerate(zip(regions,values)) if numeric_tokens(r.text)],
                result='RENDERED_PENDING_VISUAL_REVIEW')
        assert not requests
        write(destination / 'summary.json', summary)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--allow-local-dpapi', action='store_true', required=True,
        help='Use only after explicit permission for this exact capture')
    args = parser.parse_args()
    run = (ROOT / args.run).resolve()
    if not run.is_relative_to((ROOT / 'output').resolve()):
        parser.error('Analysis directory must be within project output')
    destination = recover(run, args.attempt)
    print(json.dumps({'destination': destination.relative_to(ROOT).as_posix(), 'agy_calls': 0}))


if __name__ == '__main__':
    main()
