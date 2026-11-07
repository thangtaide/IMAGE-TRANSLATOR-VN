from __future__ import annotations
import json, os, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtGui import QFontDatabase,QFont,QRawFont,QFontInfo
app=QApplication([])
sample='IMAGE TRANSLATOR VN Tiếng Việt Nguyễn Ánh ă â ê ô ơ ư đ Ạ ễ ự'
report={'platform':app.platformName(),'before_families':QFontDatabase.families(),'cases':[]}
for path in [Path('C:/Windows/Fonts/segoeui.ttf'),Path('C:/Windows/Fonts/arial.ttf')]:
    font_id=QFontDatabase.addApplicationFont(str(path))
    families=QFontDatabase.applicationFontFamilies(font_id)
    for family in families:
        font=QFontDatabase.font(family,'Regular',12)
        app.setFont(font)
        raw=QRawFont.fromFont(font)
        direct=QRawFont(str(path),16.0)
        case={'path':str(path),'families':families,'resolved':QFontInfo(font).family(),
              'raw_valid':raw.isValid(),'direct_valid':direct.isValid(),
              'missing_raw':[c for c in sample if not c.isspace() and not raw.supportsCharacter(c)],
              'missing_direct':[c for c in sample if not c.isspace() and not direct.supportsCharacter(c)],
              'missing_ucs4':[c for c in sample if not c.isspace() and not raw.supportsCharacter(ord(c))]}
        report['cases'].append(case)
folder=ROOT/'logs'/('font-inspection-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
folder.mkdir()
(folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
print(folder)
