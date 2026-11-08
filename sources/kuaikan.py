"""Topic/chapter adapter for public HTTP HTML/state and supplied captured DOM.

Public embedded page data is read without executing JavaScript. Runtime HTTP
acquisition is a separate capability; discovery never grants download rights.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import replace
from html.parser import HTMLParser

from sources.contracts import ChapterInfo, ComicInfo, DiscoveryList, InvalidURL, StructureChanged, WebsiteAdapter
from sources.kuaikan_dom import Document, ReaderPage, discover_chapters, discover_images, normalize, parse_reader
from sources.metadata_http import fetch_public_html
from sources.security import https_url
from sources.kuaikan_state import page_payload


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.hidden=0;self.parts=[];self.heading=False;self.headings=[];self.author=None
    def handle_starttag(self,tag,attrs):
        if tag in ['script','style']:self.hidden+=1
        if tag=='h3':self.heading=True;self.headings.append([])
        fields=dict(attrs)
        if tag=='meta' and fields.get('name','').lower()=='author':self.author=fields.get('content')
    def handle_endtag(self,tag):
        if tag in ['script','style']:self.hidden=max(0,self.hidden-1)
        if tag=='h3':self.heading=False
    def handle_data(self,data):
        if not self.hidden:
            self.parts.append(data)
            if self.heading:self.headings[-1].append(data)


class KuaikanAdapter(WebsiteAdapter):
    site_id='kuaikanmanhua'
    hosts=('www.kuaikanmanhua.com',)
    support_status='PUBLIC_HTTP_PARSER; DEFAULT_ALLOW_PUBLIC; CONTENT_PERMISSION_UNKNOWN'
    terms_url='https://www.kuaikanmanhua.com/webs/agreement'
    download_enabled=False

    def __init__(self, download_policy: str | None = None):
        from sources.download_policy import load_download_policy
        self.download_policy = download_policy if download_policy is not None else load_download_policy()
        self._documents: OrderedDict[str, str] = OrderedDict()
        self._image_lists = {}
        self._image_safe = {}
        self._barriers = {}
        self.permission_evidence = {}
        self.download_progress = None

    def normalize_url(self,url):
        return normalize(url)[0]

    def url_kind(self, url: str) -> str:
        return normalize(url)[1]

    def chapter_id_from_url(self, url: str) -> str:
        _, category, identifier = normalize(url)
        if category != 'chapter':
            raise InvalidURL('URL được nhập là topic, không phải chương comic-next.')
        return identifier

    def load_document(self, url: str, html: str) -> None:
        """Preload supplied HTML/rendered DOM. Does not assert live verification/rights."""
        url = self.normalize_url(url)
        if len(html.encode('utf-8')) > 5_000_000:
            raise StructureChanged('HTML/DOM vượt giới hạn 5 MB.')
        self._documents[url] = html
        self._documents.move_to_end(url)
        while len(self._documents) > 2:
            self._documents.popitem(last=False)

    def _html(self, url, control=None):
        url = self.normalize_url(url)
        if control:
            control.checkpoint()
        if url not in self._documents:
            self.load_document(url, fetch_public_html(url, self.hosts, control))
        return self._documents[url]

    def parse_reader_html(self, url: str, html: str) -> ReaderPage:
        return parse_reader(url, html)

    def parse_chapters_html(self, url: str, html: str, advertised: int | None = None):
        url, category, _ = normalize(url)
        if category != 'topic':
            raise InvalidURL('Cần URL topic để trích xuất danh sách chương.')
        return discover_chapters(Document(html), url, advertised)

    def parse_topic_html(self,url: str,html: str) -> ComicInfo:
        url=self.normalize_url(url)
        if self.url_kind(url) != 'topic':
            raise InvalidURL('parse_topic_html chỉ nhận URL topic.')
        parser=_VisibleText();parser.feed(html)
        warnings = ()
        try:
            payload=page_payload(Document(html))
        except StructureChanged:
            payload=None
            warnings=('Không đọc được Nuxt state; giữ metadata DOM, bước ánh xạ chương sẽ báo lỗi riêng.',)
        info=payload.get('topic_info',{}) if payload else {}
        if info and str(info.get('id')) != url.rstrip('/').split('/')[-1]:
            raise StructureChanged('Topic ID trong state không khớp URL; không trộn truyện.')
        title=''.join(parser.headings[0]).strip() if parser.headings else None
        text=' '.join(parser.parts).split('热门评论', 1)[0]
        count=re.search(r'共\s*(\d+)\s*个内容',text)
        main=re.search(r'共\s*(\d+)\s*篇正文',text)
        if not title or not count:
            raise StructureChanged('HTML chưa có metadata topic được xác minh; không suy đoán API hoặc dữ liệu JavaScript.')
        return ComicInfo(self.site_id,url.rstrip('/').split('/')[-1],url,title=title,
            author=info.get('user',{}).get('nickname') or parser.author,chapter_count=int(count[1]),main_chapter_count=int(main[1]) if main else None,
            source_kind='topic',topic_url=url,warnings=warnings,
            status=next((status for status in ['暂时停更','已完结','连载中'] if status in text),None))

    def get_comic_info(self,url,control=None):
        url=self.normalize_url(url)
        html=self._html(url,control)
        if self.url_kind(url) == 'topic':
            return self.parse_topic_html(url,html)
        reader = self.parse_reader_html(url,html)
        topic_id = normalize(reader.topic_url)[2] if reader.topic_url else None
        warnings = ('Đang phân tích một URL chương, không phải toàn bộ danh sách chương của truyện.',)
        if topic_id is None:
            warnings += ('Chưa xác minh được truyện gốc; comic_id/topic_url để null.',)
        return ComicInfo(self.site_id,topic_id,url,title=reader.comic_title,
                         source_kind='chapter',topic_url=reader.topic_url,warnings=warnings)

    def get_chapters(self,comic,control=None):
        if not isinstance(comic, ComicInfo) or not comic.source_url:
            raise StructureChanged('Cần metadata truyện hợp lệ trước khi phân tích danh sách chương.')
        url=self.normalize_url(comic.source_url)
        html=self._html(url,control)
        if self.url_kind(url) == 'chapter':
            return DiscoveryList([self.parse_reader_html(url,html).chapter],
                                 warnings=comic.warnings,complete=False)
        return self.parse_chapters_html(url,html,comic.chapter_count)

    def refresh_chapters(self,comic,control=None):
        self._image_lists.clear()
        self._image_safe.clear()
        self._documents.pop(self.normalize_url(comic.source_url),None)
        return self.get_chapters(comic,control)

    def download_decision(self,chapter):
        from sources.download_policy import decide_download
        from sources.kuaikan_dom import image_url
        images = self._image_lists.get(chapter.chapter_id)
        safe = self._image_safe.get(chapter.chapter_id)
        if images and any(not i.source_url or image_url(i.source_url, chapter.chapter_url) != i.source_url for i in images):
            safe = False
        decision = decide_download(chapter, self.download_policy, images_safe=safe,
            evidence=self.permission_evidence.get(chapter.chapter_id), barrier=self._barriers.get(chapter.chapter_id))
        return replace(decision, evidence_url=decision.evidence_url or self.terms_url)

    def get_chapter_images(self,chapter,control=None):
        from sources.contracts import AccessRestricted, AccessStatus
        if not isinstance(chapter, ChapterInfo) or not chapter.chapter_url:
            raise StructureChanged('Cần metadata chương và URL đã xác minh để phân tích ảnh.')
        if chapter.access_status in (AccessStatus.LOCKED, AccessStatus.RESTRICTED):
            raise AccessRestricted('Chương bị khóa/hạn chế; không phân tích ảnh bị hạn chế truy cập.')
        self._image_lists.pop(chapter.chapter_id, None)
        self._image_safe.pop(chapter.chapter_id, None)
        url=self.normalize_url(chapter.chapter_url)
        try:
            reader=self.parse_reader_html(url,self._html(url,control))
        except AccessRestricted:
            self._barriers[chapter.chapter_id] = 'Truy cập trang chương bị từ chối/giới hạn; không vượt chặn.'
            raise
        if reader.chapter.chapter_id != chapter.chapter_id:
            raise StructureChanged('ID URL không khớp chương; không trộn nguồn ảnh.')
        if reader.chapter.access_status != chapter.access_status and reader.chapter.access_status != AccessStatus.PUBLIC:
            self._barriers[chapter.chapter_id] = 'Trạng thái reader mới không còn PUBLIC; dừng tải.'
        images = discover_images(reader)
        self._image_lists[chapter.chapter_id] = images
        self._image_safe[chapter.chapter_id] = bool(images) and not images.analysis.get('manifest_rejected_entries') and (
            not images.analysis.get('manifest_items') or images.analysis.get('dom_manifest_consistent') is True)
        return images

    def download_chapter(self, chapter, cache_dir, control=None, *, limit=None, limits=None):
        from sources.contracts import AccessRestricted, InvalidURL
        from sources.kuaikan_download import download_images
        if self.download_decision(chapter).state.value == 'BLOCKED':
            raise AccessRestricted(self.download_decision(chapter).reason)
        images = self.get_chapter_images(chapter, control)
        decision = self.download_decision(chapter)
        if not decision.allowed:
            raise AccessRestricted(decision.reason)
        try:
            return download_images(chapter, images, cache_dir, decision, control, self.download_progress,
                                   limit=limit, limits=limits)
        except (AccessRestricted, InvalidURL):
            self._barriers[chapter.chapter_id] = 'CDN/URL bị hạn chế, không an toàn hoặc không trả ảnh. Dừng; không retry vượt chặn.'
            raise

