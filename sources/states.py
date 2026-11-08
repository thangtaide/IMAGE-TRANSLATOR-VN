"""Independent analysis, chapter access and download decisions (no global URL lock)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sources.contracts import AccessStatus, ChapterInfo


class AnalysisState(str, Enum):
    IDLE = 'IDLE'
    URL_INVALID = 'URL_INVALID'
    ANALYZING = 'ANALYZING'
    METADATA_READY = 'METADATA_READY'
    METADATA_ERROR = 'METADATA_ERROR'
    CHAPTER_LIST_READY = 'CHAPTER_LIST_READY'
    CHAPTER_LIST_ERROR = 'CHAPTER_LIST_ERROR'
    IMAGE_LIST_READY = 'IMAGE_LIST_READY'
    IMAGE_LIST_ERROR = 'IMAGE_LIST_ERROR'
    CONNECTION_ERROR = 'CONNECTION_ERROR'
    ACCESS_ERROR = 'ACCESS_ERROR'
    USAGE_LIMIT = 'USAGE_LIMIT'
    TECHNICAL_ERROR = 'TECHNICAL_ERROR'


class DownloadState(str, Enum):
    UNKNOWN = 'DOWNLOAD_UNKNOWN'
    ALLOWED = 'DOWNLOAD_ALLOWED'
    RESTRICTED = 'DOWNLOAD_RESTRICTED'
    FAILED = 'DOWNLOAD_FAILED'
    ALLOWED_BY_USER_POLICY = 'ALLOWED_BY_USER_POLICY'
    ALLOWED_BY_VERIFIED_PERMISSION = 'ALLOWED_BY_VERIFIED_PERMISSION'
    BLOCKED = 'BLOCKED'


class ContentPermission(str, Enum):
    UNKNOWN = 'UNKNOWN'
    ALLOWED = 'ALLOWED'
    RESTRICTED = 'RESTRICTED'


@dataclass(frozen=True)
class ContentPermissionEvidence:
    status: ContentPermission = ContentPermission.UNKNOWN
    source_url: str | None = None
    verified: bool = False
    applies_to_download: bool = False
    reason: str = ''


class ProcessingState(str, Enum):
    IDLE = 'IDLE'
    READY = 'READY_TO_TRANSLATE'
    TRANSLATING = 'TRANSLATING'
    COMPLETED = 'COMPLETED'
    COMPLETED_WITH_WARNINGS = 'COMPLETED_WITH_WARNINGS'
    CANCELLED = 'CANCELLED'
    FAILED = 'FAILED'


@dataclass(frozen=True)
class DownloadDecision:
    state: DownloadState
    reason: str
    evidence_url: str | None = None
    content_permission: ContentPermission = ContentPermission.UNKNOWN
    policy: str = 'verified_only'
    access_status: AccessStatus = AccessStatus.UNKNOWN
    basis: str | None = None
    permission_source: str | None = None

    @property
    def allowed(self) -> bool:
        # ALLOWED remains for existing adapters; it does not create content evidence.
        return self.state in (DownloadState.ALLOWED, DownloadState.ALLOWED_BY_USER_POLICY,
                              DownloadState.ALLOWED_BY_VERIFIED_PERMISSION)


def chapter_access(chapter: ChapterInfo) -> str:
    if chapter.access_status in (AccessStatus.LOCKED, AccessStatus.RESTRICTED):
        return 'CHAPTER_ACCESS_RESTRICTED'
    if chapter.access_status in (AccessStatus.LOCAL, AccessStatus.ALLOWED, AccessStatus.PUBLIC):
        return 'CHAPTER_ACCESS_ALLOWED'
    return 'CHAPTER_ACCESS_UNKNOWN'


def selectable(chapter: ChapterInfo) -> bool:
    # Unknown access does not prevent selecting a chapter or retrying its analysis.
    return chapter_access(chapter) != 'CHAPTER_ACCESS_RESTRICTED'
