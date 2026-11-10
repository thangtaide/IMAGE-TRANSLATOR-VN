"""Inspect pip's local cache for reusable wheels, without network access."""
from pathlib import Path
import json
import zipfile

cache = Path('C:/Users/ADMIN/AppData/Local/pip/Cache')
result = []
for pattern in ('*.body', '*.whl'):
    for path in cache.rglob(pattern):
        try:
            if path.stat().st_size < 1000:
                continue
            with path.open('rb') as stream:
                if stream.read(4) != b'PK\x03\x04':
                    continue
            with zipfile.ZipFile(path) as archive:
                metas = [n for n in archive.namelist() if n.endswith('.dist-info/WHEEL')]
                if metas:
                    folder = metas[0].split('/')[0]
                    result.append({'path': str(path), 'package': folder, 'size': path.stat().st_size})
        except (OSError, zipfile.BadZipFile):
            pass
out = Path(__file__).resolve().parents[1]/'logs/cached_wheels.json'
out.write_text(json.dumps(result, indent=2), encoding='utf-8')
for entry in result:
    print(entry['package'], entry['size'])
