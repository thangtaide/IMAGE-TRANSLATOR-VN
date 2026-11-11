"""Error-only local evidence. Raw bytes stay in RAM until an error occurs.

Persist raw bytes only as Windows CurrentUser DPAPI ciphertext in a protected
directory. Never decrypt/upload here. No plaintext temporary files, no cleanup.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from contextlib import contextmanager

from core.paths import ROOT

STORE_LIMIT = 64_000_000
STDOUT_LIMIT, STDERR_LIMIT = 1_000_000, 64_000
_lock = threading.Lock()
SOURCES = {'APP_PREFLIGHT', 'CLI_START', 'CLI_TIMEOUT', 'CLI_EXIT', 'CLI_RESPONSE', 'PARSER', 'VALIDATION', 'UNKNOWN'}
ERROR_CODES = {'UNKNOWN','CANCELLED','AGY_MODEL','AGY_NOT_FOUND','AGY_CAPABILITY','AGY_AUTOMATIC_EXTENSIONS',
    'NETWORK_ERROR','RESPONSE_BLOCKED',
    'AGY_INITIALIZATION_ERROR','AGY_START_FAILED','INVALID_REQUEST','AUTH_REQUIRED','ACCESS_DENIED',
    'MODEL_UNAVAILABLE','QUOTA_EXCEEDED','RATE_LIMITED','TIMEOUT','INVALID_RESPONSE','EMPTY_RESPONSE',
    'CLI_EXIT_ERROR','AGY_PROCESS_CLEANUP','PROVIDER_UNAVAILABLE','REQUEST_LIMIT','WHOLE_COMMAND_LIMIT','WHOLE_PAYLOAD_LIMIT',
    'WHOLE_TIMEOUT_CONFIG','NUMERIC_MISMATCH','TRANSLATION_VALIDATION_ERROR','WHOLE_JSON_INVALID',
    'WHOLE_RESPONSE_IDS','WHOLE_RESPONSE_IDS_OR_TEXT','WHOLE_MANIFEST_CHANGED','WHOLE_TRANSLATION_CHANGED'}


def _token(value, default='UNKNOWN'):
    return value if isinstance(value, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}', value) else default


def _identifier(value):
    return value if isinstance(value, str) and re.fullmatch(r'[a-f0-9]{32,64}', value) else None


def _private_directory(path):
    if os.name != 'nt':
        path.mkdir(mode=0o700)
        return False  # No equivalent of CurrentUser DPAPI: metadata only.
    from ctypes import wintypes as w
    class SA(ctypes.Structure):
        _fields_ = [('length', w.DWORD), ('descriptor', w.LPVOID), ('inherit', w.BOOL)]
    adv, kernel = ctypes.windll.advapi32, ctypes.windll.kernel32
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [w.LPCWSTR, w.DWORD, ctypes.POINTER(w.LPVOID), ctypes.POINTER(w.DWORD)]
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = w.BOOL
    kernel.CreateDirectoryW.argtypes = [w.LPCWSTR, ctypes.POINTER(SA)]
    kernel.CreateDirectoryW.restype = w.BOOL
    kernel.LocalFree.argtypes = [w.LPVOID]; kernel.LocalFree.restype = w.LPVOID
    descriptor = w.LPVOID()
    # Protected DACL: SYSTEM and owner rights only. DPAPI further binds to user.
    if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            'D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;OW)', 1, ctypes.byref(descriptor), None):
        path.mkdir(); return False
    try:
        sa = SA(ctypes.sizeof(SA), descriptor, False)
        if not kernel.CreateDirectoryW(str(path), ctypes.byref(sa)):
            if path.exists(): raise OSError('AGY_EVIDENCE_DIRECTORY_COLLISION')
            path.mkdir(); return False  # Safe metadata only if the private DACL cannot be applied.
        return True
    finally:
        kernel.LocalFree(descriptor)


def _protect(data):
    from ctypes import wintypes as w
    class Blob(ctypes.Structure):
        _fields_ = [('size', w.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    storage = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(storage, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt, kernel = ctypes.windll.crypt32, ctypes.windll.kernel32
    crypt.CryptProtectData.argtypes = [ctypes.POINTER(Blob), w.LPCWSTR, ctypes.POINTER(Blob),
                                      w.LPVOID, w.LPVOID, w.DWORD, ctypes.POINTER(Blob)]
    crypt.CryptProtectData.restype = w.BOOL
    kernel.LocalFree.argtypes = [w.LPVOID]; kernel.LocalFree.restype = w.LPVOID
    if not crypt.CryptProtectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise OSError('AGY_EVIDENCE_DPAPI_FAILED')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(ctypes.cast(target.data, w.LPVOID))


def _write_new(path, data):
    with path.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


@contextmanager
def _budget_lock(root):
    """Nonblocking cross-process quota lock; never wait on GUI or delete old evidence."""
    root.mkdir(parents=True, exist_ok=True)
    path = root/'.budget.lock'
    if path.is_symlink() or path.exists() and getattr(path.lstat(),'st_file_attributes',0)&0x400:
        raise OSError('AGY_EVIDENCE_LOCK_UNSAFE')
    with path.open('a+b') as stream:
        if stream.tell()==0: stream.write(b'0'); stream.flush()
        stream.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try: yield
        finally:
            stream.seek(0)
            if os.name=='nt': msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(stream,fcntl.LOCK_UN)


class AGYErrorCapture:
    def __init__(self, model='', timeout=None, context=None, payload=None):
        self.attempt_id = uuid4().hex
        from providers.agy_models import MODEL_IDS
        self.model = model if isinstance(model,str) and model in MODEL_IDS else 'unknown'
        self.timeout, self.context = timeout, dict(context or {})
        self.payload_hash = hashlib.sha256(payload).hexdigest() if isinstance(payload, bytes) else None
        self.started_at = time.monotonic()
        self.started = False
        self.exit_code = None
        self.stdout = self.stderr = b''
        self.observed = (0, 0)
        self.elapsed = None
        self.partial = False
        self.path = None
        self.write_error = None

    def observe(self, stdout=b'', stderr=b'', *, started=True, exit_code=None, observed=None, partial=False, elapsed=None):
        self.started, self.exit_code = started, exit_code
        self.stdout, self.stderr = bytes(stdout[:STDOUT_LIMIT]), bytes(stderr[:STDERR_LIMIT])
        self.observed = observed or (len(stdout), len(stderr))
        self.partial, self.elapsed = partial, elapsed

    def failure(self, exc, source='UNKNOWN', *, validation_code=None, parser=None):
        """Never mask the original provider/validation error, including disk/ACL failure."""
        try:
            if not self.path and not self.write_error:
                self._save(exc, source, validation_code, parser)
        except Exception:
            self.write_error = 'AGY_EVIDENCE_WRITE_FAILED'
        exc.agy_error_attempt_id = self.attempt_id
        exc.agy_error_path = str(self.path) if self.path else None
        exc.agy_error_write_error = self.write_error
        if self.path or self.write_error:
            self.stdout = self.stderr = b''
        return exc

    def finish(self, state):
        try:
            if self.path and state in ('done','error','errors','paused_provider','blocked','cancelled','completed_with_warnings'):
                path = self.path/'outcome.json'
                if not path.exists():
                    _write_new(path, json.dumps(dict(final_job_state=state), separators=(',', ':')).encode())
        except Exception:
            self.write_error = 'AGY_EVIDENCE_OUTCOME_WRITE_FAILED'

    def _save(self, exc, source, validation_code, parser):
        root = ROOT/'logs/diagnostics/agy_errors'
        if any(p.is_symlink() or bool(getattr(p.lstat(), 'st_file_attributes', 0) & 0x400)
               for p in (root, *root.parents) if p.exists()):
            raise OSError('AGY_EVIDENCE_PATH_UNSAFE')
        with _lock, _budget_lock(root):
            files=[]
            for path in root.rglob('*'):
                files.append(path)
                if len(files)>12000: raise OSError('AGY_EVIDENCE_STORE_LIMIT')
            if any(p.is_symlink() or getattr(p.lstat(),'st_file_attributes',0)&0x400 for p in files):
                raise OSError('AGY_EVIDENCE_STORE_LIMIT')
            used = sum(p.stat().st_size for p in files if p.is_file())
            if used + 16384 > STORE_LIMIT:
                self.write_error = 'AGY_EVIDENCE_STORE_FULL'; return
            directory = root/self.attempt_id
            protected = _private_directory(directory)
            artifacts = []
            for name, value, count in (('stdout', self.stdout, self.observed[0]), ('stderr', self.stderr, self.observed[1])):
                if not value: continue  # Never manufacture a response artifact.
                row = dict(stream=name, captured_bytes=len(value), observed_bytes=count,
                           captured_sha256=hashlib.sha256(value).hexdigest(), partial=self.partial or count > len(value))
                if not protected:
                    row['not_saved'] = 'RAW_PROTECTION_UNAVAILABLE'
                else:
                    destination = directory/(name+'.raw.dpapi')
                    try:
                        encrypted = _protect(value)
                        if used + len(encrypted) + 16384 > STORE_LIMIT:
                            row['not_saved'] = 'STORE_LIMIT'
                        else:
                            filename = name+'.raw.dpapi'
                            _write_new(directory/filename, encrypted); used += len(encrypted)
                            row.update(file=filename, encrypted_bytes=len(encrypted), encrypted_sha256=hashlib.sha256(encrypted).hexdigest())
                    except Exception:
                        row['not_saved'] = 'RAW_PROTECTION_OR_WRITE_FAILED'
                        if destination.is_file(): used += destination.stat().st_size
                artifacts.append(row)
            context = self.context
            state = 'RESPONSE_BYTES_OBSERVED' if self.stdout else 'PROCESS_STARTED' if self.started else 'NOT_ATTEMPTED' if self.started is False else 'UNKNOWN'
            metadata = dict(version=1, timestamp=datetime.now(timezone.utc).isoformat(), attempt_id=self.attempt_id,
                provider='AGY', model=self.model,
                effort=context.get('agy_effort') if context.get('agy_effort') in ('low','medium','high','default') else None,
                error_code=getattr(exc,'code',None) if getattr(exc,'code',None) in ERROR_CODES else 'CANCELLED' if type(exc).__name__=='CancelledError' else 'UNKNOWN',
                error_source=source if source in SOURCES else 'UNKNOWN', error_category=source if source in SOURCES else 'UNKNOWN',
                job_id=_identifier(context.get('job_id')), chapter_id=_identifier(context.get('chapter_id')) or
                    (context.get('chapter_id') if isinstance(context.get('chapter_id'), str) and context['chapter_id'].isdigit() and len(context['chapter_id'])<=16 else None),
                batch_id=_identifier(context.get('batch_id')), process_started=self.started, exit_code=self.exit_code,
                process_state='NOT_STARTED' if self.started is False else 'EXIT_OBSERVED' if self.exit_code is not None else 'UNKNOWN',
                elapsed_seconds=round(self.elapsed if self.elapsed is not None else time.monotonic()-self.started_at, 3),
                configured_timeout=self.timeout if type(self.timeout) in (int,float) and math.isfinite(self.timeout) else None,
                watchdog_timeout_seconds=context.get('watchdog_timeout_seconds') if
                    type(context.get('watchdog_timeout_seconds')) in (int,float) and
                    math.isfinite(context['watchdog_timeout_seconds']) and 0 < context['watchdog_timeout_seconds'] <= 2000 else None,
                timeout_layer=getattr(exc, 'agy_timeout_layer', None) if
                    getattr(exc, 'agy_timeout_layer', None) in ('CLI_TOTAL','WRAPPER_TOTAL') else None,
                invocation_kind=context.get('invocation_kind') if context.get('invocation_kind') in ('HELP','VERSION','TRANSLATION') else 'PREFLIGHT',
                preflight_step=_token(context.get('preflight_step')) if source=='APP_PREFLIGHT' else None,
                observation_state=state, response_observed=bool(self.stdout),
                response_scope='CLI_OUTPUT_ONLY_NOT_BACKEND_CONFIRMATION',
                response_complete=False if self.partial else None,
                stdout_bytes=self.observed[0], stderr_bytes=self.observed[1], response_bytes=None,
                response_artifact='stdout.raw.dpapi' if self.stdout and any(a.get('file')=='stdout.raw.dpapi' for a in artifacts) else None,
                payload_sha256=self.payload_hash,
                parser_error_code=(parser or {}).get('parser_error_code') if (parser or {}).get('parser_error_code') in ERROR_CODES|{'NONE','OTHER_ERROR'} else 'UNKNOWN',
                parser_reason=(parser or {}).get('parser_reason') if (parser or {}).get('parser_reason') in
                    {'TOOL_INDICATOR','JSON_PARSE','INVALID_EVENT','RESULT_COUNT','AGENT_TURNS','RESPONSE_STRING','SCHEMA','COUNT','FIELDS','ITEM','MISSING_ID','NONE','TRANSPORT'} else 'UNKNOWN',
                validation_failure_code=validation_code if validation_code in ERROR_CODES else 'UNKNOWN' if validation_code else None,
                final_job_state='UNKNOWN', final_state_artifact='outcome.json',
                raw_policy='DPAPI_CURRENT_USER_REQUIRED', private_dacl_applied=protected,
                raw_protection='DPAPI_CURRENT_USER_AND_OWNER_SYSTEM_DACL' if any('file' in a for a in artifacts) else 'METADATA_ONLY', artifacts=artifacts,
                backend_received='UNKNOWN', retry=False)
            _write_new(directory/'metadata.json', (json.dumps(metadata,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8'))
            self.path = directory
            if any('not_saved' in row for row in artifacts):
                self.write_error = 'AGY_RAW_EVIDENCE_INCOMPLETE'


def error_reference(exc):
    return dict(agy_attempt_id=getattr(exc,'agy_error_attempt_id',None),
                agy_error_evidence=getattr(exc,'agy_error_path',None),
                agy_evidence_error=getattr(exc,'agy_error_write_error',None))
