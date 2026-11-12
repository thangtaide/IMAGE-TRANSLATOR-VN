"""Isolated source/frozen Groq GUI and ledger-bounded live checks. Neutral input only."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from core.paths import ROOT
from core.storage import atomic_json,file_digest
from core.types import Options


def read(path):return json.loads(path.read_text(encoding='utf-8'))


@contextmanager
def budget(run,purpose):
    from providers.groq_api import BASE_URL
    import requests
    original=requests.Session.post
    def post(session,url,**kwargs):
        if url!=BASE_URL+'/chat/completions':raise AssertionError('Unexpected endpoint')
        data=read(run/'api-budget.json')
        if data['used']>=data['limit']:raise AssertionError('GROQ_QA_BUDGET_EXHAUSTED')
        data['used']+=1;n=data['used']
        data['invocations'].append(dict(number=n,purpose=purpose,model=kwargs['json']['model'],status='ATTEMPTED',cost='UNKNOWN'))
        atomic_json(run/'api-budget.json',data)
        result=original(session,url,**kwargs)
        data=read(run/'api-budget.json');data['invocations'][-1].update(status='RESPONSE_RECEIVED',http_status=result.status_code)
        atomic_json(run/'api-budget.json',data)
        return result
    with patch.object(requests.Session,'post',post):yield


def gui(folder,reopen=None):
    from PySide6.QtWidgets import QApplication,QDialogButtonBox
    from PySide6.QtCore import Qt,QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtGui import QPalette
    from core.storage import save_options,load_options
    from providers.agy import MODE
    from providers.groq_api import MODELS,MODEL
    from ui.main_window import MainWindow
    from ui.settings_dialog import SettingsDialog
    config=reopen or folder/'config';config.mkdir(exist_ok=True)
    with patch('core.storage.CONFIG',config),patch('ui.main_window.CONFIG',config):
        if not reopen:save_options(Options(mode=MODE,agy_model='claude-sonnet-4-6'))
        app=QApplication.instance() or QApplication([]);window=MainWindow(folder/'state.sqlite3');window.show();QTest.qWait(60)
        try:
            if reopen:
                assert window.options.ai_provider=='groq' and window.options.groq_model==MODEL
                d=SettingsDialog(window.options,window);d.show();QTest.qWait(30)
                assert d.ai_source.currentData()=='groq' and d.groq_model.currentData()==MODEL
                d.grab().save(str(folder/'reopened-settings.png'));d.reject()
                return dict(status='PASS',model=MODEL,reopened=True)
            errors=[]
            def action(save):
                def click():
                    d=next(w for w in app.topLevelWidgets() if isinstance(w,SettingsDialog) and w.isVisible())
                    try:
                        d.ai_source.setCurrentIndex(d.ai_source.findData('groq'))
                        assert d.groq_model.count()==3
                        for _,m in MODELS:assert d.groq_model.findData(m)>=0
                        d.groq_model.setCurrentIndex(d.groq_model.findData(MODEL))
                        if save:
                            d.grab().save(str(folder/'settings.png'))
                            d.groq_model.showPopup();QTest.qWait(40)
                            assert d.groq_model.view().palette().color(QPalette.Base).lightness()<128
                            d.groq_model.view().window().grab().save(str(folder/'model-popup.png'));d.groq_model.hidePopup()
                        QTest.mouseClick(d.buttons.button(QDialogButtonBox.Ok if save else QDialogButtonBox.Cancel),Qt.LeftButton)
                    except Exception as e:errors.append(type(e).__name__);d.reject()
                QTimer.singleShot(60,click);QTest.mouseClick(window.settings_button,Qt.LeftButton)
                assert not errors,errors
            before=(config/'settings.json').read_bytes();action(False);assert (config/'settings.json').read_bytes()==before
            action(True);saved=load_options();assert saved.ai_provider=='groq' and saved.groq_model==MODEL
            assert saved.agy_model=='claude-sonnet-4-6' and 'GroqCloud' in window.provider_info.text()
            window.grab().save(str(folder/'main.png'))
            return dict(status='PASS',provider=saved.ai_provider,model=saved.groq_model,save_cancel=True,
                scale=window.devicePixelRatioF(),main_status=window.provider_info.text(),translation_requests=0)
        finally:window.close();app.processEvents()


def live(run,folder,action):
    from providers.groq_api import GroqProvider,MODEL,key_available
    fixture=action=='fixture'
    if not fixture and not key_available():return dict(status='SKIP_KEY_MISSING',requests=0)
    if action=='connect':
        provider=GroqProvider(model=MODEL,max_requests=1,timeout=30)
        with budget(run,folder.name):
            try:target=provider.translate('你好','zh')
            finally:provider.close()
        return dict(status='PASS',model=MODEL,translation=target,diagnostic=provider.last_diagnostic)
    from PIL import Image,ImageDraw,ImageFont
    from core.pipeline import ProcessingManager
    from core.storage import TranslationCache
    from providers.agy import AGYProvider,MODE
    source=folder/'input';source.mkdir();image=Image.new('RGB',(800,240),'white')
    font=ImageFont.truetype(str(Path(os.environ['WINDIR'])/'Fonts/msyh.ttc'),64)
    ImageDraw.Draw(image).text((70,70),'你好',font=font,fill='black');image.save(source/'neutral.png')
    h=file_digest(source/'neutral.png');opts=Options(source=str(source),output=str(folder/'export'),mode=MODE,ai_provider='groq',groq_model=MODEL,agy_max_requests=1)
    cache=TranslationCache(folder/'state.sqlite3');events=[]
    @contextmanager
    def transport():
        if not fixture:
            with budget(run,folder.name):yield
            return
        import requests
        def post(session,url,**kwargs):
            packet=json.loads(kwargs['json']['messages'][1]['content']);r=requests.Response()
            r.status_code=200;r.headers['Content-Type']='application/json'
            data=dict(model=kwargs['json']['model'],choices=[dict(finish_reason='stop',message=dict(content=json.dumps(dict(
                translations=[dict(id=row['id'],text='Xin chào.') for row in packet['regions']]))))])
            r._content=json.dumps(data).encode();r._content_consumed=True;return r
        with patch.object(requests.Session,'post',post),patch('providers.groq_api.read_key',return_value='QA-NOT-A-REAL-KEY'):yield
    with transport(),patch.object(AGYProvider,'_invoke',side_effect=AssertionError('No CLI in Groq run')):
        try:
            manager=ProcessingManager(opts,cache,emit=events.append,diagnostic_root=folder/'diagnostics');result=manager.run()
            row=cache.connection.execute("SELECT value FROM cache WHERE kind='metadata'").fetchone()
            meta=json.loads(row[0]) if row else {}
        finally:cache.close()
    return dict(status='PASS' if result.get('completed')==1 else 'FAIL',result=result,http_fixture=fixture,
        source_unchanged=file_digest(source/'neutral.png')==h,ocr=[r['text'] for r in meta.get('regions',[])],
        translations=meta.get('translations'),selection=meta.get('agy_selection'),
        outputs=[str(p.relative_to(ROOT)) for p in (folder/'export').glob('*.png') if 'fallback' not in p.name])


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--phase',required=True)
    p.add_argument('--action',choices=['gui','connect','image','fixture'],default='gui');p.add_argument('--reopen',type=Path)
    args=p.parse_args();run=(ROOT/args.run).resolve()
    if not run.is_relative_to(ROOT/'output') or not args.phase.replace('-','').isalnum():p.error('Managed QA directory required')
    folder=run/args.phase;folder.mkdir(exist_ok=False);report=dict(status='FAIL',frozen=bool(getattr(sys,'frozen',False)))
    try:
        from core.runtime import prepare_inference_runtime
        prepare_inference_runtime()
        reopen=(run/args.reopen).resolve() if args.reopen else None
        if reopen and not reopen.is_relative_to(run):raise ValueError('Private settings required')
        report.update(gui(folder,reopen) if args.action=='gui' else live(run,folder,args.action))
    except Exception as exc:
        # Never stringify HTTP exceptions: they may retain a prepared auth header.
        report.update(error_code=getattr(exc,'code',type(exc).__name__),diagnostic=getattr(exc,'groq_diagnostic',None))
    atomic_json(folder/'report.json',report)
    if sys.stdout:print(json.dumps(report,ensure_ascii=True))
    return 0 if report['status']=='PASS' else 1
