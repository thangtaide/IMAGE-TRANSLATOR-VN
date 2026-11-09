"""Stage3F synthetic QA only. Network is blocked, even for the real Argos case.

python -m qa.validate_whole_chapter --case mock120
python -m qa.validate_whole_chapter --case offline
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def peak_working_set():
    if os.name != 'nt': return None
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
            (n, ctypes.c_size_t) for n in ('peak_working_set', 'working_set', 'peak_paged',
                'paged', 'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile')]
    counters = Counters(); counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
    if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return counters.peak_working_set
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=['mock120', 'offline'], required=True)
    args = parser.parse_args()
    attempts = []
    def offline(event, values):
        if event in ('socket.connect', 'socket.getaddrinfo'):
            attempts.append(event)
            raise AssertionError('Stage3F QA forbids network')
    sys.addaudithook(offline)
    from core.runtime import prepare_inference_runtime
    prepare_inference_runtime()
    from core.paths import ROOT
    from core.storage import file_digest
    from core.types import Options, OCRResult
    from core.whole_chapter import WholeChapterJob, MockWholeChapterTranslator, read_json
    from PIL import Image, ImageDraw, ImageFont
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root = ROOT / 'output' / ('stage3f-qa-' + args.case + '-' + stamp + '-' + uuid4().hex[:6])
    source = root / 'source'; source.mkdir(parents=True)
    events, ocr_calls, mt_calls = [], [], []
    if args.case == 'mock120':
        for n in range(1, 121): Image.new('RGB', (800, 400), (n, n, n)).save(source / f'{n:04d}.png')
        class OCR:
            def identity(self, language): return 'whole-chapter-synthetic-ocr-v1'
            def recognize(self, image, *args):
                n = int(image[0, 0, 0]); ocr_calls.append(n)
                return [OCRResult(f'你好 {n}', [[20, 20+i*100], [740, 20+i*100],
                    [740, 80+i*100], [20, 80+i*100]], .99, 'zh', i, i) for i in range(2)], []
        def respond(packet):
            mt_calls.append(len(packet['regions']))
            return json.dumps(dict(manifest_hash=packet['manifest_hash'], translations=[
                dict(id=r['id'], text=r['text'].replace('你好', 'Xin chào')) for r in reversed(packet['regions'])]))
        translator, ocr = MockWholeChapterTranslator(respond), OCR()
    else:
        for n in range(1, 4):
            image = Image.new('RGB', (1200, 430), 'white')
            draw = ImageDraw.Draw(image); font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 64)
            draw.text((130, 120), '你好，世界！', font=font, fill='black')
            draw.text((130, 220), '欢迎使用图像翻译。', font=font, fill='black')
            image.save(source / f'{n:04d}.png')
        translator = ocr = None  # Real installed PaddleOCR + Argos, no model downloads.
    originals = {p.name: file_digest(p) for p in source.glob('*.png')}
    tracemalloc.start(); started = time.monotonic()
    result = WholeChapterJob(source, root/'run', options=Options(), translator=translator,
                              ocr=ocr, emit=events.append).run(allow_translation=True)
    elapsed = time.monotonic() - started
    _, python_peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    manifest_path = root/'run/chapter-ocr-manifest.json'
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    output = list((root/'run/rendered').glob('*.png'))
    valid_bitmaps = 0
    for path in output:
        with Image.open(path) as image: image.verify()
        valid_bitmaps += 1
    report = dict(case=args.case, ocr_mock=args.case == 'mock120', translator_mock=args.case == 'mock120',
        result=result, pages=len(originals), regions=manifest.get('region_count'),
        source_characters=manifest.get('source_characters'), mock_invocations=len(mt_calls),
        mock_regions_per_invocation=mt_calls, elapsed_seconds=elapsed, python_allocation_peak_bytes=python_peak,
        process_peak_working_set_bytes=peak_working_set(), valid_output_bitmaps=valid_bitmaps,
        source_hashes_unchanged=originals == {p.name:file_digest(p) for p in source.glob('*.png')},
        blocked_network_attempts=len(attempts), production_read=False, production_write=False)
    (root/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(report=str(root/'report.json'), state=result['state'],
                         pages=len(originals), regions=manifest.get('region_count'),
                         output=valid_bitmaps, elapsed=elapsed), ensure_ascii=True))
    return 0 if result['state'] == 'done' and valid_bitmaps == len(originals) and not attempts else 1


if __name__ == '__main__':
    raise SystemExit(main())
