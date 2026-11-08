from __future__ import annotations

import ipaddress
import re
import socket
import unicodedata
from pathlib import Path
from urllib.parse import SplitResult, urlsplit

from sources.contracts import CacheError, InvalidURL

_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(i) for i in range(1,10)),
             *('LPT'+str(i) for i in range(1,10))}


def https_url(url: str, hosts: tuple[str, ...] | None = None) -> SplitResult:
    if not isinstance(url,str) or len(url)>2048 or any(ord(c)<32 for c in url) or '\\' in url:
        raise InvalidURL('URL không hợp lệ hoặc chứa ký tự điều khiển.')
    try:
        parsed=urlsplit(url.strip())
        if parsed.scheme!='https' or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.port not in (None,443):
            raise ValueError()
        host=parsed.hostname.lower()
        if not re.fullmatch(r'[a-z0-9.-]+',host) or host in ('localhost','localhost.localdomain') or host.endswith(('.local','.localhost','.internal')):
            raise ValueError()
        try:
            ip=ipaddress.ip_address(host)
        except ValueError:
            ip=None
        if ip is not None and not ip.is_global:
            raise ValueError()
        if hosts is not None and host not in hosts:
            raise ValueError()
    except ValueError as exc:
        raise InvalidURL('Chỉ dùng HTTPS, domain đã hỗ trợ, cổng 443; không dùng tài khoản hoặc địa chỉ nội bộ.') from exc
    return parsed


def public_addresses(host: str) -> list[str]:
    addresses=list(dict.fromkeys(r[4][0] for r in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise InvalidURL('DNS trỏ tới địa chỉ mạng nội bộ/đặc biệt; đã từ chối kết nối.')
    return addresses


def safe_id(value: str) -> str:
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',value) or value.upper() in _RESERVED:
        raise CacheError('ID không an toàn để tạo đường dẫn.')
    return value


def safe_name(title: str | None, identifier: str) -> str:
    identifier=safe_id(identifier)
    text=unicodedata.normalize('NFC',title or 'untitled')
    text=re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_',text).strip(' .') or 'untitled'
    if text.split('.')[0].upper() in _RESERVED:text='_'+text
    return text[:80].rstrip(' .')+'__'+identifier


def contained(root: Path, *parts: str) -> Path:
    base=root.resolve();target=base.joinpath(*parts).resolve()
    if not target.is_relative_to(base) or target==base:
        raise CacheError('Đường dẫn vượt phạm vi cache/output.')
    return target
