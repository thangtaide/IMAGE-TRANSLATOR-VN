"""Build gate: pytest SKIP or exit 0 alone cannot authorize an acceptance build."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.qa_common import read_latest, source_fingerprint, validate_build_evidence


def main() -> int:
    gui, gui_error = read_latest(ROOT/'logs/latest-gui-smoke.json')
    e2e, e2e_error = read_latest(ROOT/'output/e2e-validation/latest.json')
    problems = validate_build_evidence(gui, e2e, source_fingerprint(), sys.executable)
    problems += [x for x in [gui_error, e2e_error] if x]
    report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'status': 'PASS' if not problems else 'SKIPPED',
              'reason': 'GUI/E2E prerequisites not satisfied; PyInstaller was not invoked' if problems else 'Ready for build; executable smoke test still required',
              'problems': problems, 'exe_exists': (ROOT/'dist/ImageTranslatorVN/ImageTranslatorVN.exe').is_file()}
    path = ROOT/'logs'/('build-readiness-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Build prerequisite check:', report['status'])
    for problem in problems:
        print('-', problem)
    return 0 if not problems else 2


if __name__ == '__main__':
    raise SystemExit(main())
