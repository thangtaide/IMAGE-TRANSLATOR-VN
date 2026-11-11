"""Experimental chapter transaction. AGY generation requires explicit manifest consent.

Only metadata/text is held chapter-wide. Bitmaps are opened sequentially by the
existing OCR/render pipeline. Artifacts and SQLite must live in a stage3f QA run.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, replace
from pathlib import Path

from core.diagnostics import VALIDATOR_VERSION
from core.paths import ROOT
from core.pipeline import JobControl, ProcessingManager, TranslationService, scan_images
from core.storage import TranslationCache, digest, file_digest
from core.types import CancelledError, MissingModelError, Options
from providers.offline import ArgosTranslationProvider

VERSION = 'whole-chapter-local-v1'
_active = threading.Lock()
MAX_PAGES, MAX_REGIONS, MAX_CHARACTERS, MAX_JSON = 500, 10000, 1000000, 16000000


class ChapterError(ValueError):
    pass


def read_json(path):
    if path.is_symlink() or path.stat().st_size > MAX_JSON:
        raise ChapterError('WHOLE_ARTIFACT_INVALID')
    try:
        return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_keys)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ChapterError('WHOLE_JSON_INVALID') from None


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ChapterError('WHOLE_DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def seal(data):
    return dict(data, content_hash=digest(data))


def verify(data):
    if not isinstance(data, dict) or data.get('content_hash') != digest({k: v for k, v in data.items() if k != 'content_hash'}):
        raise ChapterError('WHOLE_ARTIFACT_CHANGED')
    return data


def assemble_manifest(chapter, pages, records, ocr_identity):
    """records may finish out of order; page slots always come from the input list."""
    if not 1 <= len(pages) <= MAX_PAGES or len(records) != len(pages):
        raise ChapterError('WHOLE_MANIFEST_INCOMPLETE')
    ordered, ids, characters = [], set(), 0
    for index, source in enumerate(pages, 1):
        row = records.get(source['id'])
        if not isinstance(row, dict) or row.get('page') != source or row['page']['index'] != index:
            raise ChapterError('WHOLE_MANIFEST_PAGE_MISMATCH')
        for slot, region in enumerate(row['regions']):
            expected = source['id'] + '_r' + str(slot).zfill(5)
            if region['id'] != expected or region['id'] in ids or region['region_index'] != slot:
                raise ChapterError('WHOLE_MANIFEST_REGION_MISMATCH')
            ids.add(region['id'])
            characters += len(region['ocr']['text'])
        ordered.append(row)
    if len(ids) > MAX_REGIONS or characters > MAX_CHARACTERS:
        raise ChapterError('WHOLE_MANIFEST_LIMIT')
    return seal(dict(schema_version=1, recipe=VERSION, chapter_id=chapter,
                     ocr_identity=ocr_identity, pages=ordered, region_count=len(ids),
                     source_characters=characters))


def parse_response(response, manifest, expected_ids):
    """Manual mock contract, not a claim about a real AGY protocol."""
    if not isinstance(response, (str, bytes)) or len(response.encode('utf-8') if isinstance(response, str) else response) > MAX_JSON:
        raise ChapterError('WHOLE_RESPONSE_LIMIT')
    try:
        data = json.loads(response, object_pairs_hook=unique_keys)
    except (ValueError, UnicodeError, RecursionError):
        raise ChapterError('WHOLE_JSON_INVALID') from None
    if not isinstance(data, dict) or set(data) != {'manifest_hash', 'translations'}:
        raise ChapterError('WHOLE_RESPONSE_SCHEMA')
    if data['manifest_hash'] != manifest['content_hash']:
        raise ChapterError('WHOLE_MANIFEST_CHANGED')
    rows = data['translations']
    if not isinstance(rows, list) or len(rows) != len(expected_ids):
        raise ChapterError('WHOLE_RESPONSE_IDS')
    result = {}
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'id', 'text'} or not isinstance(row['id'], str)
                or row['id'] not in expected_ids or row['id'] in result
                or not isinstance(row['text'], str) or not row['text'].strip() or len(row['text']) > 12000):
            raise ChapterError('WHOLE_RESPONSE_IDS_OR_TEXT')
        result[row['id']] = row['text']
    return result


class _NoTranslationCache:
    """Use the unchanged guard without accepting a cached target instead of raw_target."""
    def get(self, *args): return None
    def put(self, *args): pass


class _GuardIdentity:
    online = False
    engine_name = 'Whole chapter validation'
    def __init__(self, identity): self.identity = identity
    def translate(self, *args): raise ChapterError('WHOLE_UNEXPECTED_TRANSLATION')


class MockWholeChapterTranslator:
    """Explicit test-only response factory. Never invokes AGY or credentials."""
    def __init__(self, response_factory, identity='manual-mock-v1'):
        self.response_factory = response_factory
        self.identity = VERSION + ':mock:' + identity
        self.provider = _GuardIdentity(self.identity)
        self.calls = 0


class ArgosWholeChapterTranslator:
    """One chapter interface, sequential local inference per region, NOT one AGY request."""
    def __init__(self):
        self.provider = ArgosTranslationProvider()

    @property
    def identity(self): return VERSION + ':' + self.provider.identity


class AGYWholeChapterTranslator:
    """Reuse AGY transport/guard with one generation and no CLI capability probes."""
    def __init__(self, options, timeout=600):
        from providers.agy import find_agy, WHOLE_PROMPT_VERSION, SESSION_SETTINGS
        if type(timeout) is not int or not 10 <= timeout <= 1800:
            raise ChapterError('WHOLE_TIMEOUT_CONFIG')
        self.path = find_agy(options.agy_executable)  # File lookup/hash only; never runs the executable.
        self.binary_hash = file_digest(self.path)
        self.model, self.timeout = options.agy_model, timeout
        from providers.agy_models import selection
        try:_,self.effort=selection(self.model,options.agy_effort)
        except ValueError as exc:raise ChapterError('AGY_MODEL') from exc
        self.identity = 'whole-agy-v1:' + digest([self.binary_hash, self.model,
            WHOLE_PROMPT_VERSION, SESSION_SETTINGS, VALIDATOR_VERSION, 'region_id-translated_text-v1'])
        self.provider = _GuardIdentity(self.identity)
        self.provider.engine_name = 'AGY Gemini whole chapter'
        self.provider.online = True  # Diagnostic identity only; generation goes through translate_manifest.
        self.descriptor = dict(kind='agy', executable=str(self.path), model=self.model, effort=self.effort or '',timeout=timeout)
        self.error_context = {}
        self.last_capture = None

    def translate_manifest(self, manifest, request, workspace, control):
        from providers.agy import AGYProvider
        protected = {row['id']: row['text'] for row in request}
        pages = [dict(page_id=p['page']['id'], page_index=p['page']['index'], regions=[
            dict(region_id=r['id'], reading_order=r['ocr']['reading_order'],
                 original_ocr_text=r['ocr']['text'], text=protected[r['id']],
                 source_language=r['ocr']['language']) for r in p['regions']]) for p in manifest['pages']]
        packet = dict(schema_version=1, chapter_id=manifest['chapter_id'],
                      manifest_hash=manifest['content_hash'], pages=pages)
        provider = AGYProvider(str(self.path), model=self.model, timeout=min(300, self.timeout),
            effort=self.effort or '',
            max_requests=1, checkpoint=control.checkpoint, cancelled=lambda:control.cancelled,
            root=workspace/'agy', probe_cli=False, error_context=self.error_context)
        try:
            if provider.binary_hash != self.binary_hash:
                raise ChapterError('WHOLE_AGY_BINARY_CHANGED')
            targets = provider.translate_whole_chapter(packet, timeout=self.timeout)
            # Binding is from this one invocation's immutable input, not guessed from free text.
            return dict(manifest_hash=manifest['content_hash'], translations=[
                dict(id=r['id'], text=target) for r, target in zip(request, targets)])
        except Exception as exc:
            if not getattr(exc,'agy_error_attempt_id',None):
                provider.record_failure(exc, 'APP_PREFLIGHT' if provider.last_capture.started is False else 'VALIDATION')
            raise
        finally:
            self.last_capture = provider.last_capture
            provider.last_capture = None  # Whole guard still needs bytes until validation ends.
            provider.close()


class PreparedChapter:
    def __init__(self, owner, manifest, accepted):
        self.owner, self.manifest, self.accepted = owner, manifest, accepted
        self.identity = digest([VERSION, manifest['content_hash'], accepted['content_hash']])
        self.pages = {str((owner.source / p['page']['relative']).resolve()): p for p in manifest['pages']}

    def for_page(self, path, regions):
        self.owner.check_manifest(self.manifest)
        current = verify(read_json(self.owner.accepted_path))
        if current['content_hash'] != self.accepted['content_hash']:
            raise ChapterError('WHOLE_TRANSLATION_RECEIPT_CHANGED')
        page = self.pages[str(path)]
        if file_digest(path) != page['page']['source_hash']:
            raise ChapterError('WHOLE_SOURCE_CHANGED')
        if [asdict(r) for r in regions] != [r['ocr'] for r in page['regions']]:
            raise ChapterError('WHOLE_OCR_CHANGED')
        return [self.accepted['regions'][r['id']]['target'] for r in page['regions']]


class WholeChapterJob:
    """Explicit QA workspace, durable OCR/translation receipts, existing render receipts.

    run(allow_translation=False) never starts/replays MT. The caller must explicitly
    consent on every start/resume needing more translation. No startup auto-resume.
    """
    def __init__(self, source, workspace, *, options=None, chapter_id=None, translator=None,
                 ocr=None, control=None, emit=lambda _: None, input_paths=None):
        self.source, self.workspace = Path(source).resolve(), Path(workspace).resolve()
        try:
            relative = self.workspace.relative_to((ROOT / 'output').resolve())
        except ValueError:
            raise ChapterError('WHOLE_QA_WORKSPACE_REQUIRED') from None
        if not relative.parts or not relative.parts[0].startswith(('stage3f-', 'stage3g-')):
            raise ChapterError('WHOLE_QA_WORKSPACE_REQUIRED')
        if self.source == self.workspace or self.source.is_relative_to(self.workspace):
            raise ChapterError('WHOLE_SOURCE_OUTPUT_OVERLAP')
        self.options = replace(options or Options(), source=str(self.source),
            output=str(self.workspace / 'rendered'), mode='Offline', offline_provider='Argos',
            allow_online_fallback=False, recursive=True)
        self.translator = translator or ArgosWholeChapterTranslator()
        if not isinstance(self.translator, (ArgosWholeChapterTranslator, MockWholeChapterTranslator, AGYWholeChapterTranslator)):
            raise ChapterError('WHOLE_LOCAL_TRANSLATOR_REQUIRED')
        if isinstance(self.translator, AGYWholeChapterTranslator) and not relative.parts[0].startswith('stage3g-'):
            raise ChapterError('WHOLE_AGY_NEW_WORKSPACE_REQUIRED')
        self.chapter_id = str(chapter_id or digest(str(self.source)))
        self.input_paths = None if input_paths is None else tuple(Path(p).resolve() for p in input_paths)
        if self.input_paths is not None and (len(set(self.input_paths)) != len(self.input_paths)
                or any(not p.is_relative_to(self.source) for p in self.input_paths)):
            raise ChapterError('WHOLE_INPUT_CHANGED')
        self.ocr, self.control, self.emit = ocr, control or JobControl(), emit
        self.workspace.mkdir(parents=True, exist_ok=True)
        if any(p.is_symlink() for p in self.workspace.rglob('*')):
            raise ChapterError('WHOLE_QA_SYMLINK_FORBIDDEN')
        self.path = self.workspace / 'chapter-journal.json'
        self.manifest_path = self.workspace / 'chapter-ocr-manifest.json'
        self.accepted_path = self.workspace / 'validated-translations.json'
        if self.path.exists() and isinstance(self.translator,AGYWholeChapterTranslator):
            saved=verify(read_json(self.path))
            descriptor=saved.get('translator',{})
            if descriptor.get('kind')=='agy':
                pinned=(descriptor['model'],descriptor.get('effort',''))
                if (self.options.agy_model,self.options.agy_effort)!=pinned:
                    self.options=replace(self.options,agy_model=pinned[0],agy_effort=pinned[1],
                        agy_executable=descriptor['executable'])
                    self.translator=AGYWholeChapterTranslator(self.options,descriptor['timeout'])
        self.record = None
        self.validated_regions = 0

    def save(self):
        from sources.cache import atomic_json
        atomic_json(self.path, seal(self.record))

    def progress(self, phase, completed, total):
        self.control.checkpoint()
        self.emit(dict(type='whole_progress', phase=phase, completed=completed, total=total,
                       percent=int(100 * completed / max(1, total))))
        self.control.checkpoint()

    def check_manifest(self, manifest, *, sources=False):
        if verify(read_json(self.manifest_path))['content_hash'] != manifest['content_hash']:
            raise ChapterError('WHOLE_MANIFEST_CHANGED')
        if sources:
            for page in manifest['pages']:
                if file_digest(self.source / page['page']['relative']) != page['page']['source_hash']:
                    raise ChapterError('WHOLE_SOURCE_CHANGED')

    def _run(self, allow_translation):
        from core.resume import work_recipe
        from sources.cache import atomic_json, inspect_image
        files = list(self.input_paths) if self.input_paths is not None else scan_images(self.source, True, self.workspace)
        if not 1 <= len(files) <= MAX_PAGES:
            raise ChapterError('WHOLE_PAGE_LIMIT')
        pages = [dict(index=n, relative=str(p.relative_to(self.source)), source_hash=file_digest(p),
                      id='p' + str(n).zfill(6) + '_' + digest([str(p.relative_to(self.source)), file_digest(p)])[:16])
                 for n, p in enumerate(files, 1)]
        cache = TranslationCache(self.workspace / 'qa.sqlite3')
        control, adapter = self.control, self.translator
        service = TranslationService(self.options, cache, control, offline=adapter.provider)
        manager = ProcessingManager(self.options, cache=cache, control=control, ocr=self.ocr,
            service=service, diagnostic_root=self.workspace / 'diagnostics')
        try:
            ocr_identity = manager.ocr.identity(self.options.language)
            recipe = digest([VERSION, work_recipe(self.options), ocr_identity, adapter.identity])
            if self.path.exists():
                saved = verify(read_json(self.path))
                saved.pop('content_hash')
                if (saved.get('version') != 1 or saved['recipe'] != recipe
                        or saved['chapter_id'] != self.chapter_id or saved['pages'] != pages):
                    raise ChapterError('WHOLE_RECIPE_OR_SOURCE_CHANGED')
                self.record = saved
            else:
                if self.manifest_path.exists() or self.accepted_path.exists():
                    raise ChapterError('WHOLE_ORPHAN_ARTIFACT')
                self.record = dict(version=1, chapter_id=self.chapter_id, recipe=recipe, pages=pages,
                    source=str(self.source), options=self.options.to_dict(),
                    translator=getattr(adapter, 'descriptor', dict(kind='argos')),
                    explicit_paths=self.input_paths is not None,
                    ocr={}, state='ocr', render_resume_id=None, accepted_hash=None)
                self.save()
            self.progress('OCR', len(self.record['ocr']), len(pages))
            records = {}
            for page, path in zip(pages, files):
                control.checkpoint()
                record_path = self.workspace / ('ocr-' + page['id'] + '.json')
                if page['id'] in self.record['ocr']:
                    if file_digest(record_path) != self.record['ocr'][page['id']]:
                        raise ChapterError('WHOLE_OCR_RECEIPT_CHANGED')
                    row = verify(read_json(record_path)); row.pop('content_hash')
                else:
                    info = inspect_image(path)  # bitmap validation, one page at a time
                    regions, warnings, preserved, overrides = manager.load_ocr_page(path, page['source_hash'], ocr_identity)
                    if file_digest(path) != page['source_hash']:
                        raise ChapterError('WHOLE_SOURCE_CHANGED')
                    key = digest([page['source_hash'], ocr_identity, self.options.language, self.options.confidence,
                                  self.options.tile_size, self.options.reading_direction])
                    raw = cache.get('ocr', key)
                    row = dict(page=page, size=[info['width'], info['height']], raw_ocr=raw,
                        regions=[dict(id=page['id'] + '_r' + str(n).zfill(5), region_index=n, ocr=asdict(r))
                                 for n, r in enumerate(regions)], preserved_regions=[asdict(r) for r in preserved],
                        overrides=overrides, warnings=warnings)
                    atomic_json(record_path, seal(row))
                    self.record['ocr'][page['id']] = file_digest(record_path)
                    self.save()
                records[page['id']] = row
                self.progress('OCR', len(records), len(pages))
            manifest = assemble_manifest(self.chapter_id, pages, records, ocr_identity)
            if self.manifest_path.exists():
                if verify(read_json(self.manifest_path)) != manifest:
                    raise ChapterError('WHOLE_MANIFEST_CHANGED')
            else:
                atomic_json(self.manifest_path, manifest)
            self.check_manifest(manifest, sources=True)
            self.emit(dict(type='whole_manifest_ready', pages=len(pages), regions=manifest['region_count'],
                source_characters=manifest['source_characters'], manifest_hash=manifest['content_hash'],
                agy_attempt_used=bool(self.record.get('agy_attempt_used'))))
            guard = TranslationService(self.options, _NoTranslationCache(), control, offline=adapter.provider)
            flat = [r for p in manifest['pages'] for r in p['regions']]
            namespace = digest([VERSION, manifest['content_hash'], adapter.identity, VALIDATOR_VERSION, self.options.glossary])
            progress_path = self.workspace / 'translation-progress.json'
            accepted = None
            if self.accepted_path.exists():
                accepted = verify(read_json(self.accepted_path))
                if (self.record['accepted_hash'] not in (None, accepted['content_hash'])
                        or accepted.get('namespace') != namespace
                        or accepted.get('manifest_hash') != manifest['content_hash']
                        or accepted.get('validator') != VALIDATOR_VERSION):
                    raise ChapterError('WHOLE_TRANSLATION_RECEIPT_CHANGED')
                values = dict(accepted['regions'])
            elif progress_path.exists():
                old = verify(read_json(progress_path))
                if old['namespace'] != namespace:
                    raise ChapterError('WHOLE_TRANSLATION_RECIPE_CHANGED')
                values = dict(old['regions'])
            else:
                values = {}
            ids = {r['id'] for r in flat}
            if not set(values).issubset(ids):
                raise ChapterError('WHOLE_TRANSLATION_IDS')
            if accepted is not None and set(values) != ids:
                raise ChapterError('WHOLE_TRANSLATION_INCOMPLETE')
            def validate(region, raw):
                return guard._translate_using(adapter.provider, region['ocr']['text'],
                    region['ocr']['language'], namespace + region['id'], raw_target=raw)
            for region in flat:
                if region['id'] in values and validate(region, values[region['id']]['raw']) != values[region['id']]['target']:
                    raise ChapterError('WHOLE_TRANSLATION_CHANGED')
                if region['id'] in values:
                    self.validated_regions += 1
            pending = [r for r in flat if r['id'] not in values]
            is_agy = isinstance(adapter, AGYWholeChapterTranslator)
            agy_response_path = self.workspace/'agy-response.json'
            saved_response = None
            if is_agy and agy_response_path.exists():
                raw_receipt = verify(read_json(agy_response_path))
                if (not self.record.get('agy_attempt_used') or raw_receipt.get('namespace') != namespace
                        or self.record.get('agy_response_hash') not in (None, raw_receipt['content_hash'])):
                    raise ChapterError('WHOLE_AGY_RESPONSE_CHANGED')
                saved_response = parse_response(json.dumps(raw_receipt['response'], ensure_ascii=False), manifest, ids)
                self.record['agy_response_hash'] = raw_receipt['content_hash']; self.save()
            self.record['state'] = 'translation'; self.save()
            self.progress('TRANSLATION', len(values), len(flat))
            if pending and is_agy and saved_response is None and self.record.get('agy_attempt_used'):
                raise ChapterError('WHOLE_AGY_ATTEMPT_ALREADY_USED')
            if pending and not allow_translation and saved_response is None:
                self.record['state'] = 'awaiting_translation'; self.save()
                return dict(state='awaiting_translation', pages=len(pages), regions=len(flat), pending_regions=len(pending),
                            source_characters=manifest['source_characters'], manifest_hash=manifest['content_hash'])
            def accept(region, raw):
                control.checkpoint()
                target = validate(region, raw)
                self.check_manifest(manifest)
                values[region['id']] = dict(raw=raw, target=target)
                self.validated_regions = len(values)
                atomic_json(progress_path, seal(dict(namespace=namespace, regions=values)))
                self.progress('TRANSLATION', len(values), len(flat))
            if pending:
                request = []
                for r in pending:
                    deferred = []
                    guard._translate_using(adapter.provider, r['ocr']['text'], r['ocr']['language'], namespace, deferred=deferred)
                    request.append(dict(id=r['id'], text=deferred[0][0], language=r['ocr']['language']))
                if is_agy:
                    if saved_response is None:
                        if self.confirmed_manifest_hash != manifest['content_hash']:
                            raise ChapterError('WHOLE_AGY_CONFIRMATION_REQUIRED')
                        if len(pending) != len(flat):
                            raise ChapterError('WHOLE_AGY_RESPONSE_MISSING')
                        self.check_manifest(manifest, sources=True)
                        from providers.agy import check_automatic_extensions
                        from core.agy_error_evidence import AGYErrorCapture
                        adapter.error_context = dict(job_id=digest(self.workspace.name), chapter_id=self.chapter_id,
                            batch_id=manifest['content_hash'], final_job_state='blocked', configured_timeout=adapter.timeout,
                            preflight_step='AUTOMATIC_EXTENSIONS')
                        # Pure local preflight after consent; never reset a historical budget.
                        try:
                            check_automatic_extensions()
                        except Exception as exc:
                            capture = AGYErrorCapture(adapter.model, adapter.timeout, adapter.error_context)
                            capture.failure(exc, 'APP_PREFLIGHT'); exc._agy_capture = capture
                            raise
                        # Commit before process creation. Crash/timeout still consumes this journal's attempt.
                        self.record.update(agy_attempt_used=True, agy_manifest_hash=manifest['content_hash'])
                        self.save()
                        self.emit(dict(type='whole_agy_running', stage='AGY đang xử lý toàn chương — một invocation'))
                        response = adapter.translate_manifest(manifest, request, self.workspace, control)
                        self.check_manifest(manifest, sources=True)
                        saved_response = parse_response(json.dumps(response, ensure_ascii=False), manifest, ids)
                        receipt = seal(dict(namespace=namespace, response=response))
                        atomic_json(agy_response_path, receipt)
                        self.record['agy_response_hash'] = receipt['content_hash']; self.save()
                    for r in pending:
                        accept(r, saved_response[r['id']])
                elif isinstance(adapter, MockWholeChapterTranslator):
                    adapter.calls += 1
                    response = adapter.response_factory(dict(manifest_hash=manifest['content_hash'], regions=request))
                    targets = parse_response(response, manifest, {r['id'] for r in pending})
                    for r in pending: accept(r, targets[r['id']])
                else:
                    for r, item in zip(pending, request):
                        control.checkpoint()
                        accept(r, adapter.provider.translate(item['text'], item['language']))
            self.check_manifest(manifest, sources=True)
            if set(values) != ids:
                raise ChapterError('WHOLE_TRANSLATION_INCOMPLETE')
            if accepted is None:
                accepted = seal(dict(version=1, namespace=namespace, manifest_hash=manifest['content_hash'],
                    validator=VALIDATOR_VERSION, regions=values))
                atomic_json(self.accepted_path, accepted)
            self.record['accepted_hash'] = accepted['content_hash']; self.save()
            self.record['state'] = 'render'; self.save()
            self.progress('RENDER', 0, len(pages))  # All translations are durable before this event.
            self.check_manifest(manifest, sources=True)
            plan = PreparedChapter(self, manifest, accepted)
            def event(data):
                if data.get('type') == 'resume_ready':
                    self.record['render_resume_id'] = data['resume_id']; self.save()
                self.emit(data)
            renderer = ProcessingManager(self.options, cache=cache, control=control, emit=event,
                ocr=manager.ocr, service=service, prepared_chapter=plan, chapter_id=self.chapter_id,
                diagnostic_root=self.workspace / 'diagnostics', resume_id=self.record['render_resume_id'])
            result = renderer.run([str(p) for p in files])
            self.check_manifest(manifest, sources=True)
            if verify(read_json(self.accepted_path))['content_hash'] != accepted['content_hash']:
                raise ChapterError('WHOLE_TRANSLATION_RECEIPT_CHANGED')
            self.record['state'] = result['state']; self.save()
            return dict(result, pages=len(pages), regions=len(flat), manifest_hash=manifest['content_hash'],
                        workspace=str(self.workspace))
        finally:
            service.close()
            cache.close()

    def run(self, *, allow_translation=False, confirmed_manifest_hash=None):
        if not _active.acquire(blocking=False):
            return dict(state='blocked', error_code='WHOLE_JOB_ACTIVE')
        self.confirmed_manifest_hash = confirmed_manifest_hash
        self.validated_regions = 0
        self.record = None
        started = time.monotonic()
        lock = None
        try:
            # OS lock is released on process death; restart needs no stale-lock deletion.
            lock = (self.workspace / '.whole-chapter.lock').open('a+b')
            if lock.tell() == 0:
                lock.write(b'0'); lock.flush()
            lock.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise ChapterError('WHOLE_JOB_ACTIVE') from None
            result = self._run(allow_translation)
        except Exception as exc:
            code = ('CANCELLED' if isinstance(exc, CancelledError) else
                    'MISSING_MODEL' if isinstance(exc, MissingModelError) else
                    getattr(exc, 'code', None) or (str(exc) if isinstance(exc, ChapterError) else type(exc).__name__))
            result = dict(state='cancelled' if isinstance(exc, CancelledError) else 'blocked', error_code=code)
            if isinstance(self.translator, AGYWholeChapterTranslator):
                from core.agy_error_evidence import error_reference
                capture = getattr(exc, '_agy_capture', None) or self.translator.last_capture
                if capture and (getattr(exc, '_agy_capture', None) is not None or code in
                        ('NUMERIC_MISMATCH','NumericMismatchError','WHOLE_RESPONSE_IDS','WHOLE_RESPONSE_IDS_OR_TEXT',
                         'WHOLE_JSON_INVALID','WHOLE_MANIFEST_CHANGED','WHOLE_TRANSLATION_CHANGED')):
                    capture.failure(exc, 'VALIDATION', validation_code=code)
                    capture.finish(result['state'])
                    result.update(error_reference(exc))
            if self.record:
                observed = getattr(exc, 'agy_diagnostic', None)
                if isinstance(self.translator, AGYWholeChapterTranslator) and isinstance(observed, dict):
                    from providers.agy_diagnostics import sanitize
                    self.record['agy_diagnostic'] = sanitize(observed)
                self.record.update(state=result['state'], error_code=code); self.save()
        finally:
            if lock is not None:
                lock.close()
            _active.release()
            if isinstance(self.translator, AGYWholeChapterTranslator) and self.translator.last_capture:
                self.translator.last_capture.stdout = self.translator.last_capture.stderr = b''
        result['elapsed_seconds'] = time.monotonic() - started
        result['validated_regions'] = self.validated_regions
        result['agy_attempt_used'] = bool(self.record and self.record.get('agy_attempt_used'))
        self.emit(dict(result, type='whole_finished'))
        return result
