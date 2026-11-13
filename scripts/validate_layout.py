"""Replay explicit local OCR/translation fixtures through source or frozen renderer."""
import argparse
import json
import sys
from pathlib import Path

from core.imaging import open_image,erase_text,TextRenderer
from core.paths import ROOT
from core.storage import atomic_json,file_digest
from core.types import OCRResult,Options


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--phase',required=True)
    args=parser.parse_args();run=(ROOT/args.run).resolve()
    if not run.is_relative_to(ROOT/'output') or not args.phase.replace('-','').isalnum():
        parser.error('Isolated QA directory required')
    folder=run/args.phase;folder.mkdir(exist_ok=False)
    report=dict(status='FAIL',frozen=bool(getattr(sys,'frozen',False)),generation_invocations=0,ocr_inference=False)
    try:
        case=json.loads((run/'case.json').read_text(encoding='utf-8'))
        source=(ROOT/case['source_relative']).resolve()
        if file_digest(source)!=case['source_hash']:raise ValueError('SOURCE_HASH_CHANGED')
        regions=[OCRResult(**r) for r in case['ocr']['regions']]
        protected=[OCRResult(**r) for r in case.get('preserved_regions',[])]
        opts=Options.from_dict(case['options']);image=open_image(source)
        # Reuse the existing removal code unchanged; only renderer/layout differ.
        erased=erase_text(image,regions,opts);renderer=TextRenderer(opts)
        rendered=renderer.render(erased,regions,case['translations'],protected_regions=protected)
        plans=renderer.last_layout
        covered=[i for p in plans for i in p['region_indices']+p['duplicate_indices']]
        assert sorted(covered)==list(range(len(regions)))
        for i,plan in enumerate(plans):
            expected='  '.join(case['translations'][n].strip() for n in plan['region_indices'])
            assert plan['wrapped'].split()==expected.split()
            x0,y0,x1,y1=plan['paint_box']
            assert 0<=x0<x1<=image.width and 0<=y0<y1<=image.height
            assert all(not renderer._intersects(plan['paint_box'],p['paint_box']) for p in plans[i+1:])
            assert all(not renderer._intersects(plan['paint_box'],r.box) for r in protected)
        assert file_digest(source)==case['source_hash']
        rendered.save(folder/(source.stem+'-rendered.png'))
        rendered.crop((960,0,1280,90)).save(folder/'label-crop.png')
        rendered.crop((0,0,min(400,image.width),min(140,image.height))).save(folder/'left-label-crop.png')
        atomic_json(folder/'layout.json',plans)
        report.update(status='PASS',size=list(rendered.size),source_unchanged=True,
            image_filename=source.name,source_regions=len(regions),groups=len(plans),expanded=[
                dict(region_indices=p['region_indices'],source_box=p['source_box'],box=p['box'],
                    strategy=p['layout_strategy'],font_size=p['font_size'],lines=len(p['wrapped'].splitlines()))
                for p in plans if p.get('layout_strategy') in ('local-flat-background-wrap','background-overlap-wrap')])
    except Exception as exc:
        report.update(error_code=getattr(exc,'code',type(exc).__name__))
    atomic_json(folder/'report.json',report)
    if sys.stdout:print(json.dumps(report,ensure_ascii=True))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
