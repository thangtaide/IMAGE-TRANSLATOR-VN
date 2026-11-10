from __future__ import annotations

import logging
from contextlib import nullcontext
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from core.models import ModelSpec, TranslationModelManager, verify_installation
from core.pipeline import JobControl, ProcessingManager
from core.types import CancelledError, Options
from core.storage import TranslationCache


class ProcessingWorker(QThread):
    event = Signal(dict)

    def __init__(self, options: Options, only: list[str] | None = None, parent=None, cache_path: Path | None = None,
                 resume_id: str | None = None, run_id: str | None = None, run_base: Path | None = None):
        super().__init__(parent)
        self.options, self.only = options, only
        self.control = JobControl()
        self.cache_path = cache_path
        self.resume_id = resume_id
        self.run_id, self.run_base = run_id, run_base

    def run(self) -> None:
        cache = None
        try:
            from core.runtime import prepare_inference_runtime
            self.control.checkpoint()
            prepare_inference_runtime()
            self.control.checkpoint()
            from core.run_cache import RunRegistry
            registry = RunRegistry(self.run_base) if self.run_id else None
            with registry.claim(self.run_id) if registry else nullcontext():
                if registry:
                    record = registry.update(self.run_id, state='running')
                    if Path(record['database']) != Path(self.cache_path):
                        raise ValueError('CACHE_INVALID_RUN')
                if self.cache_path is not None:
                    cache = TranslationCache(self.cache_path)
                manager = ProcessingManager(self.options, cache=cache, control=self.control, emit=self.event.emit,
                                            resume_id=self.resume_id,
                                            input_exclusions=record.get('input_exclusions',[]) if registry else ())
                result = manager.run(self.only)
                if cache is not None:
                    cache.close(); cache = None
                if registry:
                    registry.update(self.run_id, state=result['state'], journal_id=manager.resume_id)
        except CancelledError:
            self.event.emit({'type':'finished', 'state':'cancelled', 'errors':[], 'total':0,
                             'completed':0, 'failed':0, 'skipped':0})
        except Exception as exc:
            logging.getLogger(__name__).exception('Processing worker runtime initialization failed')
            self.event.emit({'type': 'fatal', 'detail': str(exc) or type(exc).__name__})
            self.event.emit({'type': 'finished', 'state': 'error', 'errors': [], 'total': 0,
                             'completed': 0, 'failed': 0, 'skipped': 0})
        finally:
            if cache is not None:
                cache.close()


class ModelWorker(QThread):
    progress = Signal(int, int)
    result = Signal(bool, str)

    def __init__(self, spec: ModelSpec, action: str, parent=None):
        super().__init__(parent)
        self.spec, self.action = spec, action
        self.control = JobControl()

    def run(self) -> None:
        try:
            manager = TranslationModelManager()
            if self.action == 'download':
                manager.download(self.spec, self.progress.emit, self.control.checkpoint)
            elif self.action == 'verify':
                verify_installation(self.spec.directory)
            elif self.action == 'delete':
                manager.delete(self.spec)
            self.result.emit(True, 'Đã hoàn tất: ' + self.spec.name)
        except Exception as exc:
            self.result.emit(False, str(exc))
