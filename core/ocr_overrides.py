"""Explicit evidence-backed OCR corrections; original OCR cache remains immutable."""
from __future__ import annotations

import json
import re
from pathlib import Path

from core.paths import ROOT
from core.storage import digest


class OCROverrideError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class OCRRegionOverrides:
    def __init__(self, rules: list[dict] | None = None):
        self.rules = rules or []
        ids = set()
        for rule in self.rules:
            polygon = rule.get('polygon')
            locator = Path(rule.get('source_relative_path', ''))
            if (not isinstance(rule.get('id'), str) or rule['id'] in ids
                    or type(rule.get('version')) is not int or rule['version'] < 1
                    or type(rule.get('enabled')) is not bool
                    or rule.get('action') != 'SKIP_FALSE_POSITIVE_REGION'
                    or not re.fullmatch(r'[a-f0-9]{64}', rule.get('image_sha256', ''))
                    or not isinstance(rule.get('text'), str) or not rule['text']
                    or not isinstance(polygon, list) or len(polygon) != 4
                    or any(not isinstance(p, list) or len(p) != 2 or
                           any(type(v) not in (int, float) for v in p) for p in polygon)
                    or not rule.get('reason') or not rule.get('evidence')
                    or locator.is_absolute() or '..' in locator.parts):
                raise OCROverrideError('OCR_OVERRIDE_INVALID', 'OCR override không đúng schema/evidence; không tự áp dụng.')
            ids.add(rule['id'])

    @classmethod
    def load(cls, path: Path | None = None):
        path = path or ROOT / 'overrides' / 'ocr_regions.json'
        if not path.exists():
            return cls()
        try:
            if path.stat().st_size > 1_000_000:
                raise ValueError('size')
            data = json.loads(path.read_text(encoding='utf-8'))
            if data.get('schema_version') != 1 or not isinstance(data.get('overrides'), list):
                raise ValueError('schema')
            return cls(data['overrides'])
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            raise OCROverrideError('OCR_OVERRIDE_INVALID', 'Không đọc được OCR override; giữ nguồn để xem lại.') from exc

    def for_image(self, image_sha256: str, image_path: Path) -> list[dict]:
        selected = []
        for rule in self.rules:
            if not rule['enabled']:
                continue
            locator = rule.get('source_relative_path')
            intended_path = locator and (ROOT / locator).resolve() == image_path.resolve()
            if intended_path and image_sha256 != rule['image_sha256']:
                raise OCROverrideError('OCR_OVERRIDE_HASH_MISMATCH', 'Hash ảnh khác bằng chứng OCR override; không bỏ vùng chữ.')
            if image_sha256 == rule['image_sha256']:
                selected.append(rule)
        return selected

    @staticmethod
    def revision(rules: list[dict]) -> str | None:
        return digest(['ocr-region-override-v1', rules]) if rules else None

    @staticmethod
    def apply(regions: list, rules: list[dict]) -> tuple[list, list[dict]]:
        removed = set()
        receipts = []
        for rule in rules:
            matches = [i for i, region in enumerate(regions)
                       if region.text == rule['text'] and region.polygon == rule['polygon']]
            if len(matches) != 1 or matches[0] in removed:
                raise OCROverrideError('OCR_OVERRIDE_REGION_MISMATCH',
                                       'Vùng OCR không khớp duy nhất text/polygon bằng chứng; không đoán vùng gần giống.')
            removed.add(matches[0])
            receipts.append({key: rule[key] for key in ('id', 'version', 'action', 'image_sha256', 'reason', 'evidence')})
        return [region for i, region in enumerate(regions) if i not in removed], receipts
