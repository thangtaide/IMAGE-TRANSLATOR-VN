"""Whole-chapter input preparation, invoked only by an explicit user action.

Read existing chapter images without editing its manifest/database. New downloads
use the existing adapter/gates in a fresh cache branch, never its legacy staging.
"""
from pathlib import Path

from core.paths import CACHE, ROOT
from core.storage import digest
from core.whole_chapter import ChapterError, read_json, seal, verify
from sources.cache import ChapterCache, atomic_json, inspect_image
from sources.collection import ImageCollection
from sources.contracts import AccessStatus, WebsiteAdapter
from sources.security import contained


def context_identity(context):
    if context['kind'] == 'folder':
        return digest(['whole-main-folder-v1', str(Path(context['path']).resolve()), context.get('recursive', True)])
    comic, chapter = context['comic'], context['chapter']
    return digest(['whole-main-chapter-v1', comic.site_id, comic.comic_id, chapter.chapter_id,
                   str(chapter.local_source) if chapter.local_source else None])


def latest_workspace(context):
    """Bounded metadata discovery only; never resume, decode images or use the network."""
    key = context_identity(context)
    paths = sorted((ROOT/'output').glob('stage3g-*/input-context.json'),
                   key=lambda p:p.stat().st_mtime, reverse=True)
    for path in paths[:100]:
        try:
            data = verify(read_json(path))
            if data.get('context_key') == key:
                return path.parent
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return None


def prepare_input(context, workspace, control, emit):
    workspace = Path(workspace).resolve()
    if not workspace.is_relative_to((ROOT/'output').resolve()):
        raise ChapterError('WHOLE_QA_WORKSPACE_REQUIRED')
    relative = workspace.relative_to((ROOT/'output').resolve())
    if not relative.parts or not relative.parts[0].startswith(('stage3g-', 'stage3j-batch-')):
        raise ChapterError('WHOLE_QA_WORKSPACE_REQUIRED')
    workspace.mkdir(parents=True, exist_ok=True)
    key = context_identity(context)
    marker = workspace/'input-context.json'
    if marker.exists():
        if verify(read_json(marker)).get('context_key') != key:
            raise ChapterError('WHOLE_INPUT_CONTEXT_CHANGED')
    else:
        atomic_json(marker, seal(dict(version=1, context_key=key)))
    if context['kind'] == 'chapter' and context['chapter'].access_status in (AccessStatus.LOCKED, AccessStatus.RESTRICTED):
        raise ChapterError('WHOLE_SOURCE_ACCESS_DENIED')
    receipt_path = workspace/'selected-input.json'
    if receipt_path.exists():
        receipt = verify(read_json(receipt_path))
        if receipt.get('context_key') != key:
            raise ChapterError('WHOLE_INPUT_CONTEXT_CHANGED')
        root = Path(receipt['root']).resolve()
        paths = []
        for n, row in enumerate(receipt['files'], 1):
            control.checkpoint()
            p = Path(row['path'])
            if p.is_symlink() or not p.resolve().is_relative_to(root) or inspect_image(p)['sha256'] != row['sha256']:
                raise ChapterError('WHOLE_INPUT_CHANGED')
            paths.append(p.resolve())
            emit(dict(type='whole_input_progress', stage='Kiểm tra ảnh đã lưu', index=n, total=len(receipt['files'])))
        if not paths or len(set(paths)) != len(paths):
            raise ChapterError('WHOLE_INPUT_CHANGED')
        return ImageCollection(root, tuple(paths))

    control.checkpoint()
    if context['kind'] == 'folder':
        from core.pipeline import scan_images
        root = Path(context['path']).resolve()
        collection = ImageCollection(root, tuple(scan_images(root, context.get('recursive', True), workspace)))
    else:
        comic, chapter = context['comic'], context['chapter']
        if comic.site_id == 'local':
            if chapter.access_status != AccessStatus.LOCAL or not chapter.local_source:
                raise ChapterError('WHOLE_SOURCE_ACCESS_DENIED')
            collection = ImageCollection.discover(chapter.local_source)
        else:
            if not comic.comic_id:
                raise ChapterError('WHOLE_SOURCE_ID_MISSING')
            cache = ChapterCache()
            directory = cache.directory(comic, chapter)
            manifest = cache.read(directory)
            if manifest['pages']:
                if (manifest.get('site_id') != comic.site_id or manifest.get('comic_id') != comic.comic_id
                        or manifest.get('chapter_id') != chapter.chapter_id
                        or manifest.get('state') not in ('cached','processing','paused_provider','completed',
                                                         'completed_with_warnings')
                        or chapter.image_count is not None and len(manifest['pages']) != chapter.image_count):
                    raise ChapterError('WHOLE_SOURCE_CACHE_INCOMPLETE')
                paths = []
                for n, page in enumerate(manifest['pages'], 1):
                    control.checkpoint()
                    path = contained(directory, page['file'])
                    if inspect_image(path)['sha256'] != page['sha256']:
                        raise ChapterError('WHOLE_SOURCE_CACHE_CHANGED')
                    paths.append(path)
                    emit(dict(type='whole_input_progress', stage='Đọc ảnh chương từ cache', index=n,total=len(manifest['pages'])))
                collection = ImageCollection(directory, tuple(paths))
            else:
                adapter = context.get('adapter')
                if adapter is None or adapter.site_id != comic.site_id or type(adapter).download_chapter is WebsiteAdapter.download_chapter:
                    raise ChapterError('WHOLE_SOURCE_DOWNLOADER_UNAVAILABLE')
                if not adapter.download_decision(chapter).allowed:
                    raise ChapterError('WHOLE_SOURCE_DOWNLOAD_NOT_ALLOWED')
                # The existing downloader requires CACHE containment. Do not weaken it.
                incoming = contained(CACHE/'whole_chapter_inputs', workspace.name)
                prior = getattr(adapter, 'download_progress', None)
                def progress(event):
                    emit(dict(type='whole_input_progress', stage='Tải ảnh chương đã chọn',
                              index=event.get('index',0), total=event.get('total',0)))
                adapter.download_progress = progress
                try:
                    collection = adapter.download_chapter(chapter, incoming, control)
                finally:
                    adapter.download_progress = prior
                if not isinstance(collection, ImageCollection) or not collection.root.resolve().is_relative_to(incoming.resolve()):
                    raise ChapterError('WHOLE_SOURCE_COLLECTION_INVALID')
    if not collection.paths or len(collection.paths) > 500:
        raise ChapterError('WHOLE_PAGE_LIMIT')
    rows = []
    for path in collection.paths:
        control.checkpoint()
        if path.is_symlink() or not path.resolve().is_relative_to(collection.root.resolve()):
            raise ChapterError('WHOLE_INPUT_CHANGED')
        rows.append(dict(path=str(path.resolve()), sha256=inspect_image(path)['sha256']))
    atomic_json(receipt_path, seal(dict(version=1, context_key=key, root=str(collection.root.resolve()), files=rows)))
    return collection
