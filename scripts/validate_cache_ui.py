"""Explicit source/frozen cache/UI acceptance; real pipelines, bounded AGY transport.

All writes and confirmed cleanup target the requested new acceptance directory.
Pipeline runs use real inference. The GUI-only policy smoke uses explicit local
target fixtures and never invokes model transport.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager, closing
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

from core.paths import ROOT
from core.storage import atomic_json,file_digest


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def online_policy_smoke(folder):
    """Exercise the actual source/frozen guard and configured CLI flags locally."""
    from types import SimpleNamespace
    from core.storage import load_options
    from core.pipeline import TranslationService,JobControl,NumericMismatchError
    from providers.agy import AGYProvider,parse_response
    from providers.online import ProviderSuspended
    class MemoryCache:
        def __init__(self):self.values={}
        def get(self,kind,key):return self.values.get((kind,key))
        def put(self,kind,key,value):self.values[kind,key]=value
    options=load_options()
    provider=AGYProvider(options.agy_executable,model=options.agy_model,probe_cli=False,root=folder/'policy-cli')
    def no_transport(*args,**kwargs):raise AssertionError('GUI-only policy smoke must not call AGY')
    provider._invoke=no_transport
    try:
        service=TranslationService(options,MemoryCache(),JobControl())
        target=service._translate_using(provider,'归零24H','zh','policy',raw_target='Về 0, 24H')
        assert target=='Về 0, 24H' and not service.last_attempt['content_validation_applied']
        assert service._translate_using(provider,'15','zh','signed-cache',raw_target='-16')=='-16'
        assert service._translate_using(provider,'15','zh','signed-cache')=='-16'
        try:service._translate_using(SimpleNamespace(online=False,identity='offline-fixture'),'24','zh','offline',raw_target='0,24')
        except NumericMismatchError:pass
        else:raise AssertionError('Offline numeric guard changed')
        argv=provider.command(['policy'],10)
        assert argv[argv.index('--effort')+1]==provider.effort and provider.requests_sent==0
        error_codes=[]
        for error,expected in [('http2: server sent GOAWAY; server_shutting_down','NETWORK_ERROR'),
                               ('Your previous response was blocked by content safety filters','RESPONSE_BLOCKED')]:
            payload=(json.dumps(dict(event='result',result=dict(status='ERROR',error=error)))+'\n').encode()
            try:parse_response(payload,['policy'],0)
            except ProviderSuspended as exc:
                assert exc.code==expected
                error_codes.append(exc.code)
            else:raise AssertionError('Provider error accepted as translation')
        return dict(online_content_trusted=True,trusted_signed_cache_reused=True,offline_guard_preserved=True,model=provider.model,
            effort=provider.effort,translation_requests=0,target_fixture=True,provider_error_codes=error_codes)
    finally:provider.close()


def wait_for(predicate,timeout=420):
    from PySide6.QtCore import QEventLoop,QTimer
    if predicate():return
    loop=QEventLoop();timer=QTimer();timer.setInterval(25)
    timer.timeout.connect(lambda:loop.quit() if predicate() else None)
    deadline=QTimer();deadline.setSingleShot(True);deadline.timeout.connect(loop.quit)
    timer.start();deadline.start(int(timeout*1000));loop.exec();timer.stop();deadline.stop()
    if not predicate():raise TimeoutError('CACHE_UI_ACCEPTANCE_DEADLINE')


def dump(db):
    with closing(sqlite3.connect(Path(db).as_uri()+'?mode=ro',uri=True)) as connection:
        return list(connection.iterdump())


@contextmanager
def observe():
    from core.ocr import PaddleOCREngine
    from core.storage import TranslationCache
    from providers.offline import CTranslate2TranslationProvider
    import core.pipeline as pipeline
    from core.imaging import TextRenderer
    originals=(PaddleOCREngine.recognize,TranslationCache.get,pipeline.erase_text,TextRenderer.render,
        CTranslate2TranslationProvider.translate)
    counts={'ocr':0,'translation':0,'inpaint':0,'render':0,'cache_reads':[]}
    def ocr(*args,**kwargs):counts['ocr']+=1;return originals[0](*args,**kwargs)
    def get(cache,kind,key):
        value=originals[1](cache,kind,key)
        counts['cache_reads'].append({'database':str(cache.path),'kind':kind,'hit':value is not None})
        return value
    def erase(*args,**kwargs):counts['inpaint']+=1;return originals[2](*args,**kwargs)
    def render(*args,**kwargs):counts['render']+=1;return originals[3](*args,**kwargs)
    def translate(*args,**kwargs):counts['translation']+=1;return originals[4](*args,**kwargs)
    PaddleOCREngine.recognize=ocr;TranslationCache.get=get;pipeline.erase_text=erase
    TextRenderer.render=render;CTranslate2TranslationProvider.translate=translate
    try:yield counts
    finally:
        PaddleOCREngine.recognize,TranslationCache.get,pipeline.erase_text,TextRenderer.render,CTranslate2TranslationProvider.translate=originals


def click(window,button):
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    window.centralWidget().ensureWidgetVisible(button);QTest.qWait(60)
    QTest.mouseClick(button,Qt.LeftButton)


def snapshots(window,folder):
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    scroll=window.centralWidget();scroll.verticalScrollBar().setValue(0);QTest.qWait(80)
    window.grab().save(str(folder/'gui-top.png'))
    scroll.ensureWidgetVisible(window.fresh_button);QTest.qWait(60);window.grab().save(str(folder/'gui-actions.png'))
    scroll.ensureWidgetVisible(window.table);QTest.qWait(60);window.grab().save(str(folder/'gui-progress.png'))
    scroll.ensureWidgetVisible(window.folder_more);QTest.qWait(60)
    window.folder_more.menu().popup(window.folder_more.mapToGlobal(window.folder_more.rect().bottomLeft()))
    QTest.qWait(100);window.folder_more.menu().grab().save(str(folder/'menu.png'));window.folder_more.menu().hide()
    window.mode.showPopup();QTest.qWait(100)
    window.mode.view().window().grab().save(str(folder/'combo.png'));window.mode.hidePopup()
    before=window.size();window.resize(660,580);QTest.qWait(100)
    scroll.ensureWidgetVisible(window.fresh_button);window.grab().save(str(folder/'gui-small.png'))
    clipped=[]
    for button in [window.start_button,window.fresh_button,window.pause_button,window.continue_button,
            window.cancel_button,window.open_button,window.cache_open_button,window.cache_manager_button]:
        if button.width()<button.fontMetrics().horizontalAdvance(button.text())+20:clipped.append(button.text())
    window.resize(before)
    return {'device_pixel_ratio':window.devicePixelRatioF(),'scale_factor':os.environ.get('QT_SCALE_FACTOR','default'),
        'clipped_button_labels':clipped,'scroll_available':scroll.verticalScrollBar().maximum()>0}


def pipeline(window,run,folder,frozen,use_agy):
    from PySide6.QtCore import QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QMessageBox
    from ui.fresh_run import FreshRunDialog
    from ui.cache_manager import CacheManagerDialog
    from ui.workers import ProcessingWorker
    from scripts.acceptance_readability import instrument_transport
    from contextlib import nullcontext
    from unittest.mock import patch
    app=QApplication.instance();events=[];heartbeat=[]
    timer=QTimer();timer.setInterval(20);timer.timeout.connect(lambda:heartbeat.append(1));timer.start()
    result={}
    def run_step(name,fresh=False):
        before=read(run/'agy-budget.json')['used']
        real_start=ProcessingWorker.start
        def observed_start(worker,*args,**kwargs):
            def event(value):
                events.append(value)
                safe={k:value[k] for k in ('type','stage','completed','skipped','failed','state') if k in value}
                with (folder/'events.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(safe)+'\n')
            worker.event.connect(event)
            return real_start(worker,*args,**kwargs)
        with observe() as counts,instrument_transport(run,name,['0003']) if use_agy else nullcontext(),patch.object(ProcessingWorker,'start',observed_start):
            if fresh:
                def confirm():
                    dialogs=[w for w in app.topLevelWidgets() if isinstance(w,FreshRunDialog) and w.isVisible()]
                    if not dialogs or not dialogs[0].confirm.isEnabled():QTimer.singleShot(25,confirm);return
                    d=dialogs[0];d.grab().save(str(folder/'confirm.png'))
                    result['no_agy_before_confirmation']=read(run/'agy-budget.json')['used']==before
                    result['planned_output']=d.plan['output'];d.confirm.click()
                QTimer.singleShot(25,confirm);click(window,window.fresh_button)
            else:click(window,window.start_button)
            worker=window.worker
            if worker is None:raise AssertionError('No real Qt processing worker')
            wait_for(lambda:not worker.isRunning())
            app.processEvents()
        terminal=[e for e in events if e.get('type')=='finished']
        if not terminal:raise AssertionError('No real pipeline completion event')
        terminal=terminal[-1];assert terminal['state']=='done' and terminal['failed']==0 and terminal['fallback_original']==0,terminal['state']
        value=dict(counts,pipeline={k:terminal[k] for k in ['state','total','completed','skipped','failed','fallback_original']},
            agy_invocations=read(run/'agy-budget.json')['used']-before)
        events.clear();return value
    result['normal']=run_step('exe-normal' if frozen else 'source-normal')
    assert result['normal']['pipeline']['completed']==1 and result['normal']['ocr']==1
    result['cached']=run_step('exe-cached' if frozen else 'source-cached')
    assert result['cached']['pipeline']['skipped']==1 and result['cached']['ocr']==0 and result['cached']['render']==0
    old_dump=dump(window.cache_path);old_outputs={p:file_digest(p) for p in Path(window.output.text()).glob('*') if p.is_file()}
    result['fresh']=run_step('exe-fresh' if frozen else 'source-fresh',fresh=True)
    assert result['fresh']['pipeline']['completed']==1 and result['fresh']['pipeline']['skipped']==0
    assert result['fresh']['ocr']==1 and result['fresh']['inpaint']==1 and result['fresh']['render']==1
    if use_agy:assert result['normal']['agy_invocations']==1 and result['fresh']['agy_invocations']==1 and result['cached']['agy_invocations']==0
    else:assert result['fresh']['translation']>=1
    assert window.active_cache_path!=window.cache_path and window.output.text()==result['planned_output']
    assert all(Path(e['database'])==window.active_cache_path for e in result['fresh']['cache_reads'])
    result['old_run_unchanged']=dump(window.cache_path)==old_dump and all(file_digest(p)==h for p,h in old_outputs.items())
    assert result['old_run_unchanged'] and result['no_agy_before_confirmation']
    result['run_id']=window.active_run_id;result['cache_database']=str(window.active_cache_path)
    assert window.run_registry.active(window.collect_options())['run_id']==window.active_run_id
    result['saved_namespace_discovery']=True
    result['fresh_outputs']=[p.relative_to(ROOT).as_posix() for p in Path(window.output.text()).glob('*.jpg')]
    if not result['fresh_outputs']:result['fresh_outputs']=[p.relative_to(ROOT).as_posix() for p in Path(window.output.text()).glob('*.png')]
    snapshots(window,folder)
    # Open actual Windows folder only in frozen acceptance, no patched desktop service.
    if frozen:result['open_cache_directory']=window.open_cache();assert result['open_cache_directory']
    stage={'value':'inventory'};errors=[]
    def cache_actions():
        dialogs=[w for w in app.topLevelWidgets() if isinstance(w,CacheManagerDialog) and w.isVisible()]
        if not dialogs:QTimer.singleShot(40,cache_actions);return
        dialog=dialogs[0]
        try:
            if stage['value']=='prompt':
                prompts=[w for w in app.topLevelWidgets() if isinstance(w,QMessageBox) and w.isVisible()]
                if prompts:
                    prompts[0].button(QMessageBox.Yes).click();stage['value']='pruned'
                QTimer.singleShot(40,cache_actions);return
            if dialog.task_pending or (dialog.task and dialog.task.isRunning()):QTimer.singleShot(40,cache_actions);return
            if stage['value']=='inventory':
                dialog.table.selectRow(0);assert not dialog.prune.isEnabled()
                row=next(i for i,r in enumerate(dialog.records) if r.get('run_id')==window.active_run_id)
                dialog.table.selectRow(row);assert dialog.prune.isEnabled() and not dialog.render.isEnabled()
                dialog.grab().save(str(folder/'cache-manager.png'));stage['value']='backed-up';dialog.backup.click()
            elif stage['value']=='backed-up':
                assert 'Backup:' in dialog.summary.text();stage['value']='prompt'
                QTimer.singleShot(40,cache_actions);dialog.prune.click();return
            elif stage['value']=='pruned':
                assert 'Số mục dọn:' in dialog.summary.text();result['cache_cleanup']=dialog.summary.text();dialog.reject();return
        except Exception as exc:
            errors.append(type(exc).__name__+': '+str(exc));dialog.reject();return
        QTimer.singleShot(40,cache_actions)
    QTimer.singleShot(40,cache_actions);click(window,window.cache_manager_button)
    assert not errors,errors
    assert dump(window.cache_path)==old_dump and all(file_digest(p)==h for p,h in old_outputs.items())
    with closing(sqlite3.connect(window.active_cache_path)) as connection:
        assert connection.execute("select count(*) from cache where kind in ('ocr','translation')").fetchone()[0]==0
        assert connection.execute('select count(*) from items').fetchone()[0]==1
    result['heartbeat']=len(heartbeat);timer.stop();assert result['heartbeat']>10
    return result


def resume_check(window,folder):
    """Cancel after real OCR, reopen real widgets, resume the same isolated namespace."""
    from unittest.mock import patch
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from ui.fresh_run import FreshRunDialog
    from ui.main_window import MainWindow
    from ui.workers import ProcessingWorker
    from core.ocr import PaddleOCREngine
    from core.types import Options
    app=QApplication.instance();events=[];real_start=ProcessingWorker.start;real_ocr=PaddleOCREngine.recognize
    def started(worker,*args,**kwargs):
        worker.event.connect(events.append);return real_start(worker,*args,**kwargs)
    def cancelled_ocr(*args,**kwargs):
        result=real_ocr(*args,**kwargs)
        window.worker.control.cancel()  # Same thread-safe control used by the Cancel button.
        return result
    def confirm():
        dialogs=[d for d in app.topLevelWidgets() if isinstance(d,FreshRunDialog) and d.isVisible()]
        if not dialogs or not dialogs[0].confirm.isEnabled():QTimer.singleShot(25,confirm);return
        dialogs[0].confirm.click()
    with patch.object(ProcessingWorker,'start',started),patch.object(PaddleOCREngine,'recognize',cancelled_ocr):
        QTimer.singleShot(25,confirm);click(window,window.fresh_button)
        wait_for(lambda:not window.worker.isRunning());app.processEvents()
    cancelled=next(e for e in reversed(events) if e.get('type')=='finished')
    assert cancelled['state']=='cancelled' and cancelled['completed']==0
    run_id=window.active_run_id;database=window.active_cache_path;base=window.cache_path
    options=Options.from_dict(window.collect_options().to_dict());window.close();events.clear()
    # Inject only the saved QA options, not OCR/translation results or user config.
    with patch('ui.main_window.load_options',return_value=options):
        reopened=MainWindow(base,persist_settings=False)
    reopened.show();reopened.resume_previous.click()
    assert reopened.active_cache_path==database and reopened.active_run_id==run_id and reopened.resume_id
    with observe() as counts,patch.object(ProcessingWorker,'start',started):
        click(reopened,reopened.continue_button);wait_for(lambda:not reopened.worker.isRunning());app.processEvents()
    terminal=next(e for e in reversed(events) if e.get('type')=='finished')
    assert terminal['state']=='done' and terminal['completed']==1 and terminal['failed']==0
    assert counts['ocr']==0 and counts['translation']>=1 and counts['render']==1
    reopened.centralWidget().ensureWidgetVisible(reopened.table);reopened.grab().save(str(folder/'resume-after-reopen.png'))
    reopened.close()
    return {'state_before':'cancelled','state_after':'done','run_id':run_id,'database':str(database),
        'same_namespace':True,'ocr_on_resume':counts['ocr'],'translation_on_resume':counts['translation'],
        'render_on_resume':counts['render'],'configuration':'saved acceptance options; no user config modified',
        'cancellation':'JobControl.cancel after the actual OCR returned; actual OCR cache retained'}


def cached_agy_check(window,run,folder):
    """Replay genuine completed receipts; budget guard blocks every generation."""
    from unittest.mock import patch
    from PySide6.QtWidgets import QApplication
    from ui.workers import ProcessingWorker
    from scripts.acceptance_readability import instrument_transport
    app=QApplication.instance();events=[];real_start=ProcessingWorker.start
    before=read(run/'agy-budget.json')['used']
    def started(worker,*args,**kwargs):
        worker.event.connect(events.append);return real_start(worker,*args,**kwargs)
    with observe() as counts,instrument_transport(run,'exe-cached-agy-recheck',['0002','0003','0004']),patch.object(ProcessingWorker,'start',started):
        click(window,window.start_button)
        wait_for(lambda:window.worker and not window.worker.isRunning() and window.start_button.isEnabled() and
            not window.cancel_button.isEnabled(),120)
    final=next(e for e in reversed(events) if e.get('type')=='finished')
    assert final['state']=='done' and final['skipped']==3 and final['failed']==0
    assert counts['ocr']==0 and counts['render']==0 and read(run/'agy-budget.json')['used']==before
    window.centralWidget().ensureWidgetVisible(window.table);window.grab().save(str(folder/'cached-agy-idle.png'))
    return {'overall':'PASS','skipped':3,'ocr_calls':0,'render_calls':0,'new_agy_generations':0,
        'buttons_restored':window.start_button.isEnabled() and not window.cancel_button.isEnabled(),
        'seed':'SQLite backup of the completed real three-image AGY run; same input/options/output',
        'cache_reads':counts['cache_reads']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--phase',required=True);parser.add_argument('--gui-only',action='store_true')
    parser.add_argument('--offline',action='store_true',help='Exercise frozen OCR/MT without any AGY generation')
    parser.add_argument('--cached-agy-only',action='store_true',help='Check real AGY cache/idle widgets without any new generation')
    args=parser.parse_args();run=(ROOT/args.run).resolve()
    if args.cached_agy_only and (args.offline or args.gui_only):parser.error('Cached AGY check has its own fixed scope')
    if not run.is_relative_to((ROOT/'output').resolve()) or not args.phase.replace('-','').isalnum():parser.error('New acceptance output required')
    folder=run/args.phase;folder.mkdir(exist_ok=False)
    frozen=bool(getattr(sys,'frozen',False));report={'overall':'FAIL','frozen':frozen,'mock':False}
    window=None;started_used=read(run/'agy-budget.json')['used']
    import faulthandler
    stack_file=(folder/'stacks.log').open('w',encoding='utf-8')
    faulthandler.dump_traceback_later(60,repeat=True,file=stack_file)
    try:
        assert args.phase.startswith('exe')==frozen
        from core.runtime import prepare_inference_runtime
        prepare_inference_runtime()
        from PySide6.QtWidgets import QApplication
        from PySide6.QtTest import QTest
        from core.types import Options
        from providers.agy import MODE
        from ui.main_window import MainWindow
        app=QApplication.instance() or QApplication([])
        use_agy=frozen and not args.offline
        inputs=run/('inputs-agy' if use_agy else 'inputs-offline');assert inputs.is_dir()
        saved=None
        if args.cached_agy_only:
            with closing(sqlite3.connect((run/'exe-batch/state.sqlite3').as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(folder/'state.sqlite3')) as dst:
                src.backup(dst)
                saved=Options.from_dict(json.loads(dst.execute('SELECT options FROM jobs ORDER BY updated DESC LIMIT 1').fetchone()[0]))
        window=MainWindow(folder/'state.sqlite3',persist_settings=False)
        from core.storage import load_options
        window.options=Options(source=str(inputs),output=str(folder/'normal'),language='zh',mode=MODE if use_agy else 'Offline',
            foreground='white',alignment='left',font_min=10,agy_model=load_options().agy_model)
        if saved:window.options=saved
        window.source.setText(window.options.source);window.output.setText(window.options.output)
        window.language.setCurrentIndex(window.language.findData('zh'));window.mode.setCurrentIndex(window.mode.findData(window.options.mode))
        window.online_provider.setCurrentText(window.options.online_provider);window.offline_provider.setCurrentText(window.options.offline_provider)
        window.recursive.setChecked(window.options.recursive);window.structure.setChecked(window.options.preserve_structure);window.skip.setChecked(True)
        window.show();QTest.qWait(200)
        if args.cached_agy_only:report['cached_agy']=cached_agy_check(window,run,folder)
        elif args.gui_only:
            report['translation_policy']=online_policy_smoke(folder)
            report['gui']=snapshots(window,folder);assert not report['gui']['clipped_button_labels']
            from ui.fresh_run import FreshRunDialog
            dialog=FreshRunDialog(window.collect_options(),window.run_registry,window)
            dialog.show();wait_for(lambda:not dialog.counter.isRunning(),10);app.processEvents()
            dialog.grab().save(str(folder/'confirm.png'))
            assert dialog.confirm.isEnabled() and dialog.buttons.geometry().bottom()<=dialog.height()
            dialog.reject()
        else:
            report['pipeline']=pipeline(window,run,folder,frozen,use_agy)
            if not use_agy:report['resume']=resume_check(window,folder)
        report['mode']=window.options.mode
        report['overall']='PASS'
    except Exception as exc:
        import traceback
        report.update(error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc())
    finally:
        if window and (not window.worker or not window.worker.isRunning()):window.close()
        ledger=read(run/'agy-budget.json')
        for entry in ledger['invocations']:
            if entry['number']>started_used:entry['acceptance_result']=report['overall']
        atomic_json(run/'agy-budget.json',ledger);report['agy_used']=ledger['used']
        atomic_json(folder/'report.json',report)
        faulthandler.cancel_dump_traceback_later();stack_file.close()
    if sys.stdout:print(json.dumps({k:report[k] for k in ['overall','frozen','agy_used']}))
    return 0 if report['overall']=='PASS' else 1
