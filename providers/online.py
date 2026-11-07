from __future__ import annotations

import html
import threading
import time
from typing import Callable

import requests
from urllib.parse import urlparse

from providers.base import TranslationProvider


class ProviderError(RuntimeError):
    pass


class RateLimitedProvider(TranslationProvider):
    online = True

    def __init__(self, client: requests.Session | None = None, checkpoint: Callable = lambda: None):
        self.client = client or requests.Session()
        self.checkpoint = checkpoint
        self.last_request = 0.0
        self.lock = threading.Lock()

    def request(self, method: str, url: str, **kwargs) -> dict:
        with self.lock:
            for attempt in range(3):
                delay = max(0, 1.1 - (time.monotonic() - self.last_request))
                end = time.monotonic() + delay
                while time.monotonic() < end:
                    self.checkpoint()
                    time.sleep(min(.1, max(0, end - time.monotonic())))
                self.checkpoint()
                self.last_request = time.monotonic()
                try:
                    response = self.client.request(method, url, timeout=(8, 25), allow_redirects=False, **kwargs)
                    if response.status_code == 429:
                        # Respect service quota. Do not retry or switch identities.
                        raise ProviderError("Provider hết hạn mức (HTTP 429); thử lại sau theo quy định dịch vụ.")
                    if response.status_code >= 500:
                        raise requests.ConnectionError(f"HTTP {response.status_code}")
                    if response.status_code != 200:
                        raise ProviderError(f"Provider từ chối yêu cầu: HTTP {response.status_code}.")
                    return response.json()
                except (requests.RequestException, ValueError):
                    if attempt == 2:
                        # Avoid exception URLs containing OCR text in logs/UI.
                        raise ProviderError("Không kết nối được provider hoặc phản hồi không hợp lệ sau 3 lần thử.") from None
                    end = time.monotonic() + 2 ** attempt
                    while time.monotonic() < end:
                        self.checkpoint()
                        time.sleep(.1)
        raise ProviderError("Không có phản hồi dịch")

    def close(self) -> None:
        self.client.close()


class MyMemoryProvider(RateLimitedProvider):
    """Documented anonymous free GET API; no key, email, paid tier or uploads."""
    identity = "mymemory-anonymous-v1"

    def translate(self, text: str, source: str, target: str = "vi") -> str:
        # Documented limit is 500 bytes per query, not 500 Unicode characters.
        if len(text.encode('utf-8')) > 480:
            raise ProviderError("Đoạn vượt 480 byte; chia đoạn trước khi dùng MyMemory.")
        lang = {"zt": "zh-TW", "zh": "zh-CN"}.get(source, source)
        data = self.request("GET", "https://api.mymemory.translated.net/get",
                            params={"q": text, "langpair": f"{lang}|{target}"})
        if str(data.get("responseStatus")) != "200" or data.get("quotaFinished"):
            raise ProviderError("MyMemory hết hạn mức hoặc từ chối cặp ngôn ngữ; không xóa chữ gốc.")
        result = html.unescape(data.get("responseData", {}).get("translatedText", "")).strip()
        if not result or "MYMEMORY WARNING" in result.upper():
            raise ProviderError("MyMemory không trả bản dịch hợp lệ.")
        return result


class LibreTranslateProvider(RateLimitedProvider):
    """For a user supplied, authorized free/self-hosted instance. No API keys."""
    def __init__(self, endpoint: str, **kwargs):
        super().__init__(**kwargs)
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ProviderError("Endpoint phải dùng HTTPS hoặc localhost.")
        if parsed.username or parsed.password or parsed.query:
            raise ProviderError("Endpoint không được chứa thông tin đăng nhập hoặc API key.")
        self.endpoint = endpoint.rstrip('/')

    @property
    def identity(self) -> str:
        return f"libre-v1:{self.endpoint}"

    def translate(self, text: str, source: str, target: str = "vi") -> str:
        data = self.request("POST", self.endpoint + "/translate", json={
            "q": text, "source": "zh" if source == "zt" else source, "target": target, "format": "text"})
        result = data.get("translatedText", "").strip()
        if not result:
            raise ProviderError("LibreTranslate không trả bản dịch. Kiểm tra model và quyền dùng endpoint miễn phí.")
        return result
