"""Read-only inventory; never changes another project's environment."""
import importlib.metadata
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
packages = {d.metadata['Name']: d.version for d in importlib.metadata.distributions()}
locations = [Path('C:/Users/ADMIN/AppData/Local/pip/Cache'), Path('D:/'), Path('C:/Users/ADMIN')]
names = {}
for location in locations:
    try:
        names[str(location)] = [str(p) for p in location.iterdir() if p.is_dir() or p.suffix == '.whl']
    except OSError as exc:
        names[str(location)] = str(exc)
data = {'packages': packages, 'locations': names}
(root/'logs'/'local_dependencies.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
print(json.dumps(data, indent=2))
