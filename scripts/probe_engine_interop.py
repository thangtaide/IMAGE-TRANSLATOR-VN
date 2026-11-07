"""Read-only engine/DLL order probes; no downloads, package changes or mocks."""
from __future__ import annotations

import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT/'.venv/Scripts/python.exe'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
    folder = ROOT/'logs'/('engine-interop-'+stamp)
    folder.mkdir(parents=True, exist_ok=False)
    common = """
import json, sys, time
sys.stdout.reconfigure(encoding='utf-8')
from core.paths import initialize
initialize()
from core.models import verify_installation
from providers.offline import ArgosTranslationProvider
"""
    ocr_code = """
import numpy as np
from core.imaging import open_image
from core.ocr import PaddleOCREngine
from pathlib import Path
pointer = json.loads(Path('output/e2e-validation/latest.json').read_text())
image = open_image(Path(pointer['path']).parent/'source.png')
ocr = PaddleOCREngine()
regions, warnings = ocr.recognize(np.array(image.convert('RGB')), 'zh')
assert regions, 'OCR returned no text'
print(json.dumps({'ocr': [r.text for r in regions], 'confidences':[r.confidence for r in regions]}, ensure_ascii=False))
"""
    translate_code = """
provider = ArgosTranslationProvider()
started = time.perf_counter()
source = [r.text for r in regions] if 'regions' in globals() else ['Hello world']
language = 'zh' if 'regions' in globals() else 'en'
result = provider.translate_batch(source, language)
print(json.dumps({'source': source, 'route':provider.route(language), 'translations':result, 'seconds':time.perf_counter()-started}, ensure_ascii=False))
"""
    cases = {
        'ctranslate2_only_translation': common+translate_code,
        'ocr_then_ctranslate2': common+ocr_code+translate_code,
        'ctranslate2_then_ocr': common+'\nimport ctranslate2\n'+ocr_code+translate_code,
    }
    report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'python': str(PYTHON),
              'read_only': True, 'mock': False, 'cases': {}}
    for name, code in cases.items():
        started = __import__('time').monotonic()
        try:
            process = subprocess.run([str(PYTHON), '-c', code], cwd=ROOT, capture_output=True,
                                     text=True, encoding='utf-8', errors='replace', timeout=90)
            result = {'exit_code': process.returncode, 'status': 'PASS' if process.returncode==0 else 'FAIL',
                      'stdout':process.stdout, 'stderr':process.stderr, 'seconds':__import__('time').monotonic()-started}
        except subprocess.TimeoutExpired:
            result = {'status':'FAIL', 'reason':'Timed out after 90 seconds'}
        report['cases'][name] = result
        (folder/(name+'.log')).write_text(result.get('stdout','')+result.get('stderr',result.get('reason','')), encoding='utf-8')
        print(name, result['status'])
    (folder/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Evidence:',folder)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
