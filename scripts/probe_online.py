"""A real, minimal provider probe, with structured success/failure evidence."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import ROOT
from providers.online import MyMemoryProvider

provider = MyMemoryProvider()
data = {'provider': 'MyMemory anonymous free GET', 'timestamp': datetime.now(timezone.utc).isoformat(), 'mock': False}
try:
    result = provider.translate('Hello world', 'en')
    data.update(success=True, result=result)
except Exception as exc:
    data.update(success=False, error_type=type(exc).__name__, error=str(exc))
finally:
    provider.close()
(ROOT / 'logs' / 'online-probe.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print('MyMemory real probe:', 'PASS' if data['success'] else 'FAILED', data.get('error_type', ''))
raise SystemExit(0 if data['success'] else 1)
