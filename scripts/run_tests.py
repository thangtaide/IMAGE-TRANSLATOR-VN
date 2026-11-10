"""Structured evidence runner using stdlib when pytest cannot be installed.

These same unittest tests are discoverable by pytest without modifications.
This runner never labels unittest execution as pytest execution.
"""
from __future__ import annotations

import io
import argparse
import json
import logging
import platform
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.storage import configure_logging


class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.append(test.id())


configure_logging()
parser = argparse.ArgumentParser()
parser.add_argument('--evidence-dir', type=Path, help='New directory under project logs; preserve earlier test evidence')
args = parser.parse_args()
destination = ROOT/'logs'
if args.evidence_dir:
    destination = args.evidence_dir.resolve()
    if not destination.is_relative_to((ROOT/'logs').resolve()):
        parser.error('Evidence directory must be inside project logs')
    destination.mkdir(parents=True, exist_ok=False)
stream = io.StringIO()
suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=EvidenceResult).run(suite)
data = {'runner': 'unittest (pytest-compatible tests)', 'timestamp': datetime.now(timezone.utc).isoformat(),
        'python': sys.version, 'platform': platform.platform(), 'tests_run': result.testsRun,
        'passed': result.passed, 'failures': [{'test': test.id(), 'traceback': trace} for test, trace in result.failures],
        'errors': [{'test': test.id(), 'traceback': trace} for test, trace in result.errors],
        'skipped': [{'test': str(test), 'reason': reason} for test, reason in result.skipped],
        'success': result.wasSuccessful()}
(destination / 'test-results.json').write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
(destination / 'tests-unittest.log').write_text(stream.getvalue(), encoding='utf-8')
print(f"Run={result.testsRun}; passed={len(result.passed)}; failures={len(result.failures)}; errors={len(result.errors)}; skipped={len(result.skipped)}")
print('Evidence:', destination)
raise SystemExit(0 if result.wasSuccessful() else 1)
