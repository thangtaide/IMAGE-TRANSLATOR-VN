"""Sequential Kuaikan image IO, bounded and resumable; no policy override here."""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import getproxies
from uuid import uuid4

from core.paths import CACHE
from core.types import CancelledError
from sources.cache import atomic_json, inspect_image
from sources.collection import ImageCollection
from sources.contracts import AccessRestricted, CacheError, InvalidURL, NetworkUnavailable, SourceError, UsageLimited
from sources.kuaikan_dom import IMAGE_HOSTS, image_url
from sources.metadata_http import _PinnedHTTPS
from sources.security import contained, https_url, public_addresses


@dataclass(frozen=True)
class DownloadLimits:
    max_images: int = 200
    max_image_bytes: int = 32_000_000
    max_chapter_bytes: int = 512_000_000
    max_cache_bytes: int = 2_000_000_000
    seconds: float = 30
    attempts: int = 2
    delay: float = 0.5


def _usage(directory: Path) -> int:
    return sum(p.stat().st_size for p in directory.rglob('*') if p.is_file()) if directory.exists() else 0


def _pause(seconds, checkpoint):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        checkpoint()
        time.sleep(min(0.1, max(0, until - time.monotonic())))


def _magic(prefix: bytes) -> str | None:
    if prefix.startswith(b'\x89PNG\r\n\x1a\n'): return 'image/png'
    if prefix.startswith(b'\xff\xd8\xff'): return 'image/jpeg'
    if prefix[:4] == b'RIFF' and prefix[8:12] == b'WEBP': return 'image/webp'
    if prefix.startswith(b'BM'): return 'image/bmp'
    return None


def _fetch_image(url, directory, limits, checkpoint, progress):
    started = time.monotonic()
    current = url
    for hop in range(3):
        checkpoint()
        if time.monotonic() - started > limits.seconds:
            raise TimeoutError('image deadline')
        if image_url(current, current) != current:
            raise InvalidURL('URL ảnh/redirect không an toàn; không gửi request.')
        parsed = https_url(current, IMAGE_HOSTS)
        addresses = public_addresses(parsed.hostname)
        connection = _PinnedHTTPS(parsed.hostname, addresses[0])
        connection.timeout = min(10, limits.seconds)
        response = None
        try:
            # Keep supplied path/query exactly. No cookies, Referer, signature edits or UA rotation.
            connection.request('GET', parsed.path + ('?' + parsed.query if parsed.query else ''),
                headers={'User-Agent': 'ImageTranslatorVN/0.1 (public metadata)', 'Accept': 'image/png,image/jpeg,image/webp,image/bmp'})
            response = connection.getresponse()
            status = response.status
            if status in (401, 403):
                raise AccessRestricted('CDN trả HTTP ' + str(status) + '; dừng, không retry hoặc vượt chặn.')
            if status == 429:
                raise UsageLimited('CDN trả HTTP 429; dừng, không retry hoặc đổi danh tính.')
            if status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                if not location:
                    raise InvalidURL('Redirect ảnh thiếu Location.')
                current = urljoin(current, location)
                if image_url(current, current) != current:
                    raise InvalidURL('Redirect ảnh ngoài allowlist hoặc không an toàn.')
                continue
            if status in (500, 502, 503, 504):
                raise OSError('temporary CDN response')
            if status != 200:
                raise SourceError('CDN trả HTTP ' + str(status) + '; không tự làm mới chữ ký.')
            mime = response.getheader('Content-Type', '').split(';')[0].strip().lower()
            if mime == 'image/x-ms-bmp': mime = 'image/bmp'
            if mime not in ('image/png', 'image/jpeg', 'image/webp', 'image/bmp'):
                raise AccessRestricted('CDN không trả MIME ảnh; có thể là trang đăng nhập/CAPTCHA/HTML. Dừng, không thử cách vượt.')
            raw_length = response.getheader('Content-Length')
            if raw_length is not None and not re.fullmatch(r'[0-9]+', raw_length):
                raise SourceError('Content-Length ảnh không hợp lệ.')
            expected = int(raw_length) if raw_length is not None else None
            if expected is not None and not 0 < expected <= limits.max_image_bytes:
                raise CacheError('Ảnh rỗng hoặc vượt giới hạn dung lượng.')
            cache_usage, chapter_usage = _usage(CACHE), _usage(directory)
            temporary = contained(directory, uuid4().hex + '.part')
            size, prefix = 0, b''
            with temporary.open('xb') as stream:
                while True:
                    checkpoint()
                    if time.monotonic() - started > limits.seconds:
                        raise TimeoutError('image deadline')
                    block = response.read(65536)
                    if not block: break
                    size += len(block)
                    if (size > limits.max_image_bytes or chapter_usage + size > limits.max_chapter_bytes
                            or cache_usage + size > limits.max_cache_bytes):
                        raise CacheError('Ảnh/chương/cache vượt quota; giữ file dở để kiểm tra.')
                    if shutil.disk_usage(directory).free < len(block) + 1_000_000:
                        raise CacheError('Không đủ dung lượng đĩa.')
                    prefix = (prefix + block)[:16]
                    stream.write(block)
                    progress({'stage': 'downloading', 'bytes_received': size, 'expected_bytes': expected})
                stream.flush()
                os.fsync(stream.fileno())
            if expected is not None and size != expected:
                raise OSError('incomplete image response')
            if _magic(prefix) != mime:
                raise CacheError('Magic bytes không khớp MIME ảnh; không xuất file.')
            info = inspect_image(temporary, limits.max_image_bytes)
            if info['content_type'] != mime:
                raise CacheError('Bitmap decode không khớp MIME.')
            checkpoint()
            return temporary, dict(info, http_status=status)
        finally:
            if response is not None: response.close()
            connection.close()
    raise InvalidURL('Quá giới hạn redirect ảnh; dừng.')


