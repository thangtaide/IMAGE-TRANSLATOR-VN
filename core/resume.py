"""Versioned local journals. No schema migration, inference or network on discovery."""
from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

from core.paths import CACHE
from core.storage import digest, file_digest
from core.types import Options

PROVIDER_FIELDS = {'mode', 'online_provider', 'offline_provider', 'allow_online_fallback',
    'endpoint', 'skip_success', 'diagnostic_text', 'agy_executable', 'agy_model',
    'agy_timeout', 'agy_max_requests', 'agy_batch_chars', 'agy_batch_regions', 'agy_context',
    'gemini_api_model', 'gemini_api_timeout', 'gemini_api_max_requests', 'gemini_api_free_tier_confirmed'}


def work_recipe(options: Options) -> str:
    from core.imaging import default_font
    data = {k: v for k, v in options.to_dict().items() if k not in PROVIDER_FIELDS}
    font = Path(options.font) if options.font else default_font()
    data['font_hash'] = file_digest(font) if font.is_file() else None
    if options.erase_mode == 'custom' and options.mask_path:
        data['mask_hash'] = file_digest(Path(options.mask_path))
    return digest(data)


class ResumeStore:
    def __init__(self, database: Path | None = None):
        db = Path(database or CACHE / 'state.sqlite3').resolve()
        self.root = db.parent / (db.stem + '-resume-v1')

    def read(self, identifier: str) -> dict:
        if not re.fullmatch(r'[a-f0-9]{32}', identifier):
            raise ValueError('RESUME_INVALID: ID journal không hợp lệ')
        path = self.root / (identifier + '.json')
        if path.stat().st_size > 16_000_000:
            raise ValueError('RESUME_INVALID: journal quá lớn')
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('version') != 1 or data.get('id') != identifier:
            raise ValueError('RESUME_INVALID: phiên bản/ID journal không khớp')
        return data

    def save(self, data: dict) -> None:
        from sources.cache import atomic_json
        if not re.fullmatch(r'[a-f0-9]{32}', data['id']):
            raise ValueError('RESUME_INVALID')
        self.root.mkdir(parents=True, exist_ok=True)
        data['updated'] = datetime.now(timezone.utc).isoformat()
        # Keep completed journals as provenance; never cleanup user data here.
        atomic_json(self.root / (data['id'] + '.json'), data)

    def create(self, kind: str, **data) -> dict:
        record = dict(version=1, id=uuid4().hex, kind=kind, state='running', **data)
        self.save(record)
        return record

    def latest(self, kind: str, predicate=None) -> dict | None:
        if not self.root.is_dir():
            return None
        # Startup reads bounded metadata only. Hash/decode verification is in worker.
        paths = sorted(self.root.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in paths[:200]:
            try:
                data = self.read(path.stem)
                if data['kind'] == kind and data['state'] != 'done' and (predicate is None or predicate(data)):
                    return data
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return None

    def pipeline(self, options: Options, paths: list[Path], cache, identifier=None,
                 chapter_id=None) -> dict:
        if not identifier:
            return self.create('chapter' if chapter_id else 'pipeline', options=options.to_dict(),
                recipe=work_recipe(options), pages=[dict(path=str(p), source_hash=file_digest(p),
                state='pending') for p in paths], regions={}, chapter_id=chapter_id)
        data = self.read(identifier)
        if data['recipe'] != work_recipe(options):
            raise ValueError('RESUME_RECIPE_CHANGED: khôi phục cấu hình OCR/render cũ trước khi tiếp tục')
        from sources.cache import inspect_image
        for page in data['pages']:
            source = Path(page['path'])
            if not source.is_relative_to(Path(options.source).resolve()) or file_digest(source) != page['source_hash']:
                raise ValueError('RESUME_SOURCE_CHANGED: ảnh nguồn không khớp hash')
            if page['state'] == 'publishing' and Path(page['output']).is_file():
                output = Path(page['output'])
                metadata = cache.get('metadata', page['fingerprint'])
                if (not output.resolve().is_relative_to(Path(options.output).resolve()) or
                        inspect_image(output)['sha256'] != page['output_hash'] or not metadata or
                        metadata.get('source') != page['path'] or metadata.get('output') != str(output)):
                    raise ValueError('RESUME_PUBLICATION_CHANGED: output đang publish không khớp intent')
                cache.put('output-hash', str(output), page['output_hash'])
                cache.checkpoint(page['job_id'], page['path'], 'done', str(output), page['fingerprint'],
                                 'Recovered verified atomic publication')
                page['state'] = 'done'
            if page['state'] == 'done':
                output = Path(page['output'])
                receipt = cache.item(page['job_id'], page['path'])
                if (not output.resolve().is_relative_to(Path(options.output).resolve()) or
                        inspect_image(output)['sha256'] != page['output_hash'] or
                        cache.get('output-hash', str(output)) != page['output_hash'] or
                        not receipt or receipt['status'] != 'done' or receipt['output'] != str(output) or
                        receipt['fingerprint'] != page['fingerprint']):
                    raise ValueError('RESUME_RECEIPT_CHANGED: output/checkpoint không hợp lệ; không ghi đè')
        self.save(data)
        return data

    def page(self, data, path, **values):
        page = next(p for p in data['pages'] if p['path'] == str(path))
        page.update(values)
        self.save(data)
