"""Real local Python processes, no AGY/model/network. Tests OS containment and deadlines."""
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from providers.agy import AGYProvider, CLI_SHUTDOWN_GRACE, run_bounded, parse_response
from providers.online import OnlineProviderError, ProviderSuspended
from core.types import CancelledError


class TimeoutLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.observed = []

    def tearDown(self):
        self.temp.cleanup()

    def run_script(self, script, timeout=2, **kw):
        return run_bounded([sys.executable,'-c',script],None,self.root,timeout,
                           observer=self.observed.append,**kw)

    def test_slow_valid_response_and_progress_is_not_terminal(self):
        answer=dict(event='result',result=dict(status='SUCCESS',response=json.dumps(
            {'translations':[{'id':'r0','text':'Chương 13'}]})))
        script=("import json,time;print(json.dumps({'event':'init'}),flush=True);"
                "print(json.dumps({'event':'step_update','step_update':{'step_type':'user_input','state':'DONE'}}),flush=True);"
                "time.sleep(.25);print("+repr(json.dumps(answer))+",flush=True)")
        code,out,_=self.run_script(script)
        self.assertEqual(parse_response(out,['r0'],code),['Chương 13'])
        timing=self.observed[-1]['timings']
        self.assertGreater(timing['terminal_result_seconds']-timing['input_done_seconds'],.15)
        self.assertTrue(self.observed[-1]['cleanup_ok'])

    def test_silent_total_deadline_has_no_fabricated_response(self):
        with self.assertRaises(OnlineProviderError) as c:
            self.run_script('import time;time.sleep(30)',.15)
        self.assertEqual(c.exception.code,'TIMEOUT')
        self.assertEqual(c.exception._agy_capture.stdout,b'')
        self.assertTrue(self.observed[-1]['cleanup_ok'])

    def test_partial_init_neither_extends_deadline_nor_completes_translation(self):
        with self.assertRaises(OnlineProviderError) as c:
            self.run_script("import time;print('{\"event\":\"init\"}',flush=True);time.sleep(30)",.2)
        self.assertEqual(c.exception.code,'TIMEOUT')
        self.assertIn(b'init',c.exception._agy_capture.stdout)
        self.assertNotIn('terminal_result_seconds',self.observed[-1]['timings'])
        self.assertLess(self.observed[-1]['elapsed_seconds'],3)

    def test_repeated_init_events_do_not_extend_total_deadline(self):
        script="import time\nfor _ in range(200):\n print('{\"event\":\"init\"}',flush=True)\n time.sleep(.02)"
        with self.assertRaises(OnlineProviderError) as c:self.run_script(script,.25)
        self.assertEqual(c.exception.code,'TIMEOUT')
        self.assertLess(self.observed[-1]['elapsed_seconds'],2)

    def test_exit_zero_without_result_remains_invalid(self):
        code,out,_=self.run_script("print('{\"event\":\"init\"}',flush=True)")
        self.assertEqual(code,0)
        with self.assertRaises(OnlineProviderError):parse_response(out,['r0'],code)

    def test_cli_declared_print_timeout_rejects_even_complete_json_and_exit_zero(self):
        event=dict(event='result',result=dict(status='SUCCESS',finished_reason='print_timeout',
            response=json.dumps({'translations':[{'id':'r0','text':'Không chấp nhận partial'}]})))
        with self.assertRaises(ProviderSuspended) as c:parse_response(json.dumps(event).encode(),['r0'],0)
        self.assertEqual(c.exception.code,'TIMEOUT')
        self.assertEqual(c.exception.agy_timeout_layer,'CLI_TOTAL')

    @unittest.skipUnless(os.name=='nt','Windows Job Object containment')
    def test_root_exit_terminates_owned_child_but_leaves_unrelated_process(self):
        sentinel=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
        try:
            script=("import subprocess,sys;child=subprocess.Popen([sys.executable,'-c',"
                    "'import time;time.sleep(30)'],stdout=sys.stdout,stderr=sys.stderr);print(child.pid,flush=True)")
            code,out,_=self.run_script(script)
            self.assertEqual(code,0)
            self.assertTrue(out.strip().isdigit())
            self.assertEqual(self.observed[-1]['active_processes_after_cleanup'],0)
            self.assertTrue(self.observed[-1]['cleanup_ok'])
            self.assertIsNone(sentinel.poll())
        finally:
            sentinel.terminate();sentinel.wait(timeout=5)

    @unittest.skipUnless(os.name=='nt','Windows Job Object containment')
    def test_timeout_and_cancel_leave_zero_owned_processes(self):
        script=("import subprocess,sys,time;subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);"
                "print('ready',flush=True);time.sleep(30)")
        for cancel in (False,True):
            start=time.monotonic()
            with self.assertRaises((OnlineProviderError,CancelledError)):
                self.run_script(script,.2 if not cancel else 3,
                    cancelled=lambda:cancel and time.monotonic()-start>.2)
            self.assertEqual(self.observed[-1]['active_processes_after_cleanup'],0)

    def test_provider_cli_deadline_has_grace_and_never_retries(self):
        exe=self.root/'fixture.exe';exe.write_bytes(b'not executable; injected runner only')
        calls=[]
        error=dict(event='result',result=dict(status='ERROR',error={'code':'RATE_LIMITED'}))
        def runner(argv,payload,cwd,timeout,cancelled):
            calls.append(timeout)
            self.assertEqual(argv[argv.index('--print-timeout')+1],'0.2s')
            # CLI signals its own deadline, then needs time to serialize shutdown.
            return run_bounded([sys.executable,'-c',"import time,sys;sys.stdin.read();time.sleep(.35);print("+
                repr(json.dumps(error))+",flush=True);sys.exit(1)"],payload,cwd,timeout,cancelled)
        with patch.dict(os.environ,USERPROFILE=str(self.root)):
            p=AGYProvider(str(exe),root=self.root/'cli',probe_cli=False,runner=runner)
            with self.assertRaises(ProviderSuspended) as c:
                p._run_translation(b'fixture\n',['r0'],timeout=.2)
            self.assertEqual(c.exception.code,'RATE_LIMITED')
            self.assertEqual(calls,[.2+CLI_SHUTDOWN_GRACE])
            with self.assertRaises(ProviderSuspended):p._run_translation(b'fixture\n',['r0'],timeout=.2)
            self.assertEqual(len(calls),1)
            p.close()

    def test_observer_error_cannot_fail_valid_process(self):
        result=run_bounded([sys.executable,'-c',"print('ok')"],None,self.root,2,
            observer=lambda _:(_ for _ in ()).throw(RuntimeError('local fixture observer')))
        self.assertEqual(result[0],0)

    @unittest.skipUnless(os.name=='nt','Windows suspended startup')
    def test_isolation_failure_never_executes_child_code(self):
        marker=self.root/'must-not-exist.txt'
        script='from pathlib import Path;Path('+repr(str(marker))+').write_text("unsafe")'
        with patch('providers.agy_process.WindowsProcessTree.assign_and_resume',side_effect=OSError('fixture')):
            with self.assertRaises(OSError):self.run_script(script)
        self.assertFalse(marker.exists())


if __name__=='__main__':unittest.main()
