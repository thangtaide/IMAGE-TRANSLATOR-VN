"""Local input adapters. They feed paths into the original ProcessingManager."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from core.pipeline import natural_key, scan_images
from core.types import Options
from sources.contracts import AccessStatus, ChapterInfo, ComicInfo, SourceError


def local_id(path: Path) -> str:
    return sha256(str(path.resolve()).encode('utf-8')).hexdigest()[:20]


@dataclass(frozen=True)
class ImageCollection:
    root: Path
    paths: tuple[Path, ...]

    @classmethod
    def discover(cls, path: Path) -> ImageCollection:
        path = path.resolve()
        root = path.parent if path.is_file() else path
        paths = [path] if path.is_file() else scan_images(root, True)
        # Resolve again: a junction/symlink in an ancestor must not escape input.
        from core.imaging import SUPPORTED
        valid = tuple(sorted((p.resolve() for p in paths if p.suffix.lower() in SUPPORTED
                              and not p.is_symlink() and p.resolve().is_relative_to(root)), key=natural_key))
        if not valid:
            raise SourceError('Không có ảnh cục bộ được hỗ trợ trong nguồn đã chọn.')
        return cls(root, valid)

    def request(self, options: Options) -> tuple[Options, list[str]]:
        data = options.to_dict()
        data.update(source=str(self.root), recursive=True)
        return Options.from_dict(data), [str(p) for p in self.paths]


def discover_local(path: Path, control=None) -> tuple[ComicInfo, list[ChapterInfo]]:
    """Root images form one chapter; otherwise immediate child folders are chapters.

    IDs describe LOCAL provenance and are never represented as website IDs.
    """
    checkpoint = control.checkpoint if control else lambda: None
    checkpoint()
    original = path
    if original.is_symlink():
        raise SourceError('Không dùng liên kết tượng trưng làm nguồn chương.')
    path = path.resolve()
    if path.is_file() or (path.is_dir() and scan_images(path, False)):
        candidates = [path]
    elif path.is_dir():
        candidates = sorted((p for p in path.iterdir() if p.is_dir() and not p.is_symlink()
                             and p.resolve().is_relative_to(path)), key=natural_key)
    else:
        raise SourceError('Đường dẫn ảnh/chương không tồn tại.')
    chapters = []
    for candidate in candidates:
        checkpoint()
        try:
            collection = ImageCollection.discover(candidate)
        except SourceError:
            continue
        chapters.append(ChapterInfo(local_id(candidate), candidate.stem if candidate.is_file() else candidate.name,
                                    None, None, AccessStatus.LOCAL, len(chapters), candidate, len(collection.paths)))
    if not chapters:
        raise SourceError('Không tìm thấy ảnh hoặc thư mục chương có ảnh.')
    comic = ComicInfo('local', local_id(path), None, title=path.stem if path.is_file() else path.name,
                      chapter_count=len(chapters), status='Ảnh do người dùng cung cấp')
    return comic, chapters
