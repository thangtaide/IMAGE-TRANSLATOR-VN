"""Audit the existing project environment without installing or changing it."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
MODULES = {
    'PySide6': 'PySide6.QtWidgets', 'numpy': 'numpy', 'Pillow': 'PIL.Image',
    'opencv-contrib-python': 'cv2', 'scipy': 'scipy', 'scikit-image': 'skimage',
    'protobuf': 'google.protobuf', 'paddlepaddle': 'paddle', 'paddleocr': 'paddleocr',
    'argostranslate': 'argostranslate.tokenizer', 'ctranslate2': 'ctranslate2',
    'sentencepiece': 'sentencepiece', 'requests': 'requests', 'pytest': 'pytest',
    'pytest-qt': 'pytestqt', 'pyinstaller': 'PyInstaller',
}


def run(args: list[str], timeout: int = 40) -> dict:
    try:
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
        return {'exit_code': result.returncode, 'stdout': result.stdout[-6000:], 'stderr': result.stderr[-6000:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'exit_code': None, 'error': type(exc).__name__}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--python', default=str(ROOT/'.venv/Scripts/python.exe'))
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination = ROOT/'logs'/('install-audit-'+stamp)
    destination.mkdir(parents=True, exist_ok=False)
    pins = {}
    for line in (ROOT/'requirements.txt').read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([^\s]+)', line)
            if not match:
                raise ValueError('Unsupported requirement syntax: '+line)
            pins[match[1]] = match[2]
    inventory_code = "import importlib.metadata,json,sys; print(json.dumps({'python':sys.version,'executable':sys.executable,'packages':{d.metadata['Name'].lower():d.version for d in importlib.metadata.distributions()}}))"
    inventory = run([args.python, '-c', inventory_code])
    installed = {}
    if inventory.get('exit_code') == 0:
        installed = json.loads(inventory['stdout'])['packages']
    versions = {package: {'required': pin, 'installed': installed.get(package.lower()),
                          'status': 'PASS' if installed.get(package.lower()) == pin else 'MISSING' if package.lower() not in installed else 'VERSION_MISMATCH'}
                for package, pin in pins.items()}
    imports = {}
    for package, module in MODULES.items():
        code = "import sys;sys.stdout.reconfigure(encoding='utf-8');from core.paths import initialize;initialize();import importlib;importlib.import_module("+repr(module)+");print('IMPORT_OK')"
        result = run([args.python, '-c', code])
        imports[package] = {'module': module, 'status': 'PASS' if result.get('exit_code') == 0 else 'FAIL', **result}
    checks = run([args.python, '-m', 'pip', 'check'])
    ready = all(v['status'] == 'PASS' for v in imports.values()) and all(v['status'] == 'PASS' for v in versions.values()) and checks.get('exit_code') == 0
    report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'read_only': True, 'interpreter': args.python,
              'inventory': inventory, 'versions': versions, 'imports': imports, 'pip_check': checks,
              'resolver_check': 'NOT TESTED: no installation/dry-run performed by this read-only audit',
              'opencv_note': 'Requirements contain three distributions sharing cv2; equal pins do not establish binary compatibility. Full resolver/import tests remain required.',
              'ready': ready, 'status': 'PASS' if ready else 'FAIL'}
    (destination/'installation.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    (ROOT/'logs/latest-install-audit.json').write_text(json.dumps({'path': str(destination/'installation.json')}), encoding='utf-8')
    print('Imports PASS:', sum(v['status']=='PASS' for v in imports.values()), '/', len(imports))
    print('Required packages satisfied:', sum(v['status']=='PASS' for v in versions.values()), '/', len(versions))
    print('Ready:', ready, 'Evidence:', destination)
    return 0 if ready else 1


if __name__ == '__main__':
    raise SystemExit(main())
