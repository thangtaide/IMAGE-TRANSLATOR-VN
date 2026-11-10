"""Each native DLL regression executes in a fresh Python process."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FreshProcessRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform!='win32' or not all(importlib.util.find_spec(m) for m in ['paddleocr','ctranslate2','PySide6']):
            raise unittest.SkipTest('Windows inference packages required')
        if not all((ROOT/'models'/p/'integrity.json').is_file() for p in ['ocr/det-ch','ocr/rec-zh','ocr/cls','translation/translate-zh_en-1_9','translation/translate-en_vi-1_9']):
            raise unittest.SkipTest('Real zh OCR and pivot models required')

    def check(self, case: str, expected: str='PASS') -> None:
        process = subprocess.run([sys.executable, str(ROOT/'scripts/runtime_cases.py'),case], cwd=ROOT,
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=100)
        lines = [line for line in process.stdout.splitlines() if line.startswith('RUNTIME_RESULT ')]
        self.assertTrue(lines, process.stdout+'\n'+process.stderr)
        result = json.loads(lines[-1].split(' ',1)[1])
        self.assertEqual(process.returncode,0,process.stdout+'\n'+process.stderr)
        self.assertEqual(result['status'],expected,str(result))

    def test_raw_legacy_order_reproduces_loader_failure(self):
        self.check('legacy_raw_order','REPRODUCED')

    def test_ctranslate2_before_paddle(self):
        self.check('ct_first')

    def test_prepared_paddle_import_before_adapter(self):
        self.check('prepared_paddle_first')

    def test_direct_ocr_adapter_then_translation(self):
        self.check('adapter_ocr_first')

    def test_repeated_real_inference_reuses_models(self):
        self.check('repeat')

    def test_real_qt_worker_restart(self):
        self.check('worker_restart')

    def test_cancel_real_qt_job(self):
        self.check('cancel')
