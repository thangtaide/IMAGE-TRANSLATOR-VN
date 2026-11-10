"""Bounded sequential AGY planning; rendering remains in ProcessingManager."""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
import time
from core.storage import digest
from core.types import CancelledError
from providers.online import OnlineProviderError, ProviderSuspended
from providers.gemini_api import MODE as GEMINI_API_MODE

BATCH_VERSION = 'multipage-ids-context-v1'
AGY_MAX_PAGES = 24
AGY_MAX_CHARACTERS = 3000
AGY_MAX_REGIONS = 60
AGY_WAIT_SECONDS = (5, 10)


@dataclass(frozen=True)
class Item:
    id: str
    page: str
    region_index: int
    region: object


def pack_pages(pages, chars=3000, regions=60, *, max_pages=16, hard_chars=None):
    """Keep a fitting page whole; split oversized pages only at region boundaries."""
    if not 100 <= chars <= 12000 or not 1 <= regions <= 60:
        raise ValueError('AGY_BATCH_CONFIG: ký tự100–12000, vùng1–60')
    if not 1 <= max_pages <= AGY_MAX_PAGES:
        raise ValueError('AGY_BATCH_CONFIG: số trang không hợp lệ')
    batch, count, language, page_count = [], 0, None, 0
    for page in pages:
        if not page:
            continue
        size = sum(len(i.region.text) for i in page)
        languages = {i.region.language for i in page}
        if batch and (count + size > chars or len(batch) + len(page) > regions or
                      languages != {language} or page_count >= max_pages):
            yield batch
            batch, count, language, page_count = [], 0, None, 0
        page_count += 1
        for item in page:
            n = len(item.region.text)
            if hard_chars is not None and n > hard_chars:
                raise OnlineProviderError('INVALID_REQUEST', 'Một vùng OCR vượt giới hạn ký tự AGY batch; không cắt chữ hoặc gửi quá giới hạn.')
            if n > 6000:
                raise OnlineProviderError('INVALID_REQUEST', 'Một vùng OCR vượt6000ký tự; không cắt mất chữ.')
            if batch and (len(batch) >= regions or count + n > chars or item.region.language != language):
                yield batch
                batch, count, page_count = [], 0, 1
            batch.append(item)
            count += n
            language = item.region.language
    if batch:
        yield batch


