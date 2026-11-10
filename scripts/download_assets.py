"""Explicit one-time font download (never called by an Offline job)."""
from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.paths import ASSETS
from core.storage import file_digest


def main() -> int:
    target = ASSETS / 'fonts'
    target.mkdir(parents=True, exist_ok=True)
    base = 'https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSans/'
    files = [('NotoSans-Regular.ttf', base+'NotoSans-Regular.ttf'),
             ('OFL.txt', 'https://raw.githubusercontent.com/notofonts/noto-fonts/main/LICENSE')]
    try:
        for name, url in files:
            path = target / name
            if path.is_file():
                continue
            temp = path.with_suffix(path.suffix+'.download')
            try:
                with urllib.request.urlopen(url, timeout=20) as response, temp.open('wb') as output:
                    output.write(response.read(5_000_000))
                if name.endswith('.ttf'):
                    from PIL import ImageFont
                    ImageFont.truetype(str(temp), 20)
                elif 'SIL OPEN FONT LICENSE' not in temp.read_text(encoding='utf-8').upper():
                    raise ValueError('License font không hợp lệ')
                temp.replace(path)
                print(name, file_digest(path))
            finally:
                temp.unlink(missing_ok=True)
        return 0
    except (OSError, ValueError) as exc:
        print('Không tải được font Noto:', type(exc).__name__)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
