"""Read-only runtime readiness and source manifest, stored inside this project."""
from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.models import CATALOG
from core.storage import file_digest

required = {'PySide6': 'PySide6', 'paddle': 'paddlepaddle', 'paddleocr': 'paddleocr', 'argostranslate': 'argostranslate',
            'ctranslate2': 'ctranslate2', 'sentencepiece': 'sentencepiece', 'pytest': 'pytest', 'PyInstaller': 'pyinstaller',
            'numpy': 'numpy', 'PIL': 'Pillow', 'cv2': 'opencv-python-headless', 'requests': 'requests'}
modules = {}
for module, package in required.items():
    available = importlib.util.find_spec(module) is not None
    try:
        version = importlib.metadata.version(package) if available else None
    except importlib.metadata.PackageNotFoundError:
        version = 'unknown'
    modules[module] = {'available': available, 'version': version}
data = {'timestamp': datetime.now(timezone.utc).isoformat(), 'python': sys.version, 'executable': sys.executable,
        'modules': modules, 'models': [{'id': s.id, 'installed': (s.directory/'integrity.json').is_file()} for s in CATALOG],
        'exe_exists': (ROOT/'dist/ImageTranslatorVN/ImageTranslatorVN.exe').is_file(),
        'noto_font_exists': (ROOT/'assets/fonts/NotoSans-Regular.ttf').is_file()}
(ROOT/'logs/runtime-readiness.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
files = [ROOT/'main.py', ROOT/'requirements.txt', ROOT/'ImageTranslatorVN.spec']
for directory in ['core', 'providers', 'ui', 'scripts', 'tests']:
    files += list((ROOT/directory).glob('*.py'))
manifest = {str(p.relative_to(ROOT)): {'sha256': file_digest(p), 'bytes': p.stat().st_size} for p in sorted(files)}
(ROOT/'logs/source-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('Source files:', len(manifest), 'bytes:', sum(v['bytes'] for v in manifest.values()))
print('Missing modules:', ', '.join(k for k, v in modules.items() if not v['available']))
print('Installed model count:', sum(x['installed'] for x in data['models']), '/', len(CATALOG))
print('EXE exists:', data['exe_exists'])