class MultiPageAGY:
    def __init__(self, manager, files, relevant, ocr_identity, service_identity):
        self.manager, self.service = manager, manager.service
        self.files = files
        self.relevant, self.ocr_identity, self.service_identity = relevant, ocr_identity, service_identity
        self.expected, self.values, self.errors = {}, {}, {}
        self.is_api = manager.options.mode == GEMINI_API_MODE
        self.max_pages = 16 if self.is_api else AGY_MAX_PAGES
        self.batch_chars = manager.options.agy_batch_chars if self.is_api else min(manager.options.agy_batch_chars, AGY_MAX_CHARACTERS)
        self.batches = iter(pack_pages(self.pages(), self.batch_chars,
            manager.options.agy_batch_regions if self.is_api else min(manager.options.agy_batch_regions, AGY_MAX_REGIONS), max_pages=self.max_pages,
            hard_chars=None if self.is_api else AGY_MAX_CHARACTERS))
        self.provider = self.service._gemini_api() if self.is_api else self.service._agy()
        if self.is_api:
            self.provider.emit = manager.emit
        self.identity = digest([self.provider.identity, BATCH_VERSION, manager.options.glossary,
            manager.options.agy_batch_chars, manager.options.agy_batch_regions, manager.options.agy_context])
        journal = manager.journal
        self.context = journal.get('context', []) if journal.get('context_provider') == self.identity else []

    def pages(self):
        m = self.manager
        for page_index, path in enumerate(self.files, 1):
            page_index = m.page_indices[str(path)]
            m.control.checkpoint()
            key = str(path)
            if next(p for p in m.journal['pages'] if p['path'] == key)['state'] == 'done':
                continue
            if key in self.expected:
                continue
            try:
                if m.page_done(path, self.relevant, self.ocr_identity, self.service_identity):
                    continue
                source_hash = m.cache_source_hash(path)
                regions, _, _, _ = m.load_ocr_page(path, source_hash, self.ocr_identity)
                self.expected[key] = len(regions)
                m.resume_store.page(m.journal, path, ocr_ready=True)
                items = [Item(f'j{m.job_id[:12]}_c{digest(m.chapter_id)[:8]}_p{page_index:06d}'
                              f'_h{source_hash[:12]}_r{n:04d}_o{region.reading_order:04d}', key, n, region)
                         for n, region in enumerate(regions)]
                region_limit = 6000 if self.is_api else AGY_MAX_CHARACTERS
                if any(len(i.region.text) > region_limit for i in items):
                    raise OnlineProviderError('INVALID_REQUEST', f'Vùng OCR quá {region_limit} ký tự; cần xem lại trang, không cắt chữ.')
                yield items
            except CancelledError:
                raise
            except Exception as exc:
                self.errors[key] = (exc, {})

    def receipt_key(self, item):
        return digest([item.id, self.identity])

    def wait_before_next_invocation(self):
        """Worker-only, after validation; cache-only batches never enter this wait."""
        if self.is_api or not self.manager.control.agy_batch_completed:
            return
        minimum = getattr(self.provider, 'minimum_batch_interval_seconds', 0)
        if type(minimum) not in (int, float) or not math.isfinite(minimum) or minimum < 0:
            raise ProviderSuspended('RATE_LIMITED', 'Khoảng chờ tối thiểu của provider không xác minh được; dừng gửi.')
        deadline = time.monotonic() + max(random.uniform(*AGY_WAIT_SECONDS), minimum)
        last_shown = None
        while True:
            self.manager.control.checkpoint()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            shown = math.ceil(remaining)
            if shown != last_shown:
                self.manager.emit(dict(type='agy_batch_wait', stage='Đang chờ trước batch tiếp theo',
                                       remaining_seconds=shown))
                last_shown = shown
            # Cancel wakes this condition immediately; pause is handled by checkpoint.
            with self.manager.control.condition:
                if not self.manager.control.cancelled:
                    self.manager.control.condition.wait(min(.2, remaining))
        self.manager.control.checkpoint()

    def translate_batch(self, batch):
        m, service = self.manager, self.service
        context = digest([BATCH_VERSION, [(i.id, i.region.text) for i in batch], self.context])
        missing, protected = [], []
        for item in batch:
            old = m.journal['regions'].get(self.receipt_key(item))
            cache_context = old['context'] if old else context
            deferred = []
            target = service._translate_using(self.provider, item.region.text, item.region.language,
                                               cache_context, deferred=deferred)
            if target is not None and (not old or digest(target) == old['target_hash']):
                self.values[item.id] = target
            else:
                if not deferred:
                    raise ValueError('AGY_CACHE_INTEGRITY: bản dịch cache/receipt không khớp')
                missing.append(item)
                protected.append(deferred[0][0])
        if missing:
            self.wait_before_next_invocation()
            # Diagnostic identity only: does not enter recipe/cache/context decisions.
            batch_meta = dict(batch_id=digest([i.id for i in missing]),
                page_count=len({i.page for i in missing}), region_count=len(missing),
                source_characters=sum(len(i.region.text) for i in missing))
            if not self.is_api:
                context_meta = getattr(self.provider, 'error_context', None)
                if isinstance(context_meta, dict):
                    context_meta.update(job_id=m.job_id, chapter_id=m.chapter_id,
                        batch_id=batch_meta['batch_id'], final_job_state='paused_provider')
            def attach(exc, observed=None):
                if self.is_api:
                    from providers.gemini_diagnostics import clean
                    observed = getattr(exc, 'gemini_api_diagnostic', None) or getattr(self.provider, 'last_diagnostic', None)
                    info = dict(observed) if isinstance(observed, dict) else {}
                    info.update(batch_id=batch_meta['batch_id'])
                    exc.gemini_api_diagnostic = clean(info)
                    return  # REST responses never enter AGY NDJSON diagnostics.
                from providers.agy_diagnostics import sanitize, transport
                info = dict(observed or getattr(exc, 'agy_diagnostic', None) or
                            transport(getattr(exc, 'code', 'CANCELLED' if isinstance(exc, CancelledError) else 'OTHER_ERROR')))
                info.update(batch_meta, pending_preserved=True, retry=False, translation_cached=False)
                exc.agy_diagnostic = sanitize(info)
            m.emit({'type': 'gemini_api_batch' if self.is_api else 'agy_batch',
                    'stage': 'Gemini API batch nhiều trang' if self.is_api else 'AGY batch nhiều trang',
                    'pages': len({i.page for i in missing}), 'regions': len(missing),
                    'characters': sum(map(len, protected)), 'context_characters': len(str(self.context))})
            try:
                targets = self.provider.translate_batch(protected, missing[0].region.language,
                    item_ids=[i.id for i in missing], context=self.context if m.options.agy_context else [])
            except Exception as exc:
                if not self.is_api and hasattr(self.provider,'record_failure') and not getattr(exc,'agy_error_attempt_id',None):
                    self.provider.record_failure(exc, 'APP_PREFLIGHT' if self.provider.last_capture.started is False else 'UNKNOWN')
                attach(exc)
                raise
            if len(targets) != len(missing):
                error = ProviderSuspended('INVALID_RESPONSE', 'AGY không trả đủ vùng; không tự retry.')
                if not self.is_api and hasattr(self.provider,'record_failure'): self.provider.record_failure(error, 'VALIDATION')
                attach(error)
                raise error
            for item, target in zip(missing, targets):
                try:
                    valid = service._translate_using(self.provider, item.region.text,
                        item.region.language, context, raw_target=target)
                    self.values[item.id] = valid
                    m.journal['regions'][self.receipt_key(item)] = dict(context=context, target_hash=digest(valid))
                    m.resume_store.save(m.journal)  # Commit every validated region before rendering.
                except Exception as exc:
                    if not self.is_api and hasattr(self.provider,'record_failure'):
                        self.provider.error_context.pop('final_job_state', None)
                        self.provider.record_failure(exc, 'VALIDATION')
                    attach(exc, getattr(self.provider, 'last_diagnostic', None))
                    exc.region_index = item.region_index
                    self.errors[item.page] = (exc, dict(service.last_attempt))
        if m.options.agy_context:
            candidates = self.context + [dict(id=i.id, source=i.region.text, target=self.values[i.id])
                                        for i in batch if i.id in self.values]
            self.context = []
            seen = set()
            import json
            for entry in reversed(candidates):
                if entry.get('id') in seen:
                    continue
                seen.add(entry.get('id'))
                if len(self.context) >= 8:
                    break
                if len(json.dumps([entry] + self.context, ensure_ascii=False)) <= 1600:
                    self.context.insert(0, entry)
        else:
            self.context = []
        m.journal.update(context=self.context, context_provider=self.identity)
        m.resume_store.save(m.journal)
        if missing and not self.is_api:
            self.manager.control.agy_batch_completed = True

    def for_page(self, path, regions):
        key = str(path)
        while True:
            if key in self.errors:
                exc, attempt = self.errors[key]
                self.service.last_attempt = attempt
                raise exc
            if key in self.expected:
                ids = [i for i in self.values if self._page_id_match(i, key)]
                if len(ids) == self.expected[key]:
                    # ID insertion order may differ in responses; explicitly sort region slots.
                    return [self.values[i] for i in sorted(ids)]
            try:
                self.translate_batch(next(self.batches))
            except StopIteration:
                raise ValueError('AGY_PAGE_INCOMPLETE: thiếu bản dịch vùng; không render trang') from None

    def _page_id_match(self, identifier, key):
        index = self.manager.page_indices[key]
        return f'_p{index:06d}_' in identifier
