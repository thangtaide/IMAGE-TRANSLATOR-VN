"""Vietnamese PySide6 desktop interface.

Import the inference runtime before any Qt module in this package. main.py also
does this explicitly; this boundary protects direct UI/worker imports by tools.
"""
from core.runtime import prepare_inference_runtime

prepare_inference_runtime()
