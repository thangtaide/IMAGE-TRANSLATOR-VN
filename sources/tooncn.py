"""ToonCN adapter from observed, authorized Chrome DOM. Never fetches site via HTTP."""
from __future__ import annotations
from collections import OrderedDict
from dataclasses import replace
from decimal import Decimal
import hashlib
from pathlib import Path
import re
import shutil
import os
from urllib.parse import urlsplit
from uuid import uuid4

from sources.contracts import (WebsiteAdapter,ComicInfo,ChapterInfo,ChapterImage,DiscoveryList,
    AccessStatus,AccessRestricted,InvalidURL,StructureChanged,CacheError,SourceError,UsageLimited)
from sources.security import https_url,contained
from sources.cache import inspect_image
from sources.tooncn_bridge import validate_snapshot
from sources.tooncn_connection import connection
from sources.download_policy import load_download_policy,decide_download

HOSTS=('tooncn.net',)
TOPIC=re.compile(r'/webtoon/([1-9][0-9]*)/?')
CHAPTER=re.compile(r'/([1-9][0-9]*)-Ep-([0-9]+(?:\.[0-9]+)?)/?')


def normalize(url):
    p=https_url(url,HOSTS)
    if p.query or p.fragment:raise InvalidURL('ToonCN: dùng URL truyện/chương không có query hoặc fragment.')
    topic=TOPIC.fullmatch(p.path);chapter=CHAPTER.fullmatch(p.path)
    if topic:return f'https://tooncn.net/webtoon/{topic[1]}/','topic',topic[1],None
    if chapter:return f'https://tooncn.net/{chapter[1]}-Ep-{chapter[2]}/','chapter',chapter[1],chapter[2]
    raise InvalidURL('ToonCN: cần /webtoon/<id>/ hoặc /<id>-Ep-<số chương>/.')


class Projection:
    def __init__(self,data):
        validate_snapshot(data);self.data=data;self.rows=data['nodes'];self.by={n['index']:n for n in self.rows}
    def under(self,row,*,identifier=None,cls=None):
        while row:
            a=row['attributes']
            if identifier and a.get('id')==identifier or cls and cls in a.get('class','').split():return True
            row=self.by.get(row['parent'])
        return False
    def descendants_text(self,row):
        indexes={row['index']};parts=[]
        for n in self.rows[row['index']:]:
            if n['parent'] in indexes:indexes.add(n['index'])
            if n['index'] in indexes and n['text']:parts.append(n['text'])
        return ' '.join(parts)
    def title(self):
        values=[n['text'] for n in self.rows if n['tag']=='h1' and 'entry-title' in n['attributes'].get('class','').split()]
        if len(values)!=1 or not values[0].strip():raise StructureChanged('TOONCN_TITLE_MISSING: DOM chưa có tiêu đề truyện/chương thật.')
        return values[0]


def parse_chapters(data):
    tree=Projection(data);url,kind,comic_id,_=normalize(data['page_url'])
    if kind!='topic':raise StructureChanged('TOONCN_TOPIC_REQUIRED')
    roots=[n for n in tree.rows if n['attributes'].get('id')=='chapterlist']
    if len(roots)!=1:raise StructureChanged('TOONCN_CHAPTER_LIST_MISSING')
    found={}
    for row in tree.rows:
        href=row['attributes'].get('href')
        if row['tag']!='a' or not href or not tree.under(row,identifier='chapterlist'):continue
        try:chapter_url,category,owner,number=normalize(href)
        except InvalidURL:raise StructureChanged('TOONCN_CHAPTER_LINK_CHANGED') from None
        if category!='chapter' or owner!=comic_id:raise StructureChanged('TOONCN_CHAPTER_ID_MISMATCH')
        if chapter_url in found:raise StructureChanged('TOONCN_DUPLICATE_CHAPTER')
        labels=[n for n in tree.rows if n['attributes'].get('class')=='chapternum' and n['parent']==row['index']]
        title=tree.descendants_text(labels[0]) if labels else 'Ep '+number
        found[chapter_url]=ChapterInfo(f'{owner}-Ep-{number}',title,number,chapter_url,AccessStatus.UNKNOWN,0)
    if not found:raise StructureChanged('TOONCN_CHAPTER_LIST_EMPTY')
    ordered=sorted(found.values(),key=lambda c:Decimal(c.chapter_number))
    return DiscoveryList([replace(c,order_index=i) for i,c in enumerate(ordered)],complete=True,
        analysis=dict(source='rendered #chapterlist .eph-num a',observed_links=len(ordered)))


