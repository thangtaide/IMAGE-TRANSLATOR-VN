"""Observed DOM excerpts plus synthetic browser transport. No live site/AGY."""
import copy
import hashlib
import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
from PIL import Image
from core.paths import ROOT,CACHE
from sources.contracts import InvalidURL,StructureChanged,AccessRestricted,AccessStatus
from sources.tooncn import ToonCNAdapter,normalize,parse_chapters,parse_images,valid_image_url
from sources.registry import resolve_adapter


def captured(name):return json.loads((ROOT/'tests/fixtures'/name).read_text(encoding='utf-8'))


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.topic=captured('tooncn_topic_projection.json');self.reader=captured('tooncn_reader_projection.json')
    def test_registered_domains_and_generalized_ids(self):
        for identifier in ['5701569','123','87654321']:
            self.assertIsInstance(resolve_adapter(f'https://tooncn.net/webtoon/{identifier}/'),ToonCNAdapter)
            self.assertEqual(normalize(f'https://tooncn.net/{identifier}-Ep-25')[0],f'https://tooncn.net/{identifier}-Ep-25/')
        for url in ['http://tooncn.net/webtoon/123/','https://tooncn.net.evil.example/webtoon/123/',
                    'https://user:password@tooncn.net/webtoon/123/','https://tooncn.net/webtoon/123/?token=secret']:
            with self.assertRaises(InvalidURL):normalize(url)
    def test_real_capture_chapters_use_list_only_and_original_website_gap(self):
        chapters=parse_chapters(self.topic)
        self.assertEqual(len(chapters),32);self.assertEqual(chapters[0].chapter_number,'1');self.assertEqual(chapters[-1].chapter_number,'33')
        self.assertNotIn('19',[c.chapter_number for c in chapters])
        self.assertEqual(chapters[0].chapter_url,'https://tooncn.net/5701569-Ep-1/')
    def test_capture_generalizes_without_hardcoded_comic_id(self):
        data=json.loads(json.dumps(self.topic).replace('5701569','12345'))
        self.assertTrue(all(c.chapter_id.startswith('12345-Ep-') for c in parse_chapters(data)))
    def test_real_reader_excerpt_uses_lazy_source_not_svg(self):
        images=parse_images(self.reader)
        self.assertEqual(len(images),3)
        self.assertEqual([i.source_url.rsplit('/',1)[-1] for i in images],['0001.jpg','0002.jpg','0003.jpg'])
        self.assertTrue(all(i.source_attribute=='data_src' for i in images))
        self.assertFalse(any('readerarea.svg' in i.source_url for i in images))
    def test_duplicate_missing_reordered_images_fail_closed(self):
        for mode in ('duplicate','missing','reverse'):
            d=copy.deepcopy(self.reader);images=[n for n in d['nodes'] if n['tag']=='img']
            if mode=='duplicate':images[1]['attributes']['data_src']=images[0]['attributes']['data_src']
            elif mode=='missing':images[1]['attributes'].pop('data_src')
            else:images[0]['attributes']['data_src'],images[1]['attributes']['data_src']=images[1]['attributes']['data_src'],images[0]['attributes']['data_src']
            with self.assertRaises(StructureChanged):parse_images(d)
    def test_changed_reader_and_chapter_structure_fail_closed(self):
        for data,parser,key in [(self.topic,parse_chapters,'chapterlist'),(self.reader,parse_images,'readerarea')]:
            d=copy.deepcopy(data)
            for row in d['nodes']:
                if row['attributes'].get('id')==key:row['attributes']['id']='changed'
            with self.assertRaises(StructureChanged):parser(d)
    def test_unsafe_and_thumbnail_urls_rejected(self):
        for url in ['https://tooncn.net/wp-content/themes/mangastream/assets/img/readerarea.svg',
                    'https://other.example/0001.jpg','https://tooncn.net/wp-content/uploads/a.jpg?token=secret']:
            self.assertIsNone(valid_image_url(url))
    def test_metadata_direct_chapter_and_download_in_existing_downloader(self):
        temp=tempfile.TemporaryDirectory(dir=CACHE,prefix='tooncn-adapter-test-');self.addCleanup(temp.cleanup)
        root=Path(temp.name).resolve();self.assertTrue(root.is_relative_to(CACHE.resolve()))
        topic=self.topic;reader=self.reader
        class Bridge:
            def __init__(self):self.root=root/'bridge';self.count=0
            def request(self,url,control=None,**kw):
                if kw.get('operation')!='image':return copy.deepcopy(topic if '/webtoon/' in url else reader)
                self.count+=1;p=self.root/'images'/(uuid4().hex+'.bin');p.parent.mkdir(parents=True,exist_ok=True)
                Image.new('RGB',(160,240),'white').save(p,'PNG');raw=p.read_bytes()
                return dict(image_file=p.name,sha256=hashlib.sha256(raw).hexdigest(),mime='image/png',bytes=len(raw))
        bridge=Bridge();adapter=ToonCNAdapter(bridge,download_policy='default_allow_public')
        comic=adapter.get_comic_info(self.topic['page_url']);chapters=adapter.get_chapters(comic)
        self.assertEqual(comic.title,'为民服务App');self.assertEqual(comic.chapter_count,32)
        direct=adapter.get_comic_info(self.reader['page_url']);self.assertEqual(direct.source_kind,'chapter')
        chapter=chapters[0]
        self.assertFalse(adapter.download_decision(chapter).allowed)
        adapter.get_chapter_images(chapter);self.assertTrue(adapter.download_decision(chapter).allowed)
        result=adapter.download_chapter(chapter,root/'download',limit=2)
        self.assertEqual([p.name for p in result.paths],['0001.png','0002.png']);self.assertEqual(bridge.count,2)
        manifest=json.loads((root/'download/download-manifest.json').read_text(encoding='utf-8'));self.assertTrue(manifest['sample']);self.assertEqual(manifest['state'],'sample_complete')
        adapter.download_chapter(chapter,root/'download',limit=2);self.assertEqual(bridge.count,2)
        with self.assertRaises(AccessRestricted):adapter.get_chapter_images(replace(chapter,access_status=AccessStatus.LOCKED))


if __name__=='__main__':unittest.main()
