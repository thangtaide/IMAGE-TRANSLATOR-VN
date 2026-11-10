import importlib.util
import json
import platform
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
info = {"python": sys.version, "executable": sys.executable, "platform": platform.platform(), "root": str(root),
        "modules": {x: bool(importlib.util.find_spec(x)) for x in
                    ["PySide6", "paddle", "paddleocr", "argostranslate", "ctranslate2", "cv2", "PIL", "numpy", "httpx", "pytest", "PyInstaller"]}}
(root / "logs").mkdir(exist_ok=True)
(root / "logs" / "environment.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
print(json.dumps(info, indent=2))
