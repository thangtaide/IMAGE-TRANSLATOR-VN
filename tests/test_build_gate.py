"""Unit evidence fixtures test the build gate, not real GUI/AI execution."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

from scripts.qa_common import validate_build_evidence


class BuildGateTests(unittest.TestCase):
    def evidence(self):
        gui = {'overall': 'PASS', 'mock': False, 'source_fingerprint': 'current', 'python': sys.executable}
        e2e = {**gui, 'stages': {name: {'status': 'PASS'} for name in ['ocr', 'translation', 'inpaint', 'render', 'export', 'source_integrity']}}
        return gui, e2e

    def test_missing_evidence_cannot_build(self):
        problems = validate_build_evidence(None, None, 'current', sys.executable)
        self.assertTrue(any('GUI' in p for p in problems))
        self.assertTrue(any('E2E' in p for p in problems))

    def test_mock_pass_cannot_build(self):
        gui, e2e = self.evidence()
        e2e['mock'] = True
        self.assertTrue(validate_build_evidence(gui, e2e, 'current', sys.executable))

    def test_skipped_or_failed_core_stage_cannot_build(self):
        for status in ['SKIPPED', 'FAIL', 'NOT TESTED']:
            gui, e2e = self.evidence()
            e2e['stages']['translation']['status'] = status
            self.assertTrue(validate_build_evidence(gui, e2e, 'current', sys.executable))

    def test_old_source_or_different_python_cannot_build(self):
        gui, e2e = self.evidence()
        self.assertTrue(validate_build_evidence(gui, e2e, 'new-source', sys.executable))
        different_python = str(Path(sys.executable).parent/'different-environment/python.exe')
        self.assertTrue(validate_build_evidence(gui, e2e, 'current', different_python))

    def test_matching_successful_evidence_satisfies_gate(self):
        gui, e2e = self.evidence()
        self.assertEqual(validate_build_evidence(gui, e2e, 'current', sys.executable), [])


if __name__ == '__main__':
    unittest.main()
