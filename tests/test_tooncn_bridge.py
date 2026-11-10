"""Local native-host protocol/security tests. No Chrome, site or translation calls."""
import copy
import io
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import types
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from sources.tooncn_bridge import (BridgeError,MAX_MESSAGE,extension_origin,
    save_snapshot,serve_once,validate_snapshot)
from scripts.register_tooncn_host import registration_plan,register,REG_KEY
from core.paths import ROOT


def fixture():
    return {'version':1,'kind':'tooncn_dom','page_url':'https://tooncn.net/webtoon/123/',
            'title':'Synthetic fixture, NOT observed ToonCN reader',
            'nodes':[{'index':0,'parent':None,'tag':'h1','attributes':{'class':'fixture-title'},'text':'测试'},
                     {'index':1,'parent':None,'tag':'a','attributes':{'href':'https://tooncn.net/123-Ep-1/'},'text':'第1话'}]}


def frame(data):
    raw=json.dumps(data,ensure_ascii=False).encode('utf-8')
    return struct.pack('<I',len(raw))+raw


class ToonCNBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'inbox'

    def host(self, raw, origin=None):
        out=io.BytesIO()
        serve_once(io.BytesIO(raw),out,extension_origin() if origin is None else origin,root=self.root)
        result=out.getvalue();self.assertEqual(struct.unpack('<I',result[:4])[0],len(result)-4)
        return json.loads(result[4:])

    def test_manifest_has_only_tooncn_and_local_native_permissions(self):
        m=json.loads((ROOT/'extensions/tooncn_bridge/manifest.json').read_text())
        self.assertEqual(m['host_permissions'],['https://tooncn.net/*'])
        self.assertEqual(set(m['permissions']),{'scripting','nativeMessaging'})
        self.assertNotIn('content_scripts',m)
        self.assertNotIn('externally_connectable',m)
        self.assertRegex(extension_origin(),r'^chrome-extension://[a-p]{32}/$')

    def test_registration_plan_does_not_touch_registry_or_files(self):
        directory,manifest,launcher,data,batch=registration_plan()
        self.assertEqual(directory,ROOT/'config/tooncn_bridge')
        self.assertEqual(data['allowed_origins'],[extension_origin()])
        self.assertEqual(Path(data['path']),launcher)
        self.assertIn(' -I -u ',batch)
        self.assertNotIn('remote-debugging',batch)

    def registry_fixture(self,value):
        class Key:
            def __enter__(self):return self
            def __exit__(self,*args):pass
        deleted=[]
        def remove(hive,key,view,reserved):
            self.assertEqual(key,REG_KEY)
            if deleted:raise FileNotFoundError()
            deleted.append(view)
        fake=types.SimpleNamespace(KEY_WOW64_32KEY=1,KEY_WOW64_64KEY=2,KEY_READ=4,
            HKEY_CURRENT_USER=5,REG_SZ=1,OpenKey=lambda *a:Key(),QueryValueEx=lambda *a:(value,1),
            DeleteKeyEx=remove)
        return fake,deleted

    @unittest.skipUnless(sys.platform=='win32','Windows installer contract')
    def test_user_unregistration_handles_shared_registry_views_mock_only(self):
        fake,deleted=self.registry_fixture(str(registration_plan()[1]))
        with patch.dict(sys.modules,winreg=fake),redirect_stdout(io.StringIO()):register(remove=True)
        self.assertEqual(len(deleted),1)

    @unittest.skipUnless(sys.platform=='win32','Windows installer contract')
    def test_conflicting_registration_never_removed_mock_only(self):
        fake,deleted=self.registry_fixture(str(self.root/'another-app.json'))
        with patch.dict(sys.modules,winreg=fake):
            with self.assertRaisesRegex(ValueError,'BRIDGE_HOST_REGISTRATION_CONFLICT'):register(remove=True)
        self.assertEqual(deleted,[])

    def test_approved_snapshot_is_saved_private_without_overwrite(self):
        first=self.host(frame(fixture()));second=self.host(frame(fixture()))
        self.assertTrue(first['ok']);self.assertNotEqual(first['snapshot_id'],second['snapshot_id'])
        p=self.root/first['snapshot_id']/'snapshot.json'
        saved=json.loads(p.read_text(encoding='utf-8'))
        self.assertEqual(saved['data'],fixture())
        self.assertFalse(list(self.root.glob('*/snapshot.part')))
        self.assertEqual(len(list(self.root.glob('*/snapshot.json'))),2)
        if sys.platform=='win32':
            # The Windows API must report a protected DACL on each capture directory.
            result=subprocess.run(['icacls',str(p.parent)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0)
            self.assertNotIn('(I)',result.stdout)

    def test_wrong_origin_is_denied_before_read_or_write(self):
        class NoRead:
            def read(self,n):raise AssertionError('must not read an unapproved caller')
        out=io.BytesIO();serve_once(NoRead(),out,'chrome-extension://'+'a'*32+'/',root=self.root)
        self.assertEqual(json.loads(out.getvalue()[4:])['code'],'BRIDGE_ORIGIN_DENIED')
        self.assertFalse(self.root.exists())

    def test_non_tooncn_private_http_and_other_routes_rejected(self):
        for url in ['https://other.example/webtoon/123/','http://tooncn.net/webtoon/123/',
                    'https://tooncn.net/account/','https://user:password@tooncn.net/webtoon/123/',
                    'https://tooncn.net/webtoon/123/?token=DO_NOT_PERSIST',
                    'https://tooncn.net/webtoon/123/#private','https://tooncn.net.evil.example/webtoon/123/']:
            with self.subTest(url=url):
                data=fixture();data['page_url']=url
                self.assertFalse(self.host(frame(data))['ok'])
        self.assertFalse(self.root.exists())

    def test_secrets_commands_raw_html_and_output_paths_not_in_schema(self):
        for key in ['cookie','token','headers','html','command','output_path','environment']:
            d=fixture();d[key]='DO_NOT_PERSIST'
            self.assertFalse(self.host(frame(d))['ok'])
        self.assertFalse(self.root.exists())

    def test_unknown_attributes_controls_and_input_elements_rejected(self):
        for change in [{'attributes':{'onclick':'DO_NOT_PERSIST'}},{'tag':'input'},
                       {'attributes':{'class':'session_secret'}},{'text':'bad\nlog'},
                       {'tag':{}},{'index':True}]:
            d=fixture();d['nodes'][0].update(change)
            self.assertFalse(self.host(frame(d))['ok'])

    def test_image_urls_reject_query_secrets_and_private_networks(self):
        for url in ['https://cdn.example/image.jpg?token=DO_NOT_PERSIST','https://127.0.0.1/image.jpg',
                    'https://cdn.internal/image.jpg','file:///secret','data:image/png;base64,A']:
            d=fixture();d['nodes'][0].update(tag='img',attributes={'src':url})
            self.assertFalse(self.host(frame(d))['ok'])
        self.assertFalse(self.root.exists())

    def test_duplicate_json_keys_and_invalid_utf8_and_partial_frames_rejected(self):
        raw=b'{"kind":"tooncn_dom","kind":"secret"}'
        for message in [b'',b'\x01',struct.pack('<I',20)+b'{}',struct.pack('<I',1)+b'\xff',struct.pack('<I',len(raw))+raw]:
            self.assertFalse(self.host(message)['ok'])

    def test_size_limit_stops_before_allocating_or_writing(self):
        result=self.host(struct.pack('<I',MAX_MESSAGE+1))
        self.assertEqual(result['code'],'BRIDGE_MESSAGE_LIMIT')
        self.assertFalse(self.root.exists())

    def test_missing_duplicate_out_of_order_or_cyclic_node_ids_rejected(self):
        for index,parent in [(2,None),(0,None),(1,1),(1,3),(1,True)]:
            d=fixture();d['nodes'][1].update(index=index,parent=parent)
            self.assertFalse(self.host(frame(d))['ok'])

    def test_challenge_never_saved_as_content(self):
        d=fixture();d['title']='Just a moment...'
        self.assertEqual(self.host(frame(d))['code'],'CHALLENGE_PENDING')
        self.assertFalse(self.root.exists())

    def test_quota_never_deletes_old_data(self):
        first=self.host(frame(fixture()));p=self.root/first['snapshot_id']/'snapshot.json';before=p.read_bytes()
        with patch('sources.tooncn_bridge.STORE_LIMIT',1):
            self.assertEqual(self.host(frame(fixture()))['code'],'BRIDGE_STORE_FULL')
        self.assertEqual(p.read_bytes(),before)

    def test_private_storage_failure_does_not_store_payload(self):
        with patch('core.agy_error_evidence._private_directory',return_value=False):
            self.assertEqual(self.host(frame(fixture()))['code'],'BRIDGE_PRIVATE_STORAGE_REQUIRED')
        self.assertFalse(list(self.root.glob('*/snapshot.json')))

    def test_storage_error_never_leaks_exception(self):
        with patch('sources.tooncn_bridge.save_snapshot',side_effect=OSError('DO_NOT_PERSIST')):
            result=self.host(frame(fixture()))
        self.assertEqual(result,{'ok':False,'code':'BRIDGE_FAILED'})

    def test_native_protocol_accepts_short_reads_and_unicode(self):
        class Short(io.BytesIO):
            def read(self,n):return super().read(min(n,3))
        out=io.BytesIO();serve_once(Short(frame(fixture())),out,extension_origin(),root=self.root)
        self.assertTrue(json.loads(out.getvalue()[4:])['ok'])

    def test_native_host_in_real_local_python_process_no_browser(self):
        code=('import sys;from pathlib import Path;from sources.tooncn_bridge import serve_once;'
              'serve_once(sys.stdin.buffer,sys.stdout.buffer,sys.argv[1],root=Path(sys.argv[2]))')
        p=subprocess.run([sys.executable,'-c',code,extension_origin(),str(self.root)],input=frame(fixture()),
                         capture_output=True,timeout=10,cwd=ROOT)
        self.assertEqual(p.returncode,0);self.assertEqual(p.stderr,b'')
        self.assertTrue(json.loads(p.stdout[4:])['ok'])

    def test_js_capture_local_fixtures_no_chrome_or_network(self):
        p=subprocess.run(['node',str(ROOT/'tests/test_tooncn_capture.mjs')],capture_output=True,timeout=10,cwd=ROOT)
        self.assertEqual(p.returncode,0,p.stderr.decode('utf-8',errors='replace'))


if __name__=='__main__':unittest.main()
