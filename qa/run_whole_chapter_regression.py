"""Full suite with isolated default settings/SQLite and blocked live networking.

This is a test harness, not a production path or provider configuration change.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import unittest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runner', choices=['pytest', 'unittest'], required=True)
    parser.add_argument('--label', default='verified')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    evidence = Path(json.loads((root/'logs/latest-stage3f.json').read_text())['evidence'])
    destination = evidence / (args.runner + '-' + args.label)
    destination.mkdir(exist_ok=False)
    qa = root / 'output' / ('stage3f-regression-' + args.runner + '-' + args.label + '-' + evidence.name)
    qa.mkdir(exist_ok=False)
    for name in ('cache', 'config', 'logs', 'output'): (qa/name).mkdir()
    os.environ.update(QT_QPA_PLATFORM='offscreen', PYTHONDONTWRITEBYTECODE='1', ITVN_TEST_ONLINE='0')
    # Real credentials are unnecessary in this process and must not enter failure tracebacks.
    for name in list(os.environ):
        if any(term in name.upper() for term in ('API_KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'CREDENTIAL')):
            os.environ.pop(name)
    sys.dont_write_bytecode = True
    # Inherit a minimal network/protected-file audit in fresh native-runtime tests too.
    guards = destination/'guards'; guards.mkdir()
    protected = set(json.loads((evidence/'protected-before.json').read_text(encoding='utf-8')))
    protected.update(str(p.resolve()) for p in (root/'logs').rglob('*')
                     if p.is_file() and not p.is_relative_to(evidence))
    (guards/'protected.json').write_text(json.dumps(sorted(protected)), encoding='utf-8')
    guard_code = '''
import json,os,sys,shlex
from pathlib import Path
protected={os.path.normcase(p) for p in json.loads(Path(__file__).with_name('protected.json').read_text())}
def forbid(path):
 if isinstance(path,(str,bytes,os.PathLike)) and os.path.normcase(str(Path(os.fsdecode(path)).resolve())) in protected:
  raise AssertionError('Stage3F regression: production write forbidden')
def audit(event,args):
 if event in ('socket.connect','socket.getaddrinfo'):raise AssertionError('Stage3F regression: network forbidden')
 if event=='subprocess.Popen':
  command=str(args[1]).lower()
  executable=args[0] or shlex.split(str(args[1]),posix=False)[0].strip('"')
  local_python=os.path.normcase(str(Path(executable).resolve()))==os.path.normcase(str(Path(sys.executable).resolve()))
  local_version=(args[0] is None and command==os.environ.get('COMSPEC','').lower()+' /c "ver"')
  local_cpu=(args[0] is None and command=='lscpu')
  tokens=shlex.split(str(args[1]),posix=False)
  local_cleanup=(len(tokens)==5 and Path(executable).resolve()==(Path(os.environ.get('WINDIR','C:/Windows'))/'System32/taskkill.exe').resolve()
   and tokens[1].lower()=='/pid' and tokens[2].isdigit() and [t.lower() for t in tokens[3:]]==['/t','/f'])
  if not (local_python or local_version or local_cpu or local_cleanup):raise AssertionError('Stage3F regression: no external translation CLI')
 if event=='open':
  mode,flags=args[1],args[2]
  if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):forbid(args[0])
 if event in ('os.remove','os.rmdir','sqlite3.connect'):forbid(args[0])
 if event in ('os.rename','os.replace'):forbid(args[0]);forbid(args[1])
sys.addaudithook(audit)
'''
    (guards/'sitecustomize.py').write_text(guard_code, encoding='utf-8')
    # Loading this file installs the same audit in the parent suite process.
    import runpy
    runpy.run_path(str(guards/'sitecustomize.py'))
    os.environ['PYTHONPATH'] = str(guards) + os.pathsep + str(root)
    import core.paths as paths
    paths.CACHE = qa/'cache'; paths.CONFIG = qa/'config'
    import sources.service as source_service
    source_service.PIPELINE_STAGING_ROOT = qa/'source-staging'
    from core.runtime import prepare_inference_runtime
    prepare_inference_runtime()
    import tests.test_integration as integration
    integration.ROOT = qa  # Redirect legacy real-offline text evidence, not model paths.
    with (destination/'console.txt').open('x', encoding='utf-8') as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            if args.runner == 'pytest':
                import pytest
                code = int(pytest.main([str(root/'tests'), '-q', '-p', 'no:cacheprovider',
                                       '--junitxml='+str(destination/'results.xml')]))
                summary = dict(runner='pytest', exit_code=code)
            else:
                class Result(unittest.TextTestResult):
                    def __init__(self, *a, **kw): super().__init__(*a, **kw); self.passed = []
                    def addSuccess(self, test): super().addSuccess(test); self.passed.append(test.id())
                suite = unittest.defaultTestLoader.discover(str(root/'tests'), top_level_dir=str(root))
                result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=Result).run(suite)
                summary = dict(runner='unittest', tests=result.testsRun, passed=len(result.passed),
                    failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped))
                code = 0 if result.wasSuccessful() else 1
    (destination/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(dict(summary, evidence=str(destination)), ensure_ascii=True))
    print((destination/'console.txt').read_text(encoding='utf-8')[-6500:])
    return code


if __name__ == '__main__':
    raise SystemExit(main())
