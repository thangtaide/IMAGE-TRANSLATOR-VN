# PyInstaller onedir; AI models remain external under D:\TransTool\models.
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules
from pathlib import Path
import os
import re

root = Path(SPECPATH)
build_name = os.environ.get('ITVN_BUILD_NAME', 'ImageTranslatorVN')
if re.fullmatch(r'ImageTranslatorVN(?:-[A-Za-z0-9_-]+)?', build_name) is None:
    raise ValueError('Invalid build name')
from core.runtime import prepare_inference_runtime
prepare_inference_runtime()
datas = [(str(root / 'assets'), 'assets')]
binaries = []
hiddenimports = ['argostranslate.tokenizer']
for package in ['paddle', 'paddleocr', 'ctranslate2', 'sentencepiece', 'cv2']:
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(['main.py'], pathex=[str(root)], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=['torch', 'torchvision', 'tensorflow', 'stanza', 'matplotlib', 'IPython'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=build_name,
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=build_name)
