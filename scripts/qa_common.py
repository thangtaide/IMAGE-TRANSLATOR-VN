"""Shared evidence helpers; no dependency on GUI, OCR or translation packages."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(sys.executable).resolve().parents[2] if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]


def source_fingerprint(root: Path = ROOT) -> str:
    paths = [root/'main.py', root/'requirements.txt', root/'ImageTranslatorVN.spec']
    for folder in ['core', 'providers', 'ui', 'scripts']:
        paths += list((root/folder).glob('*.py'))
    h = hashlib.sha256()
    for path in sorted(paths):
        h.update(str(path.relative_to(root)).replace('\\', '/').encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def read_latest(pointer: Path, root: Path = ROOT) -> tuple[dict | None, str]:
    try:
        path = Path(json.loads(pointer.read_text(encoding='utf-8'))['path']).resolve()
        if not path.is_relative_to(root.resolve()):
            return None, 'Evidence path is outside project'
        return json.loads(path.read_text(encoding='utf-8')), ''
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, 'Evidence unavailable: '+type(exc).__name__


def validate_build_evidence(gui: dict | None, e2e: dict | None, fingerprint: str, interpreter: str) -> list[str]:
    problems = []
    for name, evidence in [('GUI', gui), ('E2E', e2e)]:
        if not evidence:
            problems.append(name+' evidence is missing')
            continue
        if evidence.get('overall') != 'PASS' or evidence.get('mock') is not False:
            problems.append(name+' has no real PASS result')
        if evidence.get('source_fingerprint') != fingerprint:
            problems.append(name+' evidence does not match current source')
        if Path(evidence.get('python', '')).resolve() != Path(interpreter).resolve():
            problems.append(name+' evidence uses another Python environment')
    if e2e and any(e2e.get('stages', {}).get(name, {}).get('status') != 'PASS'
                   for name in ['ocr', 'translation', 'inpaint', 'render', 'export', 'source_integrity']):
        problems.append('E2E has missing/failed core stages')
    return problems
