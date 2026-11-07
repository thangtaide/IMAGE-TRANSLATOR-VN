"""Verify deliverable existence and parse source/config without claiming AI readiness."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
required = ['main.py', 'requirements.txt', 'README.md', 'PROJECT_STATUS.md', 'TEST_REPORT.md', 'AGENTS.md',
            'install.bat', 'run.bat', 'build.bat', 'ImageTranslatorVN.spec']
directories = ['config', 'ui', 'core', 'providers', 'models/ocr', 'models/translation', 'assets/fonts', 'assets/icons',
               'cache', 'logs', 'tests', 'scripts', 'output', 'dist']
files = [ROOT/'main.py']
for folder in ['core', 'providers', 'ui', 'tests', 'scripts']:
    files.extend((ROOT/folder).glob('*.py'))
errors = []
for path in files:
    try:
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    except (SyntaxError, OSError) as exc:
        errors.append(str(exc))
for path in (ROOT/'config').glob('*.json'):
    try:
        json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError) as exc:
        errors.append(str(exc))
data = {'root': str(ROOT), 'files': {name: (ROOT/name).is_file() for name in required},
        'directories': {name: (ROOT/name).is_dir() for name in directories},
        'python_files': len(files), 'source_lines': sum(len(p.read_text(encoding='utf-8').splitlines()) for p in files),
        'parse_errors': errors, 'exe_exists': (ROOT/'dist/ImageTranslatorVN/ImageTranslatorVN.exe').is_file(),
        'acceptance': 'NOT COMPLETE: missing GUI/AI dependencies, real models and EXE verification'}
(ROOT/'logs/final-audit.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
print('All requested files:', all(data['files'].values()))
print('All requested directories:', all(data['directories'].values()))
print('Python source files:', data['python_files'], 'lines:', data['source_lines'], 'parse errors:', len(errors))
print('Executable present:', data['exe_exists'])
raise SystemExit(0 if all(data['files'].values()) and all(data['directories'].values()) and not errors else 1)
