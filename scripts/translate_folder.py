from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.pipeline import ProcessingManager
from core.storage import configure_logging
from core.types import Options

parser = argparse.ArgumentParser(description='Image Translator VN — CLI cho QA / automation')
parser.add_argument('source')
parser.add_argument('output')
parser.add_argument('--language', choices=['zh', 'zt', 'ko', 'en', 'auto'], default='zh')
parser.add_argument('--mode', choices=['Offline', 'Online'], default='Offline')
args = parser.parse_args()
configure_logging()
options = Options(source=args.source, output=args.output, language=args.language, mode=args.mode)
result = ProcessingManager(options, emit=lambda event: print(json.dumps(event, ensure_ascii=True))).run()
raise SystemExit(0 if result['state'] == 'done' else 1)
