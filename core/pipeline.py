from __future__ import annotations

import logging
import json
import os
import re
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable
from uuid import uuid4

import numpy as np

from core.imaging import SUPPORTED, TextRenderer, atomic_save, default_font, erase_text, open_image
from core.ocr import PaddleOCREngine
from core.ocr_overrides import OCRRegionOverrides
from core.paths import ROOT
from core.storage import TranslationCache, digest, file_digest
from core.types import CancelledError, MissingModelError, OCRResult, Options
from core.diagnostics import (DiagnosticLog, VALIDATOR_VERSION, safe_text,
    TRANSLATED_SUCCESS, FALLBACK_ORIGINAL, FAILED_NO_OUTPUT)
from providers.offline import create_offline_provider
from providers.online import LibreTranslateProvider, MyMemoryProvider, ProviderError, ProviderSuspended
from providers.agy import AGYProvider, MODE as AGY_MODE
from providers.gemini_api import GeminiAPIProvider, MODE as GEMINI_API_MODE

LOGGER = logging.getLogger(__name__)
NUMBER_PATTERN = r'[+\-−－＋]?\d+(?:[.,:/%+−-]\d+)*%?'


def has_signed_number(text: str) -> bool:
    return any(token[0] in '+-−－＋' for token in re.findall(NUMBER_PATTERN, text))


class NumericMismatchError(ProviderError):
    code = 'NUMERIC_MISMATCH'


def natural_key(path: Path) -> list:
    return [(1, int(part)) if part.isdigit() else (0, part.casefold()) for part in re.split(r'(\d+)', str(path))]


def scan_images(source: Path, recursive: bool, output: Path | None = None) -> list[Path]:
    if not source.is_dir():
        raise FileNotFoundError('Thư mục ảnh nguồn không tồn tại')
    output = output.resolve() if output else None
    iterator = source.rglob('*') if recursive else source.iterdir()
    return sorted([path for path in iterator if path.is_file() and not path.is_symlink() and
                   path.suffix.lower() in SUPPORTED and not (output and path.resolve().is_relative_to(output))], key=natural_key)


class JobControl:
    def __init__(self):
        self.condition = threading.Condition()
        self.paused = False
        self.cancelled = False

    def pause(self) -> None:
        with self.condition:
            self.paused = True

    def resume(self) -> None:
        with self.condition:
            self.paused = False
            self.condition.notify_all()

    def cancel(self) -> None:
        with self.condition:
            self.cancelled = True
            self.condition.notify_all()

    def checkpoint(self) -> None:
        with self.condition:
            while self.paused and not self.cancelled:
                self.condition.wait(.2)
            if self.cancelled:
                raise CancelledError('Đã hủy tại checkpoint an toàn')


