from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(sys.executable).resolve().parents[2] if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
CACHE = ROOT / "cache"
OCR_MODELS = ROOT / "models" / "ocr"
TRANSLATION_MODELS = ROOT / "models" / "translation"
ASSETS = Path(getattr(sys, "_MEIPASS", ROOT)) / "assets"


def initialize() -> None:
    for relative in ("config", "cache", "logs", "models/ocr", "models/translation", "assets/fonts", "assets/icons", "output", "dist"):
        (ROOT / relative).mkdir(parents=True, exist_ok=True)
    # Set before importing any AI framework. No system/user cache locations.
    for name, path in {
        "XDG_DATA_HOME": CACHE / "data", "XDG_CACHE_HOME": CACHE,
        "XDG_CONFIG_HOME": CONFIG, "ARGOS_PACKAGES_DIR": TRANSLATION_MODELS,
        "PADDLE_HOME": OCR_MODELS, "HF_HOME": CACHE / "huggingface",
        "TORCH_HOME": CACHE / "torch", "STANZA_RESOURCES_DIR": TRANSLATION_MODELS / "stanza",
    }.items():
        os.environ[name] = str(path)
    os.environ["ARGOS_DEVICE_TYPE"] = "cpu"
    os.environ["ARGOS_MODEL_PROVIDER"] = "OPENNMT"
    os.environ["OMP_NUM_THREADS"] = "2"
    os.environ["MKL_NUM_THREADS"] = "2"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["QT_API"] = "pyside6"


initialize()
