"""USER-RUN installer: register one HKCU native host. Does not install an extension.

Codex must not run --install/--remove against the user's registry automatically.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sources.tooncn_bridge import HOST_NAME, extension_origin, _no_links

REG_KEY=r'Software\Google\Chrome\NativeMessagingHosts'+'\\'+HOST_NAME


def registration_plan(root=ROOT):
    root=Path(root).resolve()
    if any(c in str(root) for c in '%!&|<>^\r\n"'):raise ValueError('BRIDGE_UNSAFE_INSTALL_PATH')
    python=root/'.venv/Scripts/python.exe'
    host=root/'scripts/tooncn_native_host.py'
    if not python.is_file() or not host.is_file():raise ValueError('BRIDGE_HOST_FILES_MISSING')
    directory=root/'config/tooncn_bridge'
    manifest=directory/'native-host.json'
    launcher=directory/'native-host.bat'
    body={'name':HOST_NAME,'description':'Image Translator VN ToonCN local bridge',
          'path':str(launcher),'type':'stdio','allowed_origins':[extension_origin()]}
    batch='@echo off\r\n"'+str(python)+'" -I -u "'+str(host)+'" %*\r\n'
    return directory,manifest,launcher,body,batch


def register(*, remove=False):
    if os.name!='nt':raise ValueError('WINDOWS_ONLY')
    import winreg
    directory,manifest,launcher,body,batch=registration_plan()
    target=str(manifest)
    # Never replace a conflicting host in either view. No browser profile reads.
    found=[]
    for view in (winreg.KEY_WOW64_32KEY,winreg.KEY_WOW64_64KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,REG_KEY,0,winreg.KEY_READ|view) as key:
                value,kind=winreg.QueryValueEx(key,'')
                if kind!=winreg.REG_SZ or Path(value).resolve()!=manifest.resolve():
                    raise ValueError('BRIDGE_HOST_REGISTRATION_CONFLICT')
                found.append(view)
        except FileNotFoundError:pass
    if remove:
        for view in found:
            try:winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER,REG_KEY,view,0)
            except FileNotFoundError:pass  # HKCU may be shared between the two views.
        print('HOST_UNREGISTERED. Extension, Chrome and existing files were not modified.')
        return
    _no_links(directory)
    from core.agy_error_evidence import _private_directory
    if not directory.exists() and not _private_directory(directory):raise ValueError('BRIDGE_PRIVATE_STORAGE_REQUIRED')
    for file,content in [(launcher,batch.encode('utf-8')),(manifest,(json.dumps(body,indent=2)+'\n').encode('utf-8'))]:
        _no_links(file)
        if file.exists():
            if file.read_bytes()!=content:raise ValueError('BRIDGE_EXISTING_HOST_FILES_DIFFER')
        else:
            with file.open('xb') as stream:stream.write(content);stream.flush();os.fsync(stream.fileno())
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,REG_KEY,0,winreg.KEY_SET_VALUE|winreg.KEY_WOW64_64KEY) as key:
        winreg.SetValueEx(key,'',0,winreg.REG_SZ,target)
    print('HOST_REGISTERED. No extension/profile installed or changed.')
    print('Allowed extension ID:',extension_origin().split('/')[2])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--install',action='store_true');group.add_argument('--remove',action='store_true')
    args=parser.parse_args()
    try:register(remove=args.remove)
    except Exception as exc:
        # Codes only: never dump registry values, environment or personal paths.
        code=str(exc) if isinstance(exc,ValueError) and str(exc).startswith(('BRIDGE_','WINDOWS_')) else 'BRIDGE_REGISTRATION_FAILED'
        print(code);raise SystemExit(1)
