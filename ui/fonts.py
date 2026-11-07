"""Register a Vietnamese font explicitly, including Qt offscreen on Windows.

Installed Windows fonts are used in place, never copied or redistributed.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QRawFont
from PySide6.QtWidgets import QApplication

from core.paths import ASSETS

VIETNAMESE_SAMPLE = 'IMAGE TRANSLATOR VN Tiếng Việt: Nguyễn Ánh ă â ê ô ơ ư đ Ạ ễ ự'


def configure_ui_font() -> dict:
    app = QApplication.instance()
    if app is None:
        raise RuntimeError('QApplication is required before font registration')
    cached = app.property('itvn_font_report')
    if cached:
        return cached
    before = QFontDatabase.families()
    old_font = QRawFont.fromFont(app.font())
    before_missing = sorted({c for c in VIETNAMESE_SAMPLE if not c.isspace() and (not old_font.isValid() or not old_font.supportsCharacter(ord(c)))})
    candidates = [ASSETS/'fonts/NotoSans-Regular.ttf', Path('C:/Windows/Fonts/segoeui.ttf'), Path('C:/Windows/Fonts/arial.ttf')]
    attempts = []
    for path in candidates:
        if not path.is_file():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id>=0 else []
        attempts.append({'path':str(path),'font_id':font_id,'families':families})
        if not families:
            continue
        font = QFont(families[0], 10)
        raw = QRawFont.fromFont(font)
        missing = sorted({c for c in VIETNAMESE_SAMPLE if not c.isspace() and (not raw.isValid() or not raw.supportsCharacter(ord(c)))})
        if missing:
            continue
        app.setFont(font)
        report = {'status':'PASS','selected_family':families[0],'path':str(path),
                  'families_before':before,'missing_glyphs_before':before_missing,'missing_glyphs_after':missing,
                  'platform':app.platformName(),'redistributed_windows_font':False,'attempts':attempts}
        app.setProperty('itvn_font_report',report)
        return report
    report = {'status':'FAIL','reason':'No registered font covers required Vietnamese glyphs',
              'missing_glyphs_before':before_missing,'attempts':attempts,'platform':app.platformName()}
    app.setProperty('itvn_font_report',report)
    return report
