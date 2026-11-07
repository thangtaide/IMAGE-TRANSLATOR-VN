from __future__ import annotations

import gc
import json
import sys
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from core.models import verify_installation
from core.paths import OCR_MODELS
from core.storage import digest
from core.types import MissingModelError, OCRResult

LANGUAGES = {'zh': ('ch', 'ch'), 'zt': ('chinese_cht', 'ch'), 'ko': ('korean', 'ml'), 'en': ('en', 'en')}


def overlap(a: tuple, b: tuple) -> float:
    inter = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    area_a = max(1, (a[2]-a[0]) * (a[3]-a[1]))
    area_b = max(1, (b[2]-b[0]) * (b[3]-b[1]))
    return inter / min(area_a, area_b)


def deduplicate(results: list[OCRResult]) -> list[OCRResult]:
    kept: list[OCRResult] = []
    for result in sorted(results, key=lambda x: x.confidence, reverse=True):
        if not any(overlap(result.box, old.box) > .65 for old in kept):
            kept.append(result)
    return kept


def reading_order(results: list[OCRResult], direction: str) -> list[OCRResult]:
    # Conservative order: no speculative merges across unknown comic bubbles.
    if direction == 'rtl':
        results.sort(key=lambda r: (-round(r.box[0] / 40), r.box[1]))
    else:
        results.sort(key=lambda r: (round(r.box[1] / 16), r.box[0]))
    for index, result in enumerate(results):
        result.reading_order = index
        result.group_id = index
    return results


