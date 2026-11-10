"""App lease/port tests with isolated files and fake Chrome. No live website."""
import io
import json
import os
import queue
import struct
import subprocess
import tempfile
import threading
import time
import base64
import hashlib
import unittest
from pathlib import Path
from core.paths import ROOT
from sources.cache import atomic_json
from sources.contracts import SourceError
from sources.tooncn_bridge import extension_origin
from sources.tooncn_connection import ToonCNConnection,active_lease,prune_runtime,RETENTION_SECONDS
from sources.tooncn_native_session import serve_connection
from tests.test_tooncn_bridge import fixture


class Pipe:
    def __init__(self):self.queue=queue.Queue();self.buffer=bytearray()
    def read(self,n):
        while len(self.buffer)<n:
            data=self.queue.get(timeout=5)
            if data is None:break
            self.buffer.extend(data)
        data=bytes(self.buffer[:n]);del self.buffer[:n];return data
    def send(self,value):
        raw=json.dumps(value).encode();self.queue.put(struct.pack('<I',len(raw))+raw)


class Output:
    def __init__(self):self.queue=queue.Queue();self.buffer=bytearray()
    def write(self,data):
        self.buffer.extend(data)
        while len(self.buffer)>=4:
            size=struct.unpack('<I',self.buffer[:4])[0]
            if len(self.buffer)<size+4:break
            self.queue.put(json.loads(self.buffer[4:size+4]));del self.buffer[:size+4]
    def flush(self):pass


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'runtime';self.c=ToonCNConnection(self.root)

    def test_default_off_does_not_create_files_or_issue_requests(self):
        with self.assertRaisesRegex(SourceError,'CONNECTION_OFF'):self.c.request('https://tooncn.net/webtoon/123/')
        self.c.disable();self.assertFalse(self.root.exists())

    def test_enable_disable_expiration_and_second_owner(self):
        self.c.enable();self.assertEqual(active_lease(self.root)['session'],self.c.session)
        with self.assertRaisesRegex(SourceError,'CONNECTION_IN_USE'):ToonCNConnection(self.root).enable()
        d=json.loads((self.root/'lease.json').read_text());d['expires']=time.time()-1;atomic_json(self.root/'lease.json',d)
        self.assertIsNone(active_lease(self.root));self.c.disable();self.assertIsNone(active_lease(self.root))

    def test_all_public_routes_allowed_other_domains_and_auth_still_rejected(self):
        from sources.tooncn_bridge import _url
        for url in ['https://tooncn.net/','https://tooncn.net/webtoon/456/','https://tooncn.net/456-Ep-200/','https://tooncn.net/public-other-route/']:_url(url,page=True)
        for url in ['https://other.example/','https://tooncn.net/account/','https://tooncn.net/?token=private']:
            with self.assertRaises(Exception):_url(url,page=True)

    def test_on_demand_capture_roundtrip_and_no_old_snapshot_reuse(self):
        self.c.enable();incoming=Pipe();out=Output();stop=threading.Event()
        thread=threading.Thread(target=serve_connection,args=(incoming,out,extension_origin()),kwargs=dict(root=self.root,stop=stop),daemon=True);thread.start()
        def fake_browser():
            while True:
                message=out.queue.get(timeout=5)
                if message.get('type')=='request':
                    incoming.send(dict(id=message['id'],session=message['session'],ok=True,data=fixture()));return
        worker=threading.Thread(target=fake_browser);worker.start()
        try:
            data=self.c.request(fixture()['page_url'],open_missing=False,timeout=3)
            self.assertEqual(data,fixture());worker.join(3)
            self.assertEqual(len(list((self.root/'requests').glob('*.json'))),1)
            self.c.disable()
            with self.assertRaisesRegex(SourceError,'CONNECTION_OFF'):self.c.request(fixture()['page_url'])
        finally:stop.set();incoming.queue.put(None);thread.join(3)

    def test_prune_only_ephemeral_uuid_files_never_legacy_or_outputs(self):
        self.c.enable();p=self.root/'responses';p.mkdir();old=p/('a'*32+'.json');old.write_text('{}');os.utime(old,(1,1))
        keep=p/'user-data.json';keep.write_text('keep');os.utime(keep,(1,1))
        legacy=self.root.parent/'inbox';legacy.mkdir();source=legacy/'snapshot.json';source.write_text('old snapshot')
        prune_runtime(self.root);self.assertFalse(old.exists());self.assertTrue(keep.exists());self.assertTrue(source.exists())

    def test_cancellation_and_disabled_inflight_request_do_not_accept_data(self):
        self.c.enable()
        timer=threading.Timer(.15,self.c.disable);timer.start()
        with self.assertRaisesRegex(SourceError,'CONNECTION_OFF'):self.c.request(fixture()['page_url'],timeout=1)
        timer.join()

    def test_request_timeout_is_finite_and_no_browser_retry(self):
        self.c.enable()
        with self.assertRaisesRegex(SourceError,'BROWSER_TIMEOUT'):self.c.request(fixture()['page_url'],timeout=.2)
        self.assertEqual(len(list((self.root/'requests').glob('*.json'))),1);self.c.disable()

    def test_background_only_reads_requested_tooncn_when_enabled_fake_chrome(self):
        p=subprocess.run(['node',str(ROOT/'tests/test_tooncn_background.mjs')],capture_output=True,timeout=10,cwd=ROOT)
        self.assertEqual(p.returncode,0,p.stderr.decode('utf-8',errors='replace'))

    def test_image_chunk_roundtrip_and_source_scoping(self):
        self.c.enable();incoming=Pipe();out=Output();stop=threading.Event()
        thread=threading.Thread(target=serve_connection,args=(incoming,out,extension_origin()),kwargs=dict(root=self.root,stop=stop),daemon=True);thread.start()
        payload=b'generated fixture bytes'
        def browser():
            while True:
                m=out.queue.get(timeout=5)
                if m.get('type')=='request':break
            common=dict(id=m['id'],session=m['session'])
            incoming.send(dict(common,kind='image_start',mime='image/jpeg',bytes=len(payload)))
            self.assertEqual(out.queue.get(timeout=5)['sequence'],-1)
            incoming.send(dict(common,kind='image_chunk',sequence=0,data=base64.b64encode(payload).decode()))
            self.assertEqual(out.queue.get(timeout=5)['sequence'],0)
            incoming.send(dict(common,kind='image_end',chunks=1))
        worker=threading.Thread(target=browser);worker.start()
        try:
            result=self.c.request('https://tooncn.net/123-Ep-1/',operation='image',image_src='https://tooncn.net/wp-content/uploads/fixture/0001.jpg',timeout=3)
            self.assertEqual((self.root/'images'/result['image_file']).read_bytes(),payload)
            self.assertEqual(result['sha256'],hashlib.sha256(payload).hexdigest());self.assertFalse(list((self.root/'requests').glob('*.json')))
            worker.join(3)
        finally:self.c.disable();stop.set();incoming.queue.put(None);thread.join(3)

    def test_page_image_fetch_fake_browser_scope_and_no_tokens_exported(self):
        p=subprocess.run(['node',str(ROOT/'tests/test_tooncn_image.mjs')],capture_output=True,timeout=10,cwd=ROOT)
        self.assertEqual(p.returncode,0,p.stderr.decode('utf-8',errors='replace'))

    def test_invalid_image_chunk_does_not_publish_image_or_retry(self):
        self.c.enable();incoming=Pipe();out=Output();stop=threading.Event()
        thread=threading.Thread(target=serve_connection,args=(incoming,out,extension_origin()),kwargs=dict(root=self.root,stop=stop),daemon=True);thread.start()
        requests=[]
        def browser():
            while True:
                m=out.queue.get(timeout=5)
                if m.get('type')=='request':break
            requests.append(m);common=dict(id=m['id'],session=m['session'])
            incoming.send(dict(common,kind='image_start',mime='image/png',bytes=3));out.queue.get(timeout=5)
            incoming.send(dict(common,kind='image_chunk',sequence=5,data='AQID'))
        worker=threading.Thread(target=browser);worker.start()
        try:
            with self.assertRaisesRegex(SourceError,'INVALID_RESPONSE'):
                self.c.request('https://tooncn.net/123-Ep-1/',operation='image',image_src='https://tooncn.net/wp-content/uploads/fixture/0001.png',timeout=3)
            worker.join(3);self.assertEqual(len(requests),1);self.assertFalse(list((self.root/'images').glob('*.bin')))
        finally:self.c.disable();stop.set();incoming.queue.put(None);thread.join(3)


if __name__=='__main__':unittest.main()
