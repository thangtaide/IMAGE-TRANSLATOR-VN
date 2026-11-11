"""Explicit source/frozen settings acceptance and ledger-bounded live model QA.

GUI settings/DB are isolated under --run. Live fixtures contain only 你好.
No credentials/profile changes, automatic retries or original job resumption.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch, Mock
from types import SimpleNamespace

from core.paths import ROOT
from core.storage import atomic_json,file_digest
from core.types import Options
from providers.agy_models import MODELS,selection,identifier,label


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def gui_check(run,folder,reopen=None):
    from PySide6.QtWidgets import QApplication,QDialogButtonBox,QComboBox,QScrollArea
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtGui import QPalette
    from PySide6.QtTest import QTest
    from core.storage import save_options,load_options
    from ui.main_window import MainWindow
    from ui.settings_dialog import SettingsDialog
    from providers.agy import MODE
    settings=(run/reopen).resolve() if reopen else folder/'settings'
    if not settings.is_relative_to(run):raise ValueError('QA settings must stay under run')
    settings.mkdir(exist_ok=True)
    report=dict(frozen=bool(getattr(sys,'frozen',False)),translation_requests=0,private_settings=str(settings.relative_to(ROOT)),choices=[])
    with ExitStack() as stack:
        stack.enter_context(patch('core.storage.CONFIG',settings))
        stack.enter_context(patch('ui.main_window.CONFIG',settings))
        if not reopen:save_options(Options(mode=MODE,agy_model='gemini-3.8-flash-medium'))
        expected=load_options()
        app=QApplication.instance() or QApplication([])
        window=MainWindow(folder/'state.sqlite3',persist_settings=True)
        window.show();QTest.qWait(80)
        try:
            assert not hasattr(window,'ai_model') and not hasattr(window,'ai_effort')
            assert window.options.agy_model==expected.agy_model
            report['initial_model']=expected.agy_model
            report['scale']=window.devicePixelRatioF()
            if reopen:
                assert window.options.to_dict()['agy_effort']==expected.agy_effort
                choice,effective=selection(expected.agy_model,expected.agy_effort)
                dialog=SettingsDialog(window.options,window);dialog.show();QTest.qWait(50)
                assert dialog.ai_model.currentData()==choice.key
                assert dialog.ai_effort.currentData()==(effective or '')
                dialog.grab().save(str(folder/'reopened-settings.png'));dialog.reject()
                window.grab().save(str(folder/'reopened.png'))
                report.update(model=expected.agy_model,effort=expected.agy_effort,main_status=window.provider_info.text(),reopened=True)
                return report
            errors=[]
            def open_settings(action):
                def act():
                    d=next((w for w in app.topLevelWidgets() if isinstance(w,SettingsDialog) and w.isVisible()),None)
                    if d is None:errors.append('Dialog not visible');return
                    try:action(d)
                    except Exception as exc:errors.append(type(exc).__name__+': '+str(exc));d.reject()
                QTimer.singleShot(80,act)
                QTest.mouseClick(window.settings_button,Qt.LeftButton)
                assert not errors,errors
            def cancelled(d):
                assert d.ai_effort.currentData()=='medium'  # Preserve valid legacy config.
                d.ai_model.setCurrentIndex(d.ai_model.findData('claude-opus'));d.reject()
            before=(settings/'settings.json').read_bytes()
            open_settings(cancelled);assert (settings/'settings.json').read_bytes()==before
            report['cancel_preserved']=True
            for choice in MODELS:
                for effort,model in choice.variants:
                    def saved(d,choice=choice,effort=effort,model=model):
                        d.ai_model.setCurrentIndex(d.ai_model.findData(choice.key))
                        d.ai_effort.setCurrentIndex(d.ai_effort.findData(effort))
                        assert d.ai_effort.isEnabled()==(choice.key=='gemini-flash')
                        scroll=d.findChild(QScrollArea);scroll.ensureWidgetVisible(d.ai_group);QTest.qWait(30)
                        assert d.buttons.geometry().bottom()<d.height()
                        assert d.ai_model.width()>=d.ai_model.fontMetrics().horizontalAdvance(choice.label)+25
                        if model.endswith('-high'):
                            d.grab().save(str(folder/'settings.png'))
                            for name,combo in [('model-popup',d.ai_model),('effort-popup',d.ai_effort)]:
                                combo.showPopup();QTest.qWait(60)
                                palette=combo.view().palette()
                                assert palette.color(QPalette.Base).lightness()<128
                                assert palette.color(QPalette.Text).lightness()>128
                                combo.view().window().grab().save(str(folder/(name+'.png')));combo.hidePopup()
                        QTest.mouseClick(d.buttons.button(QDialogButtonBox.Ok),Qt.LeftButton)
                    open_settings(saved)
                    loaded=load_options();assert (loaded.agy_model,loaded.agy_effort)==(model,effort)
                    assert label(model,effort) in window.provider_info.text()
                    # Exercise the compiled provider from the GUI's saved options,
                    # without launching even a capability probe or generation.
                    from providers.agy import AGYProvider
                    provider=AGYProvider(loaded.agy_executable,model=loaded.agy_model,
                        effort=loaded.agy_effort,root=folder/'cli-command-check',probe_cli=False)
                    for whole in (False,True):
                        argv=provider.command(['r0'],60,whole=whole)
                        assert argv[argv.index('--model')+1]==model
                        if effort:assert argv[argv.index('--effort')+1]==effort
                        else:assert '--effort' not in argv
                    assert provider.requests_sent==0
                    report['choices'].append(dict(model=model,effort=effort or 'default',saved=True,batch_and_whole_argv=True))
            # Exercise actual Settings/Start/Continue clicks against an old
            # Gemini journal. Worker transport is explicitly a local fixture.
            def saved_sonnet(d):
                d.ai_model.setCurrentIndex(d.ai_model.findData('claude-sonnet'))
                QTest.mouseClick(d.buttons.button(QDialogButtonBox.Ok),Qt.LeftButton)
            open_settings(saved_sonnet)
            from PIL import Image
            from core.resume import ResumeStore
            from providers.agy import AGYProvider
            source=folder/'queue-input';source.mkdir()
            Image.new('RGB',(32,32),'white').save(source/'neutral.png')
            window.source.setText(str(source));window.output.setText(str(folder/'queue-export'))
            current=window.collect_options()
            old=Options.from_dict(current.to_dict());old.agy_model='gemini-3.8-flash-low';old.agy_effort='low'
            store=ResumeStore(window.active_cache_path)
            journal=store.pipeline(old,[source/'neutral.png'],None)
            journal['state']='paused_provider';store.save(journal)
            before=file_digest(store.root/(journal['id']+'.json'))
            queued=[]
            def worker_fixture(options,only,parent,**kwargs):
                queued.append((options,kwargs))
                return SimpleNamespace(event=Mock(),finished=Mock(),start=Mock(),isRunning=lambda:False)
            def forbidden(*args,**kwargs):raise AssertionError('GUI queue test must not invoke AGY')
            with patch('ui.main_window.ProcessingWorker',side_effect=worker_fixture),patch.object(AGYProvider,'_invoke',forbidden):
                window.resume_id=journal['id']
                QTest.mouseClick(window.start_button,Qt.LeftButton)
                assert queued[-1][0].agy_model=='claude-sonnet-4-6'
                assert queued[-1][1]['resume_id'] is None
                window.grab().save(str(folder/'start-sonnet.png'))
                window.set_running(False);window.resume_id=journal['id']
                window.provider_paused=True;window.provider_pending=[str(source/'neutral.png')]
                window.continue_button.setEnabled(True)
                QTest.mouseClick(window.continue_button,Qt.LeftButton)
                assert queued[-1][0].agy_model=='gemini-3.8-flash-low'
                assert queued[-1][1]['resume_id']==journal['id']
                assert load_options().agy_model=='claude-sonnet-4-6'
                assert window.options.agy_model=='claude-sonnet-4-6'
                assert file_digest(store.root/(journal['id']+'.json'))==before
            window.timer.stop();window.set_running(False);window.worker=None;window.update_mode()
            report['start_continue']=dict(start_model=queued[0][0].agy_model,start_resume_id=queued[0][1]['resume_id'],
                continue_model=queued[1][0].agy_model,continue_uses_saved_journal=True,
                saved_preference=load_options().agy_model,old_journal_preserved=True,mock_worker=True,agy_invocations=0)
            window.grab().save(str(folder/'main.png'))
            report['main_status']=window.provider_info.text()
            report['model']=window.options.agy_model;report['effort']=window.options.agy_effort
            assert window.provider_info.fontMetrics().horizontalAdvance(window.provider_info.text())<window.width()
        finally:window.close();app.processEvents()
    return report


def live_check(run,folder,key,effort,whole=False):
    from PIL import Image,ImageDraw,ImageFont
    import numpy as np
    from core.ocr import PaddleOCREngine
    from core.pipeline import TranslationService,ProcessingManager,JobControl
    from core.storage import TranslationCache,digest
    from providers.agy import AGYProvider,MODE
    from scripts.acceptance_readability import instrument_transport
    model=identifier(key,effort);inputs=folder/'inputs';inputs.mkdir()
    source=inputs/'0001.png';image=Image.new('RGB',(800,240),'white')
    ImageDraw.Draw(image).text((80,70),'你好',font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',64),fill='black')
    image.save(source)
    source_sha=file_digest(source)
    opts=Options(source=str(inputs),output=str(folder/'export'),mode=MODE,agy_model=model,agy_effort=effort,agy_max_requests=1)
    ocr=PaddleOCREngine();regions,warnings=ocr.recognize(np.array(image),'zh',opts.confidence,opts.tile_size,opts.reading_direction,lambda:None)
    if [r.text for r in regions]!=['你好']:raise AssertionError('Unexpected fixture OCR; no request sent')
    reported=[];argvs=[]
    original=AGYProvider._invoke
    def observed(p,argv,payload,*args,**kwargs):
        result=original(p,argv,payload,*args,**kwargs)
        if payload is not None:
            argvs.append(dict(model=argv[argv.index('--model')+1],effort=argv[argv.index('--effort')+1] if '--effort' in argv else None))
            for line in result[1].splitlines():
                try:e=json.loads(line)
                except ValueError:continue
                if e.get('event')=='init':
                    value=e.get('init',{}).get('model')
                    if value==model:reported.append(value)
        return result
    result={}
    started=read(run/'agy-budget.json')['used']
    # Tracker wraps the real observer, not a fixture response supplier.
    with patch.object(AGYProvider,'_invoke',observed),instrument_transport(run,folder.name,['0001.png']):
        if whole:
            from core.whole_chapter import WholeChapterJob,AGYWholeChapterTranslator
            workspace=ROOT/'output'/('stage3g-model-qa-'+run.name+'-'+folder.name)
            job=WholeChapterJob(inputs,workspace,options=opts,translator=AGYWholeChapterTranslator(opts),ocr=ocr)
            prepared=job.run()
            assert prepared['state']=='awaiting_translation',prepared.get('error_code')
            result=job.run(allow_translation=True,confirmed_manifest_hash=prepared['manifest_hash'])
            outputs=list((workspace/'rendered').glob('*.png'))
        else:
            cache=TranslationCache(folder/'state.sqlite3')
            cache.put('ocr',digest([file_digest(source),ocr.identity('zh'),'zh',opts.confidence,opts.tile_size,opts.reading_direction]),dict(regions=[asdict(r) for r in regions],warnings=warnings))
            events=[];service=TranslationService(opts,cache,JobControl())
            manager=ProcessingManager(opts,cache,service=service,ocr=ocr,emit=events.append,diagnostic_root=folder/'diagnostics')
            try:result=manager.run()
            finally:cache.close()
            result['provider_error']=next((e['code'] for e in events if e.get('type')=='provider_paused'),None)
            outputs=list((folder/'export').glob('*.png'))
    status='PASS' if result.get('completed')==1 and result.get('state')=='done' and reported==[model] else 'FAIL'
    code=result.get('provider_error') or result.get('error_code')
    if code in ('QUOTA_EXCEEDED','RATE_LIMITED'):status='BLOCKED_BY_QUOTA'
    if code=='RESPONSE_BLOCKED':status='BLOCKED_BY_PROVIDER'
    ledger=read(run/'agy-budget.json')
    for entry in ledger['invocations']:
        if entry['number']>started:entry.update(acceptance_result=status,error_code=code,cost='UNKNOWN')
    atomic_json(run/'agy-budget.json',ledger)
    return dict(status=status,model=model,effort=effort or 'default',whole=whole,request_count=ledger['used']-started,
        argv_selections=argvs,reported_models=reported,effort_evidence='CLI flag plus catalog ID; init does not report a separate effort metric',
        completed=result.get('completed',0),state=result.get('state'),error_code=code,outputs=[str(p.relative_to(ROOT)) for p in outputs],source_unchanged=file_digest(source)==source_sha)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--phase',required=True)
    parser.add_argument('--live',choices=[c.key for c in MODELS]);parser.add_argument('--effort',default='')
    parser.add_argument('--whole',action='store_true');parser.add_argument('--reopen-settings',type=Path)
    args=parser.parse_args();run=(ROOT/args.run).resolve()
    if not run.is_relative_to((ROOT/'output').resolve()) or not args.phase.replace('-','').isalnum():parser.error('Managed QA directory required')
    folder=run/args.phase;folder.mkdir(exist_ok=False)
    report=dict(status='FAIL',frozen=bool(getattr(sys,'frozen',False)))
    try:
        from core.runtime import prepare_inference_runtime
        prepare_inference_runtime()
        if args.live:report.update(live_check(run,folder,args.live,args.effort,args.whole))
        else:report.update(gui_check(run,folder,args.reopen_settings));report['status']='PASS'
    except Exception as exc:
        import traceback
        report.update(error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc())
    atomic_json(folder/'report.json',report)
    if sys.stdout:print(json.dumps({k:report[k] for k in ('status','frozen','model') if k in report},ensure_ascii=True))
    return 0 if report['status']=='PASS' else 1
