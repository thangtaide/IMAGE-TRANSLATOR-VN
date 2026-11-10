"""Bounded public HTML only. No image requests, browser impersonation or cookies."""
from __future__ import annotations

import http.client
import os
import socket
import ssl
import time
from urllib.parse import urljoin
from urllib.request import getproxies

from sources.contracts import AccessRestricted, NetworkUnavailable, SourceError, UsageLimited
from sources.security import https_url, public_addresses


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host: str,address: str):
        super().__init__(host,timeout=10,context=ssl.create_default_context())
        self.address=address

    def connect(self):
        sock=socket.create_connection((self.address,443),self.timeout)
        try:self.sock=self._context.wrap_socket(sock,server_hostname=self.host)
        except BaseException:sock.close();raise


def fetch_public_html(url: str, hosts: tuple[str,...], control=None) -> str:
    # A direct, DNS-pinned connection must never silently bypass an existing proxy.
    if os.environ.get('CODEX_SANDBOX_NETWORK_DISABLED')=='1' or any(k in getproxies() for k in ['http','https','all']):
        raise NetworkUnavailable('Mạng bị giới hạn hoặc có proxy: bộ đọc metadata trực tiếp chưa hỗ trợ proxy. Không bỏ qua cấu hình mạng.')
    checkpoint=control.checkpoint if control else lambda:None
    start=time.monotonic();current=url
    try:
        for hop in range(4):
            checkpoint()
            parsed=https_url(current,hosts)
            addresses=public_addresses(parsed.hostname)
            connection=_PinnedHTTPS(parsed.hostname,addresses[0])
            try:
                connection.request('GET',parsed.path+('?' + parsed.query if parsed.query else ''),
                                   headers={'User-Agent':'ImageTranslatorVN/0.1 (public metadata)', 'Accept':'text/html'})
                response=connection.getresponse()
                if response.status == 429:
                    raise UsageLimited('Website giới hạn truy cập HTTP 429; dừng, không retry hoặc né giới hạn.')
                if response.status in [401,403]:
                    raise AccessRestricted('Website trả HTTP '+str(response.status)+'; không retry hoặc vượt giới hạn.')
                if response.status in [301,302,303,307,308]:
                    location=response.getheader('Location')
                    if not location:raise SourceError('Redirect không có địa chỉ đích.')
                    current=urljoin(current,location);https_url(current,hosts)
                    continue
                if response.status!=200:raise SourceError('Lỗi metadata HTTP '+str(response.status))
                if response.getheader('Content-Type','').split(';')[0].strip().lower() not in ('text/html','application/xhtml+xml'):
                    raise SourceError('Nguồn metadata không phải HTML.')
                if int(response.getheader('Content-Length','0'))>2_000_000:raise SourceError('HTML vượt giới hạn 2 MB.')
                blocks=[];size=0
                while True:
                    checkpoint()
                    if time.monotonic()-start>30:raise NetworkUnavailable('Metadata quá thời gian 30 giây.')
                    block=response.read(65536)
                    if not block:break
                    size+=len(block)
                    if size>2_000_000:raise SourceError('HTML vượt giới hạn 2 MB.')
                    blocks.append(block)
                return b''.join(blocks).decode('utf-8',errors='strict')
            finally:connection.close()
        raise SourceError('Quá số lần redirect được phép.')
    except (OSError,UnicodeError,http.client.HTTPException,ValueError) as exc:
        raise NetworkUnavailable('Không đọc được HTML công khai: '+type(exc).__name__) from exc
