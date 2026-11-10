"""Managed, isolated reruns. Never remove databases, journals, outputs or credentials."""
from __future__ import annotations

from contextlib import contextmanager, closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
from uuid import uuid4

from core.paths import CACHE, ROOT
from sources.cache import atomic_json as _atomic_json
from core.types import Options


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    plain_path(path)
    _atomic_json(path, value)  # Exclusive UUID temp file; never follow a predictable .tmp symlink.


def plain_path(path):
    """Refuse symlinks/junctions at every existing component before managed writes."""
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError('CACHE_UNSAFE_PATH: đường dẫn liên kết không được quản lý')
        if part.is_file() and part.stat().st_nlink > 1:
            raise ValueError('CACHE_UNSAFE_PATH: không quản lý file có hardlink')
        if part.exists() and getattr(part.stat(), 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
            raise ValueError('CACHE_UNSAFE_PATH: junction/reparse point không được quản lý')
    return path


@contextmanager
def exclusive(path):
    """Cross-process lease shared by processing, backup and cleanup, not a DB delete."""
    path = plain_path(path)
    with path.open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError('CACHE_BUSY: lượt đang xử lý hoặc được ứng dụng khác sử dụng') from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)


class RunRegistry:
    def __init__(self, database=None):
        # Honor injected/runtime database locations, including an external cache.
        self.database = plain_path(database or CACHE/'state.sqlite3')
        self.root = plain_path(self.database.parent/(self.database.stem+'-runs'))
        self.backups = plain_path(self.database.parent/'cache-backups')

    def directory(self, run_id):
        if not re.fullmatch('[a-f0-9]{32}', str(run_id)):
            raise ValueError('CACHE_INVALID_RUN: ID lượt không hợp lệ')
        return plain_path(self.root/run_id)

    def plan(self, options, *, whole=False):
        run_id = uuid4().hex
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        workspace = ROOT/'output'/('stage3g-restart-'+run_id) if whole else None
        output = workspace/'rendered' if whole else Path(options.output).resolve()/('run-'+stamp+'-'+run_id[:8])
        return dict(version=1, run_id=run_id, created=timestamp(), state='ready',
            base_database=str(self.database), database=str(self.directory(run_id)/'state.sqlite3'),
            source=str(Path(options.source).resolve()), output=str(output), mode=options.mode,
            output_base=str(Path(options.output).resolve()),
            workspace=str(workspace) if workspace else None, cache_policy='isolated-new-run')

    def create(self, plan, options):
        directory = self.directory(plan['run_id'])
        if plan.get('base_database') != str(self.database) or plan.get('database') != str(directory/'state.sqlite3'):
            raise ValueError('CACHE_INVALID_RUN')
        output = plain_path(plan['output']); source = Path(options.source).resolve()
        if not source.is_dir() or output == source or source.is_relative_to(output):
            raise ValueError('Thư mục xuất phải tách khỏi nguồn')
        if output == ROOT.resolve() or ROOT.resolve().is_relative_to(output):
            raise ValueError('Không xuất vào thư mục gốc/cha của ứng dụng')
        for name in ('config','models','cache','core','ui','providers','sources','scripts','tests','logs','.venv','assets','dist','build'):
            if output.is_relative_to((ROOT/name).resolve()):
                raise ValueError('Không xuất vào khu vực mã nguồn/model/cache/build')
        if output.exists():
            raise FileExistsError('Thư mục lượt mới đã tồn tại; chọn vị trí mới, không ghi đè')
        directory.mkdir(parents=True, exist_ok=False)
        output.mkdir(parents=True, exist_ok=False)
        copied = Options.from_dict(options.to_dict()); copied.output = str(output)
        copied.skip_success = True  # Empty namespace initially; later resume can retain its own finished pages.
        # Output is empty and the database is new. No legacy checkpoint/cache is imported.
        record = dict(plan, options=copied.to_dict(), journal_id=None)
        previous_output=Path(options.output).resolve()
        record['input_exclusions']=[str(previous_output)] if previous_output.is_relative_to(source) else []
        atomic_json(directory/'run.json', record)
        self.activate(record['run_id'])
        return record

    def activate(self,run_id):
        self.read(run_id)
        atomic_json(self.root/'active.json',dict(version=1,run_id=run_id))

    def active(self,options):
        """Bounded discovery only. Restoring a namespace never starts processing."""
        try:
            path=plain_path(self.root/'active.json')
            if path.stat().st_size>4096:return None
            marker=json.loads(path.read_text(encoding='utf-8'))
            if marker.get('version')!=1:return None
            record=self.read(marker['run_id'])
            if record['source']==str(Path(options.source).resolve()) and record['output']==str(Path(options.output).resolve()):
                return record
        except (OSError,ValueError,KeyError):pass
        return None

    def read(self, run_id):
        directory = self.directory(run_id); marker = plain_path(directory/'run.json')
        if marker.stat().st_size > 1_000_000:
            raise ValueError('CACHE_INVALID_RUN')
        record = json.loads(marker.read_text(encoding='utf-8'))
        if (record.get('version') != 1 or record.get('run_id') != run_id or
                record.get('base_database') != str(self.database) or
                record.get('database') != str(directory/'state.sqlite3')):
            raise ValueError('CACHE_INVALID_RUN')
        database=plain_path(record['database'])
        if database.exists() and database.stat().st_nlink > 1:
            raise ValueError('CACHE_UNSAFE_PATH: database có hardlink')
        return record

    def update(self, run_id, **changes):
        record = self.read(run_id); record.update(changes, updated=timestamp())
        atomic_json(self.directory(run_id)/'run.json', record)
        return record

    @contextmanager
    def claim(self, run_id):
        self.read(run_id)
        with exclusive(self.directory(run_id)/'.lease'):
            yield self.read(run_id)

    def inventory(self):
        records = []
        started=time.monotonic();self.inventory_incomplete=False
        if self.root.exists():
            for directory in sorted(self.root.iterdir(), key=lambda p:p.name):
                if len(records)>=500 or time.monotonic()-started>3:
                    self.inventory_incomplete=True;break
                try:
                    record = self.read(directory.name)
                    db = Path(record['database']); kinds = {}; busy = False
                    try:
                        with self.claim(directory.name):
                            pass
                    except ValueError:
                        busy = True
                    if db.is_file() and not busy:
                        with closing(sqlite3.connect(db.as_uri()+'?mode=ro', uri=True, timeout=.2)) as connection:
                            kinds = dict(connection.execute('SELECT kind, count(*) FROM cache GROUP BY kind'))
                    size=0
                    for folder,dirs,files in os.walk(directory,followlinks=False):
                        dirs[:]=[d for d in dirs if not (Path(folder)/d).is_symlink() and not
                            getattr((Path(folder)/d).stat(),'st_file_attributes',0)&1024]
                        for name in files:
                            item=Path(folder)/name
                            if not item.is_symlink():size+=item.stat().st_size
                        if time.monotonic()-started>3:self.inventory_incomplete=True;break
                    record.update(kinds=kinds, busy=busy, bytes=size,
                        cleanable=not busy and record['state']=='done')
                    records.append(record)
                except (OSError, ValueError, KeyError, sqlite3.Error):
                    continue  # Untrusted/unrecognized directories never become cleanup targets.
        return records

    def _snapshot(self, record, connection):
        folder = plain_path(self.backups/record['run_id']/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')))
        folder.mkdir(parents=True, exist_ok=False)
        deadline=time.monotonic()+15
        def progress(status,remaining,total):
            if time.monotonic()>deadline:
                raise TimeoutError('CACHE_BACKUP_FAILED: quá thời gian sao lưu; giữ nguyên cache')
        with closing(sqlite3.connect(folder/'state.sqlite3')) as destination:
            connection.backup(destination,pages=128,progress=progress,sleep=.01)
        # Retain all checkpoint JSON as a bounded, validated backup. Never move WAL/SHM.
        journal = plain_path(Path(record['database']).with_name('state-resume-v1'))
        if journal.exists():
            copies = folder/'state-resume-v1'; copies.mkdir()
            for path in journal.glob('*.json'):
                plain_path(path)
                if path.stat().st_size > 16_000_000:
                    raise ValueError('CACHE_BACKUP_FAILED: journal quá lớn; giữ nguyên cache')
                (copies/path.name).write_bytes(path.read_bytes())
        atomic_json(folder/'run.json', record)
        return folder

    def backup(self, run_id):
        with self.claim(run_id) as record:
            db = Path(record['database'])
            with closing(sqlite3.connect(db.as_uri()+'?mode=rw', uri=True, timeout=1)) as connection:
                return self._snapshot(record, connection)

    def prune(self, run_id, kinds):
        kinds = set(kinds)
        if not kinds or not kinds <= {'ocr','translation'}:
            raise ValueError('CACHE_SCOPE_UNSUPPORTED: chỉ dọn OCR/bản dịch của lượt đã hoàn tất')
        with self.claim(run_id) as record:
            if record['state'] != 'done':
                raise ValueError('CACHE_CHECKPOINT_PROTECTED: lượt chưa hoàn tất; không dọn checkpoint')
            with closing(sqlite3.connect(Path(record['database']).as_uri()+'?mode=rw', uri=True, timeout=1)) as connection:
                # Backup first. Any backup error aborts before DELETE.
                backup = self._snapshot(record, connection)
                connection.execute('BEGIN IMMEDIATE')
                if connection.execute("SELECT count(*) FROM jobs WHERE state != 'done'").fetchone()[0]:
                    raise ValueError('CACHE_CHECKPOINT_PROTECTED: còn job chưa hoàn tất')
                count = 0
                for kind in sorted(kinds):
                    count += connection.execute('DELETE FROM cache WHERE kind=?', (kind,)).rowcount
                connection.commit()
            self.update(run_id, last_cleanup=timestamp(), last_backup=str(backup))
            return dict(deleted_entries=count, backup=str(backup), retained='DB, journals, receipts, output, other runs')