def valid_image_url(url,base=None):
    try:
        p=https_url(url,HOSTS)
        if p.query or p.fragment or not p.path.startswith('/wp-content/uploads/') or not re.search(r'\.(?:jpe?g|png|webp|bmp)$',p.path,re.I):return None
        return url
    except (InvalidURL,TypeError):return None


def parse_images(data):
    tree=Projection(data);_,kind,owner,number=normalize(data['page_url'])
    if kind!='chapter':raise StructureChanged('TOONCN_CHAPTER_REQUIRED')
    tree.title();roots=[n for n in tree.rows if n['attributes'].get('id')=='readerarea']
    if len(roots)!=1:raise StructureChanged('TOONCN_READER_MISSING')
    images=[];seen=set()
    for row in tree.rows:
        if row['tag']!='img' or not tree.under(row,identifier='readerarea'):continue
        a=row['attributes']
        if 'ts-main-image' not in a.get('class','').split():raise StructureChanged('TOONCN_READER_IMAGE_CLASS_CHANGED')
        candidates=[(key,a.get(key)) for key in ('data_src','data_lazy_src','current_src','src') if valid_image_url(a.get(key))]
        if not candidates:raise StructureChanged('TOONCN_IMAGE_URL_MISSING_OR_PLACEHOLDER')
        if len({value for _,value in candidates})>1:raise StructureChanged('TOONCN_IMAGE_SOURCE_AMBIGUOUS')
        attribute,url=candidates[0]
        if url in seen:raise StructureChanged('TOONCN_DUPLICATE_IMAGE')
        seen.add(url);images.append(ChapterImage(len(images)+1,url,source_attribute=attribute))
    if not images:raise StructureChanged('TOONCN_IMAGE_LIST_EMPTY')
    numbers=[re.fullmatch(r'(\d{4})\.(?:jpg|png|webp|bmp)',urlsplit(i.source_url).path.rsplit('/',1)[-1],re.I) for i in images]
    if all(numbers) and [int(n[1]) for n in numbers]!=list(range(1,len(images)+1)):
        raise StructureChanged('TOONCN_IMAGE_SEQUENCE_GAP_OR_REORDER')
    return DiscoveryList(images,complete=True,analysis=dict(source='rendered #readerarea img.ts-main-image',
        order='DOM order verified; numbered sequence when available',lazy_loading='data-src precedes SVG placeholder'))


