"""Kuaikan discovery from supplied DOM and its observed public Nuxt page data.

Selectors and alias grammar are verified against captured topic/reader DOM.
Discovery never fetches images or grants download permission; no JS is executed.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit

from sources.contracts import AccessRestricted, AccessStatus, ChapterImage, ChapterInfo, DiscoveryList, InvalidURL, StructureChanged
from sources.security import https_url
from sources.kuaikan_state import page_payload

HOSTS = ('www.kuaikanmanhua.com',)
# Hostname supplied by the user, NOT a wildcard for all Kuaikan/CDN resources.
IMAGE_HOSTS = ('tn1.kkmh.com',)
TOPIC = re.compile(r'/web/topic/([1-9][0-9]*)/?')
CHAPTER = re.compile(r'/webs/comic-next/([1-9][0-9]*)/?')
MAIN_NUMBER = re.compile(r'第\s*([0-9０-９一二三四五六七八九十百千零两〇]+)\s*[话話章回集]')
EXTRAS = re.compile(r'番外|预告|預告|公告|通知|停更|外传|外傳|福利|开奖')
LOCKED = re.compile(r'🔒|付费阅读|付費閱讀|需付费|需要付费|购买本话|VIP章节|登录后阅读')
STOP = re.compile(r'热门评论|熱門評論|相关推荐|猜你喜欢|推荐作品')
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


def normalize(url: str) -> tuple[str, str, str]:
    parsed = https_url(url, HOSTS)
    match = TOPIC.fullmatch(parsed.path)
    if match:
        return 'https://' + HOSTS[0] + '/web/topic/' + match[1] + '/', 'topic', match[1]
    match = CHAPTER.fullmatch(parsed.path)
    if match:
        return 'https://' + HOSTS[0] + '/webs/comic-next/' + match[1], 'chapter', match[1]
    raise InvalidURL('URL phải là /web/topic/<id>/ hoặc /webs/comic-next/<chapter_id> trên www.kuaikanmanhua.com.')


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    index: int
    parent: Node | None = None
    children: list[Node | str] = field(default_factory=list)

    def text(self) -> str:
        if self.tag in ('script', 'style', 'template'):
            return ''
        return ' '.join(child if isinstance(child, str) else child.text() for child in self.children)

    def ancestors(self):
        node = self.parent
        while node:
            yield node
            node = node.parent


class Document(HTMLParser):
    def __init__(self, html: str):
        super().__init__(convert_charrefs=True)
        if len(html.encode('utf-8')) > 5_000_000:
            raise StructureChanged('HTML/DOM vượt giới hạn 5 MB.')
        self.root = Node('document', {}, 0)
        self.stack = [self.root]
        self.nodes = []
        self.text_events = []
        self.content_events = []
        self.index = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.index += 1
        node = Node(tag, {k: v or '' for k, v in attrs}, self.index, self.stack[-1])
        self.nodes.append(node)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, data):
        self.index += 1
        self.stack[-1].children.append(data)
        if not any(node.tag in ('script', 'style', 'template') for node in self.stack):
            text = ' '.join(data.split())
            self.text_events.append((self.index, text))
            if not any(node.tag in ('head', 'header', 'nav', 'aside', 'footer') for node in self.stack):
                self.content_events.append((self.index, text))

    def visible(self) -> str:
        return ' '.join(text for _, text in self.text_events).split('热门评论', 1)[0]

    def reader_visible(self) -> str:
        text = ' '.join(value for _, value in self.content_events)
        end = STOP.search(text)
        return text[:end.start()] if end else text


def clean(text: str) -> str:
    return ' '.join(text.split())


def chapter_number(title: str) -> str | None:
    match = MAIN_NUMBER.search(title)
    if not match:
        return None
    number = unicodedata.normalize('NFKC', match[1])
    if number.isdecimal():
        return str(int(number))
    digits = dict(zip('零〇一二两三四五六七八九', [0, 0, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9]))
    value = current = 0
    for char in number:
        if char in digits:
            current = digits[char]
        elif char in '十百千':
            value += (current or 1) * {'十': 10, '百': 100, '千': 1000}[char]
            current = 0
        else:
            return None
    return str(value + current)


def kind(title: str) -> str:
    if MAIN_NUMBER.match(title):
        return 'main'
    if EXTRAS.search(title):
        return 'supplementary'
    return 'main' if MAIN_NUMBER.search(title) else 'unknown'


def valid_chapter_link(href: str, base: str) -> tuple[str, str] | None:
    if not href or href.startswith(('#', 'javascript:', 'data:')):
        return None
    try:
        url, category, identifier = normalize(urljoin(base, href))
    except InvalidURL:
        return None
    return (url, identifier) if category == 'chapter' else None


def has_class(node: Node, name: str) -> bool:
    return name in node.attrs.get('class', '').split()


def topic_items(document: Document) -> list[Node]:
    return [node for node in document.nodes if has_class(node, 'title-item')
            and any(has_class(parent, 'TopicEpisode') for parent in node.ancestors())]


def record_access(record: dict) -> AccessStatus:
    if record.get('locked') is True:
        return AccessStatus.LOCKED
    if any(record.get(key) is True for key in ('need_vip', 'is_pay_comic', 'need_login',
            'login_required', 'requires_login', 'drm', 'captcha', 'need_captcha')):
        return AccessStatus.RESTRICTED
    if (record.get('is_free') is True and record.get('locked') is False
            and record.get('need_vip') is False and record.get('is_pay_comic') is False):
        return AccessStatus.PUBLIC  # Snapshot reading status; never download permission.
    return AccessStatus.UNKNOWN


def numeric_id(value) -> str | None:
    return str(value) if type(value) is int and value > 0 else None


def captured_chapters(document: Document, topic_url: str, advertised: int | None, items: list[Node]):
    payload = page_payload(document)
    info = payload.get('topic_info', {}) if payload else {}
    if numeric_id(info.get('id')) != normalize(topic_url)[2]:
        raise StructureChanged('Không có topic ID trùng URL trong Nuxt state để ánh xạ mục chương không có href.')
    records = info.get('comics')
    if not isinstance(records, list):
        raise StructureChanged('Nuxt topic_info thiếu comics array đã quan sát trong DOM mẫu.')
    if not items:
        # Initial HTTP HTML has an empty episode region but this same public
        # topic_info.comics array. Preserve its explicit order, never sort IDs.
        result, seen, missing = [], set(), 0
        for index, record in enumerate(records):
            identifier = numeric_id(record.get('id')) if isinstance(record, dict) else None
            title = clean(record['title']) if isinstance(record, dict) and isinstance(record.get('title'), str) else ''
            if not identifier or not title or identifier in seen:
                missing += 1
                continue
            seen.add(identifier)
            result.append(ChapterInfo(identifier, title, chapter_number(title),
                'https://' + HOSTS[0] + '/webs/comic-next/' + identifier, record_access(record), index,
                content_kind=kind(title), url_source='embedded_id+verified_route'))
        if not result:
            raise StructureChanged('Nuxt topic_info.comics không có ID/tiêu đề chương hợp lệ.')
        warnings = ['Danh sách lấy từ public topic_info.comics trong HTML ban đầu; giữ thứ tự mảng state, không phải thứ tự mục DOM sau render.']
        complete = len(result) == len(records) == advertised if advertised is not None else None
        if complete is not True:
            warnings.append(f'Danh sách state từng phần: {len(result)}/{len(records)} record hợp lệ; {missing} record thiếu/trùng ID hoặc tiêu đề.')
        return DiscoveryList(result, complete=complete, warnings=warnings, analysis={
            'source': 'embedded_state', 'order_source': 'topic_info.comics', 'dom_items': 0,
            'state_items': len(records), 'advertised_count': advertised,
            'advertised_main_count': info.get('comic_body_count'), 'mapped_items': len(result),
            'literal_href_count': 0, 'derived_url_count': len(result), 'missing_url_count': missing,
            'main_count': sum(c.content_kind == 'main' for c in result),
            'supplementary_count': sum(c.content_kind == 'supplementary' for c in result),
            'unknown_kind_count': sum(c.content_kind == 'unknown' for c in result)})
    identity = lambda text: re.sub(r'\s+', '', unicodedata.normalize('NFC', text))
    by_title = {}
    for record in records:
        if isinstance(record, dict) and isinstance(record.get('title'), str) and numeric_id(record.get('id')):
            by_title.setdefault(identity(record['title']), []).append(record)
    result, seen = [], set()
    literal = derived = missing = 0
    for index, node in enumerate(items):
        title = clean(node.text())
        matches = by_title.get(identity(title), [])
        if len(matches) != 1:
            missing += 1
            continue
        record = matches[0]
        identifier = numeric_id(record['id'])
        if identifier in seen:
            missing += 1
            continue
        seen.add(identifier)
        links = [valid_chapter_link(child.attrs.get('href', ''), topic_url) for child in document.nodes
                 if child.tag == 'a' and (child is node or any(parent is node for parent in child.ancestors()))]
        links = [link for link in links if link]
        if links:
            if any(link[1] != identifier for link in links):
                raise StructureChanged('Href chương mâu thuẫn với ánh xạ ID/tiêu đề trong state; không trộn dữ liệu.')
            url, _ = links[0]
            source = 'dom_href'
            literal += 1
        else:
            # ID/title come from this DOM; the route is verified by reader capture.
            url = 'https://' + HOSTS[0] + '/webs/comic-next/' + identifier
            source = 'embedded_id+verified_route'
            derived += 1
        result.append(ChapterInfo(identifier, title, chapter_number(title), url, record_access(record), index,
                                  content_kind=kind(title), url_source=source))
    if not result:
        raise StructureChanged('Có mục chương nhưng không ánh xạ được tiêu đề duy nhất sang ID thực trong state.')
    complete = len(result) == len(items) == advertised if advertised is not None else None
    warnings = ['URL chương không có href được lập từ ID thật trong Nuxt và route reader đã xác minh; không phải href literal.']
    if missing or complete is not True:
        warnings.append(f'Danh sách từng phần: {len(result)}/{len(items)} mục DOM ánh xạ được; {missing} mục thiếu URL/ánh xạ.')
    return DiscoveryList(result, complete=complete, warnings=warnings, analysis={
        'source': 'captured_structure+embedded_state', 'dom_items': len(items), 'state_items': len(records),
        'advertised_count': advertised, 'advertised_main_count': info.get('comic_body_count'),
        'mapped_items': len(result), 'literal_href_count': literal, 'derived_url_count': derived,
        'missing_url_count': missing, 'main_count': sum(c.content_kind == 'main' for c in result),
        'supplementary_count': sum(c.content_kind == 'supplementary' for c in result),
        'unknown_kind_count': sum(c.content_kind == 'unknown' for c in result)})


def discover_chapters(document: Document, topic_url: str, advertised: int | None) -> DiscoveryList[ChapterInfo]:
    items = topic_items(document)
    if items:
        return captured_chapters(document, topic_url, advertised, items)
    payload = page_payload(document)
    if payload and isinstance(payload.get('topic_info'), dict) and 'comics' in payload['topic_info']:
        return captured_chapters(document, topic_url, advertised, [])
    # Scope by the observed visible chapter heading, not a guessed CSS class.
    starts = [index for index, text in document.text_events if '章节列表' in text or '章節列表' in text]
    starts += [node.index for node in document.nodes if node.attrs.get('aria-label') in ('章节列表', '章節列表')]
    if not starts:
        raise StructureChanged('HTML/DOM thiếu mục danh sách chương. Cần DOM sau render nếu JavaScript tạo mục này.')
    start = min(starts)
    end = min([index for index, text in document.text_events if index > start and STOP.search(text)] or [document.index + 1])
    result = []
    seen = set()
    for node in document.nodes:
        if node.tag != 'a' or not start < node.index < end:
            continue
        if any(parent.tag in ('script', 'style', 'template') for parent in node.ancestors()):
            continue
        link = valid_chapter_link(node.attrs.get('href', ''), topic_url)
        title = clean(node.text() or node.attrs.get('title', '') or node.attrs.get('aria-label', ''))
        if not link or kind(title) == 'unknown' or link[1] in seen:
            continue
        seen.add(link[1])
        access = AccessStatus.LOCKED if LOCKED.search(title + ' ' + node.attrs.get('aria-label', '')) else AccessStatus.UNKNOWN
        result.append(ChapterInfo(link[1], title, chapter_number(title), link[0], access,
                                  len(result), content_kind=kind(title), url_source='dom_href'))
    if not result:
        raise StructureChanged('Có mục chương nhưng không tìm thấy thẻ a/href comic-next kèm tiêu đề chương. Không suy đoán onclick/API; cần HTML/DOM sau render.')
    warnings = ['Giữ thứ tự xuất hiện trong DOM; chưa suy ra thứ tự phát hành từ ID chương.']
    complete = len(result) == advertised if advertised is not None else None
    if not complete:
        warnings.append(f'Danh sách từng phần: xác minh {len(result)} link; số nội dung công bố: {advertised if advertised is not None else "chưa biết"}.')
    return DiscoveryList(result, warnings=warnings, complete=complete)


@dataclass(frozen=True)
class ReaderPage:
    chapter: ChapterInfo
    topic_url: str | None
    comic_title: str | None
    previous_url: str | None
    next_url: str | None
    document: Document
    payload: dict | None = None


def parse_reader(url: str, html: str) -> ReaderPage:
    url, category, identifier = normalize(url)
    if category != 'chapter':
        raise InvalidURL('Cần URL chương comic-next.')
    document = Document(html)
    payload = page_payload(document)
    info = payload.get('comic_info', {}) if payload else {}
    if info and numeric_id(info.get('id')) != identifier:
        raise StructureChanged('Chapter ID trong state không khớp URL được nhập.')
    headings = [node for node in document.nodes if node.tag in ('h1', 'h2', 'h3')
                and kind(clean(node.text())) != 'unknown'
                and not any(parent.tag in ('header', 'nav', 'aside', 'footer', 'template') for parent in node.ancestors())]
    title_node = min(headings, key=lambda node: (node.tag, node.index)) if headings else None
    title = clean(title_node.text()) if title_node else None
    steps = [clean(node.text()) for node in document.nodes if has_class(node, 'step-comic')]
    if steps:
        title = steps[0]
        if info and clean(info.get('title', '')) != title:
            raise StructureChanged('Tiêu đề reader và comic_info không khớp.')
    if not title:
        for node in document.nodes:
            candidate = (node.attrs.get('content', '') if node.tag == 'meta' and node.attrs.get('property') == 'og:title'
                         else node.text() if node.tag == 'title' else '')
            if kind(candidate) != 'unknown':
                title = clean(candidate)
                # Prefer a literal matching image name when document title adds branding.
                names = {clean(image.attrs.get('alt') or image.attrs.get('aria-label') or '') for image in document.nodes if image.tag == 'img'}
                names = {name for name in names if name and name in title and kind(name) != 'unknown'
                         and chapter_number(name) == chapter_number(title)}
                if names:
                    title = max(names, key=len)
                break
    if not title:
        raise StructureChanged('Không xác minh được tiêu đề chương trong heading/title/og:title. Cần DOM sau render, không dùng tiêu đề hardcode.')
    boundary = title_node.index if title_node else document.index + 1
    topics = {}
    previous = following = None
    for node in document.nodes:
        if node.tag not in ('a', 'link'):
            continue
        href = node.attrs.get('href', '')
        rel = node.attrs.get('rel', '').split()
        link = valid_chapter_link(href, url)
        name = clean(node.text())
        if link:
            if 'prev' in rel or name in ('上一话', '上一話', '上一章'):
                previous = link[0]
            if 'next' in rel or name in ('下一话', '下一話', '下一章'):
                following = link[0]
        if node.index < boundary or 'up' in rel:
            try:
                target, target_kind, _ = normalize(urljoin(url, href))
            except InvalidURL:
                continue
            if target_kind == 'topic':
                topics[target] = name or None
    topic_url, comic_title = next(iter(topics.items())) if len(topics) == 1 else (None, None)
    access = record_access(info) if info else (AccessStatus.LOCKED if LOCKED.search(document.reader_visible()) else AccessStatus.UNKNOWN)
    chapter = ChapterInfo(identifier, title, chapter_number(title), url, access, 0, content_kind=kind(title))
    return ReaderPage(chapter, topic_url, comic_title, previous, following, document, payload)


def image_url(candidate: str, base: str) -> str | None:
    try:
        parsed = https_url(urljoin(base, candidate), IMAGE_HOSTS)
    except InvalidURL:
        return None
    if (parsed.path.lower().endswith(('.svg', '.gif'))
            or re.search(r'(?:^|[/_.-])(?:loading|placeholder|transparent|spacer|blank)(?:$|[/_.-])', parsed.path, re.I)):
        return None
    query = parse_qsl(parsed.query, keep_blank_values=True)
    public_cdn_signature = (len(query) == 2 and {key for key, _ in query} == {'sign', 't'}
        and bool(re.fullmatch(r'[a-fA-F0-9]{32}', dict(query)['sign']))
        and bool(re.fullmatch(r'[a-fA-F0-9]{8,16}', dict(query)['t'])))
    if not public_cdn_signature and any(re.search(r'token|signature|credential|authorization|secret|api.?key|^sign$|(?:^|[-_])(?:sig|auth)(?:$|[-_])', key, re.I)
                                      for key, _ in query):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ''))


def srcset_url(value: str, base: str) -> str | None:
    candidates = []
    for item in value.split(','):
        parts = item.split()
        if not 1 <= len(parts) <= 2:
            continue
        descriptor = parts[1] if len(parts) == 2 else '1x'
        if not re.fullmatch(r'(?:[1-9][0-9]*w|[0-9]+(?:\.[0-9]+)?x)', descriptor):
            continue
        url = image_url(parts[0], base)
        if url:
            candidates.append((descriptor[-1], float(descriptor[:-1]), url))
    if not candidates or len({entry[0] for entry in candidates}) != 1:
        return None
    return max(candidates, key=lambda entry: entry[1])[2]


def discover_images(reader: ReaderPage) -> DiscoveryList[ChapterImage]:
    if reader.chapter.access_status in (AccessStatus.LOCKED, AccessStatus.RESTRICTED):
        raise AccessRestricted('DOM công khai cho biết chương yêu cầu truy cập bị hạn chế; không lấy ảnh nội dung bị khóa.')
    result = []
    seen = set()
    scopes = [node for node in reader.document.nodes if has_class(node, 'imgList')
              and any(has_class(parent, 'comicDetails') for parent in node.ancestors())]
    all_images = [node for node in reader.document.nodes if node.tag == 'img']
    content_elements = 0
    manifest = reader.payload.get('comic_info', {}).get('comic_images', []) if reader.payload else []
    manifest_by_path = {}
    manifest_positions = {}
    manifest_images = []
    manifest_rejected = 0
    manifest_seen = set()
    info = reader.payload.get('comic_info', {}) if reader.payload else {}
    manifest_identity_verified = (numeric_id(info.get('id')) == reader.chapter.chapter_id
        and clean(info.get('title', '')) == reader.chapter.chapter_title)
    if isinstance(manifest, list):
        for index, entry in enumerate(manifest):
            if isinstance(entry, dict):
                for key in ('url', 'url1280'):
                    value = entry.get(key)
                    if isinstance(value, str) and image_url(value, reader.chapter.chapter_url):
                        manifest_by_path[urlsplit(value).path] = entry
                        manifest_positions[urlsplit(value).path] = index
            chosen = attribute = None
            for key in ('url1280', 'url'):
                value = entry.get(key) if isinstance(entry, dict) else None
                candidate = image_url(value, reader.chapter.chapter_url) if isinstance(value, str) else None
                if candidate:
                    chosen, attribute = candidate, key
                    break
            if not chosen or urlsplit(chosen).path in manifest_seen:
                manifest_rejected += 1
                continue
            manifest_seen.add(urlsplit(chosen).path)
            def dimension(key):
                value = entry.get(key)
                return value if type(value) is int and 0 < value <= 1_000_000 else None
            width = dimension('width1280' if attribute == 'url1280' else 'width')
            height = dimension('height')
            if attribute == 'url1280' and width != dimension('width'):
                height = None  # No declared height for this scaled variant; don't guess.
            manifest_images.append(ChapterImage(len(manifest_images) + 1, chosen, width=width, height=height,
                download_status='discovered', source_attribute='comic_info.comic_images.' + attribute,
                dimensions_source='embedded_metadata'))
    for node in reader.document.nodes:
        if node.tag != 'img':
            continue
        if scopes and not any(parent is scope for parent in node.ancestors() for scope in scopes):
            continue
        if any(parent.tag in ('script', 'style', 'template', 'nav', 'header', 'footer', 'aside') or parent.attrs.get('role') in ('banner', 'navigation', 'complementary')
               for parent in node.ancestors()):
            continue
        name = clean(node.attrs.get('alt') or node.attrs.get('aria-label') or node.attrs.get('title') or '')
        # Name observed by the user, not a blanket assumption that every CDN img is a page.
        if name != clean(reader.chapter.chapter_title or ''):
            continue
        content_elements += 1
        if node.attrs.get('width') in ('1', '2') and node.attrs.get('height') in ('1', '2'):
            continue
        url = attribute = None
        for key in ('data-srcset', 'data-src', 'data-original', 'data-lazy-src', 'srcset', 'src'):
            raw = node.attrs.get(key, '').strip()
            if not raw:
                continue
            candidate = srcset_url(raw, reader.chapter.chapter_url) if key.endswith('srcset') else image_url(raw, reader.chapter.chapter_url)
            if candidate:
                url, attribute = candidate, key
                break
        identity = urlsplit(url).path if url and scopes else url
        if not url or identity in seen:
            continue
        seen.add(identity)
        def size(key):
            value = node.attrs.get(key, '')
            return int(value) if re.fullmatch(r'[1-9][0-9]{0,6}', value) else None
        metadata = manifest_by_path.get(urlsplit(url).path, {})
        width, height = size('width'), size('height')
        dimensions_source = 'html_attributes' if width or height else None
        if not dimensions_source and metadata:
            width = metadata.get('width1280') if '-t.w1280' in urlsplit(url).path else metadata.get('width')
            height = metadata.get('height')
            dimensions_source = 'embedded_metadata'
        result.append(ChapterImage(len(result) + 1, url, width=width, height=height,
                                   download_status='discovered', source_attribute=attribute,
                                   dimensions_source=dimensions_source))
    dom_unique = len(result)
    dom_positions = [manifest_positions.get(urlsplit(image.source_url).path) for image in result]
    dom_consistent = (all(position is not None for position in dom_positions)
                      and dom_positions == sorted(set(dom_positions)))
    source = 'dom_elements'
    if manifest_identity_verified and manifest_images and dom_consistent and len(manifest_images) > dom_unique:
        # HTTP SSR exposes only the first reader boxes; all URL strings below
        # already exist in this response's public, identity-checked manifest.
        result = manifest_images
        source = 'embedded_manifest'
    if not result:
        raise StructureChanged('Chưa tìm thấy img có tên khớp chương và URL hợp lệ trên hostname ảnh đã biết. Có thể cần DOM sau lazy loading; không lấy ảnh UI hoặc đoán URL.')
    warnings = [
        'IMAGE_LIST_READY chỉ xác nhận URL trong HTML/state hiện có, chưa xác nhận toàn bộ ảnh chương.',
        'Kích thước (nếu có) là HTML/metadata khai báo; chưa tải/giải mã ảnh để xác minh bitmap.',
        'Chưa tải ảnh; điều kiện tải tự động vẫn được đánh giá riêng.']
    if source == 'embedded_manifest':
        warnings.append(f'Danh sách URL lấy từ public comic_info.comic_images trong response; {dom_unique} URL xuất hiện trong thẻ img, {len(result)} URL hợp lệ trong manifest.')
    if manifest_rejected:
        warnings.append(f'Manifest có {manifest_rejected} record URL thiếu/không hợp lệ/trùng; không tạo URL thay thế.')
    if manifest and not dom_consistent:
        warnings.append('URL/thứ tự img không khớp manifest; giữ kết quả DOM, không ghép thêm metadata mâu thuẫn.')
    return DiscoveryList(result, complete=None, warnings=warnings, analysis={
        'discovery_source': source, 'dom_unique_valid_urls': dom_unique,
        'manifest_valid_urls': len(manifest_images), 'manifest_rejected_entries': manifest_rejected,
        'dom_manifest_consistent': dom_consistent, 'manifest_identity_verified': manifest_identity_verified,
        'all_img_elements': len(all_images), 'content_img_elements': content_elements,
        'content_boxes': sum(has_class(node, 'img-box') for node in reader.document.nodes) if scopes else None,
        'unique_valid_urls': len(result), 'duplicate_elements': content_elements - dom_unique,
        'manifest_items': len(manifest) if isinstance(manifest, list) else None,
        'manifest_matched_urls': sum(urlsplit(image.source_url).path in manifest_by_path for image in result),
        'lazy_attribute_counts': {key: sum(key in node.attrs for node in all_images
            if any(parent is scope for parent in node.ancestors() for scope in scopes))
            for key in ('data-src','data-original','data-lazy-src','srcset','data-srcset','lazy','noinit')},
        'network_access_checked': False, 'image_bytes_downloaded': False, 'download_permission_verified': False})
