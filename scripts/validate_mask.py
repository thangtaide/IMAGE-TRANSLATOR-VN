"""Compare actual OpenCV output against saved pre-change implementation/evidence."""
from __future__ import annotations
import argparse
import importlib.util
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.paths import ROOT


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--legacy-module',type=Path,required=True)
    args=parser.parse_args()
    import numpy as np
    from PIL import Image
    from core.imaging import build_mask,erase_text
    from core.storage import file_digest
    from core.types import OCRResult,Options
    source=args.evidence/'source.png';before_hash=file_digest(source)
    image=Image.open(source).convert('RGB');rgb=np.array(image)
    regions=[OCRResult(**r) for r in json.loads((args.evidence/'ocr.json').read_text(encoding='utf-8'))['regions']]
    spec=importlib.util.spec_from_file_location('pre_recovery_imaging',args.legacy_module)
    legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
    folder=ROOT/'output/mask-validation'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
    folder.mkdir(parents=True,exist_ok=False)
    text_zone=np.zeros(rgb.shape[:2],dtype=bool)
    for r in regions:
        x0,y0,x1,y1=r.box
        text_zone[max(0,y0-20):y1+21,max(0,x0-20):x1+21]=True
    # This fixture has black text and a colored outline. Metrics are fixture-specific.
    colored=(rgb.max(axis=2).astype(int)-rgb.min(axis=2).astype(int)>15)
    report={'source':str(source),'source_kind':'synthetic fixture; OCR JSON came from real PaddleOCR',
            'legacy_module':str(args.legacy_module),'metrics':{},'mock':False}
    for name,module in [('before',legacy),('after',sys.modules['core.imaging'])]:
        mask=module.build_mask(rgb,regions)
        result=module.erase_text(image,regions,Options())
        out=np.array(result)
        Image.fromarray(mask).save(folder/(name+'-mask.png'))
        result.save(folder/(name+'-erased.png'))
        report['metrics'][name]={'masked_pixels':int(np.count_nonzero(mask)),
            'remaining_dark_pixels_in_text_zone':int(np.count_nonzero(text_zone & (out.min(axis=2)<245))),
            'colored_border_changed_pixels':int(np.count_nonzero(colored & np.any(out!=rgb,axis=2)))}
    image.save(folder/'source.png')
    report['source_unchanged']=file_digest(source)==before_hash
    report['overall']='PASS' if (report['source_unchanged'] and
        report['metrics']['after']['remaining_dark_pixels_in_text_zone'] < report['metrics']['before']['remaining_dark_pixels_in_text_zone'] and
        report['metrics']['after']['colored_border_changed_pixels']==0) else 'FAIL'
    (folder/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2));print('Evidence:',folder)
    return 0 if report['overall']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