class ToonCNAdapter(WebsiteAdapter):
    site_id='tooncn';hosts=HOSTS
    support_status='AUTHORIZED_CHROME_CONTEXT'
    download_enabled=True
    def __init__(self,bridge=None,download_policy=None):
        self.bridge=bridge;self.policy=download_policy or load_download_policy();self._documents=OrderedDict();self._images={}
        self.download_progress=None
    def transport(self):return self.bridge or connection()
    def _request(self,url,control=None,**kwargs):
        try:return self.transport().request(url,control,**kwargs)
        except SourceError as exc:
            code=str(exc).split(':',1)[0]
            if code in ('TOONCN_CHALLENGE_PENDING','TOONCN_ACCESS_DENIED'):
                raise AccessRestricted(code+': Website đang xác minh hoặc từ chối truy cập trong Chrome; không tự vượt chặn.') from None
            if code=='TOONCN_RATE_LIMITED':raise UsageLimited(code+': Website giới hạn truy cập; dừng, không tự retry.') from None
            raise
    def normalize_url(self,url):return normalize(url)[0]
    def url_kind(self,url):return normalize(url)[1]
    def _snapshot(self,url,control=None):
        url=self.normalize_url(url)
        data=self._request(url,control)
        self._documents[url]=data;self._documents.move_to_end(url)
        while len(self._documents)>2:self._documents.popitem(last=False)
        return data
    def get_comic_info(self,url,control=None):
        url,kind,identifier,number=normalize(url);data=self._snapshot(url,control);title=Projection(data).title()
        if kind=='topic':
            chapters=parse_chapters(data)
            return ComicInfo(self.site_id,identifier,url,title=title,chapter_count=len(chapters),source_kind='topic',topic_url=url)
        title=re.sub(r'\s*[–-]\s*Ep\s*[0-9.]+\s*$','',title)
        return ComicInfo(self.site_id,identifier,url,title=title,source_kind='chapter',topic_url=f'https://tooncn.net/webtoon/{identifier}/')
    def get_chapters(self,comic,control=None):
        url,kind,identifier,number=normalize(comic.source_url)
        if kind=='topic':return parse_chapters(self._documents.get(url) or self._snapshot(url,control))
        return DiscoveryList([ChapterInfo(f'{identifier}-Ep-{number}','Ep '+number,number,url,AccessStatus.UNKNOWN,0)],complete=False)
    def refresh_chapters(self,comic,control=None):
        self._documents.clear();return self.get_chapters(comic,control)
    def get_chapter_images(self,chapter,control=None):
        if chapter.access_status in (AccessStatus.LOCKED,AccessStatus.RESTRICTED):raise AccessRestricted('TOONCN_ACCESS_RESTRICTED')
        url,kind,owner,number=normalize(chapter.chapter_url)
        if kind!='chapter' or chapter.chapter_id!=f'{owner}-Ep-{number}':raise StructureChanged('TOONCN_CHAPTER_ID_MISMATCH')
        images=parse_images(self._snapshot(url,control));self._images[chapter.chapter_id]=images;return images
    def download_decision(self,chapter):
        # Readable in the user-authorized browser, not evidence of content licensing.
        verified=bool(self._images.get(chapter.chapter_id))
        observed=replace(chapter,access_status=AccessStatus.PUBLIC) if verified and chapter.access_status==AccessStatus.UNKNOWN else chapter
        return decide_download(observed,self.policy,images_safe=True if verified else None)
    def download_chapter(self,chapter,cache_dir,control=None,*,limit=None,limits=None):
        from sources.kuaikan_download import download_images,DownloadLimits,_usage
        from core.paths import CACHE
        images=self.get_chapter_images(chapter,control);decision=self.download_decision(chapter)
        if not decision.allowed:raise AccessRestricted(decision.reason)
        def fetch(url,directory,bounds,checkpoint,progress):
            result=self._request(chapter.chapter_url,control,operation='image',image_src=url,timeout=60)
            name=result.get('image_file','')
            if not re.fullmatch(r'[a-f0-9]{32}\.bin',name):raise CacheError('TOONCN_IMAGE_RECEIPT_INVALID')
            source=contained(self.transport().root/'images',name)
            info=inspect_image(source,bounds.max_image_bytes)
            if info['sha256']!=result.get('sha256') or info['content_type']!=result.get('mime') or info['bytes']!=result.get('bytes'):
                raise CacheError('TOONCN_IMAGE_RECEIPT_MISMATCH')
            if info['width']<=1 or info['height']<=1:raise CacheError('TOONCN_IMAGE_PLACEHOLDER')
            if (_usage(directory)+info['bytes']>bounds.max_chapter_bytes or _usage(CACHE)+info['bytes']>bounds.max_cache_bytes
                    or shutil.disk_usage(directory).free<info['bytes']+1_000_000):raise CacheError('TOONCN_DOWNLOAD_QUOTA')
            temporary=contained(directory,uuid4().hex+'.part')
            with source.open('rb') as src,temporary.open('xb') as dst:
                while True:
                    checkpoint();block=src.read(65536)
                    if not block:break
                    dst.write(block)
                dst.flush();os.fsync(dst.fileno())
            if inspect_image(temporary)['sha256']!=info['sha256']:raise CacheError('TOONCN_IMAGE_COPY_MISMATCH')
            source.unlink()  # Only this request's ephemeral transport file, not source cache.
            progress(dict(stage='downloading',bytes_received=info['bytes'],expected_bytes=info['bytes']))
            return temporary,dict(info,http_status=200)
        return download_images(chapter,images,Path(cache_dir),decision,control,self.download_progress,limit=limit,
            limits=limits or DownloadLimits(max_images=500,seconds=60,delay=.5),image_fetcher=fetch,url_validator=valid_image_url)
