"""Explicit, bounded acceptance runs through real source/frozen application code.

Artifacts stay under a new project output directory. No credentials are read,
changed or copied. Transport instrumentation counts generation invocations;
it never supplies OCR, targets or CLI responses.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

if not getattr(sys,'frozen',False):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.paths import ROOT
from core.storage import atomic_json, file_digest
from core.types import Options, OCRResult


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rgb_hash(image):
    return hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()


@contextmanager
def instrument_transport(run,phase,pages):
    from providers.agy import AGYProvider
    original=AGYProvider._invoke
    def invoke(provider,argv,payload,work,timeout,**kwargs):
        path=run/'agy-budget.json'
        generation=payload is not None
        number=None
        if generation:
            data=read(path)
            if data['used'] >= data['limit']:
                raise RuntimeError('ACCEPTANCE_AGY_BUDGET_EXHAUSTED')
            data['used']+=1;data['remaining']=data['limit']-data['used'];number=data['used']
            data['invocations'].append(dict(number=number,purpose=phase,pages=pages,image_count=len(pages),
                started=now(),status='RESERVED',model=provider.model,remaining=data['remaining']))
            atomic_json(path,data)
        started=time.monotonic()
        try:
            result=original(provider,argv,payload,work,timeout,**kwargs)
            if number:
                data=read(path);entry=next(x for x in data['invocations'] if x['number']==number)
                entry.update(ended=now(),seconds=time.monotonic()-started,status='CLI_RETURNED',exit_code=result[0],
                    stdout_bytes=len(result[1]),stderr_bytes=len(result[2]),remaining=data['remaining'])
                atomic_json(path,data)
            return result
        except Exception as exc:
            if number:
                data=read(path);entry=next(x for x in data['invocations'] if x['number']==number)
                entry.update(ended=now(),seconds=time.monotonic()-started,status='ERROR',
                    error_code=getattr(exc,'code',type(exc).__name__),remaining=data['remaining'])
                atomic_json(path,data)
            raise
    AGYProvider._invoke=invoke
    try:
        yield
    finally:
        AGYProvider._invoke=original


class Capture:
    def __init__(self,phase,inputs):
        self.phase=phase;self.cases={};self.captured={}
        from core.imaging import open_image
        for path in inputs.glob('*.jpg'):
            self.cases[rgb_hash(open_image(path))]=path.stem

    @contextmanager
    def install(self):
        import core.imaging as imaging
        import core.pipeline as pipeline
        from PIL import Image,ImageDraw
        import numpy as np
        original_erase=pipeline.erase_text;original_mask=imaging.build_mask;original_render=imaging.TextRenderer.render
        def mask(rgb,regions,expansion=1):
            result=original_mask(rgb,regions,expansion)
            case=self.cases.get(hashlib.sha256(rgb.tobytes()).hexdigest())
            if case:
                directory=self.phase/case;directory.mkdir(exist_ok=True)
                Image.fromarray(result).save(directory/'mask.png')
            return result
        def erase(image,regions,options):
            result=original_erase(image,regions,options)
            case=self.cases.get(rgb_hash(image))
            if case:
                directory=self.phase/case;directory.mkdir(exist_ok=True)
                image.save(directory/'original.png');result.save(directory/'inpainted.png')
                overlay=image.copy();draw=ImageDraw.Draw(overlay)
                for i,region in enumerate(regions):
                    draw.polygon([tuple(p) for p in region.polygon],outline='red',width=2)
                    draw.text(tuple(region.polygon[0]),str(i),fill='yellow')
                overlay.save(directory/'ocr.png')
                atomic_json(directory/'ocr.json',dict(regions=[asdict(r) for r in regions]))
                self.captured[rgb_hash(result)]=(case,[asdict(r) for r in regions],options)
            return result
        def render(renderer,image,regions,targets):
            found=self.captured.get(rgb_hash(image))
            result=original_render(renderer,image,regions,targets)
            if found:
                case,_,options=found;directory=self.phase/case
                result.save(directory/'final.png')
                overlay=result.copy();draw=ImageDraw.Draw(overlay)
                for i,p in enumerate(renderer.last_layout):
                    draw.rectangle(tuple(p['box']),outline='#00ff00',width=2)
                    draw.text((p['box'][0],p['box'][1]),f'{i}: {p["font_size"]}px',fill='yellow')
                overlay.save(directory/'layout.png')
                indices=[i for p in renderer.last_layout for i in p['region_indices']+p['duplicate_indices']]
                intact=all(''.join(p['wrapped'].split())==''.join(' '.join(targets[i] for i in p['region_indices']).split()) for p in renderer.last_layout)
                collisions=[(i,j) for i,p in enumerate(renderer.last_layout) for j,q in enumerate(renderer.last_layout)
                    if i<j and renderer._intersects(p['paint_box'],q['paint_box'])]
                atomic_json(directory/'render.json',dict(regions=[asdict(r) for r in regions],targets=targets,
                    layout=renderer.last_layout,source_is_inpainted=True,content_intact=intact,
                    all_ids_accounted=sorted(indices)==list(range(len(regions))),collisions=collisions))
            return result
        imaging.build_mask=mask;pipeline.erase_text=erase;imaging.TextRenderer.render=render
        try:yield
        finally:
            imaging.build_mask=original_mask;pipeline.erase_text=original_erase;imaging.TextRenderer.render=original_render


def gui_batch(run,phase,inputs,options):
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QFileDialog
    from ui.main_window import MainWindow
    app=QApplication.instance() or QApplication([])
    window=MainWindow(cache_path=phase/'state.sqlite3',persist_settings=False)
    window.options=Options.from_dict(options.to_dict())
    window.output.setText(options.output)
    window.source_tabs.setCurrentIndex(1)
    window.language.setCurrentIndex(window.language.findData('zh'))
    window.mode.setCurrentIndex(window.mode.findData(options.mode))
    window.show()
    report=dict(mock=False,display_mode=app.platformName(),heartbeat=0,events=[],picker=False,overall='FAIL')
    heartbeat=QTimer();heartbeat.timeout.connect(lambda:report.update(heartbeat=report['heartbeat']+1));heartbeat.start(25)
    finish_wait=[None]
    def finished():
        if window.worker and window.worker.isRunning():QTimer.singleShot(50,finished);return
        if finish_wait[0] is None:finish_wait[0]=time.monotonic()
        # QThread can stop before its queued finished slot restores the widgets.
        if not window.start_button.isEnabled() and time.monotonic()-finish_wait[0]<5:
            QTimer.singleShot(50,finished);return
        report['gui_buttons_restored']=window.start_button.isEnabled()
        window.grab().save(str(phase/'window.png'))
        window.close();app.quit()
    def event(value):
        report['events'].append({k:value[k] for k in ('type','stage','state','completed','failed','fallback_original','code') if k in value})
        if value.get('type')=='finished':
            report['pipeline']=value
            report['overall']='PASS' if value.get('completed')==3 and value.get('failed')==0 and value.get('fallback_original',0)==0 else 'FAIL'
            QTimer.singleShot(50,finished)
    def start():
        dialog=QFileDialog(window,'Acceptance input selection',str(inputs))
        dialog.setOption(QFileDialog.DontUseNativeDialog,True);dialog.setFileMode(QFileDialog.Directory)
        QTimer.singleShot(100,dialog.accept)
        if dialog.exec()!=QFileDialog.Accepted:
            report['reason']='Picker did not select input';finished();return
        selected=Path(dialog.selectedFiles()[0]).resolve()
        report['picker']=selected==inputs.resolve()
        window.source.setText(str(selected))
        QTest.mouseClick(window.start_button,Qt.LeftButton)
        if window.worker:window.worker.event.connect(event)
        else:report['reason']='Worker not created';finished()
    def timeout():
        report['reason']='GUI acceptance deadline exceeded'
        if window.worker:window.worker.control.cancel()
        finished()
    deadline=QTimer();deadline.setSingleShot(True);deadline.timeout.connect(timeout);deadline.start(420000)
    QTimer.singleShot(0,start);app.exec();heartbeat.stop();deadline.stop()
    report['overall']='PASS' if report['overall']=='PASS' and report['picker'] and report['heartbeat']>=3 and report.get('gui_buttons_restored') else 'FAIL'
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--phase',choices=['source-batch','source-whole','source-cached','exe-batch','exe-whole','exe-cached'],required=True)
    parser.add_argument('--attempt',type=int,default=1,help='New evidence directory; never replace a previous attempt')
    args=parser.parse_args();run=(ROOT/args.run).resolve()
    if not run.is_relative_to((ROOT/'output').resolve()):parser.error('Run must be inside project output')
    if args.attempt < 1:parser.error('Attempt must be positive')
    phase=run/(args.phase if args.attempt==1 else args.phase+'-'+str(args.attempt));phase.mkdir(exist_ok=False)
    report=dict(phase=phase.name,started=now(),frozen=bool(getattr(sys,'frozen',False)),overall='FAIL',mock=False)
    protected={p:file_digest(p) for p in (ROOT/'config').glob('*.json')}
    try:
        if args.phase.startswith('exe-') != report['frozen']:
            raise ValueError('Acceptance phase does not match the actual source/frozen interpreter')
        from core.runtime import prepare_inference_runtime
        prepare_inference_runtime()
        from core.imaging import IMAGING_REVISION,open_image,erase_text,TextRenderer
        report['imaging_revision']=IMAGING_REVISION
        inputs=run/'inputs';inputs.mkdir(exist_ok=True)
        for case in ('0002','0003','0004'):
            metadata=read(run/'forensic'/case/'metadata.json')
            source=(ROOT/metadata['source']).resolve();target=inputs/(case+'.jpg')
            if not target.exists():shutil.copy2(source,target)
            if file_digest(source)!=file_digest(target):raise ValueError('Acceptance source copy mismatch')
        options=Options.from_dict(read(run/'forensic/0002/options.json'))
        options.source=str(inputs);options.output=str(phase/'translated');options.skip_success=True
        options.quality=95
        # Exact source options, isolated outputs/database; no settings persistence.
        pages=['0002','0003','0004']
        if args.phase.endswith('cached'):
            for p in sorted((run/'forensic').glob('*/metadata.json')):
                data=read(p);case=p.parent.name;image=open_image(p.parent/'original.png')
                regions=[OCRResult(**r) for r in data['regions']];opts=Options.from_dict(read(p.parent/'options.json'))
                erased=erase_text(image,regions,opts);renderer=TextRenderer(opts)
                target=phase/case;target.mkdir();erased.save(target/'inpainted.png')
                renderer.render(erased,regions,data['translations']).save(target/'final.png')
                atomic_json(target/'layout.json',renderer.last_layout)
            report.update(overall='PASS',images=len(list(phase.glob('*/final.png'))),inference_calls=0)
        else:
            capture=Capture(phase,inputs)
            with instrument_transport(run,phase.name,pages),capture.install():
                if args.phase.endswith('batch'):
                    report.update(gui_batch(run,phase,inputs,options))
                else:
                    from core.whole_chapter import WholeChapterJob,AGYWholeChapterTranslator
                    workspace=ROOT/'output'/('stage3g-acceptance-'+run.name+'-'+phase.name)
                    if workspace.exists():raise FileExistsError('Whole acceptance workspace already exists')
                    translator=AGYWholeChapterTranslator(options)
                    job=WholeChapterJob(inputs,workspace,options=options,translator=translator)
                    prepared=job.run(allow_translation=False)
                    report['preparation']=prepared
                    if prepared.get('state')!='awaiting_translation':
                        raise RuntimeError('Whole preparation did not produce a confirmable manifest')
                    result=job.run(allow_translation=True,confirmed_manifest_hash=prepared['manifest_hash'])
                    report.update(pipeline=result,workspace=workspace.relative_to(ROOT).as_posix(),
                        overall='PASS' if result.get('completed')==3 and result.get('failed')==0 and result.get('fallback_original',0)==0 else 'FAIL')
            rendered=list(phase.glob('*/render.json'))
            if len(rendered)!=3 or any(not read(p)['content_intact'] or not read(p)['all_ids_accounted'] or read(p)['collisions'] for p in rendered):
                report.update(overall='FAIL',render_audit='Missing or invalid actual render artifacts')
            report['rendered_images']=len(rendered)
    except Exception as exc:
        report.update(error_code=getattr(exc,'code',type(exc).__name__),overall='FAIL')
    report['config_unchanged']=all(p.is_file() and file_digest(p)==h for p,h in protected.items())
    if not report['config_unchanged']:report['overall']='FAIL'
    report['ended']=now()
    ledger=read(run/'agy-budget.json')
    for entry in ledger['invocations']:
        if entry['purpose']==phase.name:
            entry['pipeline_result']=report['overall']
    atomic_json(run/'agy-budget.json',ledger)
    report['budget']=ledger
    atomic_json(phase/'report.json',report)
    if sys.stdout:print(json.dumps({'phase':args.phase,'overall':report['overall'],'used':report['budget']['used'],'remaining':report['budget']['remaining']}))
    return 0 if report['overall']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
