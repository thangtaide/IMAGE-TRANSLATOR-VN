"""Real Qt button workflow and local inference, isolated cache, synthetic source."""
from __future__ import annotations
import json
import os
import shutil
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

if not getattr(sys,'frozen',False):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.paths import ROOT, CONFIG


def main() -> int:
    from core.runtime import prepare_inference_runtime
    prepare_inference_runtime()
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton, QSlider
    from ui.main_window import MainWindow
    from ui.preview import PreviewDialog
    from ui.models_dialog import ModelManagerDialog
    from ui.settings_dialog import SettingsDialog
    from core.storage import file_digest
    from scripts.qa_common import source_fingerprint
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
    folder=ROOT/'output/gui-workflow'/stamp;folder.mkdir(parents=True,exist_ok=False)
    source=folder/'source';source.mkdir();output=folder/'translated'
    fixture=ROOT/'output/e2e-validation/20261106T094832Z-8100b8/source.png'
    if not fixture.is_file():
        candidates=sorted((ROOT/'output/e2e-validation').glob('*/source.png'))
        if not candidates:raise FileNotFoundError('Run validate_e2e.py first to create a labelled source fixture.')
        fixture=candidates[-1]
    for name in ['1.png','2.png']:shutil.copy2(fixture,source/name)
    (source/'3-corrupt.png').write_bytes(b'INTENTIONALLY CORRUPT TEST FIXTURE')
    hashes={p.name:file_digest(p) for p in source.iterdir()}
    settings=CONFIG/'settings.json';settings_before=settings.read_bytes() if settings.exists() else None
    app=QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window=MainWindow(cache_path=folder/'state.sqlite3')
    window.source.setText(str(source));window.output.setText(str(output))
    window.language.setCurrentIndex(window.language.findData('zh'))
    window.mode.setCurrentText('Offline');window.offline_provider.setCurrentText('Argos')
    window.skip.setChecked(True);window.recursive.setChecked(True)
    window.show()
    report={'mock':False,'python':sys.executable,'source_fingerprint':source_fingerprint(),
            'source_kind':'synthetic source images plus intentionally corrupt fixture',
            'display_mode':app.platformName(),'overall':'FAIL','checks':{},'runs':[],
            'events':[],'heartbeat':0,'not_tested':['native Windows picker','physical desktop',
            'model download/delete','Explorer launch','user comic/photo accuracy']}
    state={'phase':0,'paused':False,'cancelled':False,'failed':False,'output_hashes':{}}
    def check(name,condition):
        report['checks'][name]='PASS' if condition else 'FAIL'
        if not condition:raise AssertionError(name)
    def fail(error):
        state['failed']=True;report['error']=str(error);report['traceback']=traceback.format_exc()
        if window.worker and window.worker.isRunning():
            window.worker.control.cancel();QTimer.singleShot(100,wait_stop)
        else:app.quit()
    def wait_stop():
        if window.worker and window.worker.isRunning():QTimer.singleShot(100,wait_stop)
        else:app.quit()
    def heartbeat():report['heartbeat']+=1
    pulse=QTimer();pulse.timeout.connect(heartbeat);pulse.start(25)
    def event(value):
        report['events'].append({'phase':state['phase'],**value})
        try:
            if value.get('type')=='fatal':raise RuntimeError(value['detail'])
            if value.get('type')=='finished':report['runs'].append(value)
            if state['phase']!=1 or 'stage' not in value:return
            if value['stage']=='OCR' and not state['paused']:
                state['paused']=True;QTest.mouseClick(window.pause_button,Qt.LeftButton)
                check('pause_flag',window.worker.control.paused)
                def resume():
                    try:
                        QTest.mouseClick(window.continue_button,Qt.LeftButton)
                        check('resume_flag',not window.worker.control.paused)
                    except Exception as exc:fail(exc)
                QTimer.singleShot(300,resume)
            elif value['stage']=='OCR' and Path(value['file']).name=='2.png' and not state['cancelled']:
                state['cancelled']=True;QTest.mouseClick(window.cancel_button,Qt.LeftButton)
                check('cancel_flag',window.worker.control.cancelled)
        except Exception as exc:fail(exc)
    def launch(retry=False):
        QTest.mouseClick(window.retry_button if retry else window.start_button,Qt.LeftButton)
        check('worker_started_phase_'+str(state['phase']),window.worker is not None)
        window.worker.event.connect(event)
        window.worker.finished.connect(lambda:QTimer.singleShot(50,phase_finished))
    def phase_finished():
        if state['failed']:return
        try:
            result=report['runs'][-1]
            if state['phase']==1:
                check('cancelled_with_completed_output',result['state']=='cancelled' and result['completed']>=1)
                state['phase']=2;launch(True)
            elif state['phase']==2:
                check('retry_unfinished_and_corrupt_error',result['state']=='errors' and result['failed']==1)
                state['output_hashes']={str(p):file_digest(p) for p in output.rglob('*.png')}
                check('two_valid_images_exported',len(state['output_hashes'])==2)
                state['phase']=3;launch(True)
            elif state['phase']==3:
                check('retry_only_failed_image',result['total']==1 and result['failed']==1)
                state['phase']=4;launch(False)
            else:
                check('checkpoint_skips_two_completed',result['skipped']==2 and result['failed']==1)
                check('previous_outputs_unchanged',all(file_digest(Path(p))==h for p,h in state['output_hashes'].items()))
                check('originals_unchanged',all(file_digest(source/n)==h for n,h in hashes.items()))
                check('progress_signals_real',any(e.get('stage')=='OCR' for e in report['events']) and
                      any(e.get('stage')=='Hoàn thành' for e in report['events']))
                check('buttons_restored',window.start_button.isEnabled() and not window.cancel_button.isEnabled())
                QTimer.singleShot(0,preview)
        except Exception as exc:fail(exc)
    def preview():
        def interact():
            try:
                dialog=app.activeModalWidget()
                if isinstance(dialog,QMessageBox):dialog.accept();QTimer.singleShot(50,interact);return
                check('preview_dialog',isinstance(dialog,PreviewDialog))
                dialog.findChild(QSlider).setValue(175)
                check('preview_zoom',abs(dialog.views[0].transform().m11()-1.75)<.01)
                for button in dialog.findChildren(QPushButton):
                    if button.text()=='Vừa cửa sổ':QTest.mouseClick(button,Qt.LeftButton)
                dialog.grab().save(str(folder/'preview.png'));dialog.accept()
            except Exception as exc:fail(exc)
        QTimer.singleShot(100,interact)
        window.inspect(window.rows[str(source/'1.png')],0)
        if not state['failed']:QTimer.singleShot(0,settings_dialog)
    def settings_dialog():
        def interact():
            try:
                dialog=app.activeModalWidget();check('settings_opens',isinstance(dialog,SettingsDialog));dialog.reject()
            except Exception as exc:fail(exc)
        QTimer.singleShot(100,interact);QTest.mouseClick(window.settings_button,Qt.LeftButton)
        if not state['failed']:QTimer.singleShot(0,models_dialog)
    def models_dialog():
        def interact():
            try:
                dialog=app.activeModalWidget();check('models_opens',isinstance(dialog,ModelManagerDialog))
                dialog.table.selectRow(0);QTest.mouseClick(dialog.buttons[1],Qt.LeftButton)
                def poll():
                    try:
                        if dialog.worker.isRunning():QTimer.singleShot(50,poll);return
                        check('installed_ocr_model_verify_button','Đã hoàn tất' in dialog.status.text())
                        dialog.accept()
                    except Exception as exc:fail(exc)
                QTimer.singleShot(100,poll)
            except Exception as exc:fail(exc)
        QTimer.singleShot(100,interact);QTest.mouseClick(window.models_button,Qt.LeftButton)
        if not state['failed']:
            check('event_loop_heartbeat',report['heartbeat']>10)
            window.grab().save(str(folder/'window.png'));report['overall']='PASS';app.quit()
    def start():
        try:state['phase']=1;launch()
        except Exception as exc:fail(exc)
    QTimer.singleShot(100,start)
    QTimer.singleShot(120_000,lambda:fail(TimeoutError('GUI workflow exceeded 120 seconds')))
    try:app.exec()
    finally:
        pulse.stop()
        if settings_before is not None:
            temporary=settings.with_suffix('.recovery-restore.tmp');temporary.write_bytes(settings_before);os.replace(temporary,settings)
        report['configuration_restored']=settings_before is None or settings.read_bytes()==settings_before
        (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('GUI workflow:',report['overall'],'Evidence:',folder)
    return 0 if report['overall']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
