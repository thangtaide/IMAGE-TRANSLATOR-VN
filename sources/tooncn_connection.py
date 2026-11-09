"""App-owned lease and on-demand local Native Messaging requests. No network."""
from __future__ import annotations
import json
import os
import re
import threading
import time
from pathlib import Path
from uuid import uuid4
from core.paths import CACHE
from sources.cache import atomic_json
from sources.contracts import SourceError
from sources.tooncn_bridge import _no_links, _url, validate_snapshot, MAX_MESSAGE

RUNTIME = CACHE/'tooncn_browser/runtime-v2'
LEASE_SECONDS = 20
RETENTION_SECONDS = 600


def private_root(root):
    root=Path(root);_no_links(root)
    root.parent.mkdir(parents=True,exist_ok=True)
    if not root.exists():
        from core.agy_error_evidence import _private_directory
        if not _private_directory(root):raise SourceError('TOONCN_PRIVATE_STORAGE_REQUIRED')
    return root


def read_json(path, maximum=MAX_MESSAGE+4096):
    _no_links(path)
    if path.stat().st_size>maximum:raise SourceError('TOONCN_LOCAL_DATA_LIMIT')
    return json.loads(path.read_text(encoding='utf-8'))


def active_lease(root=RUNTIME):
    try:
        d=read_json(Path(root)/'lease.json',4096)
        if (d.get('enabled') is True and re.fullmatch('[a-f0-9]{32}',d.get('session',''))
                and type(d.get('expires')) in (int,float) and time.time()<d['expires']<=time.time()+LEASE_SECONDS+2):
            return d
    except (OSError,ValueError,SourceError,TypeError):pass
    return None


def prune_runtime(root=RUNTIME, now=None):
    """Only v2 ephemeral request files, never legacy inbox, source cache or outputs."""
    root=Path(root);now=time.time() if now is None else now
    for folder in ('requests','responses','images'):
        directory=root/folder
        _no_links(directory)
        if not directory.exists():continue
        for p in directory.iterdir():
            try:
                _no_links(p)
                if re.fullmatch(r'[a-f0-9]{32}\.(?:json|bin|part)',p.name) and p.is_file() and now-p.stat().st_mtime>RETENTION_SECONDS:
                    p.unlink(missing_ok=True)
            except FileNotFoundError:pass  # Other side may have just consumed/pruned it.


class ToonCNConnection:
    def __init__(self,root=RUNTIME):
        self.root=Path(root);self.session=uuid4().hex;self.enabled=False
        self.lock=threading.RLock()

    def enable(self):
        with self.lock:
            private_root(self.root)
            old=active_lease(self.root)
            if old and old['session']!=self.session:raise SourceError('TOONCN_CONNECTION_IN_USE')
            self.enabled=True;self.pulse()

    def pulse(self):
        with self.lock:
            if not self.enabled:return
            atomic_json(self.root/'lease.json',dict(version=2,enabled=True,session=self.session,
                         expires=time.time()+LEASE_SECONDS,pid=os.getpid()))
            prune_runtime(self.root)

    def disable(self):
        with self.lock:
            if not self.enabled:return
            self.enabled=False
            if not self.root.exists():return
            old=active_lease(self.root)
            if old and old['session']!=self.session:return
            atomic_json(self.root/'lease.json',dict(version=2,enabled=False,session=self.session,expires=0))

    def status(self):
        try:
            d=read_json(self.root/'host-status.json',4096)
            if time.time()-d.get('updated',0)<10:return d.get('state','UNKNOWN')
        except (OSError,ValueError,SourceError,TypeError):pass
        return 'WAITING_EXTENSION' if self.enabled else 'OFF'

    def request(self,url,control=None,*,open_missing=True,timeout=100,operation='capture',**extra):
        _url(url,page=True)
        if operation not in ('capture','image'):raise SourceError('TOONCN_INVALID_OPERATION')
        if operation=='image':
            _url(extra.get('image_src'),same_site=True)
            if not extra['image_src'].startswith('https://tooncn.net/wp-content/uploads/'):raise SourceError('TOONCN_IMAGE_SOURCE_INVALID')
        if not self.enabled:raise SourceError('TOONCN_CONNECTION_OFF: Bật Kết nối ToonCN trong ứng dụng.')
        identifier=uuid4().hex
        for folder in ('requests','responses'):private_root(self.root/folder)
        if len(list((self.root/'requests').glob('*.json')))>=128:raise SourceError('TOONCN_QUEUE_LIMIT')
        if sum(p.stat().st_size for folder in ('requests','responses') for p in (self.root/folder).glob('*.json'))>16_000_000:
            raise SourceError('TOONCN_STORE_FULL')
        request=dict(version=2,id=identifier,session=self.session,op=operation,url=url,
                     open_missing=bool(open_missing),expires=time.time()+timeout,**extra)
        target=self.root/'responses'/f'{identifier}.json'
        atomic_json(self.root/'requests'/f'{identifier}.json',request)
        started=time.monotonic();last_pulse=0
        while time.monotonic()-started<timeout:
            if control:control.checkpoint()
            if not self.enabled:raise SourceError('TOONCN_CONNECTION_OFF')
            if time.monotonic()-last_pulse>5:self.pulse();last_pulse=time.monotonic()
            if target.exists():
                result=read_json(target)
                if result.get('id')!=identifier or result.get('session')!=self.session:raise SourceError('TOONCN_RESPONSE_ID')
                if not result.get('ok'):raise SourceError('TOONCN_'+result.get('code','BRIDGE_FAILED'))
                if operation=='capture':
                    data=validate_snapshot(result['data'])
                    if data['page_url']!=url:raise SourceError('TOONCN_PAGE_MISMATCH')
                    return data
                # Remove request before response, so a consumed result cannot replay.
                (self.root/'requests'/f'{identifier}.json').unlink(missing_ok=True)
                target.unlink(missing_ok=True)
                return result
            time.sleep(.1)
        raise SourceError('TOONCN_BROWSER_TIMEOUT: Kiểm tra extension đã Reload/kết nối và trang đã tải thật.')


_connection=None
def connection():
    global _connection
    if _connection is None:_connection=ToonCNConnection()
    return _connection
