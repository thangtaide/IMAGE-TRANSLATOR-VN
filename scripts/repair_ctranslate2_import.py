"""Diagnose and repair only setuptools compatibility for CTranslate2 4.6.0.

Default is read-only. --apply installs a validated, cached setuptools wheel
without network or dependency resolution. All other installed versions must stay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT/'.venv/Scripts/python.exe'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def run(args: list[str]) -> dict:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=90)
    return {'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}


def inventory() -> dict:
    result = run([str(PYTHON), '-c', "import importlib.metadata,json; print(json.dumps({d.metadata['Name'].lower():d.version for d in importlib.metadata.distributions()}))"])
    if result['exit_code']:
        raise RuntimeError(result['stderr'])
    return json.loads(result['stdout'])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-sha256')
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
    folder = ROOT/'logs'/('ctranslate2-repair-'+stamp)
    folder.mkdir(parents=True, exist_ok=False)
    before = inventory()
    report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'interpreter': str(PYTHON), 'before': before,
              'import_before': run([str(PYTHON), '-c', 'import ctranslate2; print(ctranslate2.__version__)']),
              'pkg_resources_before': run([str(PYTHON), '-c', 'import pkg_resources; print(pkg_resources.__file__)']),
              'applied': False}
    (folder/'traceback-before.txt').write_text(report['import_before']['stderr'], encoding='utf-8')
    cached = json.loads((ROOT/'logs/cached_wheels.json').read_text(encoding='utf-8'))
    candidates = [Path(x['path']) for x in cached if x['package']=='setuptools-80.9.0.dist-info' and Path(x['path']).is_file()]
    if not candidates:
        raise FileNotFoundError('No cached setuptools 80.9.0 wheel; do not change the environment')
    wheel = candidates[0]
    checksum = hashlib.sha256(wheel.read_bytes()).hexdigest()
    with zipfile.ZipFile(wheel) as archive:
        if archive.testzip() is not None or 'pkg_resources/__init__.py' not in archive.namelist():
            raise ValueError('Cached setuptools wheel is invalid or lacks pkg_resources')
        metadata = archive.read('setuptools-80.9.0.dist-info/METADATA').decode('utf-8')
        if '\nVersion: 80.9.0\n' not in metadata:
            raise ValueError('Unexpected setuptools version in cached wheel')
    report['cached_wheel'] = {'path': str(wheel), 'sha256': checksum, 'bytes': wheel.stat().st_size,
                              'pkg_resources_present': True}
    if args.apply:
        if not args.expected_sha256 or checksum != args.expected_sha256:
            raise ValueError('Official expected SHA-256 is required and must match before installing')
        if before.get('ctranslate2') != '4.6.0':
            raise ValueError('This scoped repair is for CTranslate2 4.6.0 only')
        local = ROOT/'cache/compat-wheels/setuptools-80.9.0-py3-none-any.whl'
        local.parent.mkdir(parents=True, exist_ok=True)
        if local.exists():
            if hashlib.sha256(local.read_bytes()).hexdigest() != checksum:
                raise FileExistsError('Existing cached wheel differs; refusing overwrite')
        else:
            shutil.copyfile(wheel, local)
        result = run([str(PYTHON), '-m', 'pip', 'install', '--no-index', '--no-deps', str(local), '--disable-pip-version-check'])
        report['install'] = result
        report['applied'] = result['exit_code']==0
        (folder/'install.log').write_text(result['stdout']+result['stderr'], encoding='utf-8')
    after = inventory()
    report['after'] = after
    changes = {name: [before.get(name), after.get(name)] for name in before.keys() | after.keys() if before.get(name)!=after.get(name)}
    report['version_changes'] = changes
    report['only_setuptools_changed'] = all(name=='setuptools' for name in changes)
    report['import_after'] = run([str(PYTHON), '-c', 'import ctranslate2; print(ctranslate2.__version__)'])
    report['pip_check'] = run([str(PYTHON), '-m', 'pip', 'check'])
    (folder/'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('CTranslate2 before:', report['import_before']['exit_code'], 'setuptools:', before.get('setuptools'))
    print('Wheel:', report['cached_wheel'])
    print('Version changes:', changes)
    print('CTranslate2 after:', report['import_after']['exit_code'], 'Evidence:', folder)
    return 0 if not args.apply or (report['only_setuptools_changed'] and report['import_after']['exit_code']==0 and report['pip_check']['exit_code']==0) else 1


if __name__ == '__main__':
    raise SystemExit(main())
