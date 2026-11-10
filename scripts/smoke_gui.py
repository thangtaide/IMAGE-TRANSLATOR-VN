"""Launch the real main.py for a Qt offscreen smoke check, without mock widgets."""
from __future__ import annotations

import json
import argparse
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.qa_common import source_fingerprint


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--platform',choices=['offscreen','windows'],default='offscreen')
    parser.add_argument('--exe',type=Path,help='Validate the built executable instead of the Python entry point')
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
    folder = ROOT/'logs'/('gui-smoke-'+stamp)
    folder.mkdir(parents=True, exist_ok=False)
    path = folder/'report.json'
    report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'python': sys.executable,
              'source_fingerprint': source_fingerprint(), 'mock': False, 'display_mode': 'Qt offscreen',
              'overall': 'SKIPPED', 'desktop_display_verified': False}
    probe = subprocess.run([sys.executable, '-c', 'from PySide6.QtWidgets import QApplication;print("QT_IMPORT_OK")'], capture_output=True, text=True, errors='replace')
    if probe.returncode:
        report.update(reason='PySide6 import failed; main.py GUI not launched to avoid a blocking missing-library dialog', import_error=probe.stderr)
    else:
        import os
        env = dict(os.environ, QT_QPA_PLATFORM=args.platform)
        try:
            entry = [str(args.exe.resolve())] if args.exe else [sys.executable,str(ROOT/'main.py')]
            result = subprocess.run(entry+['--smoke-test', '--smoke-report', str(path)],
                                    cwd=ROOT, env=env, capture_output=True, timeout=30)
            (folder/'stdout.log').write_bytes(result.stdout)
            (folder/'stderr.log').write_bytes(result.stderr)
            if path.is_file():
                report = json.loads(path.read_text(encoding='utf-8'))
                report['process_exit_code'] = result.returncode
                if result.returncode:
                    report['overall'] = 'FAIL'
            else:
                report.update(overall='FAIL', reason='main.py exited without GUI evidence', process_exit_code=result.returncode)
        except subprocess.TimeoutExpired:
            report.update(overall='FAIL', reason='GUI smoke process exceeded 30-second limit')
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    pointer = ROOT/'logs'/('latest-exe-smoke.json' if args.exe else 'latest-gui-smoke.json')
    pointer.write_text(json.dumps({'path': str(path)}), encoding='utf-8')
    print('GUI smoke:', report['overall'], 'Evidence:', path)
    return 0 if report['overall']=='PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
