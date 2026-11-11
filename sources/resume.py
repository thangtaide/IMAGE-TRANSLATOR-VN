"""Reconstruct explicitly requested source jobs from their local cache, never HTTP."""
from dataclasses import asdict
from pathlib import Path

from core.resume import ResumeStore
from core.types import Options
from sources.cache import ChapterCache, inspect_image
from sources.contracts import AccessStatus, ChapterInfo, ComicInfo, CacheError


def save_source_request(store, comic, chapters, output, options, cache, identifier=None):
    fields = [asdict(c) for c in chapters]
    for chapter in fields:
        if chapter.get('local_source') is not None:
            chapter['local_source'] = str(chapter['local_source'])
    data = store.read(identifier) if identifier else store.create('source', comic=asdict(comic),
        chapters=fields, output=str(output), options=options.to_dict(),
        cache_root=str(cache.root), cached_chapters={})
    data.update(state='running', options=options.to_dict())
    # JSON encodes optional local_source Path without introducing a custom serializer.
    for chapter in data['chapters']:
        if chapter.get('local_source') is not None:
            chapter['local_source'] = str(chapter['local_source'])
    store.save(data)
    return data


def restore_source_request(data, database, options):
    """Validate all cached originals/outputs in worker before loading an engine."""
    cache = ChapterCache(Path(data['cache_root']))
    comic = ComicInfo(**data['comic'])
    chapters = []
    for fields in data['chapters']:
        fields = dict(fields)
        fields['access_status'] = AccessStatus(fields['access_status'])
        if fields.get('local_source'):
            fields['local_source'] = Path(fields['local_source'])
        chapter = ChapterInfo(**fields)
        chapters.append(chapter)
        if chapter.chapter_id not in data.get('cached_chapters', {}):
            # Still selected, but not yet downloaded. The explicit resume job
            # must recheck website access/policy; it may not pretend this is cache.
            continue
        manifest = cache.read(cache.directory(comic, chapter))
        if (manifest.get('site_id') != comic.site_id or manifest.get('comic_id') != comic.comic_id or
                manifest.get('chapter_id') != chapter.chapter_id or not manifest.get('pages')):
            raise CacheError('RESUME_CACHE_MISSING: chương chưa tải/cache đầy đủ; không tự truy cập CDN')
        if (manifest.get('state') in ('new', 'copying', 'staging') or
                data.get('cached_chapters', {}).get(chapter.chapter_id) != len(manifest['pages'])):
            raise CacheError('RESUME_CACHE_INCOMPLETE: cache chương chưa hoàn tất')
        for page in manifest['pages']:
            from sources.security import contained
            if inspect_image(contained(cache.directory(comic, chapter), page['file']))['sha256'] != page['sha256']:
                raise CacheError('RESUME_SOURCE_CHANGED: ảnh cache đổi/hỏng; không tự tải lại')
            if page.get('output') and not page.get('needs_retry') and not page.get('error'):
                if inspect_image(Path(page['output']))['sha256'] != page['output_sha256']:
                    raise CacheError('RESUME_RECEIPT_CHANGED: output thành công đổi/hỏng')
    # Restore original OCR/render options, accept only explicitly chosen method/settings.
    from core.resume import PROVIDER_FIELDS
    merged = Options.from_dict(data['options'])
    for name in PROVIDER_FIELDS:
        setattr(merged, name, getattr(options, name))
    from providers.agy_models import bind_run_model
    bind_run_model(merged,data['options'])
    from sources.registry import resolve_adapter
    adapter = resolve_adapter(comic.source_url) if comic.site_id != 'local' else None
    return dict(comic=comic, chapters=chapters, output=Path(data['output']), options=merged,
        cache=cache, database=database, adapter=adapter, retry_only=False, resume_source_id=data['id'])