def download_images(chapter, images, cache_dir: Path, decision, control=None, progress=None,
                    *, limit: int | None = None, limits: DownloadLimits | None = None,
                    image_fetcher=None,url_validator=None) -> ImageCollection:
    """Return verified local files only. A limit is an explicit QA/sample selection."""
    if not decision.allowed:
        raise AccessRestricted(decision.reason)
    if os.environ.get('CODEX_SANDBOX_NETWORK_DISABLED') == '1' or any(k in getproxies() for k in ('http', 'https', 'all')):
        raise NetworkUnavailable('Mạng bị giới hạn hoặc proxy chưa hỗ trợ; không bỏ qua cấu hình.')
    limits = limits or DownloadLimits()
    if not 1 <= limits.attempts <= 3 or not 0 < limits.seconds <= 120:
        raise CacheError('Giới hạn timeout/retry không hợp lệ.')
    checkpoint = control.checkpoint if control else lambda: None
    progress = progress or (lambda event: None)
    if not images or len(images) > limits.max_images:
        raise CacheError('Số ảnh chương rỗng hoặc vượt giới hạn; không tải từng phần âm thầm.')
    if limit is not None and (type(limit) is not int or not 1 <= limit <= len(images)):
        raise CacheError('Giới hạn mẫu phải nằm trong danh sách ảnh thực tế.')
    selected = images if limit is None else images[:limit]
    validate_url=url_validator or image_url
    fetch=image_fetcher or _fetch_image
    for image in images:
        if not image.source_url or validate_url(image.source_url, chapter.chapter_url) != image.source_url:
            raise InvalidURL('Danh sách chứa URL ảnh không an toàn; không bắt đầu tải.')
    directory = cache_dir.resolve()
    if not directory.is_relative_to(CACHE.resolve()) or directory == CACHE.resolve() or cache_dir.is_symlink():
        raise CacheError('Chỉ tải vào thư mục con cache an toàn của ứng dụng.')
    directory.mkdir(parents=True, exist_ok=True)
    receipt = contained(directory, 'download-manifest.json')
    if receipt.is_symlink(): raise CacheError('Manifest không được là symlink.')
    if receipt.exists():
        if receipt.stat().st_size > 1_000_000:
            raise CacheError('Download manifest vượt giới hạn; không đọc hoặc ghi đè.')
        try:
            manifest = json.loads(receipt.read_text(encoding='utf-8'))
            if (manifest['version'] != 1 or manifest['chapter_id'] != chapter.chapter_id
                    or not isinstance(manifest['pages'], list) or len(manifest['pages']) > len(images)):
                raise ValueError('schema')
            for index, page in enumerate(manifest['pages'], 1):
                if (page['index'] != index or not re.fullmatch(f'{index:04d}\\.(png|jpg|webp|bmp)', page['file'])
                        or not re.fullmatch('[a-f0-9]{64}', page['sha256']) or not re.fullmatch('[a-f0-9]{64}', page['source_path_sha256'])):
                    raise ValueError('page schema')
        except (OSError, ValueError, KeyError, TypeError, AssertionError):
            raise CacheError('Download manifest hỏng/khác chương; giữ nguyên, không ghi đè.') from None
    else:
        if any(directory.iterdir()):
            raise CacheError('Thư mục có dữ liệu chưa có receipt; không ghi đè hoặc tự nhận làm cache.')
        manifest = {'version': 1, 'chapter_id': chapter.chapter_id, 'pages': []}
    manifest.update(state='downloading', discovered_images=len(images), requested_images=len(selected),
                    sample=limit is not None and limit < len(images), decision=asdict(decision))
    atomic_json(receipt, manifest)
    paths = []
    try:
        for index, image in enumerate(selected, 1):
            checkpoint()
            parsed = urlsplit(image.source_url)
            identity = hashlib.sha256((parsed.hostname + parsed.path).encode('utf-8')).hexdigest()
            def emit(event): progress(dict(event, index=index, total=len(selected)))
            if index <= len(manifest['pages']):
                page = manifest['pages'][index - 1]
                cached = contained(directory, page['file'])
                info = inspect_image(cached, limits.max_image_bytes)
                if cached.is_symlink() or page['source_path_sha256'] != identity or info['sha256'] != page['sha256']:
                    raise CacheError('Cache đổi nội dung/nguồn; không ghi đè.')
                paths.append(cached)
                emit({'stage': 'cached', 'bytes_received': info['bytes'], 'expected_bytes': info['bytes']})
                continue
            if index > 1: _pause(limits.delay, checkpoint)
            if any((directory / (f'{index:04d}.' + extension)).exists() for extension in ('png', 'jpg', 'webp', 'bmp')):
                raise CacheError('Ảnh đích không có receipt; giữ nguyên, không tải lại hoặc ghi đè.')
            for attempt in range(limits.attempts):
                try:
                    temporary, info = fetch(image.source_url, directory, limits, checkpoint, emit)
                    break
                except (OSError, http.client.HTTPException) as exc:
                    if attempt + 1 >= limits.attempts:
                        raise NetworkUnavailable('Tải ảnh thất bại sau retry hữu hạn: ' + type(exc).__name__) from None
                    emit({'stage': 'retry', 'attempt': attempt + 1, 'bytes_received': 0, 'expected_bytes': None})
                    _pause(0.5 * 2 ** attempt, checkpoint)
            target = contained(directory, f'{index:04d}.' + info['extension'])
            checkpoint()
            if target.exists(): raise CacheError('File đích đã có nhưng không có receipt hợp lệ; không ghi đè.')
            temporary.rename(target)  # Atomic no-replace on Windows.
            page = dict(info, index=index, file=target.name, source_path_sha256=identity,
                        source_url_sha256=hashlib.sha256(image.source_url.encode('utf-8')).hexdigest())
            manifest['pages'].append(page)
            atomic_json(receipt, manifest)
            paths.append(target)
            emit({'stage': 'downloaded', 'bytes_received': info['bytes'], 'expected_bytes': info['bytes']})
        manifest['state'] = 'sample_complete' if manifest['sample'] else 'downloaded'
        atomic_json(receipt, manifest)
        return ImageCollection(directory, tuple(paths))
    except BaseException as exc:
        manifest['state'] = ('cancelled' if isinstance(exc, CancelledError) else 'restricted'
                             if isinstance(exc, (AccessRestricted, InvalidURL)) else 'failed')
        manifest['error_type'] = type(exc).__name__  # No raw URLs/HTTP exception text.
        atomic_json(receipt, manifest)
        raise
