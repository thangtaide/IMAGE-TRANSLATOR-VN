"""Coordinate native inference libraries within one Windows worker process.

CTranslate2 4.6 imports torch through its converters/specs during package import.
That import must complete before Paddle initializes its native DLLs. Keep this
at the framework boundary, not only in main.py, so CLI and direct adapters work.
"""
from __future__ import annotations

import importlib
import sys
import threading
from types import ModuleType

_lock = threading.RLock()
_runtime: ModuleType | None = None


class RuntimeOrderError(RuntimeError):
    pass


def prepare_inference_runtime() -> ModuleType:
    """Load CT2 (and optional torch) once, on the calling worker thread.

    No model, download, DLL copying or system environment change. A caller that
    imported Paddle outside our adapters must start a clean process, because
    native DLLs cannot safely be unloaded and reordered in a running process.
    """
    global _runtime
    with _lock:
        if _runtime is not None:
            return _runtime
        if sys.platform == 'win32' and 'paddle' in sys.modules and 'ctranslate2' not in sys.modules:
            raise RuntimeOrderError('Paddle đã được nạp trước CTranslate2 ngoài cơ chế khởi tạo của ứng dụng. '
                                    'Khởi động lại worker/tiến trình; không thử tháo hoặc thay DLL trong tiến trình đang chạy.')
        try:
            module = importlib.import_module('ctranslate2')
        except OSError as exc:
            raise RuntimeOrderError('Không khởi tạo được runtime CTranslate2/Torch trước Paddle: '+str(exc)) from exc
        if not hasattr(module, 'Translator'):
            raise RuntimeOrderError('CTranslate2 thiếu native Translator; kiểm tra binary trong môi trường hiện tại.')
        _runtime = module
        return module
