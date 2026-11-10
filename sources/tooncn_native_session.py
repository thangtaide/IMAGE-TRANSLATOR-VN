"""Persistent, origin-scoped native port. Only serves an active app lease."""
from __future__ import annotations
import json
import queue
import re
import struct
import threading
import time
import base64
import hashlib
import os
from pathlib import Path
from sources.cache import atomic_json
from sources.tooncn_bridge import (MAX_MESSAGE,_read_exact,_unique_pairs,extension_origin,
                                  serve_once,validate_snapshot,_url)
from sources.tooncn_connection import RUNTIME,private_root,read_json,active_lease,prune_runtime

CODES={'BRIDGE_FAILED','TOONCN_TAB_REQUIRED','PAGE_NOT_READY','CHALLENGE_PENDING','ACCESS_DENIED',
       'DOM_LIMIT','TAB_NOT_OPEN','UNEXPECTED_NAVIGATION','BROWSER_TIMEOUT','CONNECTION_OFF',
       'INVALID_RESPONSE','IMAGE_UNAVAILABLE','IMAGE_CORS_BLOCKED','IMAGE_LIMIT','IMAGE_SOURCE_CHANGED',
       'RATE_LIMITED','NETWORK_ERROR'}


def write_frame(output,data):
    raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    if len(raw)>MAX_MESSAGE:raise ValueError('MESSAGE_LIMIT')
    output.write(struct.pack('<I',len(raw))+raw);output.flush()


def serve_connection(stream,output,origin,*,root=RUNTIME,stop=None,initial=None):
    root=Path(root)
    if origin!=extension_origin():write_frame(output,dict(ok=False,code='BRIDGE_ORIGIN_DENIED'));return
    root=private_root(root)
    inbox=queue.Queue(maxsize=8);closed=threading.Event()
    def receive():
        try:
            while True:
                size=struct.unpack('<I',_read_exact(stream,4))[0]
                if not 0<size<=MAX_MESSAGE:break
                msg=json.loads(_read_exact(stream,size).decode('utf-8'),object_pairs_hook=_unique_pairs)
                inbox.put(msg,timeout=2)
        except Exception:pass
        finally:closed.set()
    if initial is not None:inbox.put(initial)
    threading.Thread(target=receive,daemon=True).start()
    waiting=None;last_state=object();last_status=0
    peer_version=initial.get('extension_version','unknown') if isinstance(initial,dict) else 'unknown'
    if not isinstance(peer_version,str) or not re.fullmatch(r'\d{1,3}\.\d{1,3}\.\d{1,3}',peer_version):peer_version='unknown'
    while not (stop and stop.is_set()):
        lease=active_lease(root);session=lease['session'] if lease else None
        if session!=last_state:
            write_frame(output,dict(type='connection',enabled=bool(lease),session=session))
            last_state=session
        if time.monotonic()-last_status>2:
            atomic_json(root/'host-status.json',dict(state='CONNECTED' if lease else 'OFF',updated=time.time(),extension_version=peer_version))
            last_status=time.monotonic();prune_runtime(root)
        if waiting and (not lease or waiting['session']!=session or waiting['expires']<time.time()):
            if waiting.get('_image'):waiting['_image']['file'].close()
            target=root/'responses'/f"{waiting['id']}.json";private_root(target.parent)
            atomic_json(target,dict(id=waiting['id'],session=waiting['session'],ok=False,code='CONNECTION_OFF' if not lease else 'BROWSER_TIMEOUT'))
            waiting=None
        try:msg=inbox.get(timeout=.1)
        except queue.Empty:msg=None
        if msg is not None:
            if not isinstance(msg,dict):continue
            if msg.get('kind')=='hello':
                write_frame(output,dict(type='connection',enabled=bool(lease),session=session))
            elif waiting and msg.get('id')==waiting['id'] and msg.get('session')==session:
                if waiting['op']=='image' and msg.get('kind') in ('image_start','image_chunk','image_end'):
                    try:
                        if msg['kind']=='image_start':
                            if waiting.get('_image') or msg.get('mime') not in ('image/jpeg','image/png','image/webp','image/bmp') or type(msg.get('bytes')) is not int or not 0<msg['bytes']<=8*1024*1024:raise ValueError()
                            directory=private_root(root/'images')
                            if sum(p.stat().st_size for p in directory.iterdir() if p.is_file())+msg['bytes']>64*1024*1024:raise ValueError()
                            path=directory/f"{waiting['id']}.part"
                            waiting['_image']=dict(file=path.open('xb'),path=path,expected=msg['bytes'],mime=msg['mime'],size=0,sequence=0,hash=hashlib.sha256())
                            write_frame(output,dict(type='image_ack',id=waiting['id'],sequence=-1))
                        elif msg['kind']=='image_chunk':
                            transfer=waiting['_image'];raw=msg.get('data')
                            if msg.get('sequence')!=transfer['sequence'] or not isinstance(raw,str) or len(raw)>240000:raise ValueError()
                            raw=base64.b64decode(raw,validate=True)
                            if transfer['size']+len(raw)>transfer['expected']:raise ValueError()
                            transfer['file'].write(raw);transfer['hash'].update(raw);transfer['size']+=len(raw);transfer['sequence']+=1
                            write_frame(output,dict(type='image_ack',id=waiting['id'],sequence=msg['sequence']))
                        else:
                            transfer=waiting['_image']
                            if transfer['size']!=transfer['expected'] or msg.get('chunks')!=transfer['sequence']:raise ValueError()
                            transfer['file'].flush();os.fsync(transfer['file'].fileno());transfer['file'].close()
                            target=transfer['path'].with_suffix('.bin');transfer['path'].rename(target)
                            private_root(root/'responses')
                            atomic_json(root/'responses'/f"{waiting['id']}.json",dict(ok=True,id=waiting['id'],session=session,image_file=target.name,
                                bytes=transfer['size'],mime=transfer['mime'],sha256=transfer['hash'].hexdigest()))
                            waiting=None
                        continue
                    except Exception:
                        if waiting.get('_image'):waiting['_image']['file'].close()
                        msg=dict(ok=False,code='INVALID_RESPONSE')
                result=dict(id=waiting['id'],session=session,ok=False,code='INVALID_RESPONSE')
                if lease and msg.get('ok') is True and waiting['op']=='capture':
                    try:
                        data=validate_snapshot(msg['data'])
                        if data['page_url']!=waiting['url']:raise ValueError()
                        result.update(ok=True,data=data);result.pop('code',None)
                    except Exception:pass
                elif msg.get('code') in CODES:result['code']=msg['code']
                if waiting.get('_image'):waiting['_image']['file'].close()
                target=root/'responses'/f"{waiting['id']}.json";private_root(target.parent);atomic_json(target,result)
                waiting=None
        if closed.is_set() and inbox.empty():break
        if lease and waiting is None:
            private_root(root/'requests')
            def submitted(p):
                try:return p.stat().st_mtime_ns
                except FileNotFoundError:return 0
            for p in sorted((root/'requests').glob('*.json'),key=submitted):
                if not re.fullmatch(r'[a-f0-9]{32}\.json',p.name):continue
                if (root/'responses'/p.name).exists():continue
                try:
                    req=read_json(p,4096)
                    if (req.get('session')!=session or req.get('expires',0)<time.time() or
                            req.get('expires',0)>time.time()+120 or req.get('id')!=p.stem or req.get('op') not in ('capture','image')):continue
                    _url(req['url'],page=True)
                    if req['op']=='image':
                        _url(req.get('image_src'),same_site=True)
                        if not req['image_src'].startswith('https://tooncn.net/wp-content/uploads/'):continue
                    waiting=req
                    command=dict(type='request',id=req['id'],session=session,op=req['op'],url=req['url'],open_missing=req.get('open_missing') is True)
                    if req['op']=='image':command['image_src']=req['image_src']
                    write_frame(output,command)
                    break
                except (OSError,ValueError,KeyError,TypeError):continue
    if waiting and waiting.get('_image'):waiting['_image']['file'].close()


