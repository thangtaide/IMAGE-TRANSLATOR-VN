"""Isolated source/EXE smoke and a persistent, three-generation Qoder QA budget."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from core.paths import ROOT
from core.storage import atomic_json, file_digest
from core.types import Options, OCRResult


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def gui(folder):
    from PySide6.QtWidgets import QApplication, QDialogButtonBox
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPalette
    from PySide6.QtTest import QTest
    from core.storage import save_options, load_options
    from ui.main_window import MainWindow
    from ui.settings_dialog import SettingsDialog
    from ui.whole_chapter import WholeChapterDialog
    app=QApplication.instance() or QApplication([])
    config=folder/'config';config.mkdir()
    with patch('core.storage.CONFIG',config),patch('ui.main_window.CONFIG',config):
        save_options(Options(mode='AI Gemini AGY'))
        window=MainWindow(folder/'state.sqlite3');window.show();QTest.qWait(50)
        try:
            before=(config/'settings.json').read_bytes()
            d=SettingsDialog(window.options,window);d.show();d.ai_source.setCurrentIndex(d.ai_source.findData('qoder'))
            d.qoder_model.setCurrentIndex(d.qoder_model.findData('Ultimate'));d.reject()
            assert (config/'settings.json').read_bytes()==before
            d=SettingsDialog(window.options,window);d.show();d.ai_source.setCurrentIndex(d.ai_source.findData('qoder'))
            d.qoder_model.setCurrentIndex(d.qoder_model.findData('Ultimate'))
            QTest.qWait(30);d.grab().save(str(folder/'settings.png'))
            d.qoder_model.showPopup();QTest.qWait(40)
            assert d.qoder_model.view().palette().color(QPalette.Base).lightness()<128
            d.qoder_model.view().window().grab().save(str(folder/'models.png'));d.qoder_model.hidePopup()
            QTest.mouseClick(d.buttons.button(QDialogButtonBox.Ok),Qt.LeftButton)
            save_options(window.options);window.update_mode()
            assert 'Qoder' in window.provider_info.text()
            assert load_options().qoder_model=='Ultimate'
            reopened=SettingsDialog(load_options(),window)
            assert reopened.ai_source.currentData()=='qoder' and reopened.qoder_model.currentData()=='Ultimate'
            reopened.reject()
            whole=WholeChapterDialog(window.options,window,translator_kind='qoder');whole.show();QTest.qWait(30)
            assert whole.translator.currentData()=='qoder' and 'Qoder' in whole.note.text()
            whole.grab().save(str(folder/'whole.png'));whole.close()
            window.grab().save(str(folder/'main.png'))
            return dict(status='PASS',settings_save_cancel_reopen=True,dark_popup=True,
                whole_provider=True,scale=window.devicePixelRatioF(),generation_invocations=0)
        finally:
            window.close();app.processEvents()


class FixtureOCR:
    def identity(self,language):return 'QODER-QA-OCR-FIXTURE'
    def recognize(self,*args):
        return [OCRResult('你好',[[65,65],[320,65],[320,175],[65,175]],.99,'zh')],[]


def images(folder):
    from PIL import Image, ImageDraw, ImageFont
    source=folder/'input';source.mkdir()
    font=ImageFont.truetype(str(Path(os.environ['WINDIR'])/'Fonts/msyh.ttc'),64)
    for n,text in enumerate(('你好','谢谢','再见'),1):
        image=Image.new('RGB',(800,260),'white')
        ImageDraw.Draw(image).text((70,70),text,font=font,fill='black');image.save(source/f'{n:02d}.png')
    return source


def pipeline(run,folder,live,model='Ultimate'):
    from core.pipeline import ProcessingManager
    from core.storage import TranslationCache
    from core.whole_chapter import WholeChapterJob, QoderWholeChapterTranslator
    from providers.qoder import QoderProvider, preflight
    from providers.qoder_process import run_process
    source=images(folder);hashes={p.name:file_digest(p) for p in source.glob('*.png')}
    opts=Options(source=str(source),output=str(folder/'rendered'),mode='AI Gemini AGY',ai_provider='qoder',
        qoder_model=model,agy_max_requests=3,agy_context=False)
    traces=[]
    def runner(argv,payload,cwd,timeout,cancelled=lambda:False):
        packet=json.loads(payload)
        traces.append(dict(images=len(packet['images']),regions=sum(len(p['regions']) for p in packet['images']),
            batch_id=packet['batch_id'],cwd_outside_project=not cwd.is_relative_to(ROOT)))
        if live:
            ledger=read(run/'live-ledger.json')
            if ledger['generation_invocations']>=3:raise AssertionError('QODER_QA_BUDGET_EXHAUSTED')
            ledger['generation_invocations']+=1;atomic_json(run/'live-ledger.json',ledger)
            result=run_process(argv,payload,cwd,timeout,cancelled)
            (folder/'cli-stdout.json').write_bytes(result[1]);(folder/'cli-stderr.txt').write_bytes(result[2])
            return result
        result=json.loads(payload)
        for page in result['images']:
            for row in page['regions']:row['text']='Xin chào.'
        return 0,json.dumps(dict(type='result',subtype='success',is_error=False,num_turns=1,
            stop_reason='end_turn',permission_denials=[],modelUsage={'smodel' if model=='Sonus' else 'ultimate':{}},result=json.dumps(result))).encode(),b''
    cache=TranslationCache(folder/'state.sqlite3');events=[]
    try:
        with patch('providers.qoder.QoderProvider',side_effect=lambda *a,**kw:QoderProvider(*a,**kw,runner=runner,
                probe=None if live else dict(models=[model],plugins={}))):
            first=ProcessingManager(opts,cache=cache,ocr=None if live else FixtureOCR(),emit=events.append,
                diagnostic_root=folder/'diagnostics').run()
            atomic_json(folder/'batch-result.json',first)
            assert first['state']=='done' and first['completed']==3,first
            assert len(traces)==1 and traces[0]['images']==3,traces
            resume_id=next(e['resume_id'] for e in events if e.get('type')=='resume_ready')
            second=ProcessingManager(opts,cache=cache,ocr=None if live else FixtureOCR(),resume_id=resume_id,
                diagnostic_root=folder/'diagnostics').run()
            assert second['skipped']==3 and len(traces)==1,second
        metadata=[json.loads(r[0]) for r in cache.connection.execute("SELECT value FROM cache WHERE kind='metadata'")]
        assert len(metadata)==3 and all(m['translations'] for m in metadata)
        assert hashes=={p.name:file_digest(p) for p in source.glob('*.png')}
        report=dict(status='PASS',live=live,model=model,batch=first,resume=second,invocations=traces,
            source_unchanged=True,real_ocr=live,outputs=[str(p.relative_to(ROOT)) for p in (folder/'rendered').glob('*.png')])
        if not live:
            from uuid import uuid4
            work=ROOT/'output'/('stage3g-qoder-smoke-'+folder.name+'-'+uuid4().hex[:8])
            adapter=QoderWholeChapterTranslator(opts,runner=runner,probe=dict(models=[model],plugins={}))
            job=WholeChapterJob(source,work,options=opts,translator=adapter,ocr=FixtureOCR())
            prep=job.run();assert prep['state']=='awaiting_translation',prep
            result=job.run(allow_translation=True,confirmed_manifest_hash=prep['manifest_hash'])
            assert result['state']=='done' and result['completed']==3,result
            resumed=job.run();assert resumed['skipped']==3,resumed
            report.update(whole=result,whole_resume=resumed)
        return report
    finally:
        atomic_json(folder/'invocations.json',traces);cache.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--phase',required=True);parser.add_argument('--action',choices=('gui','fixture','live'),default='gui')
    parser.add_argument('--model',choices=('Ultimate','Sonus'),default='Ultimate')
    args=parser.parse_args();run=(ROOT/args.run).resolve()
    if not run.is_relative_to(ROOT/'output') or not args.phase.replace('-','').isalnum():parser.error('Isolated QA run required')
    folder=run/args.phase;folder.mkdir(exist_ok=False)
    report=dict(status='FAIL',frozen=bool(getattr(sys,'frozen',False)))
    try:
        from core.runtime import prepare_inference_runtime
        prepare_inference_runtime()
        report.update(gui(folder) if args.action=='gui' else pipeline(run,folder,args.action=='live',args.model))
    except Exception as exc:
        report.update(error_code=getattr(exc,'code',type(exc).__name__))
        if isinstance(exc,AssertionError):report['assertion']=str(exc)[:2000]
    atomic_json(folder/'report.json',report)
    if sys.stdout:print(json.dumps(report,ensure_ascii=True))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
