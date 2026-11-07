"""Explicit developer/QA model actions. End users use the GUI model manager."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.models import CATALOG, TranslationModelManager, verify_installation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['list', 'download', 'verify'])
    parser.add_argument('ids', nargs='*')
    args = parser.parse_args()
    manager = TranslationModelManager()
    specs = [s for s in CATALOG if s.id in args.ids] if args.ids else CATALOG
    if args.ids and len(specs) != len(set(args.ids)):
        parser.error('Model id không tồn tại trong danh mục')
    result = 0
    for spec in specs:
        if args.action == 'list':
            print(spec.id, spec.languages, 'installed' if spec.directory.exists() else 'missing')
            continue
        try:
            if args.action == 'download':
                manager.download(spec, lambda done, total: print(f'{done}/{total} bytes', end='\r'))
            else:
                verify_installation(spec.directory)
            print(spec.id, 'OK')
        except Exception as exc:
            print(spec.id, 'ERROR:', str(exc))
            result = 1
            if args.action == 'download' and isinstance(exc, ConnectionError):
                break
    return result


if __name__ == '__main__':
    raise SystemExit(main())
