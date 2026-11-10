"""Fresh-process real-runtime scenarios; no mock OCR, MT, workers or output."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def dll_diagnostics() -> dict:
    """Read loaded paths and PE exports; never alters the DLL search path."""
    import ctypes
    import pefile
    base = ROOT/'.venv/Lib/site-packages'
    torch_lib = base/'torch/lib'
    paddle_lib = base/'paddle/libs'
    common = {p.name.lower() for p in torch_lib.glob('*.dll')} & {p.name.lower() for p in paddle_lib.glob('*.dll')}
    kernel = ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
    kernel.GetModuleHandleW.restype = ctypes.c_void_p
    kernel.GetModuleFileNameW.argtypes = [ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_uint]
    loaded = {}
    for name in sorted(common):
        handle = kernel.GetModuleHandleW(name)
        buffer = ctypes.create_unicode_buffer(32768)
        if handle and kernel.GetModuleFileNameW(handle,buffer,len(buffer)):
            loaded[name] = buffer.value
    missing = []
    for path in torch_lib.glob('*.dll'):
        try:
            binary = pefile.PE(str(path),fast_load=True)
            binary.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
            for entry in getattr(binary,'DIRECTORY_ENTRY_IMPORT',[]):
                dependency = entry.dll.decode().lower()
                if dependency not in loaded:
                    continue
                actual = pefile.PE(loaded[dependency],fast_load=True)
                actual.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']])
                exports = {s.name for s in getattr(actual,'DIRECTORY_ENTRY_EXPORT',type('Empty',(),{'symbols':[]})()).symbols}
                absent = [item.name.decode() for item in entry.imports if item.name and item.name not in exports]
                if absent:
                    missing.append({'requester':str(path),'dependency':loaded[dependency],'missing_exports':absent})
                actual.close()
            binary.close()
        except pefile.PEFormatError:
            continue
    return {'shared_dll_names':sorted(common),'loaded_shared_dlls':loaded,'missing_exports':missing}


def fixture(folder: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (1200, 430), 'white')
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 64)
    draw = ImageDraw.Draw(image)
    draw.text((130, 120), '你好，世界！', font=font, fill='black')
    draw.text((130, 220), '欢迎使用图像翻译。', font=font, fill='black')
    source = folder/'input'
    source.mkdir()
    path = source/'中文测试.png'
    image.save(path)
    return path


def run(case: str, folder: Path) -> dict:
    import numpy as np
    from core.paths import initialize
    initialize()
    from core.imaging import open_image
    from core.ocr import PaddleOCREngine, local_models_only
    from core.runtime import prepare_inference_runtime
    from core.storage import file_digest
    from providers.offline import ArgosTranslationProvider
    source = fixture(folder)
    original_hash = file_digest(source)
    events = []
    def audit(event, args):
        if event=='import' and args[0] in ('paddle', 'paddleocr', 'torch', 'ctranslate2'):
            events.append({'module':args[0], 'time':time.perf_counter()})
    sys.addaudithook(audit)
    report = {'case':case, 'mock':False, 'source':str(source), 'import_events':events, 'status':'FAIL'}
    if case=='legacy_raw_order':
        # Intentionally bypass our adapters, retaining the actual failing order.
        from paddleocr import PaddleOCR
        import importlib
        module = sys.modules[PaddleOCR.__module__]
        module.maybe_download = local_models_only
        ocr = PaddleOCR(lang='ch', use_gpu=False, show_log=False, use_angle_cls=True,
            det_model_dir=str(ROOT/'models/ocr/det-ch'), rec_model_dir=str(ROOT/'models/ocr/rec-zh'),
            cls_model_dir=str(ROOT/'models/ocr/cls'), enable_mkldnn=False, cpu_threads=2)
        raw = ocr.ocr(np.array(open_image(source).convert('RGB'))[:, :, ::-1].copy(), cls=True)
        report['ocr_regions'] = len(raw[0])
        report['dll_diagnostics'] = dll_diagnostics()
        try:
            importlib.import_module('ctranslate2')
            report.update(status='NOT_REPRODUCED', reason='Reverse order no longer fails in this environment')
        except OSError as exc:
            report.update(status='REPRODUCED', error=str(exc), winerror=getattr(exc,'winerror',None))
        return report
    if case in ('ct_first', 'prepared_paddle_first'):
        prepare_inference_runtime()
        if case=='prepared_paddle_first':
            import paddle
    if case in ('ct_first', 'prepared_paddle_first', 'adapter_ocr_first', 'repeat'):
        ocr = PaddleOCREngine()
        provider = ArgosTranslationProvider()
        rgb = np.array(open_image(source).convert('RGB'))
        records = []
        identities = []
        for index in range(4 if case=='repeat' else 1):
            regions, warnings = ocr.recognize(rgb, 'zh')
            if not regions:
                raise AssertionError('No real OCR output')
            translated = provider.translate_batch([r.text for r in regions], 'zh')
            if len(translated)!=len(regions) or not all(translated):
                raise AssertionError('Missing real translation')
            identities.append((id(ocr.engine), tuple(id(v[0]) for v in provider.loaded.values())))
            records.append({'ocr':[r.text for r in regions], 'translated':translated})
        report['records'] = records
        report['model_reused'] = all(identity==identities[0] for identity in identities)
        if not report['model_reused']:
            raise AssertionError('Model instances were not reused')
        report['native_modules'] = [m for m in ('ctranslate2','torch','paddle') if m in sys.modules]
    elif case in ('worker_restart', 'cancel'):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from ui.workers import ProcessingWorker
        from PySide6.QtCore import QEventLoop, QTimer
        from PySide6.QtWidgets import QApplication
        from core.types import Options
        app = QApplication.instance() or QApplication([])
        runs = []
        for index in range(2 if case=='worker_restart' else 1):
            options = Options(source=str(source.parent), output=str(folder/f'result-{index}'), language='zh', mode='Offline', skip_success=False)
            # Fresh SQLite state ensures the real worker executes OCR/MT rather
            # than returning results from another validation run's cache.
            worker = ProcessingWorker(options, cache_path=folder/f'state-{index}.sqlite3')
            loop = QEventLoop()
            captured, beats = [], []
            timer = QTimer()
            timer.setInterval(15)
            timer.timeout.connect(lambda: beats.append(time.monotonic()))
            def receive(event):
                captured.append(event)
                if case=='cancel' and event.get('stage')=='OCR':
                    worker.control.cancel()
            worker.event.connect(receive)
            worker.finished.connect(loop.quit)
            timeout = QTimer()
            timeout.setSingleShot(True)
            timeout.timeout.connect(lambda: (worker.control.cancel(), loop.quit()))
            timer.start()
            timeout.start(60000)
            worker.start()
            loop.exec()
            timer.stop()
            timeout.stop()
            if not worker.wait(10000):
                raise AssertionError('Worker failed to stop safely')
            final = next((e for e in reversed(captured) if e.get('type')=='finished'), None)
            if final is None:
                raise AssertionError('No final worker signal')
            if case=='cancel':
                if final['state']!='cancelled' or list(Path(options.output).rglob('*.png')):
                    raise AssertionError('Cancelled job saved output or did not cancel')
            elif final['state']!='done' or final['completed']!=1 or final['failed']:
                raise AssertionError('Real GUI worker failed: '+json.dumps(captured, ensure_ascii=False))
            if len(beats)<3:
                raise AssertionError('Qt event loop was blocked')
            runs.append({'result':final, 'events':captured, 'heartbeat':len(beats)})
        report['worker_runs'] = runs
    else:
        raise ValueError(case)
    if file_digest(source)!=original_hash:
        raise AssertionError('Original image changed')
    report['status'] = 'PASS'
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('case', choices=['legacy_raw_order','ct_first','prepared_paddle_first','adapter_ocr_first','repeat','worker_restart','cancel'])
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
    folder = ROOT/'output/runtime-validation'/stamp
    folder.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    try:
        report = run(args.case, folder)
    except Exception as exc:
        import traceback
        report = {'case':args.case, 'mock':False, 'status':'FAIL', 'error':str(exc), 'traceback':traceback.format_exc()}
    report.update(seconds=time.monotonic()-started, python=sys.executable)
    (folder/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('RUNTIME_RESULT '+json.dumps({'case':args.case,'status':report['status'],'report':str(folder/'report.json')}, ensure_ascii=True))
    return 0 if report['status'] in ('PASS','REPRODUCED') else 1


if __name__=='__main__':
    raise SystemExit(main())
