"""Small, pure policy evaluator. Owner policy is never an official permission."""
from __future__ import annotations

import json
from pathlib import Path

from core.paths import CONFIG
from sources.contracts import AccessStatus, ChapterInfo
from sources.states import ContentPermission, ContentPermissionEvidence, DownloadDecision, DownloadState

DEFAULT_ALLOW_PUBLIC = 'default_allow_public'
VERIFIED_ONLY = 'verified_only'


def load_download_policy(path: Path | None = None) -> str:
    path = path or CONFIG / 'download_policy.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return DEFAULT_ALLOW_PUBLIC
    except (OSError, ValueError):
        return VERIFIED_ONLY  # Malformed configuration must not broaden access.
    policy = data.get('download_policy') if isinstance(data, dict) else None
    return policy if policy in (DEFAULT_ALLOW_PUBLIC, VERIFIED_ONLY) else VERIFIED_ONLY


def decide_download(chapter: ChapterInfo, policy: str, *, images_safe: bool | None,
                    evidence: ContentPermissionEvidence | None = None,
                    barrier: str | None = None) -> DownloadDecision:
    evidence = evidence or ContentPermissionEvidence()
    verified = evidence.verified and evidence.applies_to_download and bool(evidence.source_url)
    permission = evidence.status if verified else ContentPermission.UNKNOWN
    def decision(state, reason, basis=None):
        return DownloadDecision(state, reason, evidence.source_url, permission, policy,
                                chapter.access_status, basis, evidence.source_url if verified else None)
    if permission == ContentPermission.RESTRICTED:
        return decision(DownloadState.BLOCKED, evidence.reason or 'Hạn chế tải áp dụng đã xác minh.', 'VERIFIED_RESTRICTION')
    if barrier:
        return decision(DownloadState.BLOCKED, barrier, 'TECHNICAL_RESTRICTION')
    if chapter.access_status in (AccessStatus.LOCKED, AccessStatus.RESTRICTED):
        return decision(DownloadState.BLOCKED, 'Chương khóa/VIP/paywall/đăng nhập hoặc bị hạn chế.', 'TECHNICAL_RESTRICTION')
    if chapter.access_status != AccessStatus.PUBLIC:
        return decision(DownloadState.UNKNOWN, 'Chưa xác minh chương PUBLIC miễn phí/không khóa.')
    if images_safe is False:
        return decision(DownloadState.BLOCKED, 'Danh sách ảnh có URL/host hoặc thứ tự không an toàn.', 'TECHNICAL_RESTRICTION')
    if images_safe is not True:
        return decision(DownloadState.UNKNOWN, 'Phân tích ảnh chương để xác minh URL trước khi tải.')
    if permission == ContentPermission.ALLOWED:
        return decision(DownloadState.ALLOWED_BY_VERIFIED_PERMISSION, 'Có bằng chứng cho phép tải phù hợp đã xác minh.', 'VERIFIED_PERMISSION')
    if policy == DEFAULT_ALLOW_PUBLIC:
        return decision(DownloadState.ALLOWED_BY_USER_POLICY,
                        'Cho phép theo cấu hình chủ ứng dụng; quyền nội dung vẫn UNKNOWN.', 'USER_POLICY_DEFAULT_ALLOW')
    return decision(DownloadState.UNKNOWN, 'Chế độ verified_only cần bằng chứng cho phép phù hợp.')
