from __future__ import annotations

import hashlib
import json
import logging
import logging.handlers
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

from core.paths import CACHE, CONFIG, ROOT
from core.types import Options


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path: Path, data: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def load_options() -> Options:
    path = CONFIG / "settings.json"
    if path.exists():
        try:
            return Options.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            logging.getLogger(__name__).exception("Cấu hình lỗi; dùng mặc định")
    return Options()


def save_options(options: Options) -> None:
    atomic_json(CONFIG / "settings.json", options.to_dict())


def configure_logging() -> None:
    handler = logging.handlers.RotatingFileHandler(ROOT / "logs" / "app.log", maxBytes=4_000_000, backupCount=4, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    # HTTP URLs may contain source text; do not log request URLs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


class TranslationCache:
    def __init__(self, path: Path | None = None):
        self.connection = sqlite3.connect(path or CACHE / "state.sqlite3", check_same_thread=False)
        self.lock = threading.RLock()
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS cache (kind TEXT, key TEXT, value TEXT, PRIMARY KEY(kind,key));
        CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, options TEXT, state TEXT, updated TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS items (job TEXT, path TEXT, status TEXT, output TEXT, fingerprint TEXT, detail TEXT,
                                        PRIMARY KEY(job,path));
        """)
        self.connection.commit()

    def get(self, kind: str, key: str) -> Any:
        with self.lock:
            row = self.connection.execute("SELECT value FROM cache WHERE kind=? AND key=?", (kind, key)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, kind: str, key: str, value: Any) -> None:
        with self.lock, self.connection:
            self.connection.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)", (kind, key, json.dumps(value, ensure_ascii=False)))

    def job(self, job_id: str, options: Options, state: str) -> None:
        with self.lock, self.connection:
            self.connection.execute("INSERT OR REPLACE INTO jobs(id,options,state,updated) VALUES (?,?,?,CURRENT_TIMESTAMP)",
                                    (job_id, json.dumps(options.to_dict(), ensure_ascii=False), state))

    def checkpoint(self, job: str, path: str, status: str, output: str = "", fingerprint: str = "", detail: str = "") -> None:
        with self.lock, self.connection:
            self.connection.execute("INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?)", (job, path, status, output, fingerprint, detail))

    def item(self, job: str, path: str) -> dict | None:
        with self.lock:
            row = self.connection.execute("SELECT status,output,fingerprint,detail FROM items WHERE job=? AND path=?", (job, path)).fetchone()
        return dict(zip(("status", "output", "fingerprint", "detail"), row)) if row else None

    def pending_job(self) -> Options | None:
        with self.lock:
            row = self.connection.execute("SELECT options FROM jobs WHERE state != 'done' ORDER BY updated DESC LIMIT 1").fetchone()
        return Options.from_dict(json.loads(row[0])) if row else None

    def close(self) -> None:
        self.connection.close()
