"""Receive user-approved, filtered ToonCN DOM locally. No network or browser control.

Not a website adapter: actual reader DOM must be inspected before writing one.
No cookie, token, raw HTML, arbitrary path, shell or provider operation exists.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import struct
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from core.paths import ROOT, CACHE
from sources.security import https_url
from sources.contracts import InvalidURL

HOST_NAME = 'vn.imagetranslator.tooncn'
MAX_MESSAGE = 1_000_000
STORE_LIMIT = 16_000_000
MAX_SNAPSHOTS = 32
TAGS = {'main','article','section','div','aside','h1','h2','h3','p','span','strong','b',
        'ul','ol','li','a','img','figure','figcaption','picture','source'}
URL_FIELDS = {'href','src','current_src','data_src','data_lazy_src'}
ATTRIBUTES = URL_FIELDS | {'id','class','alt','srcset','natural_width','natural_height','loaded'}
PAGE_PATH = re.compile(r'(?:/webtoon/[1-9][0-9]*/|/[1-9][0-9]*-Ep-[0-9]+(?:\.[0-9]+)?/)')
PRIVATE_PATH = re.compile(r'login|logout|wp-admin|wp-login|account|password|authorization|credential|session|token',re.I)


class BridgeError(ValueError):
    pass


def extension_origin() -> str:
    manifest = json.loads((ROOT/'extensions/tooncn_bridge/manifest.json').read_text(encoding='utf-8'))
    raw = base64.b64decode(manifest['key'],validate=True)
    letters = ''.join(chr(ord('a')+int(n,16)) for n in hashlib.sha256(raw).hexdigest()[:32])
    return 'chrome-extension://'+letters+'/'


def _text(value, maximum):
    if not isinstance(value,str) or len(value)>maximum or any(ord(c)<32 or ord(c)==127 for c in value):
        raise BridgeError('BRIDGE_INVALID_DATA')
    return value


def _url(value, *, page=False, same_site=False):
    _text(value,2048)
    try:
        p=https_url(value,('tooncn.net',) if page or same_site else None)
    except (ValueError, InvalidURL):
        raise BridgeError('BRIDGE_INVALID_DATA') from None
    # No query/fragment or credentials cross the browser/native boundary.
    if p.query or p.fragment or PRIVATE_PATH.search(p.path) or any(len(x)>160 for x in p.path.split('/')):
        raise BridgeError('BRIDGE_INVALID_DATA')
    # Every public route on the granted origin; never account/auth routes.
    if page and (not p.path.startswith('/') or '..' in p.path.split('/')):
        raise BridgeError('BRIDGE_INVALID_DATA')
    return value


def validate_snapshot(data):
    if (not isinstance(data,dict) or set(data)!={'version','kind','page_url','title','nodes'}
            or type(data['version']) is not int or data['version']!=1 or data['kind']!='tooncn_dom'):
        raise BridgeError('BRIDGE_INVALID_DATA')
    _url(data['page_url'],page=True)
    title=_text(data['title'],200)
    if re.search(r'just a moment|checking your browser|verifying you are human',title,re.I):
        raise BridgeError('CHALLENGE_PENDING')
    rows=data['nodes']
    if not isinstance(rows,list) or not 1<=len(rows)<=4000:
        raise BridgeError('BRIDGE_INVALID_DATA')
    for i,row in enumerate(rows):
        if not isinstance(row,dict) or set(row)!={'index','parent','tag','attributes','text'}:
            raise BridgeError('BRIDGE_INVALID_DATA')
        if type(row['index']) is not int or row['index']!=i or not isinstance(row['tag'],str) or row['tag'] not in TAGS:
            raise BridgeError('BRIDGE_INVALID_DATA')
        parent=row['parent']
        if parent is not None and (type(parent) is not int or not 0<=parent<i):
            raise BridgeError('BRIDGE_INVALID_DATA')
        _text(row['text'],400)
        attrs=row['attributes']
        if not isinstance(attrs,dict) or set(attrs)-ATTRIBUTES:
            raise BridgeError('BRIDGE_INVALID_DATA')
        for name,value in attrs.items():
            if name in URL_FIELDS:
                if name=='href' and row['tag']!='a' or name!='href' and row['tag'] not in ('img','source'):
                    raise BridgeError('BRIDGE_INVALID_DATA')
                _url(value,same_site=name=='href')
            elif name=='srcset':
                if row['tag'] not in ('img','source') or not isinstance(value,list) or not 1<=len(value)<=12:
                    raise BridgeError('BRIDGE_INVALID_DATA')
                for item in value:_url(item)
            elif name in ('natural_width','natural_height'):
                if row['tag']!='img' or type(value) is not int or not 0<=value<=100000:
                    raise BridgeError('BRIDGE_INVALID_DATA')
            elif name=='loaded':
                if row['tag']!='img' or type(value) is not bool:raise BridgeError('BRIDGE_INVALID_DATA')
            else:
                _text(value,200)
                if name in ('id','class') and re.search('token|secret|credential|password|session|authorization',value,re.I):
                    raise BridgeError('BRIDGE_INVALID_DATA')
    return data


def _no_links(path):
    for p in (path,*path.parents):
        if p.is_symlink() or p.exists() and getattr(p.stat(),'st_file_attributes',0)&0x400:
            raise BridgeError('BRIDGE_UNSAFE_PATH')


def save_snapshot(data, root=None):
    validate_snapshot(data)
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    if len(payload)>MAX_MESSAGE:raise BridgeError('BRIDGE_MESSAGE_LIMIT')
    root=Path(root) if root is not None else CACHE/'tooncn_browser/inbox'
    _no_links(root)
    root.mkdir(parents=True,exist_ok=True)
    # Reuse local file quota locking and Windows private DACL creation only.
    # This module does not import or execute an AGY provider.
    from core.agy_error_evidence import _budget_lock, _private_directory
    identifier=uuid4().hex
    receipt={'schema_version':1,'snapshot_id':identifier,'received_utc':datetime.now(timezone.utc).isoformat(),
             'payload_sha256':hashlib.sha256(payload).hexdigest(),'page_url':data['page_url'],
             'node_count':len(data['nodes']),'data':data}
    raw=json.dumps(receipt,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    with _budget_lock(root):
        _no_links(root)
        files=[]
        for p in root.rglob('*'):
            _no_links(p)
            if p.is_file() and p.name!='.budget.lock':files.append(p)
        if sum(p.stat().st_size for p in files)+len(raw)>STORE_LIMIT or len(list(root.glob('*/snapshot.json')))>=MAX_SNAPSHOTS:
            raise BridgeError('BRIDGE_STORE_FULL')
        directory=root/identifier
        if not _private_directory(directory):raise BridgeError('BRIDGE_PRIVATE_STORAGE_REQUIRED')
        pending=directory/'snapshot.part'
        with pending.open('xb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        pending.rename(directory/'snapshot.json')  # Unique private directory, no replace.
    return dict(ok=True,snapshot_id=identifier,node_count=len(data['nodes']))


def _read_exact(stream,size):
    parts=[];remaining=size
    while remaining:
        part=stream.read(remaining)
        if not part:raise BridgeError('BRIDGE_TRUNCATED_MESSAGE')
        parts.append(part);remaining-=len(part)
    return b''.join(parts)


def _unique_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise BridgeError('BRIDGE_INVALID_DATA')
        result[key]=value
    return result


def serve_once(stream, output, origin, *, root=None):
    try:
        if origin!=extension_origin():raise BridgeError('BRIDGE_ORIGIN_DENIED')
        size=struct.unpack('<I',_read_exact(stream,4))[0]
        if not 0<size<=MAX_MESSAGE:raise BridgeError('BRIDGE_MESSAGE_LIMIT')
        data=json.loads(_read_exact(stream,size).decode('utf-8'),object_pairs_hook=_unique_pairs)
        result=save_snapshot(data,root)
    except Exception as exc:
        codes={'BRIDGE_INVALID_DATA','BRIDGE_ORIGIN_DENIED','BRIDGE_MESSAGE_LIMIT','BRIDGE_TRUNCATED_MESSAGE',
               'BRIDGE_UNSAFE_PATH','BRIDGE_STORE_FULL','BRIDGE_PRIVATE_STORAGE_REQUIRED','CHALLENGE_PENDING'}
        result=dict(ok=False,code=str(exc) if isinstance(exc,BridgeError) and str(exc) in codes else 'BRIDGE_FAILED')
    payload=json.dumps(result).encode('utf-8')
    output.write(struct.pack('<I',len(payload))+payload);output.flush()


def main():
    import sys
    if os.name=='nt':
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(),os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(),os.O_BINARY)
    serve_once(sys.stdin.buffer,sys.stdout.buffer,sys.argv[1] if len(sys.argv)>1 else '')