class TranslationService:
    def __init__(self, options: Options, cache: TranslationCache, control: JobControl,
                 offline=None, online=None):
        self.options, self.cache, self.control = options, cache, control
        self.offline = offline
        self.online = online
        self.agy = None
        self.gemini_api = None
        self.last_attempt: dict = {}

    def _offline(self):
        if self.offline is None:
            self.offline = create_offline_provider(self.options.offline_provider)
        return self.offline

    def _online(self):
        if self.online is None:
            self.online = (MyMemoryProvider(checkpoint=self.control.checkpoint) if self.options.online_provider == 'MyMemory'
                           else LibreTranslateProvider(self.options.endpoint, checkpoint=self.control.checkpoint))
        return self.online

    def _agy(self):
        if self.agy is None:
            self.agy = AGYProvider(executable=self.options.agy_executable, model=self.options.agy_model,
                timeout=self.options.agy_timeout, max_requests=self.options.agy_max_requests,
                checkpoint=self.control.checkpoint, cancelled=lambda: self.control.cancelled)
        return self.agy

    def identity(self) -> str:
        parts = ['literal-numbers-v1', self.options.mode, self.options.allow_online_fallback, self.options.glossary]
        if self.options.mode == AGY_MODE:
            return digest(parts + [self._agy().identity])
        if self.options.mode == GEMINI_API_MODE:
            return digest(parts + [self._gemini_api().identity])
        if self.options.mode not in ('Online', 'Online Free'):
            parts.append(self._offline().identity)
        if self.options.mode in ('Online', 'Online Free') or (self.options.mode == 'Auto Fallback' and self.options.allow_online_fallback):
            parts.append(self._online().identity)
        return digest(parts)

    def _chunks(self, text: str) -> list[str]:
        # Bound anonymous API query length while retaining every character.
        chunks, current = [], ''
        for char in text:
            if char in '\r\n':
                if current:
                    chunks.append(current)
                    current = ''
                continue
            if len((current + char).encode('utf-8')) > 450:
                chunks.append(current)
                current = ''
            current += char
        if current:
            chunks.append(current)
        return chunks

    def _gemini_api(self):
        if self.gemini_api is None:
            self.gemini_api = GeminiAPIProvider(model=self.options.gemini_api_model,
                timeout=self.options.gemini_api_timeout, max_requests=self.options.gemini_api_max_requests,
                free_tier_confirmed=self.options.gemini_api_free_tier_confirmed,
                checkpoint=self.control.checkpoint)
        return self.gemini_api

    def _translate_using(self, provider, text: str, language: str, context: str,
                         deferred: list | None = None, raw_target: str | None = None) -> str | None:
        provider_name = getattr(provider, 'engine_name', None)
        self.last_attempt = {'provider': provider_name if isinstance(provider_name, str) else type(provider).__name__,
                             'model_identity': provider.identity, 'mode': self.options.mode if self.options.mode in (AGY_MODE, GEMINI_API_MODE) else 'Online' if provider.online else 'Offline',
                             'ocr_source_text': text, 'raw_translated_target': None}
        key = digest([text, language, 'vi', provider.identity, self.options.glossary, context, 'glossary-v3-literal-numbers'])
        cached = self.cache.get('translation', key)
        # Keep unsigned legacy cache/118 existing receipts intact. Signed source or
        # legacy signed target must use freshly validated, versioned cache entries.
        signed_namespace = has_signed_number(text) or (cached is not None and has_signed_number(cached))
        if signed_namespace:
            key = digest([text, language, 'vi', provider.identity, self.options.glossary, context, 'glossary-v4-signed-numbers'])
            cached = self.cache.get('translation', key)
        if cached is not None:
            return cached
        # Names retain explicit glossary markers. Numbers stay in their sentence
        # context: untranslated synthetic markers confuse the installed MT models.
        substitutions = []
        protected = text
        for term, replacement in sorted(self.options.glossary.items(), key=lambda pair: len(pair[0]), reverse=True):
            if term and term in protected:
                marker = 'ZXQ' + chr(65 + len(substitutions)//26) + chr(65 + len(substitutions)%26) + 'QXZ'
                protected = protected.replace(term, marker)
                substitutions.append((marker, replacement))
        number_pattern = NUMBER_PATTERN
        expected_numbers = re.findall(number_pattern, protected)
        self.last_attempt['source_numeric_tokens'] = expected_numbers
        self.control.checkpoint()
        if deferred is not None:
            deferred.append((protected, language))
            return None
        try:
            if raw_target is not None:
                translated = raw_target
            elif provider.online and isinstance(provider, MyMemoryProvider):
                translated = ' '.join(provider.translate(chunk, language) for chunk in self._chunks(protected))
            else:
                translated = provider.translate(protected, language)
        finally:
            count = getattr(provider, 'retry_count', 0)
            self.last_attempt['retry_count'] = count if isinstance(count, int) else 0
        self.last_attempt.update(raw_translated_target=translated,
                                 target_numeric_tokens=re.findall(number_pattern, translated or ''))
        if not translated or not translated.strip():
            raise ProviderError('Provider trả bản dịch rỗng')
        if re.findall(number_pattern, translated) != expected_numbers:
            raise NumericMismatchError('Bản dịch không qua kiểm tra số; giữ ảnh gốc để xem lại.')
        for marker, replacement in substitutions:
            pattern = re.compile(re.escape(marker), flags=re.IGNORECASE)
            if not pattern.search(translated):
                raise ProviderError('Provider làm thay đổi tên riêng/số được bảo vệ; không xuất ảnh này. Hãy thử provider khác.')
            translated = pattern.sub(lambda _: replacement, translated)
        if re.search(r'ZX[QN][A-Z]{2}[QN]XZ', translated, flags=re.I):
            raise ProviderError('Không khôi phục được ký hiệu bảo vệ')
        self.cache.put('translation', key, translated)
        return translated

    def translate(self, text: str, language: str, context: str) -> str:
        self.last_attempt = {}
        if self.options.mode == AGY_MODE:
            return self._translate_using(self._agy(), text, language, context)
        if self.options.mode == GEMINI_API_MODE:
            return self._translate_using(self._gemini_api(), text, language, context)
        if self.options.mode in ('Online', 'Online Free'):
            return self._translate_using(self._online(), text, language, context)
        try:
            return self._translate_using(self._offline(), text, language, context)
        except (MissingModelError, ProviderError, RuntimeError, ValueError, ImportError):
            if self.options.mode != 'Auto Fallback' or not self.options.allow_online_fallback:
                raise
            self.control.checkpoint()
            return self._translate_using(self._online(), text, language, context)

    def translate_regions(self, regions: list[OCRResult], context: str) -> list[str]:
        """Batch only cache misses; retain the exact existing per-region guard/cache."""
        provider = self._gemini_api() if self.options.mode == GEMINI_API_MODE else self._agy()
        results, pending = [], []
        for region in regions:
            results.append(self._translate_using(provider, region.text, region.language, context, deferred=pending))
        slots = [i for i, value in enumerate(results) if value is None]
        groups = {}
        for index, item in zip(slots, pending):
            groups.setdefault(item[1], []).append((index, item[0]))
        for language, group in groups.items():
            try:
                first = group[0][0]
                # Establish diagnostic context before the one batch request.
                self._translate_using(provider, regions[first].text, language, context, deferred=[])
                targets = provider.translate_batch([text for _, text in group], language)
                for (index, _), target in zip(group, targets):
                    try:
                        results[index] = self._translate_using(provider, regions[index].text, language, context, raw_target=target)
                    except Exception as exc:
                        exc.region_index = index
                        raise
            except Exception as exc:
                if not hasattr(exc, 'region_index'):
                    exc.region_index = group[0][0]
                raise
        return results

    def close(self) -> None:
        if self.online is not None and hasattr(self.online, 'close'):
            self.online.close()
        if self.agy is not None:
            self.agy.close()
        if self.gemini_api is not None:
            self.gemini_api.close()


class ProcessingManager:
    """One image/model inference at a time; Qt-free and CLI/test friendly."""
    def __init__(self, options: Options, cache: TranslationCache | None = None,
                 control: JobControl | None = None, emit: Callable[[dict], None] = lambda _: None,
                 ocr=None, service=None, chapter_id: str | None = None, diagnostic_root: Path | None = None,
                 override_registry: OCRRegionOverrides | None = None, resume_id: str | None = None,
                 prepared_chapter=None):
        self.options = options
        self.cache = cache or TranslationCache()
        self.owns_cache = cache is None
        self.control = control or JobControl()
        self.emit = emit
        self.ocr = ocr or PaddleOCREngine()
        self.service = service or TranslationService(options, self.cache, self.control)
        self.source = Path(options.source).resolve()
        self.output = Path(options.output).resolve()
        self.job_id = ''
        self.chapter_id = chapter_id
        self.diagnostic_root = diagnostic_root
        self.diagnostics = None
        self.override_registry = override_registry
        self.started = 0.0
        self.counts = {'completed': 0, 'failed': 0, 'skipped': 0}
        self.fallback_count = 0
        self.review_pages: list[dict] = []
        from core.resume import ResumeStore
        self.resume_store = ResumeStore(getattr(self.cache, 'path', None))
        self.resume_id = resume_id
        self.journal = None
        self.prepared_chapter = prepared_chapter

    def cache_source_hash(self, path):
        value = file_digest(path)
        if self.journal:
            page = next(p for p in self.journal['pages'] if p['path'] == str(path))
            if value != page['source_hash']:
                raise ValueError('RESUME_SOURCE_CHANGED: ảnh nguồn đổi trong khi xử lý')
        return value

    def page_done(self, path, relevant, ocr_identity, service_identity):
        previous = self.cache.item(self.job_id, str(path))
        if not previous or previous['status'] != 'done':
            return False
        registry = self.override_registry if self.override_registry is not None else OCRRegionOverrides.load()
        rules = registry.for_image(self.cache_source_hash(path), path)
        parts = [file_digest(path), relevant, ocr_identity, service_identity]
        revision = registry.revision(rules)
        if revision:
            parts.append({'ocr_override_revision': revision})
        target = self.destination(path)
        return (previous['fingerprint'] == digest(parts) and target.is_file()
                and self.cache.get('output-hash', str(target)) == file_digest(target))

    def load_ocr_page(self, path, source_hash, ocr_identity):
        registry = self.override_registry if self.override_registry is not None else OCRRegionOverrides.load()
        rules = registry.for_image(source_hash, path)
        key = digest([source_hash, ocr_identity, self.options.language, self.options.confidence,
                      self.options.tile_size, self.options.reading_direction])
        data = self.cache.get('ocr', key)
        if data is None:
            image = open_image(path)
            regions, warnings = self.ocr.recognize(np.array(image.convert('RGB')), self.options.language,
                self.options.confidence, self.options.tile_size, self.options.reading_direction, self.control.checkpoint)
            self.cache.put('ocr', key, {'regions': [asdict(r) for r in regions], 'warnings': warnings})
        else:
            regions, warnings = [OCRResult(**r) for r in data['regions']], list(data['warnings'])
        regions, receipts = registry.apply(regions, rules)
        if receipts:
            warnings.append(f'Đã bỏ qua {len(receipts)} vùng OCR giả theo evidence/hash/polygon; cache OCR gốc giữ nguyên.')
        preserved = [r for r in regions if not any(c.isalpha() for c in r.text)]
        regions = [r for r in regions if any(c.isalpha() for c in r.text)]
        if preserved:
            warnings.append(f'Giữ nguyên {len(preserved)} vùng chỉ có số/ký hiệu; không xóa/chèn lại.')
        return regions, warnings, preserved, receipts

    def fallback_original(self, path: Path, destination: Path, expected_hash: str) -> Path:
        """Publish a verified byte-for-byte original under a separate immutable name."""
        target = destination.with_name(destination.stem + '.fallback-original' + path.suffix.lower())
        return self._copy_original(path, target, expected_hash)

    def _copy_original(self, path: Path, target: Path, expected_hash: str, before_publish=None) -> Path:
        if target.resolve() == path.resolve() or not target.resolve().is_relative_to(self.output):
            raise ValueError('Không sao chép đè nguồn hoặc ngoài thư mục output.')
        # Local import avoids the sources.collection -> pipeline import cycle.
        from sources.cache import inspect_image
        info = inspect_image(path)
        if info['sha256'] != expected_hash:
            raise IOError('Ảnh nguồn đã đổi; không dùng làm ảnh dự phòng')
        if target.exists():
            if inspect_image(target)['sha256'] != expected_hash:
                raise FileExistsError('Ảnh dự phòng đã tồn tại và khác nội dung; không ghi đè')
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + '.' + uuid4().hex + '.part')
        try:
            with path.open('rb') as src, temp.open('xb') as dst:
                while True:
                    self.control.checkpoint()
                    block = src.read(1024 * 1024)
                    if not block:
                        break
                    dst.write(block)
                dst.flush()
                os.fsync(dst.fileno())
            if inspect_image(temp)['sha256'] != expected_hash or file_digest(path) != expected_hash:
                raise IOError('Ảnh thay đổi khi sao chép dự phòng')
            self.control.checkpoint()
            if before_publish:
                before_publish(temp)
            # Atomic no-clobber publication, even if another process creates target.
            if os.name == 'nt':
                os.rename(temp, target)  # Windows rename refuses to replace existing targets, including on FAT.
            else:
                os.link(temp, target)
        finally:
            temp.unlink(missing_ok=True)
        return target

    def validate(self) -> None:
        if not self.source.is_dir():
            raise FileNotFoundError('Chọn thư mục nguồn tồn tại')
        if self.output == self.source or self.source.is_relative_to(self.output):
            raise ValueError('Thư mục xuất phải tách khỏi ảnh nguồn và không được là thư mục cha của nguồn')
        if not self.output.is_relative_to(ROOT.resolve()) or self.output == ROOT.resolve():
            raise ValueError(f'Mọi kết quả phải nằm trong thư mục con của {ROOT}')
        for reserved in ('models', 'config', 'cache', 'logs', 'ui', 'core', 'providers', 'scripts', 'tests', '.venv', 'assets'):
            if self.output.is_relative_to((ROOT / reserved).resolve()):
                raise ValueError('Thư mục xuất trùng khu vực mã nguồn/model/cache của ứng dụng')
        if self.options.mode not in ('Online', 'Online Free', 'Offline', 'Auto Fallback', AGY_MODE, GEMINI_API_MODE):
            raise ValueError('Chế độ dịch không hợp lệ')
        if self.options.language not in ('zh', 'zt', 'ko', 'en', 'auto'):
            raise ValueError('Ngôn ngữ OCR không hợp lệ')
        if not (4 <= self.options.font_min <= self.options.font_max <= 200):
            raise ValueError('Cỡ chữ không hợp lệ')
        self.output.mkdir(parents=True, exist_ok=True)

    def api_diagnostic(self, record, exc, checkpoint, pending_count):
        if self.options.mode == GEMINI_API_MODE:
            from providers.gemini_diagnostics import clean
            info = dict(getattr(exc, 'gemini_api_diagnostic', None) or {})
            info.update(job_id=self.job_id, chapter_id=self.chapter_id, checkpoint_state=checkpoint,
                        pending_page_count=pending_count, cache_preservation_state='RETAINED',
                        error_code=record.get('error_code', 'UNKNOWN'))
            record['gemini_api_request'] = clean(info)

    def destination(self, path: Path) -> Path:
        relative = path.relative_to(self.source)
        suffix = path.suffix.lower() if self.options.output_format == 'original' else '.' + self.options.output_format
        stem = path.stem if self.options.output_format == 'original' else path.name
        if not self.options.preserve_structure:
            stem += '__' + digest(str(relative))[:8]
        # Include job identity: different providers/configs never clobber earlier work.
        name = stem + '.vi-' + self.job_id[:8] + suffix
        destination = self.output / (relative.parent if self.options.preserve_structure else Path()) / name
        if destination.resolve() == path.resolve() or not destination.resolve().is_relative_to(self.output):
            raise ValueError('Đường dẫn đầu ra không an toàn')
        return destination

    def event(self, path: Path | None, stage: str, percent: int, index: int, total: int, **extra) -> None:
        elapsed = time.monotonic() - self.started
        finished = self.counts['completed'] + self.counts['failed'] + self.counts['skipped']
        eta = (elapsed / finished * (total-finished)) if finished else None
        self.emit({'file': str(path) if path else '', 'stage': stage, 'percent': percent,
                   'index': index, 'total': total, 'elapsed': elapsed, 'eta': eta,
                   **self.counts, 'fallback_original': self.fallback_count,
                   'failed_no_output': self.counts['failed'] - self.fallback_count, **extra})

    def run(self, only: list[str] | None = None) -> dict:
        self.started = time.monotonic()
        files = []
        errors = []
        pending_paths = []
        state = 'interrupted'
        try:
            self.validate()
            files = scan_images(self.source, self.options.recursive, self.output)
            image_indices = {str(p): n for n, p in enumerate(files, 1)}
            self.page_indices = image_indices
            if only is not None:
                requested = set(only)
                files = [p for p in files if str(p) in requested]
            if not files:
                raise ValueError('Thư mục không có ảnh được hỗ trợ hoặc không còn ảnh cần thử lại')
            self.journal = self.resume_store.pipeline(self.options, files, self.cache, self.resume_id, self.chapter_id)
            self.resume_id = self.journal['id']
            self.emit({'type': 'resume_ready', 'resume_id': self.resume_id})
            self.emit({'type': 'files', 'files': [str(p) for p in files]})
            # Validate model presence before decoding/erasing images.
            preflight_error, preflight_stage = None, None
            try:
                ocr_identity = self.ocr.identity(self.options.language)
            except Exception as exc:
                preflight_error, preflight_stage = exc, 'OCR'
                ocr_identity = 'unavailable:' + type(exc).__name__
            try:
                service_identity = self.service.identity()
                if self.prepared_chapter is not None:
                    service_identity = digest([service_identity, self.prepared_chapter.identity])
            except Exception as exc:
                if preflight_error is None:
                    preflight_error, preflight_stage = exc, 'TRANSLATION'
                service_identity = 'unavailable:' + type(exc).__name__
            relevant = self.options.to_dict()
            relevant['imaging_revision'] = 'adaptive-mask-v2'
            relevant['text_region_revision'] = 'preserve-symbol-regions-v1'
            relevant.pop('skip_success', None)
            # Operational logging must not invalidate existing job/translation keys.
            relevant.pop('diagnostic_text', None)
            for key in ('gemini_api_model', 'gemini_api_timeout', 'gemini_api_max_requests', 'gemini_api_free_tier_confirmed'):
                if self.options.mode != GEMINI_API_MODE or key == 'gemini_api_free_tier_confirmed':
                    relevant.pop(key, None)
            if self.options.mode != AGY_MODE:
                # Adding optional AGY settings must not invalidate old jobs.
                for key in ('agy_executable', 'agy_model', 'agy_timeout', 'agy_max_requests',
                            'agy_batch_chars', 'agy_batch_regions', 'agy_context'):
                    relevant.pop(key, None)
            else:
                relevant['agy_batch_revision'] = 'multipage-ids-context-v1'
            if self.options.mode == GEMINI_API_MODE:
                relevant['gemini_api_batch_recipe'] = ['multipage-ids-context-v1',
                    self.options.agy_batch_chars, self.options.agy_batch_regions, self.options.agy_context]
            font_path = Path(self.options.font) if self.options.font else default_font()
            relevant['font_sha256'] = file_digest(font_path) if font_path.is_file() else 'missing-font'
            if self.options.erase_mode == 'custom' and self.options.mask_path:
                relevant['mask_sha256'] = file_digest(Path(self.options.mask_path))
            self.job_id = digest([relevant, ocr_identity, service_identity, 'pipeline-v3'])
            self.diagnostics = DiagnosticLog(self.job_id, self.options.diagnostic_text, self.diagnostic_root)
            self.cache.job(self.job_id, self.options, 'running')
            batching = None
            if self.prepared_chapter is None and self.options.mode in (AGY_MODE, GEMINI_API_MODE) and files and preflight_error is None:
                from core.multipage import MultiPageAGY
                batching = MultiPageAGY(self, files, relevant, ocr_identity, service_identity)
            for index, path in enumerate(files):
                self.control.checkpoint()
                destination = self.destination(path)
                stage = 'EXPORT'
                region_index, current_region = None, None
                original_hash, fingerprint = None, ''
                self.service.last_attempt = {}
                try:
                    restored = next(p for p in self.journal['pages'] if p['path'] == str(path))
                    if restored['state'] == 'done':
                        self.counts['skipped'] += 1
                        self.event(path, 'Bỏ qua', 100, index+1, len(files), output=restored['output'],
                            output_status=TRANSLATED_SUCCESS, image_index=image_indices[str(path)],
                            receipt_job_id=restored['job_id'])
                        continue
                    original_hash = self.cache_source_hash(path)
                    stage = 'OCR'
                    registry = self.override_registry if self.override_registry is not None else OCRRegionOverrides.load()
                    override_rules = registry.for_image(original_hash, path)
                    override_revision = registry.revision(override_rules)
                    fingerprint_parts = [original_hash, relevant, ocr_identity, service_identity]
                    if override_revision:
                        fingerprint_parts.append({'ocr_override_revision': override_revision})
                    fingerprint = digest(fingerprint_parts)
                    stage = 'EXPORT'
                    previous = self.cache.item(self.job_id, str(path))
                    if previous and previous['status'] == 'done' and previous['fingerprint'] == fingerprint:
                        if destination.is_file():
                            old = self.cache.get('output-hash', str(destination))
                            if old == file_digest(destination):
                                self.counts['skipped'] += 1
                                self.event(path, 'Bỏ qua', 100, index+1, len(files), output=str(destination),
                                           output_status=TRANSLATED_SUCCESS, image_index=image_indices[str(path)])
                                self.resume_store.page(self.journal, path, state='done', output=str(destination),
                                    output_hash=file_digest(destination), job_id=self.job_id, fingerprint=fingerprint)
                                continue
                    # Never overwrite a user-created/modified result with no matching receipt.
                    if destination.exists():
                        known = self.cache.get('output-hash', str(destination))
                        if known != file_digest(destination):
                            raise FileExistsError('File kết quả đã có và không khớp checkpoint; chọn thư mục xuất khác')
                    self.cache.checkpoint(self.job_id, str(path), 'working', fingerprint=fingerprint)
                    if preflight_error is not None:
                        stage = preflight_stage
                        raise preflight_error
                    stage = 'OCR'
                    self.event(path, 'OCR', 5, index+1, len(files))
                    image = open_image(path)
                    regions, warnings, preserved_regions, override_receipts = self.load_ocr_page(path, original_hash, ocr_identity)
                    self.resume_store.page(self.journal, path, ocr_ready=True)
                    self.control.checkpoint()
                    self.event(path, 'Dịch', 30, index+1, len(files), language=', '.join(sorted({r.language for r in regions})))
                    context = digest([r.text for r in regions])
                    translations = []
                    stage = 'TRANSLATION'
                    if self.prepared_chapter is not None:
                        translations = self.prepared_chapter.for_page(path, regions)
                    elif self.options.mode in (AGY_MODE, GEMINI_API_MODE) and regions:
                        region_index, current_region = 0, regions[0]
                        try:
                            translations = batching.for_page(path, regions)
                        except Exception as exc:
                            region_index = getattr(exc, 'region_index', 0)
                            current_region = regions[region_index]
                            raise
                    for n, region in enumerate([] if self.prepared_chapter is not None or self.options.mode in (AGY_MODE, GEMINI_API_MODE) else regions):
                        region_index, current_region = n, region
                        self.control.checkpoint()
                        translations.append(self.service.translate(region.text, region.language, context))
                        self.event(path, 'Dịch', 30+int(30*(n+1)/max(1, len(regions))), index+1, len(files))
                    if not regions:
                        warnings.append('Không có vùng chữ cần dịch; giữ nguyên nội dung ảnh.')
                    self.control.checkpoint()
                    current_region, region_index = None, None
                    stage = 'INPAINT'
                    self.event(path, 'Xóa chữ', 65, index+1, len(files))
                    erased = erase_text(image, regions, self.options)
                    self.control.checkpoint()
                    stage = 'RENDER'
                    self.event(path, 'Chèn chữ', 80, index+1, len(files))
                    renderer = TextRenderer(self.options)
                    rendered = renderer.render(erased, regions, translations)
                    self.control.checkpoint()
                    stage = 'EXPORT'
                    self.event(path, 'Đang lưu', 95, index+1, len(files))
                    if file_digest(path) != original_hash:
                        raise IOError('Ảnh nguồn thay đổi trong khi xử lý; không ghi kết quả')
                    metadata = {'source': str(path), 'output': str(destination),
                        'size': list(image.size), 'regions': [asdict(r) for r in regions],
                        'preserved_regions': [asdict(r) for r in preserved_regions], 'ocr_overrides': override_receipts,
                        'no_text_to_translate': not regions, 'numeric_validator_version': VALIDATOR_VERSION,
                        'translations': translations, 'warnings': warnings}
                    def before_publish(temp):
                        if self.prepared_chapter is not None:
                            self.prepared_chapter.for_page(path, regions)  # Recheck the chapter transaction before publish.
                        self.cache.put('metadata', fingerprint, metadata)
                        self.resume_store.page(self.journal, path, state='publishing', output=str(destination),
                            output_hash=file_digest(temp), job_id=self.job_id, fingerprint=fingerprint)
                    if not regions and self.options.output_format == 'original':
                        self._copy_original(path, destination, original_hash, before_publish)
                    else:
                        warnings += atomic_save(rendered, destination, self.options.quality, overwrite=False,
                                                before_publish=before_publish)
                    self.cache.put('output-hash', str(destination), file_digest(destination))
                    self.cache.put('metadata', fingerprint, metadata)
                    self.cache.checkpoint(self.job_id, str(path), 'done', str(destination), fingerprint, '\n'.join(warnings))
                    self.resume_store.page(self.journal, path, state='done', output=str(destination),
                        output_hash=file_digest(destination), job_id=self.job_id, fingerprint=fingerprint)
                    self.counts['completed'] += 1
                    self.event(path, 'Hoàn thành', 100, index+1, len(files), output=str(destination), detail='\n'.join(warnings),
                               output_status=TRANSLATED_SUCCESS, image_index=image_indices[str(path)])
                except ProviderSuspended as exc:
                    # No erasing, fallback publication or failure counter on quota.
                    # Successful receipts remain immutable; retry starts at this page.
                    done_paths = {p['path'] for p in self.journal['pages'] if p['state'] == 'done'}
                    pending_paths = [str(p) for p in files[index:] if str(p) not in done_paths]
                    record = dict(job_id=self.job_id, chapter_id=self.chapter_id,
                        image_index=image_indices[str(path)], image_filename=path.name,
                        stage='TRANSLATION', error_code=exc.code, error_message=str(exc),
                        exception_type=type(exc).__name__, checkpoint_state='paused_provider',
                        fallback_action='NONE', **self.service.last_attempt)
                    if self.options.mode == AGY_MODE:
                        from providers.agy_diagnostics import transport
                        record['agy_protocol'] = getattr(exc, 'agy_diagnostic', None) or transport(exc.code)
                    if getattr(exc, 'phase', None) == 'provider_preflight':
                        record.update(preflight_phase=exc.phase, request_sent=False, request_scope='current_batch')
                        for key in ('ocr_source_text', 'raw_translated_target', 'source_numeric_tokens', 'target_numeric_tokens'):
                            record.pop(key, None)
                    self.api_diagnostic(record, exc, 'paused_provider', len(pending_paths))
                    log_path = self.diagnostics.write(record)
                    self.cache.checkpoint(self.job_id, str(path), 'paused_provider',
                                          fingerprint=fingerprint, detail=exc.code)
                    self.emit(dict(type='provider_paused', code=exc.code, file=str(path),
                        detail=str(exc), retry_after=exc.retry_after, diagnostic_path=log_path,
                        phase=getattr(exc, 'phase', None), request_sent=getattr(exc, 'request_sent', None),
                        request_scope=getattr(exc, 'request_scope', None),
                        image_index=image_indices[str(path)], provider=self.service.last_attempt.get('provider'),
                        gemini_api_request=record.get('gemini_api_request'),
                        pending_paths=pending_paths))
                    state = 'paused_provider'
                    break
                except CancelledError as exc:
                    if self.options.mode == GEMINI_API_MODE:
                        record = dict(job_id=self.job_id, chapter_id=self.chapter_id, stage='TRANSLATION',
                            error_code='CANCELLED', checkpoint_state='cancelled', mode=GEMINI_API_MODE)
                        self.api_diagnostic(record, exc, 'cancelled', len(files)-index)
                        self.diagnostics.write(record)
                    if self.options.mode == AGY_MODE and getattr(exc, 'agy_diagnostic', None):
                        self.diagnostics.write(dict(job_id=self.job_id, chapter_id=self.chapter_id,
                            image_index=image_indices[str(path)], image_filename=path.name,
                            stage='TRANSLATION', error_code='CANCELLED', checkpoint_state='cancelled',
                            provider='AGY Gemini', mode=AGY_MODE, agy_protocol=exc.agy_diagnostic))
                    self.cache.checkpoint(self.job_id, str(path), 'cancelled')
                    raise
                except Exception as exc:
                    self.counts['failed'] += 1
                    errors.append(str(path))
                    detail = safe_text(str(exc) or type(exc).__name__)
                    code = getattr(exc, 'code', stage + '_ERROR')
                    error_stage = 'VALIDATION' if isinstance(exc, NumericMismatchError) else stage
                    LOGGER.error('file=%s stage=%s error=%s code=%s', path.name, error_stage, type(exc).__name__, code)
                    output, fallback_error = None, None
                    try:
                        if original_hash is not None:
                            output = self.fallback_original(path, destination, original_hash)
                    except CancelledError:
                        self.cache.checkpoint(self.job_id, str(path), 'cancelled')
                        raise
                    except Exception as fallback_exc:
                        fallback_error = safe_text(fallback_exc)
                    status = FALLBACK_ORIGINAL if output else FAILED_NO_OUTPUT
                    checkpoint = 'fallback_original' if output else 'error'
                    if output:
                        self.fallback_count += 1
                        self.cache.put('output-hash', str(output), file_digest(output))
                    attempt = getattr(self.service, 'last_attempt', {}) if stage == 'TRANSLATION' else {}
                    record = dict(timestamp=None, job_id=self.job_id, chapter_id=self.chapter_id,
                        image_index=image_indices[str(path)], image_filename=path.name, image_path=str(path),
                        stage=error_stage, error_code=code, exception_type=type(exc).__name__, error_message=detail,
                        provider='PaddleOCR' if stage == 'OCR' else attempt.get('provider'), mode=attempt.get('mode', self.options.mode),
                        model_identity=ocr_identity if stage == 'OCR' else attempt.get('model_identity'), ocr_region_index=region_index,
                        ocr_confidence=current_region.confidence if current_region else None,
                        ocr_source_text=attempt.get('ocr_source_text', current_region.text if current_region else None),
                        raw_translated_target=attempt.get('raw_translated_target'),
                        source_numeric_tokens=attempt.get('source_numeric_tokens'),
                        target_numeric_tokens=attempt.get('target_numeric_tokens'), validator_version=VALIDATOR_VERSION,
                        retry_count=attempt.get('retry_count', 0), fallback_action=status, output_status=status,
                        output_path=str(output) if output else None, checkpoint_state=checkpoint,
                        fallback_error=fallback_error)
                    if self.options.mode == AGY_MODE:
                        from providers.agy_diagnostics import transport
                        record['agy_protocol'] = getattr(exc, 'agy_diagnostic', None) or transport(code)
                    self.api_diagnostic(record, exc, checkpoint, len(files)-index)
                    log_path = self.diagnostics.write(record)
                    # UI/checkpoints receive metadata only, never raw OCR/provider text.
                    review = {k: record[k] for k in ('job_id', 'chapter_id', 'image_index', 'image_filename', 'image_path',
                        'stage', 'error_code', 'exception_type', 'error_message', 'provider', 'mode',
                        'output_status', 'output_path', 'checkpoint_state', 'fallback_error')}
                    review.update(diagnostic_path=log_path, diagnostic_error=self.diagnostics.error)
                    self.review_pages.append(review)
                    self.cache.checkpoint(self.job_id, str(path), checkpoint, str(output) if output else '',
                                          fingerprint, json.dumps(review, ensure_ascii=False))
                    self.resume_store.page(self.journal, path, state=checkpoint)
                    action = 'đã xuất ảnh gốc dự phòng' if output else 'chưa có output hợp lệ'
                    message = f'Trang {image_indices[str(path)]} • {path.name} • {error_stage} • {code} • {action}. {detail}'
                    self.event(path, 'Ảnh gốc dự phòng' if output else 'Lỗi', 100, index+1, len(files),
                               output=str(output) if output else None, detail=message, review=review,
                               output_status=status, image_index=image_indices[str(path)], diagnostic_path=log_path)
            if state != 'paused_provider':
                state = ('completed_with_warnings' if self.fallback_count == len(errors) else 'errors') if errors else 'done'
        except CancelledError:
            state = 'cancelled'
        except Exception as exc:
            LOGGER.exception('Batch initialization failed: %s', type(exc).__name__)
            self.emit({'type': 'fatal', 'detail': str(exc) or type(exc).__name__})
            state = 'error'
        finally:
            if self.journal:
                if not pending_paths:
                    pending_paths = [p['path'] for p in self.journal['pages'] if p['state'] != 'done']
                self.journal['state'] = 'done' if not pending_paths else state
                self.resume_store.save(self.journal)
            if self.job_id:
                self.cache.job(self.job_id, self.options, state)
            self.service.close()
            result = {'type': 'finished', 'state': state, 'errors': errors, **self.counts, 'total': len(files),
                      'translated_success': self.counts['completed'] + self.counts['skipped'],
                      'partial_translation': 0, 'fallback_original': self.fallback_count,
                      'failed_no_output': self.counts['failed'] - self.fallback_count,
                      'files_exported': self.counts['completed'] + self.counts['skipped'] + self.fallback_count,
                      'needs_retry': errors, 'review_pages': self.review_pages, 'job_id': self.job_id,
                      'pending_paths': pending_paths,
                      'resume_id': self.resume_id,
                      'diagnostic_dir': str(self.diagnostics.directory) if self.diagnostics else None}
            self.emit(result)
            if self.owns_cache:
                self.cache.close()
        return result
