"""Create explicit CV-only validation artifacts, never fake OCR/translation evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageFont
from core.imaging import TextRenderer, atomic_save, default_font, erase_text
from core.paths import ROOT
from core.storage import atomic_json, file_digest
from core.types import OCRResult, Options

destination = ROOT / 'output' / 'cv-validation'
destination.mkdir(parents=True, exist_ok=True)
source = destination / 'before.png'
target = destination / 'after.png'
if source.exists() or target.exists():
    raise SystemExit('Validation artifacts already exist; refusing to overwrite without inspection.')
image = Image.new('RGBA', (960, 520), (224, 233, 245, 220))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((80, 80, 880, 420), radius=70, fill=(255, 255, 255, 220), outline=(48, 66, 87, 220), width=4)
font = ImageFont.truetype(str(default_font()), 50)
draw.text((180, 170), 'Hello world!', font=font, fill=(20, 30, 40, 220))
draw.text((180, 240), 'How are you today?', font=font, fill=(20, 30, 40, 220))
image.save(source)
original = file_digest(source)
region = OCRResult('Hello world! How are you today?', [[165, 150], [820, 150], [820, 320], [165, 320]], 1.0, 'en')
translation = 'Xin chào thế giới!\nHôm nay bạn thế nào?'
options = Options(font_max=48, font_min=12, stroke=0, line_spacing=8)
rendered = TextRenderer(options).render(erase_text(image, [region], options), [region], [translation])
atomic_save(rendered, target)
assert file_digest(source) == original
assert rendered.size == image.size
atomic_json(destination / 'evidence.json', {
    'scope': 'REAL OpenCV inpainting + REAL Pillow Vietnamese rendering and PNG export only',
    'source': str(source), 'output': str(target), 'original_sha256': original, 'output_sha256': file_digest(target),
    'size': list(image.size), 'alpha_preserved': rendered.getchannel('A').tobytes() == image.getchannel('A').tobytes(),
    'ocr': 'NOT EXECUTED; manually supplied validation coordinates',
    'translation': 'NOT EXECUTED; manually supplied Vietnamese test string',
})
print('Created CV-only validation artifacts:', destination)
