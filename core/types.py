from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class OCRResult:
    text: str
    polygon: list[list[float]]
    confidence: float
    language: str
    reading_order: int = 0
    group_id: int = 0

    @property
    def box(self) -> tuple[int, int, int, int]:
        return (int(min(p[0] for p in self.polygon)), int(min(p[1] for p in self.polygon)),
                int(max(p[0] for p in self.polygon)), int(max(p[1] for p in self.polygon)))


@dataclass
class Options:
    source: str = ""
    output: str = ""
    language: str = "zh"
    mode: str = "Offline"
    online_provider: str = "MyMemory"
    offline_provider: str = "Argos"
    allow_online_fallback: bool = False
    recursive: bool = True
    preserve_structure: bool = True
    skip_success: bool = True
    output_format: str = "original"
    quality: int = 95
    font: str = ""
    font_min: int = 8
    font_max: int = 40
    alignment: str = "center"
    foreground: str = "black"
    stroke: int = 1
    line_spacing: int = 3
    erase_mode: str = "inpaint"
    mask_path: str = ""
    mask_expand: int = 1
    confidence: float = 0.55
    tile_size: int = 1600
    endpoint: str = "http://127.0.0.1:5000"
    glossary: dict[str, str] = field(default_factory=dict)
    reading_direction: str = "ltr"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Options:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class MissingModelError(RuntimeError):
    pass


class CancelledError(RuntimeError):
    pass


class LayoutError(RuntimeError):
    pass
