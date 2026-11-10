"""Bounded local error records. Never perform network I/O or retain credentials."""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from core.paths import ROOT

VALIDATOR_VERSION = 'literal-numbers-v2-signed'
TRANSLATED_SUCCESS = 'TRANSLATED_SUCCESS'
PARTIAL_TRANSLATION = 'PARTIAL_TRANSLATION'
FALLBACK_ORIGINAL = 'FALLBACK_ORIGINAL'
FAILED_NO_OUTPUT = 'FAILED_NO_OUTPUT'


def safe_text(value, limit: int = 2048) -> str:
    text = str(value or '')[:limit * 2]
    text = re.sub(r'https?://[^\s<>"\']+', '[URL ẩn]', text, flags=re.I)
    text = re.sub(r'(?i)\b(?:api[_-]?key|authorization|cookie|token|password|secret|sign)\s*[:=]\s*[^\s,;]+',
                  '[thông tin xác thực ẩn]', text)
    return text[:limit]


class DiagnosticLog:
    """Append one bounded JSON line, fsync it; preserve a torn tail in its old file.

    Capture text only on errors. Disabling text capture still retains error codes,
    context and counts, but removes source/target and numeric tokens.
    """
    _lock = threading.Lock()

    def __init__(self, job_id: str, capture_text: bool = True, root: Path | None = None,
                 max_bytes: int = 4_000_000, max_records: int = 1000):
        if not re.fullmatch(r'[a-f0-9]{64}', job_id):
            raise ValueError('Invalid diagnostic job ID')
        self.directory = (root or ROOT / 'logs' / 'diagnostics') / job_id
        self.capture_text = capture_text
        self.max_bytes, self.max_records = max_bytes, max_records
        self.path = self.directory / 'errors.jsonl'
        self.error = ''

    def write(self, record: dict) -> str | None:
        try:
            with self._lock:
                self.directory.mkdir(parents=True, exist_ok=True)
                if self.directory.is_symlink() or self.path.is_symlink():
                    raise OSError('Diagnostic path cannot be a symlink')
                files = list(self.directory.glob('errors*.jsonl'))
                if sum(p.stat().st_size for p in files) >= self.max_bytes:
                    raise OSError('Diagnostic byte limit reached')
                count = 0
                for p in files:
                    with p.open('rb') as f:
                        count += sum(1 for _ in f)
                if count >= self.max_records:
                    raise OSError('Diagnostic record limit reached')
                if self.path.exists() and self.path.stat().st_size:
                    with self.path.open('rb') as f:
                        f.seek(-1, 2)
                        if f.read(1) != b'\n':
                            self.path = self.directory / ('errors-' + uuid4().hex + '.jsonl')
                data = dict(record, timestamp=datetime.now(timezone.utc).isoformat())
                if 'agy_protocol' in data:
                    from providers.agy_diagnostics import sanitize
                    data['agy_protocol'] = sanitize(data['agy_protocol'])
                    # Protocol diagnostics never retain OCR/target/path/exception payload,
                    # regardless of the legacy sensitive-text diagnostic preference.
                    for key in ('ocr_source_text', 'raw_translated_target', 'source_numeric_tokens',
                                'target_numeric_tokens', 'image_path', 'output_path'):
                        data[key] = None
                    data['error_message'] = 'AGY diagnostic: see error_code and agy_protocol.'
                if 'gemini_api_request' in data:
                    from providers.gemini_diagnostics import clean
                    data['gemini_api_request'] = clean(data['gemini_api_request'])
                    allowed = {'timestamp', 'job_id', 'chapter_id', 'image_index', 'stage', 'error_code',
                        'exception_type', 'checkpoint_state', 'fallback_action', 'mode', 'provider',
                        'model_identity', 'validator_version', 'retry_count', 'gemini_api_request'}
                    data = {k:v for k,v in data.items() if k in allowed}
                    data['error_message'] = 'Gemini API diagnostic: see error_code and gemini_api_request.'
                truncated = []
                for key, value in list(data.items()):
                    if isinstance(value, str):
                        if len(value) > 2048:
                            truncated.append(key)
                        data[key] = safe_text(value)
                    elif isinstance(value, list):
                        if len(value) > 100 or any(len(str(v)) > 80 for v in value):
                            truncated.append(key)
                        data[key] = [safe_text(v, 80) for v in value[:100]]
                data['truncated_fields'] = truncated
                if not self.capture_text:
                    for key in ('ocr_source_text', 'raw_translated_target', 'source_numeric_tokens', 'target_numeric_tokens'):
                        data[key] = None
                data['text_capture_enabled'] = self.capture_text
                line = (json.dumps(data, ensure_ascii=False) + '\n').encode('utf-8')
                if len(line) + sum(p.stat().st_size for p in self.directory.glob('errors*.jsonl')) > self.max_bytes:
                    raise OSError('Diagnostic byte limit reached')
                with self.path.open('ab') as f:
                    f.write(line)
                    f.flush()
                    os.fsync(f.fileno())
                self.error = ''
                return str(self.path)
        except (OSError, ValueError, TypeError) as exc:
            self.error = safe_text(exc)
            return None