def group_lines(results: list[OCRResult], image: np.ndarray, direction: str) -> list[OCRResult]:
    """Merge only tightly aligned horizontal lines, without crossing dark borders.

    This is a conservative geometric heuristic, not speech-bubble segmentation.
    Vertical comic columns remain separate to avoid joining different dialogues.
    """
    ordered = reading_order(results, direction)
    if direction == 'rtl':
        return ordered
    groups: list[list[OCRResult]] = []
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    for item in ordered:
        x0, y0, x1, y1 = item.box
        merged = False
        for group in reversed(groups):
            previous = group[-1]
            a0, b0, a1, b1 = previous.box
            wa, wb = max(1, a1-a0), max(1, x1-x0)
            ha, hb = max(1, b1-b0), max(1, y1-y0)
            horizontal = min(wa, wb)/max(wa, wb) > .65 and (min(a1, x1)-max(a0, x0))/min(wa, wb) > .85
            gap = y0-b1
            if item.language != previous.language or not horizontal or not (0 <= gap <= .65*min(ha, hb)):
                continue
            if max(ha, hb)/min(ha, hb) > 1.5 or max(ha, hb) > min(wa, wb):
                continue
            between = gray[max(0, b1):max(0, y0), max(0, max(a0, x0)):max(0, min(a1, x1))]
            if between.size and np.mean(between < 70) > .15:
                continue
            group.append(item)
            merged = True
            break
        if not merged:
            groups.append([item])
    output = []
    for group in groups:
        x0 = min(r.box[0] for r in group)
        y0 = min(r.box[1] for r in group)
        x1 = max(r.box[2] for r in group)
        y1 = max(r.box[3] for r in group)
        output.append(OCRResult(' '.join(r.text for r in group), [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
                                min(r.confidence for r in group), group[0].language))
    return reading_order(output, direction)


def local_models_only(directory: str, url: str) -> None:
    # Replace PaddleOCR's implicit downloader for this application, including Online
    # jobs: OCR model installation is always an explicit Model Manager operation.
    if not all((Path(directory) / name).is_file() for name in ('inference.pdmodel', 'inference.pdiparams')):
        raise MissingModelError('Thiếu file OCR cục bộ; không tự tải model trong lúc dịch.')


class PaddleOCREngine:
    def __init__(self, root: Path = OCR_MODELS):
        self.root = root
        self.engine = None
        self.language: str | None = None

    def model_dirs(self, language: str) -> tuple[Path, Path, Path]:
        _, det = LANGUAGES[language]
        return self.root / f'det-{det}', self.root / f'rec-{language}', self.root / 'cls'

    def identity(self, language: str) -> str:
        codes = list(LANGUAGES) if language == 'auto' else [language]
        manifests = []
        for code in codes:
            for folder in self.model_dirs(code):
                receipt = folder / 'integrity.json'
                if not receipt.is_file():
                    raise MissingModelError(f'Thiếu model OCR: {folder.name}. Tải qua Quản lý mô hình AI trước khi xử lý.')
                manifests.append(json.loads(receipt.read_text(encoding='utf-8')))
        return 'paddle-2.9.1-v4-tiles-v1:' + digest(manifests)

    def _load(self, language: str):
        if self.engine is not None and self.language == language:
            return self.engine
        dirs = self.model_dirs(language)
        for directory in dirs:
            verify_installation(directory)
        self.engine = None
        gc.collect()
        from core.runtime import prepare_inference_runtime
        prepare_inference_runtime()
        from paddleocr import PaddleOCR
        module = sys.modules[PaddleOCR.__module__]
        module.BASE_DIR = str(self.root)
        module.maybe_download = local_models_only
        self.engine = PaddleOCR(lang=LANGUAGES[language][0], use_gpu=False, show_log=False,
                                det_model_dir=str(dirs[0]), rec_model_dir=str(dirs[1]), cls_model_dir=str(dirs[2]),
                                use_angle_cls=True, enable_mkldnn=False, cpu_threads=2, det_limit_side_len=1536,
                                det_limit_type='max', rec_batch_num=6, ocr_version='PP-OCRv4')
        self.language = language
        return self.engine

    def recognize(self, image: np.ndarray, language: str, confidence: float = .55, tile_size: int = 1600,
                  direction: str = 'ltr', checkpoint: Callable = lambda: None) -> tuple[list[OCRResult], list[str]]:
        if language == 'auto':
            candidates = []
            for code in LANGUAGES:
                checkpoint()
                results, _ = self.recognize(image, code, confidence, tile_size, direction, checkpoint)
                score = sum(r.confidence * min(len(r.text), 30) for r in results) / max(1, sum(min(len(r.text), 30) for r in results))
                # Prefer outputs matching the expected script.
                text = ''.join(r.text for r in results)
                if code == 'ko' and not any('\uac00' <= c <= '\ud7af' for c in text):
                    score *= .65
                if code in ('zh', 'zt') and not any('\u4e00' <= c <= '\u9fff' for c in text):
                    score *= .7
                candidates.append((score, results))
            candidates.sort(key=lambda v: v[0], reverse=True)
            if not candidates[0][1]:
                return [], ['Không tìm thấy chữ ở các model đã cài.']
            warning = []
            if candidates[0][0] - candidates[1][0] < .08:
                warning.append('Nhận diện tự động còn mơ hồ; hãy chọn ngôn ngữ cụ thể và kiểm tra preview (đặc biệt giản/phồn thể).')
            return candidates[0][1], warning
        engine = self._load(language)
        height, width = image.shape[:2]
        tile_size = max(512, min(2400, tile_size))
        stride = tile_size - 192
        results = []
        ys = list(range(0, max(1, height-tile_size+1), stride))
        xs = list(range(0, max(1, width-tile_size+1), stride))
        if ys[-1] + tile_size < height:
            ys.append(max(0, height-tile_size))
        if xs[-1] + tile_size < width:
            xs.append(max(0, width-tile_size))
        for y in ys:
            for x in xs:
                checkpoint()
                tile = image[y:y+tile_size, x:x+tile_size]
                raw = engine.ocr(np.ascontiguousarray(tile[:, :, ::-1]), cls=True)
                for page in raw or []:
                    for line in page or []:
                        polygon, (text, score) = line
                        if text.strip() and float(score) >= confidence:
                            poly = [[max(0, min(width-1, float(p[0])+x)), max(0, min(height-1, float(p[1])+y))] for p in polygon]
                            results.append(OCRResult(text.strip(), poly, float(score), language))
        return group_lines(deduplicate(results), image, direction), []
