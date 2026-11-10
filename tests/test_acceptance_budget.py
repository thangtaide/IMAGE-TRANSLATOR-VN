"""Budget instrumentation contracts only; no CLI/model/network calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from core.paths import ROOT
from providers.agy import AGYProvider
from scripts.acceptance_readability import instrument_transport


class AcceptanceBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'output',prefix='budget-fixture-')
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        (self.root/'agy-budget.json').write_text(json.dumps(dict(limit=6,used=0,remaining=6,invocations=[])),encoding='utf-8')
        self.provider=object.__new__(AGYProvider);self.provider.model='gemini-fixture'

    def test_seventh_generation_is_blocked_before_transport(self):
        transport=Mock(return_value=(0,b'{}',b''))
        with patch.object(AGYProvider,'_invoke',transport),instrument_transport(self.root,'fixture',['a']):
            for _ in range(6):self.provider._invoke([],b'fixture',self.root,1)
            with self.assertRaisesRegex(RuntimeError,'BUDGET_EXHAUSTED'):
                self.provider._invoke([],b'fixture',self.root,1)
        self.assertEqual(transport.call_count,6)
        ledger=json.loads((self.root/'agy-budget.json').read_text())
        self.assertEqual((ledger['used'],ledger['remaining']),(6,0))

    def test_local_probes_do_not_consume_generation_budget(self):
        with patch.object(AGYProvider,'_invoke',return_value=(0,b'fixture-help',b'')),instrument_transport(self.root,'fixture',['a']):
            self.provider._invoke(['--help'],None,self.root,1,role='HELP')
        self.assertEqual(json.loads((self.root/'agy-budget.json').read_text())['used'],0)

    def test_transport_error_consumes_one_attempt_and_is_not_retried(self):
        transport=Mock(side_effect=OSError('intentional local fixture failure'))
        with patch.object(AGYProvider,'_invoke',transport),instrument_transport(self.root,'fixture',['a']):
            with self.assertRaises(OSError):self.provider._invoke([],b'fixture',self.root,1)
        self.assertEqual(transport.call_count,1)
        ledger=json.loads((self.root/'agy-budget.json').read_text())
        self.assertEqual((ledger['used'],ledger['remaining']),(1,5))
        self.assertEqual(ledger['invocations'][0]['status'],'ERROR')
