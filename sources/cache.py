"""Verified copies of user-supplied pages; no network image downloader.

Partial files and manifests survive cancellation. Cleanup is explicit and only
removes verified cache copies after every page has been published successfully.
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from PIL import Image

from core.paths import CACHE
from core.storage import file_digest
from sources.collection import ImageCollection
from sources.contracts import CacheError, ChapterInfo, ComicInfo
from sources.security import contained, safe_id

FORMATS = {'PNG': ('png', 'image/png'), 'JPEG': ('jpg', 'image/jpeg'),
           'WEBP': ('webp', 'image/webp'), 'BMP': ('bmp', 'image/bmp')}


def inspect_image(path: Path, max_bytes: int = 32_000_000) -> dict:
    if not 0 < path.stat().st_size <= max_bytes:
        raise CacheError('Dung lượng ảnh rỗng hoặc vượt giới hạn 32 MB.')
    try:
        with Image.open(path) as image:
            if image.format not in FORMATS or getattr(image, 'n_frames', 1) != 1:
                raise CacheError('Định dạng ảnh không được hỗ trợ hoặc ảnh động.')
            extension, mime = FORMATS[image.format]
            width, height = image.size
            if width * height > 65_000_000:
                raise CacheError('Ảnh vượt giới hạn 65 triệu pixel.')
            image.verify()
        with Image.open(path) as image:
            image.load()
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise CacheError('File không giải mã được như ảnh hợp lệ.') from exc
    return {'extension': extension, 'content_type': mime, 'width': width, 'height': height,
            'bytes': path.stat().st_size, 'sha256': file_digest(path)}


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.part')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class ChapterCache:
    def __init__(self, root: Path | None = None, quota: int = 2_000_000_000):
        self.root = (root or CACHE / 'online_comics').resolve()
        self.quota = quota

    def directory(self, comic: ComicInfo, chapter: ChapterInfo) -> Path:
        return contained(self.root, safe_id(comic.site_id), safe_id(comic.comic_id),
                         'chapter_' + safe_id(chapter.chapter_id))

    def read(self, directory: Path) -> dict:
        path = directory / 'manifest.json'
        if not path.exists():
            return {'version': 1, 'state': 'new', 'pages': []}
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('pages'), list):
                raise ValueError('schema')
            for index, page in enumerate(data['pages'], 1):
                if (not isinstance(page, dict) or page.get('index') != index
                        or not isinstance(page.get('file'), str)
                        or Path(page['file']).name != page['file']
                        or not isinstance(page.get('source'), str)
                        or not isinstance(page.get('sha256'), str)):
                    raise ValueError('page schema')
                contained(directory, page['file'])
            return data
        except (OSError, ValueError, TypeError) as exc:
            raise CacheError('Manifest hỏng; giữ nguyên dữ liệu để kiểm tra.') from exc

    def save(self, directory: Path, manifest: dict) -> None:
        if not directory.resolve().is_relative_to(self.root) or directory.resolve() == self.root:
            raise CacheError('Manifest ngoài cache.')
        directory.mkdir(parents=True, exist_ok=True)
        atomic_json(directory / 'manifest.json', manifest)

    def stage(self, comic: ComicInfo, chapter: ChapterInfo, collection: ImageCollection,
              control, emit=lambda _: None, *, download_decision=None) -> tuple[ImageCollection, Path, dict]:
        directory = self.directory(comic, chapter)
        directory.mkdir(parents=True, exist_ok=True)
        manifest = self.read(directory)
        manifest.update(site_id=comic.site_id, comic_id=comic.comic_id, chapter_id=chapter.chapter_id,
                        provenance='user_supplied_local_images' if comic.site_id == 'local' else 'verified_adapter_download', state='copying')
        if comic.site_id != 'local' and download_decision is not None:
            manifest['download_decision'] = asdict(download_decision)
            if download_decision.basis == 'USER_POLICY_DEFAULT_ALLOW':
                manifest['provenance'] = 'adapter_download_by_user_policy'
        previous = {p['index']: p for p in manifest['pages']}
        if len(previous) > len(collection.paths):
            raise CacheError('Nguồn đã mất trang so với manifest; không tái sử dụng chương cũ.')
        paths = []
        for index, source in enumerate(collection.paths, 1):
            control.checkpoint()
            info = inspect_image(source)
            name = f'{index:04d}.' + info['extension']
            target = contained(directory, name)
            old = previous.get(index)
            if old and (old.get('source') != str(source) or old.get('sha256') != info['sha256']):
                raise CacheError('Nguồn chương đã đổi; hãy chọn thư mục mới để tránh trộn trang cũ.')
            if target.exists():
                if not old or inspect_image(target)['sha256'] != info['sha256']:
                    raise CacheError('Ảnh cache không khớp manifest; không ghi đè.')
            else:
                usage = sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file() and not p.is_symlink())
                if usage + info['bytes'] > self.quota or shutil.disk_usage(directory).free < info['bytes'] + 1_000_000:
                    raise CacheError('Không đủ dung lượng cache/ổ đĩa; chưa xóa dữ liệu cũ.')
                temporary = contained(directory, name + '.' + uuid4().hex + '.part')
                manifest['partial_file'] = temporary.name
                self.save(directory, manifest)
                with source.open('rb') as src, temporary.open('xb') as dst:
                    while True:
                        control.checkpoint()
                        block = src.read(1024 * 1024)
                        if not block:
                            break
                        dst.write(block)
                    dst.flush()
                    os.fsync(dst.fileno())
                if inspect_image(temporary)['sha256'] != info['sha256']:
                    raise CacheError('Nguồn thay đổi trong lúc sao chép; giữ file dở để kiểm tra.')
                if target.exists():
                    raise CacheError('Đích cache vừa xuất hiện; không ghi đè.')
                # Windows rename is atomic and refuses to overwrite an existing file.
                temporary.rename(target)
            record = dict(old or {}, index=index, source=str(source), file=name, **info)
            previous[index] = record
            manifest['pages'] = [previous[i] for i in sorted(previous)]
            manifest.pop('partial_file', None)
            self.save(directory, manifest)
            paths.append(target)
            emit({'phase': 'cache', 'index': index, 'total': len(collection.paths), 'file': str(source)})
        manifest['state'] = 'cached'
        self.save(directory, manifest)
        return ImageCollection(directory, tuple(paths)), directory, manifest

    def cleanup_completed(self, directory: Path, manifest: dict) -> None:
        if manifest.get('state') != 'completed' or not manifest['pages']:
            raise CacheError('Không dọn cache của chương chưa hoàn tất.')
        verified = []
        for page in manifest['pages']:
            cached = contained(directory, page['file'])
            output = Path(page.get('output', ''))
            if not output.is_file() or file_digest(output) != page.get('output_sha256'):
                raise CacheError('Output chưa hợp lệ; giữ cache để thử lại.')
            if cached.exists():
                if inspect_image(cached)['sha256'] != page['sha256']:
                    raise CacheError('Cache thay đổi; không xóa.')
                verified.append(cached)
        # Check the cache boundary before any deletion, including junction resolution.
        if not directory.resolve().is_relative_to(self.root) or directory.resolve() == self.root:
            raise CacheError('Không dọn ngoài cache.')
        for path in verified:
            path.unlink()
        manifest['cache_cleaned'] = True
        self.save(directory, manifest)
