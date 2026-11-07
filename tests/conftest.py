"""Initialize native libraries before pytest-qt configures Qt on Windows."""
import importlib.util
import sys

if sys.platform=='win32' and importlib.util.find_spec('ctranslate2'):
    from core.runtime import prepare_inference_runtime
    prepare_inference_runtime()