def main():
    import sys,os
    if os.name=='nt':
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(),os.O_BINARY);msvcrt.setmode(sys.stdout.fileno(),os.O_BINARY)
    try:
        origin=sys.argv[1] if len(sys.argv)>1 else ''
        if origin!=extension_origin():write_frame(sys.stdout.buffer,dict(ok=False,code='BRIDGE_ORIGIN_DENIED'));return
        size=struct.unpack('<I',_read_exact(sys.stdin.buffer,4))[0]
        if not 0<size<=MAX_MESSAGE:raise ValueError()
        raw=_read_exact(sys.stdin.buffer,size)
        first=json.loads(raw.decode('utf-8'),object_pairs_hook=_unique_pairs)
        if isinstance(first,dict) and first.get('kind')=='tooncn_dom':
            import io
            serve_once(io.BytesIO(struct.pack('<I',len(raw))+raw),sys.stdout.buffer,origin)
        elif isinstance(first,dict) and first.get('kind')=='hello' and first.get('version')==2 and not set(first)-{'kind','version','extension_version'}:
            serve_connection(sys.stdin.buffer,sys.stdout.buffer,origin,initial=first)
        else:write_frame(sys.stdout.buffer,dict(ok=False,code='BRIDGE_INVALID_DATA'))
    except Exception:
        # No raw exception/payload/Chrome state in stderr or metadata.
        try:write_frame(sys.stdout.buffer,dict(ok=False,code='BRIDGE_FAILED'))
        except Exception:pass
