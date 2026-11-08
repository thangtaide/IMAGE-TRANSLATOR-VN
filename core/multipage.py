"""Bounded sequential AGY planning; rendering remains in ProcessingManager."""
from __future__ import annotations

from dataclasses import dataclass
from core.storage import digest
from core.types import CancelledError
from providers.online import OnlineProviderError, ProviderSuspended

BATCH_VERSION = 'multipage-ids-context-v1'


@dataclass(frozen=True)
class Item:
    id: str
    page: str
    region_index: int
    region: object


def pack_pages(pages, chars=3000, regions=60):
    """Keep a fitting page whole; split oversized pages only at region boundaries."""
    if not 100 <= chars <= 12000 or not 1 <= regions <= 60:
        raise ValueError('AGY_BATCH_CONFIG: ký tự100–12000, vùng1–60')
    batch, count, language, page_count = [], 0, None, 0
    for page in pages:
        if not page:
            continue
        size = sum(len(i.region.text) for i in page)
        languages = {i.region.language for i in page}
        if batch and (count + size > chars or len(batch) + len(page) > regions or
                      languages != {language} or page_count >= 16):
            yield batch
            batch, count, language, page_count = [], 0, None, 0
        page_count += 1
        for item in page:
            n = len(item.region.text)
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
        self.batches = iter(pack_pages(self.pages(), manager.options.agy_batch_chars,
                                      manager.options.agy_batch_regions))
        self.provider = self.service._agy()
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
                if any(len(i.region.text) > 6000 for i in items):
                    raise OnlineProviderError('INVALID_REQUEST', 'Vùng OCR quá6000ký tự; cần xem lại trang.')
                yield items
            except CancelledError:
                raise
            except Exception as exc:
                self.errors[key] = (exc, {})

    def receipt_key(self, item):
        return digest([item.id, self.identity])

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
            m.emit({'type': 'agy_batch', 'stage': 'AGY batch nhiều trang',
                    'pages': len({i.page for i in missing}), 'regions': len(missing),
                    'characters': sum(map(len, protected)), 'context_characters': len(str(self.context))})
            targets = self.provider.translate_batch(protected, missing[0].region.language,
                item_ids=[i.id for i in missing], context=self.context if m.options.agy_context else [])
            if len(targets) != len(missing):
                raise ProviderSuspended('INVALID_RESPONSE', 'AGY không trả đủ vùng; không tự retry.')
            for item, target in zip(missing, targets):
                try:
                    valid = service._translate_using(self.provider, item.region.text,
                        item.region.language, context, raw_target=target)
                    self.values[item.id] = valid
                    m.journal['regions'][self.receipt_key(item)] = dict(context=context, target_hash=digest(valid))
                    m.resume_store.save(m.journal)  # Commit every validated region before rendering.
                except Exception as exc:
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
