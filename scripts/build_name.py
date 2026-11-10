"""Name a new build alongside the existing executable, without replacing it."""
from datetime import datetime, timezone

print('ImageTranslatorVN-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
