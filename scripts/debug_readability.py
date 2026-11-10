"""Local CV/render evidence from existing cache. Never calls OCR or providers."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from PIL import Image, ImageDraw
from core.imaging import TextRenderer, build_mask, erase_text, open_image
from core.types import Options, OCRResult


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return os.path.relpath(path, ROOT).replace('\\', '/')


def capture(directory, cases, job_prefix=None):
    directory.mkdir(parents=True, exist_ok=False)
    for name in ('imaging.py', 'pipeline.py'):
        shutil.copy2(ROOT/'core'/name, directory/('before-'+name))
    protected = {}
    database = ROOT/'cache/state.sqlite3'
    protected[relative(database)] = checksum(database)
    with sqlite3.connect(database.as_uri()+'?mode=ro', uri=True) as connection:
        jobs = {key[:8]: json.loads(value) for key, value in connection.execute('SELECT id,options FROM jobs')}
        records = [json.loads(value) for value, in connection.execute("SELECT value FROM cache WHERE kind='metadata'")]
    selected = {}
    for record in records:
        source, output = Path(record['source']), Path(record['output'])
        if source.stem in cases and source.is_file() and output.is_file() and (not job_prefix or output.stem.endswith(job_prefix)):
            selected[source.stem] = record
    if not selected:
        raise FileNotFoundError('No requested real images found in current project cache')
    for case, record in sorted(selected.items()):
        folder = directory/case
        folder.mkdir()
        source, output = Path(record['source']), Path(record['output'])
        for path in (source, output):
            protected[relative(path)] = checksum(path)
        options = jobs[output.stem.split('.vi-')[-1]]
        options = dict(options, source=relative(Path(options['source'])), output=relative(Path(options['output'])))
        record = dict(record, source=relative(source), output=relative(output))
        (folder/'metadata.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        (folder/'options.json').write_text(json.dumps(options, ensure_ascii=False, indent=2), encoding='utf-8')
        image = open_image(source)
        image.save(folder/'original.png')
        open_image(output).save(folder/'final-existing.png')
        render_case(folder, 'before')
    (directory/'protected.json').write_text(json.dumps(protected, ensure_ascii=False, indent=2), encoding='utf-8')


def render_case(folder, suffix):
    record = json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
    options = Options.from_dict(json.loads((folder/'options.json').read_text(encoding='utf-8')))
    image = open_image(folder/'original.png')
    regions = [OCRResult(**item) for item in record['regions']]
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    for n, region in enumerate(regions):
        draw.polygon([tuple(p) for p in region.polygon], outline='red', width=2)
        draw.text(tuple(region.polygon[0]), str(n), fill='yellow')
    overlay.save(folder/'ocr-boxes.png')
    mask = build_mask(np.array(image.convert('RGB')), regions, options.mask_expand)
    Image.fromarray(mask).save(folder/('mask-'+suffix+'.png'))
    erased = erase_text(image, regions, options)
    erased.save(folder/('inpainted-'+suffix+'.png'))
    renderer = TextRenderer(options)
    final = renderer.render(erased, regions, record['translations'])
    final.save(folder/('final-'+suffix+'.png'))
    if suffix == 'after':
        (folder/'layout.json').write_text(json.dumps(renderer.last_layout, ensure_ascii=False, indent=2), encoding='utf-8')
    names = ['original', 'ocr-boxes', 'mask-before', 'mask-after', 'inpainted-before', 'inpainted-after', 'final-existing', 'final-after']
    available = [name for name in names if (folder/(name+'.png')).is_file()]
    crop_height = min(image.height, 190)
    sheet = Image.new('RGB', (image.width, (crop_height+24)*len(available)), '#dddddd')
    labels = ImageDraw.Draw(sheet)
    for n, name in enumerate(available):
        sheet.paste(Image.open(folder/(name+'.png')).convert('RGB').crop((0, 0, image.width, crop_height)), (0,n*(crop_height+24)+24))
        labels.text((4,n*(crop_height+24)+4), name, fill='black')
    sheet.save(folder/('comparison-'+suffix+'.png'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--cases', nargs='+', default=['0002', '0007', '0011'])
    parser.add_argument('--job-prefix', help='Select an exact historical job instead of another output of the same image')
    args = parser.parse_args()
    directory = (ROOT/(args.directory or Path('output')/('readability-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')))).resolve()
    if not directory.is_relative_to((ROOT/'output').resolve()) or directory == (ROOT/'output').resolve():
        parser.error('Evidence directory must be a child of project output')
    if args.capture:
        capture(directory, args.cases, args.job_prefix)
    else:
        for path in sorted(directory.glob('*/metadata.json')):
            render_case(path.parent, 'after')
    protected = json.loads((directory/'protected.json').read_text(encoding='utf-8'))
    changed = [ref for ref, expected in protected.items() if checksum((ROOT/ref).resolve()) != expected]
    report = {'evidence_directory': relative(directory), 'protected_files': len(protected), 'changed_originals_or_database': changed,
              'inference_calls': 0, 'agy_calls': 0, 'exe_builds': 0}
    (directory/'preservation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))
    return 1 if changed else 0


if __name__ == '__main__':
    raise SystemExit(main())
