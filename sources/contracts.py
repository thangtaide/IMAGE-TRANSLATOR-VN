from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, Iterable, TypeVar
from enum import Enum
from pathlib import Path


class SourceError(RuntimeError):
    category = 'source'


class InvalidURL(SourceError):
    category = 'url'


class UnsupportedWebsite(SourceError):
    category = 'website'


class AccessRestricted(SourceError):
    category = 'access'


class StructureChanged(SourceError):
    category = 'analysis'


class NetworkUnavailable(SourceError):
    category = 'network'


class UsageLimited(AccessRestricted):
    category = 'usage_limit'


class CacheError(SourceError):
    category = 'cache'


class DownloadNotReady(SourceError):
    category = 'download_policy'


class AccessStatus(str, Enum):
    UNKNOWN = 'unknown'
    LOCKED = 'locked'
    RESTRICTED = 'restricted'
    LOCAL = 'local_supplied'
    ALLOWED = 'verified_download_allowed'
    PUBLIC = 'public_readable'


@dataclass(frozen=True)
class ComicInfo:
    site_id: str
    comic_id: str | None
    source_url: str | None
    title: str | None = None
    author: str | None = None
    chapter_count: int | None = None
    status: str | None = None
    main_chapter_count: int | None = None
    source_kind: str = 'unknown'
    topic_url: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChapterInfo:
    chapter_id: str
    chapter_title: str | None
    chapter_number: str | None
    chapter_url: str | None
    access_status: AccessStatus
    order_index: int
    local_source: Path | None = None
    image_count: int | None = None
    content_kind: str = 'unknown'
    image_list_complete: bool | None = None
    url_source: str | None = None


@dataclass(frozen=True)
class ChapterImage:
    image_index: int
    source_url: str | None = None
    local_path: Path | None = None
    content_type: str | None = None
    width: int | None = None
    height: int | None = None
    download_status: str = 'not_downloaded'
    source_attribute: str | None = None
    dimensions_source: str | None = None


T = TypeVar('T')


class DiscoveryList(list[T], Generic[T]):
    """A backward-compatible list with explicit completeness and discovery warnings."""
    def __init__(self, values: Iterable[T] = (), *, warnings: Iterable[str] = (), complete: bool | None = None,
                 analysis: dict | None = None):
        super().__init__(values)
        self.warnings = tuple(warnings)
        self.complete = complete
        self.analysis = analysis or {}


class WebsiteAdapter(ABC):
    site_id: str
    hosts: tuple[str, ...]
    support_status = 'UNVERIFIED'
    download_enabled = False  # Legacy information only; never an analysis/UI gate.

    def download_decision(self, chapter: ChapterInfo):
        from sources.states import DownloadDecision, DownloadState
        if chapter.access_status in (AccessStatus.LOCKED, AccessStatus.RESTRICTED):
            return DownloadDecision(DownloadState.RESTRICTED, 'Chương bị khóa hoặc hạn chế truy cập.')
        return DownloadDecision(DownloadState.UNKNOWN,
                                'Chưa xác minh điều kiện tải tự động của chương; vẫn có thể phân tích và chọn chương.')

    def can_handle(self, url: str) -> bool:
        try:
            self.normalize_url(url)
            return True
        except InvalidURL:
            return False

    @abstractmethod
    def normalize_url(self, url: str) -> str: ...

    @abstractmethod
    def get_comic_info(self, url: str, control=None) -> ComicInfo: ...

    @abstractmethod
    def get_chapters(self, comic: ComicInfo, control=None) -> list[ChapterInfo]: ...

    @abstractmethod
    def get_chapter_images(self, chapter: ChapterInfo, control=None) -> list[ChapterImage]: ...

    def download_chapter(self, chapter: ChapterInfo, cache_dir: Path, control=None):
        raise SourceError('Adapter chưa triển khai downloader tương thích; không phải kết luận về quyền đọc chương.')
