"""Chapter orchestration around the existing, unmodified OCR/translation pipeline."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from uuid import uuid4

from core.ocr import PaddleOCREngine
from core.paths import CACHE, ROOT

# Separate staging location from ROOT's safety checks; QA may redirect this constant.
PIPELINE_STAGING_ROOT = ROOT / 'output' / 'online_comics_work'
from core.pipeline import JobControl, ProcessingManager, TranslationService
from providers.agy import MODE as AGY_MODE, WHOLE_MODE
from providers.gemini_api import MODE as GEMINI_API_MODE
from core.storage import TranslationCache, digest, file_digest
from core.types import CancelledError, Options
from core.diagnostics import DiagnosticLog, safe_text, VALIDATOR_VERSION, TRANSLATED_SUCCESS, FALLBACK_ORIGINAL, FAILED_NO_OUTPUT
from sources.cache import ChapterCache, inspect_image
from sources.collection import ImageCollection
from sources.contracts import AccessRestricted, AccessStatus, CacheError, ChapterInfo, ComicInfo, DownloadNotReady, SourceError, WebsiteAdapter
from sources.states import DownloadState
from sources.security import contained, safe_id, safe_name

LOGGER = logging.getLogger(__name__)


def validate_output(output: Path, chapters: list[ChapterInfo]) -> Path:
    output = output.resolve()
    # Publishing can target a chosen directory; internal pipeline staging stays in ROOT/output.
    if output == ROOT.resolve() or ROOT.resolve().is_relative_to(output) or '_internal' in output.parts:
        raise CacheError('Chọn thư mục kết quả riêng, không phải thư mục ứng dụng/cha của ứng dụng.')
    for name in ('models', 'config', 'cache', 'logs', 'core', 'providers', 'sources', 'ui',
                 'scripts', 'tests', '.venv', 'assets', 'dist', 'build', '.git', 'backups'):
        if output.is_relative_to((ROOT / name).resolve()):
            raise CacheError('Không xuất vào mã nguồn/model/cache/build/backup.')
    for chapter in chapters:
        if chapter.local_source:
            original = chapter.local_source.resolve()
            source = original.parent if original.is_file() else original
            if output.is_relative_to(source) or source.is_relative_to(output):
                raise CacheError('Thư mục xuất phải tách biệt với ảnh nguồn.')
    return output


def publish_image(source: Path, target: Path, control: JobControl, expected_size: tuple[int, int]) -> str:
    info = inspect_image(source)
    if (info['width'], info['height']) != expected_size:
        raise CacheError('Ảnh dịch thay đổi kích thước; không xuất.')
    if target.exists():
        if file_digest(target) == info['sha256']:
            return info['sha256']
        raise CacheError('Output đã tồn tại và khác nội dung; không ghi đè. Chọn thư mục khác.')
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.' + uuid4().hex + '.part')
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
        raise CacheError('File tạm xuất ảnh không khớp; đã giữ lại để kiểm tra.')
    control.checkpoint()
    if target.exists():
        raise CacheError('Output vừa xuất hiện; không ghi đè.')
    temporary.rename(target)
    return info['sha256']


class LocalComicJob:
    def __init__(self, comic: ComicInfo, chapters: list[ChapterInfo], output: Path, options: Options,
                 keep_cached: bool = True, control: JobControl | None = None, emit=lambda _: None,
                 cache: ChapterCache | None = None, database: Path | None = None,
                 adapter: WebsiteAdapter | None = None, retry_only: bool = False, resume_source_id: str | None = None,
                 fresh_inputs: dict | None = None):
        self.comic, self.chapters, self.output = comic, chapters, output
        self.options = Options.from_dict(options.to_dict())
        # Legacy source jobs retain Offline enforcement. The explicitly selected
        # Stage3A mode is opt-in and shares the existing processing service.
        if self.options.mode == WHOLE_MODE:
            raise SourceError('Whole Chapter cần luồng chuẩn bị/xác nhận riêng; không chuyển ngầm sang Offline hoặc dùng journal batch.')
        if self.options.mode not in ('Online Free', AGY_MODE, GEMINI_API_MODE):
            self.options.mode = 'Offline'
        self.options.allow_online_fallback = False
        self.keep_cached = keep_cached
        self.control = control or JobControl()
        self.emit = emit
        self.cache = cache or ChapterCache()
        self.database = database or CACHE / 'online_comics' / 'pipeline.sqlite3'
        self.adapter = adapter
        self.retry_only = retry_only
        self.resume_source_id = resume_source_id
        self.fresh_inputs = fresh_inputs
        if fresh_inputs is not None:
            fresh_root = CACHE/'online_comics/_fresh'
            if (self.options.mode != AGY_MODE or not self.cache.root.is_relative_to(fresh_root.resolve())
                    or self.cache.root == fresh_root.resolve() or retry_only or resume_source_id):
                raise CacheError('Lượt AGY mới cần cache riêng, không nối journal cũ.')
            if self.cache.root.exists():
                raise CacheError('Cache lượt mới đã tồn tại; không dùng lại bản dịch hoặc ghi đè. Tạo lượt mới khác.')

    def run(self) -> dict:
        result = {'state': 'interrupted', 'chapters_completed': 0, 'chapters_failed': 0,
                  'chapters_with_warnings': 0, 'images_exported': 0, 'images_failed': 0,
                  'images_total': 0, 'translated_success': 0, 'partial_translation': 0,
                  'fallback_original': 0, 'failed_no_output': 0, 'skipped': 0,
                  'review_pages': [], 'diagnostic_dirs': [], 'errors': [], 'outputs': []}
        current_directory = None
        manifest = None
        database = None
        source_record = None
        try:
            if not self.chapters:
                raise CacheError('Chưa chọn chương nào.')
            local = self.comic.site_id == 'local'
            if local:
                if any(c.access_status != AccessStatus.LOCAL or not c.local_source for c in self.chapters):
                    raise AccessRestricted('Nguồn cục bộ cần đường dẫn ảnh do người dùng cung cấp.')
            elif self.fresh_inputs is None and not self.retry_only and (self.adapter is None or self.adapter.site_id != self.comic.site_id
                  or type(self.adapter).download_chapter is WebsiteAdapter.download_chapter):
                raise SourceError('Adapter chưa có downloader tương thích cho nguồn đã chọn.')
            elif self.comic.comic_id is None:
                raise SourceError('Chưa xác minh ID truyện gốc để tạo cache tải; không dùng chapter ID thay comic ID.')
            self.output = validate_output(self.output, self.chapters)
            from core.resume import ResumeStore
            from sources.resume import save_source_request
            source_store = ResumeStore(self.database)
            source_record = save_source_request(source_store, self.comic, self.chapters,
                self.output, self.options, self.cache, self.resume_source_id)
            self.emit({'type': 'source_resume_ready', 'resume_id': source_record['id']})
            self.database.parent.mkdir(parents=True, exist_ok=True)
            database = TranslationCache(self.database)
            # Exactly one OCR engine and translation service per batch, reused across chapters.
            ocr = PaddleOCREngine()
            service = TranslationService(self.options, database, self.control)
            for position, chapter in enumerate(sorted(self.chapters, key=lambda c: c.order_index), 1):
                current_directory = None
                manifest = None
                self.control.checkpoint()
                self.emit({'type': 'chapter_start', 'chapter_id': chapter.chapter_id,
                           'position': position, 'total_chapters': len(self.chapters)})
                try:
                    retry_this = self.retry_only or (self.resume_source_id is not None and
                        chapter.chapter_id in source_record.get('cached_chapters', {}))
                    if retry_this:
                        # Retry from verified chapter cache, without HTTP/discovery/CDN.
                        current_directory = self.cache.directory(self.comic, chapter)
                        manifest = self.cache.read(current_directory)
                        if (not manifest['pages'] or manifest.get('chapter_id') != chapter.chapter_id
                                or manifest.get('comic_id') != self.comic.comic_id
                                or manifest.get('site_id') != self.comic.site_id):
                            raise CacheError('Không có manifest cache đúng chương để retry Offline.')
                        paths = []
                        for page in manifest['pages']:
                            self.control.checkpoint()
                            source = contained(current_directory, page['file'])
                            if inspect_image(source)['sha256'] != page['sha256']:
                                raise CacheError('Ảnh cache đổi/hỏng; không tự tải lại khi retry.')
                            if page.get('output') and inspect_image(Path(page['output']))['sha256'] != page.get('output_sha256'):
                                raise CacheError('Output đã đổi/hỏng; giữ nguyên để kiểm tra, không ghi đè.')
                            paths.append(source)
                        cached = ImageCollection(current_directory, tuple(paths))
                    elif self.fresh_inputs is not None:
                        collection = self.fresh_inputs[chapter.chapter_id]
                        if not isinstance(collection, ImageCollection) or not collection.paths:
                            raise CacheError('Lượt mới chưa có ảnh nguồn đã xác minh.')
                        decision = None  # No new grant: images were verified by the existing input gate.
                    elif local:
                        collection = ImageCollection.discover(chapter.local_source)
                    else:
                        # Recheck per chapter in the worker; UI enablement is not authorization.
                        if self.resume_source_id:
                            self.adapter.get_chapter_images(chapter, self.control)
                        decision = self.adapter.download_decision(chapter)
                        if chapter.access_status in (AccessStatus.LOCKED, AccessStatus.RESTRICTED):
                            raise AccessRestricted(decision.reason)
                        if not decision.allowed:
                            raise DownloadNotReady(decision.reason)
                        incoming = contained(self.cache.root, '_incoming', safe_id(self.comic.site_id),
                                             safe_id(self.comic.comic_id), safe_id(chapter.chapter_id))
                        previous_progress = getattr(self.adapter, 'download_progress', None)
                        last_download = {}
                        def download_progress(event):
                            last_download.update(event)
                            self.emit(dict(event, type='download', chapter_id=chapter.chapter_id))
                        self.adapter.download_progress = download_progress
                        try:
                            collection = self.adapter.download_chapter(chapter, incoming, self.control)
                        except CancelledError:
                            raise
                        except Exception as exc:
                            transfer_id = digest(['source-transfer-v1', self.comic.site_id, self.comic.comic_id,
                                                  chapter.chapter_id, str(self.output)])
                            diagnostic = DiagnosticLog(transfer_id, self.options.diagnostic_text)
                            record = dict(job_id=transfer_id, chapter_id=chapter.chapter_id,
                                image_index=last_download.get('index'), image_filename=last_download.get('file'),
                                image_path=None, stage='DOWNLOAD', error_code='DOWNLOAD_ERROR',
                                exception_type=type(exc).__name__, error_message=safe_text(exc),
                                provider=self.comic.site_id, mode=self.options.mode, model_identity=None,
                                ocr_region_index=None, ocr_confidence=None, ocr_source_text=None,
                                raw_translated_target=None, source_numeric_tokens=None, target_numeric_tokens=None,
                                validator_version=VALIDATOR_VERSION, retry_count=0, fallback_action=FAILED_NO_OUTPUT,
                                output_status=FAILED_NO_OUTPUT, output_path=None, checkpoint_state='download_error')
                            record.update(diagnostic_path=diagnostic.write(record), diagnostic_error=diagnostic.error)
                            result['review_pages'].append(record)
                            result['diagnostic_dirs'].append(str(diagnostic.directory))
                            self.emit({'type': 'image_source_error', 'chapter_id': chapter.chapter_id, 'review': record})
                            raise
                        finally:
                            self.adapter.download_progress = previous_progress
                        if not isinstance(collection, ImageCollection) or not collection.paths:
                            raise CacheError('Downloader phải trả ImageCollection ảnh đã xác minh.')
                        if not collection.root.resolve().is_relative_to(incoming.resolve()):
                            raise CacheError('Downloader trả nguồn ngoài vùng cache được cấp.')
                        if any(not p.resolve().is_relative_to(collection.root.resolve()) for p in collection.paths):
                            raise CacheError('Ảnh tải nằm ngoài collection.')
                    if not retry_this:
                        cached, current_directory, manifest = self.cache.stage(
                            self.comic, chapter, collection, self.control,
                            lambda event: self.emit(dict(event, type='cache', chapter_id=chapter.chapter_id)),
                            download_decision=decision if not local else None)
                        if self.fresh_inputs is not None:
                            manifest['provenance'] = 'verified_existing_images_fresh_agy_run'
                            self.cache.save(current_directory, manifest)
                    source_record.setdefault('cached_chapters', {})[chapter.chapter_id] = len(cached.paths)
                    source_store.save(source_record)
                    # A separate receipt database must have a separate staging area.
                    # Otherwise isolated QA/user profiles can see outputs they cannot verify.
                    namespace = digest(str(self.database.resolve()))[:20]
                    stage = (PIPELINE_STAGING_ROOT / namespace
                             / self.comic.comic_id / chapter.chapter_id)
                    if self.cache.root.is_relative_to((CACHE/'online_comics/_fresh').resolve()):
                        stage = stage/('fresh_'+self.cache.root.name)
                    data = self.options.to_dict()
                    data.update(output=str(stage), skip_success=True, preserve_structure=True)
                    options, only = cached.request(Options.from_dict(data))
                    if retry_this:
                        # Reusing successful pages across an explicitly changed
                        # provider keeps their own receipts; never rewrite them.
                        for page in manifest['pages']:
                            if page.get('output') and not page.get('needs_retry') and not page.get('error'):
                                if inspect_image(Path(page['output']))['sha256'] != page.get('output_sha256'):
                                    raise CacheError('Output thành công không khớp hash; dừng resume.')
                        only = [str(p) for p, page in zip(cached.paths, manifest['pages'])
                                if page.get('needs_retry') or page.get('error') or not page.get('output')]
                    manager = ProcessingManager(options, database, self.control, ocr=ocr, service=service,
                                                chapter_id=chapter.chapter_id,
                                                resume_id=manifest.get('pipeline_resume_id') if retry_this else None)
                    pages_by_path = {str(p): page for p, page in zip(cached.paths, manifest['pages'])}
                    manifest['state'] = 'processing'
                    self.cache.save(current_directory, manifest)
                    publish_errors = []
                    processing_errors = []
                    stages = {}

                    def event_received(event: dict) -> None:
                        if event.get('type') == 'resume_ready':
                            manifest['pipeline_resume_id'] = event['resume_id']
                            self.cache.save(current_directory, manifest)
                        if event.get('type') == 'finished':
                            return
                        if event.get('type') == 'fatal':
                            processing_errors.append(event.get('detail', 'Lỗi khởi tạo pipeline'))
                            manifest['initialization_error'] = processing_errors[-1]
                        if event.get('file') and event.get('stage') not in ('Lỗi', 'Hoàn thành', 'Bỏ qua'):
                            stages[event['file']] = event.get('stage')
                        if event.get('stage') == 'Lỗi':
                            page = pages_by_path[event['file']]
                            page['error'] = {'stage': stages.get(event['file'], 'processing'),
                                             'detail': event.get('detail', '')}
                            page.update(output_status=FAILED_NO_OUTPUT, needs_retry=True, review=event.get('review'))
                            processing_errors.append(page['error']['stage'] + ': ' + page['error']['detail'])
                            self.cache.save(current_directory, manifest)
                        if event.get('stage') in ('Hoàn thành', 'Bỏ qua', 'Ảnh gốc dự phòng') and event.get('output'):
                            page = pages_by_path[event['file']]
                            index = page['index']
                            fallback = event.get('output_status') == FALLBACK_ORIGINAL
                            receipt_job_id = event.get('receipt_job_id', manager.job_id)
                            destination = contained(self.output, safe_name(self.comic.title, self.comic.comic_id),
                                f'{chapter.order_index + 1:04d}_' + safe_name(chapter.chapter_title, chapter.chapter_id),
                                'run_' + receipt_job_id[:16], *(['original'] if fallback else []),
                                f'{index:04d}' + Path(event['output']).suffix)
                            try:
                                checksum = publish_image(Path(event['output']), destination, self.control,
                                                         (page['width'], page['height']))
                                page.update(output=str(destination), output_sha256=checksum,
                                            pipeline_output=event['output'], pipeline_job_id=receipt_job_id,
                                            warnings=event.get('detail', ''), needs_retry=fallback,
                                            output_status=FALLBACK_ORIGINAL if fallback else TRANSLATED_SUCCESS)
                                if fallback:
                                    page['error'] = {'stage': event['review']['stage'], 'detail': event['detail']}
                                    page['review'] = dict(event['review'], output_path=str(destination))
                                    event = dict(event, review=page['review'])
                                else:
                                    page.pop('error', None)
                                    page.pop('review', None)
                                self.cache.save(current_directory, manifest)
                            except CancelledError:
                                raise
                            except Exception as exc:
                                page['error'] = {'stage': 'export', 'detail': safe_text(exc)}
                                page.update(needs_retry=True, output_status=FAILED_NO_OUTPUT)
                                fallback_path, fallback_error = None, None
                                try:
                                    original = Path(event['file'])
                                    saved_original = manager.fallback_original(original, manager.destination(original), page['sha256'])
                                    fallback_path = contained(self.output, safe_name(self.comic.title, self.comic.comic_id),
                                        f'{chapter.order_index + 1:04d}_' + safe_name(chapter.chapter_title, chapter.chapter_id),
                                        'run_' + manager.job_id[:16], 'original', f'{index:04d}' + original.suffix.lower())
                                    checksum = publish_image(saved_original, fallback_path, self.control, (page['width'], page['height']))
                                    page.update(output=str(fallback_path), output_sha256=checksum, pipeline_output=str(saved_original),
                                                pipeline_job_id=manager.job_id, output_status=FALLBACK_ORIGINAL)
                                except CancelledError:
                                    raise
                                except Exception as fallback_exc:
                                    fallback_error = safe_text(fallback_exc)
                                    fallback_path = None
                                    publish_errors.append(safe_text(exc))
                                status = FALLBACK_ORIGINAL if fallback_path else FAILED_NO_OUTPUT
                                review = dict(job_id=manager.job_id, chapter_id=chapter.chapter_id,
                                    image_index=index, image_filename=page['file'], image_path=event['file'],
                                    stage='EXPORT', error_code='EXPORT_ERROR', exception_type=type(exc).__name__,
                                    error_message=safe_text(exc), provider=None, mode=self.options.mode, model_identity=None,
                                    ocr_region_index=None, ocr_confidence=None, ocr_source_text=None,
                                    raw_translated_target=None, source_numeric_tokens=None, target_numeric_tokens=None,
                                    validator_version=VALIDATOR_VERSION, retry_count=0, fallback_action=status,
                                    output_status=status, output_path=str(fallback_path) if fallback_path else None,
                                    fallback_error=fallback_error, checkpoint_state='publish_fallback' if fallback_path else 'publish_error')
                                review['diagnostic_path'] = manager.diagnostics.write(review)
                                page['review'] = review
                                self.cache.save(current_directory, manifest)
                                event = dict(event, stage='Ảnh gốc dự phòng' if fallback_path else 'Lỗi xuất',
                                             detail=safe_text(exc), output=str(fallback_path) if fallback_path else None,
                                             output_status=status, review=review)
                        self.emit(dict(event, type='pipeline', pipeline_event_type=event.get('type'),
                                       chapter_id=chapter.chapter_id))

                    manager.emit = event_received
                    summary = (manager.run(only) if only else
                               dict(state='done', skipped=len(manifest['pages']), errors=[]))
                    if summary['state'] == 'paused_provider':
                        pending = set(summary['pending_paths'])
                        for p, page in zip(cached.paths, manifest['pages']):
                            if str(p) in pending:
                                page['needs_retry'] = True
                        manifest.update(state='paused_provider', pipeline_summary=summary,
                            needs_retry=[p['index'] for p in manifest['pages'] if p.get('needs_retry') or not p.get('output')])
                        self.cache.save(current_directory, manifest)
                        result.update(state='paused_provider', paused_chapter=chapter.chapter_id,
                            pending_chapters=[c.chapter_id for c in self.chapters[position-1:]],
                            images_exported=result['images_exported'] + sum(bool(p.get('output')) for p in manifest['pages']))
                        break
                    pages = manifest['pages']
                    review_pages = [p.get('review') for p in pages if p.get('needs_retry') and p.get('review')]
                    originals = sum(p.get('output_status') == FALLBACK_ORIGINAL and bool(p.get('output')) for p in pages)
                    translated = sum(bool(p.get('output')) and not p.get('error') and not p.get('needs_retry') for p in pages)
                    missing = len(pages) - originals - translated
                    counts = dict(images_total=len(pages), translated_success=translated, partial_translation=0,
                                  fallback_original=originals, failed_no_output=missing,
                                  files_exported=originals + translated, skipped=summary['skipped'],
                                  needs_review=len(pages)-translated)
                    has_errors = summary['state'] not in ('done', 'completed_with_warnings') or publish_errors or missing
                    manifest.update(pipeline_summary=summary, publish_errors=publish_errors, counts=counts,
                                    needs_retry=[p['index'] for p in pages if p.get('needs_retry') or not p.get('output')],
                                    state='error' if has_errors else 'completed_with_warnings' if originals else 'completed')
                    for key in ('images_total', 'translated_success', 'partial_translation', 'fallback_original', 'failed_no_output', 'skipped'):
                        result[key] += counts[key]
                    result['images_exported'] += counts['files_exported']
                    result['images_failed'] += missing
                    result['outputs'].extend(p['output'] for p in pages if p.get('output'))
                    result['review_pages'].extend(review_pages)
                    if summary.get('diagnostic_dir'):
                        result['diagnostic_dirs'].append(summary['diagnostic_dir'])
                    self.cache.save(current_directory, manifest)
                    if summary['state'] == 'cancelled':
                        raise CancelledError('Đã hủy an toàn.')
                    if has_errors:
                        raise RuntimeError('Pipeline/xuất ảnh kết thúc với lỗi; xem manifest và chi tiết từng ảnh. '
                                           + '; '.join(processing_errors + publish_errors))
                    if len([p for p in manifest['pages'] if p.get('pipeline_job_id') and p.get('output')]) != len(cached.paths):
                        raise CacheError('Thiếu trang xuất so với danh sách chương.')
                    if originals:
                        result['chapters_with_warnings'] += 1
                        self.emit({'type': 'chapter_warning', 'chapter_id': chapter.chapter_id, 'counts': counts,
                                   'detail': 'Đủ file xuất, còn ảnh gốc dự phòng cần xem lại.'})
                        continue
                    if not self.keep_cached:
                        self.cache.cleanup_completed(current_directory, manifest)
                    result['chapters_completed'] += 1
                    self.emit({'type': 'chapter_done', 'chapter_id': chapter.chapter_id,
                               'position': position, 'total_chapters': len(self.chapters), 'counts': counts})
                except CancelledError:
                    raise
                except Exception as exc:
                    LOGGER.error('Local chapter failed: %s exception=%s', chapter.chapter_id, type(exc).__name__)
                    if manifest is not None and current_directory:
                        manifest.update(state='error', error=safe_text(exc))
                        self.cache.save(current_directory, manifest)
                    result['chapters_failed'] += 1
                    result['errors'].append({'chapter_id': chapter.chapter_id, 'detail': safe_text(exc),
                                             'category': getattr(exc, 'category', 'processing')})
                    self.emit({'type': 'chapter_error', **result['errors'][-1]})
            if result['errors']:
                result['state'] = 'errors'
            elif result['chapters_with_warnings']:
                result['state'] = 'completed_with_warnings'
            elif result['state'] != 'paused_provider':
                result['state'] = 'done'
        except CancelledError:
            result['state'] = 'cancelled'
            if current_directory and manifest is not None:
                manifest['state'] = 'cancelled'
                self.cache.save(current_directory, manifest)
        except Exception as exc:
            LOGGER.error('Comic job failed: %s', type(exc).__name__)
            result['state'] = 'error'
            result['errors'].append({'chapter_id': None, 'detail': safe_text(exc),
                                     'category': getattr(exc, 'category', 'processing')})
        finally:
            if source_record:
                source_record['state'] = 'done' if result['state'] == 'done' else result['state']
                source_store.save(source_record)
            if database:
                database.close()
            self.emit({'type': 'job_finished', **result})
        return result
