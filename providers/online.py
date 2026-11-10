from __future__ import annotations

import html
import json
import threading
import time
from typing import Callable

import requests
from urllib.parse import urlparse

from providers.base import TranslationProvider


class ProviderError(RuntimeError):
    code = 'TRANSLATION_VALIDATION_ERROR'


class OnlineProviderError(ProviderError):
    """Safe metadata only: never retain request URLs, text or response bodies."""
    def __init__(self, code: str, message: str, *, status=None, retry_after=None):
        super().__init__(message)
        self.code, self.status, self.retry_after = code, status, retry_after
        self.suspend = code in ('QUOTA_EXCEEDED', 'RATE_LIMITED', 'AUTH_REQUIRED')


class ProviderSuspended(OnlineProviderError):
    """Stop dispatching; only an explicit user resume can create a new session."""


class RateLimitedProvider(TranslationProvider):
    online = True

    def __init__(self, client: requests.Session | None = None, checkpoint: Callable = lambda: None):
        self.client = client or requests.Session()
        self.checkpoint = checkpoint
        self.last_request = 0.0
        self.lock = threading.Lock()
        self.blocked_error = None
        self.retry_count = 0

    def wait(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.checkpoint()
            time.sleep(min(.1, max(0, end - time.monotonic())))

    def block(self, error: OnlineProviderError):
        self.blocked_error = ProviderSuspended(error.code, str(error), status=error.status,
                                               retry_after=error.retry_after)
        raise self.blocked_error

    def request(self, method: str, url: str, **kwargs) -> dict:
        with self.lock:
            if self.blocked_error is not None:
                raise self.blocked_error
            self.retry_count = 0
            for attempt in range(3):
                delay = max(0, 1.1 - (time.monotonic() - self.last_request))
                self.wait(delay)
                self.checkpoint()
                self.last_request = time.monotonic()
                response = None
                try:
                    response = self.client.request(method, url, timeout=(8, 25), allow_redirects=False,
                                                   verify=True, stream=True, **kwargs)
                    if response.status_code == 429:
                        raw_delay = response.headers.get('Retry-After')
                        retry_after = int(raw_delay) if isinstance(raw_delay, str) and raw_delay.isdigit() and len(raw_delay) < 8 else None
                        self.block(OnlineProviderError('RATE_LIMITED', 'Online Free bị giới hạn tốc độ (HTTP 429).',
                                                      status=429, retry_after=retry_after))
                    if response.status_code in (401, 403):
                        self.block(OnlineProviderError('AUTH_REQUIRED', 'Provider yêu cầu xác thực hoặc từ chối truy cập.',
                                                      status=response.status_code))
                    if response.status_code >= 500:
                        raise requests.ConnectionError(f"HTTP {response.status_code}")
                    if response.status_code != 200:
                        raise OnlineProviderError('PROVIDER_UNAVAILABLE', f'Provider từ chối HTTP {response.status_code}; không chuyển endpoint.')
                    # Real HTTP responses are streamed and bounded. Legacy injected
                    # test clients may expose only json(); never used for live I/O.
                    if isinstance(response, requests.Response):
                        mime = response.headers.get('Content-Type', '').split(';')[0].strip().lower()
                        if mime not in ('application/json', 'text/json'):
                            raise OnlineProviderError('INVALID_RESPONSE', 'Provider không trả JSON.')
                        body = bytearray()
                        for block in response.iter_content(8192):
                            self.checkpoint()
                            body.extend(block)
                            if len(body) > 1_000_000:
                                raise OnlineProviderError('INVALID_RESPONSE', 'Phản hồi provider vượt giới hạn dung lượng.')
                        try:
                            data = json.loads(body.decode('utf-8'))
                        except (ValueError, UnicodeError):
                            raise OnlineProviderError('INVALID_RESPONSE', 'JSON provider không hợp lệ.') from None
                    else:
                        data = response.json()
                    if not isinstance(data, dict):
                        raise OnlineProviderError('INVALID_RESPONSE', 'Cấu trúc JSON provider không hợp lệ.')
                    self.checkpoint()
                    return data
                except requests.RequestException as exc:
                    if attempt == 2:
                        code = 'TIMEOUT' if isinstance(exc, requests.Timeout) else 'PROVIDER_UNAVAILABLE' if response is not None else 'NETWORK_ERROR'
                        raise OnlineProviderError(code, 'Không nhận được phản hồi dịch sau tối đa 3 lần thử.') from None
                    self.retry_count += 1
                except ValueError:
                    raise OnlineProviderError('INVALID_RESPONSE', 'Provider trả JSON không hợp lệ.') from None
                finally:
                    if response is not None:
                        response.close()
                self.wait(2 ** attempt)
        raise OnlineProviderError('PROVIDER_UNAVAILABLE', 'Không có phản hồi dịch')

    def close(self) -> None:
        self.client.close()


class MyMemoryProvider(RateLimitedProvider):
    """Documented anonymous free GET API; no key, email, paid tier or uploads."""
    identity = "mymemory-official-anonymous-v2:mt1:utf8-480:literal-numbers-v2-signed"

    def translate(self, text: str, source: str, target: str = "vi") -> str:
        # Documented limit is 500 bytes per query, not 500 Unicode characters.
        if len(text.encode('utf-8')) > 480:
            raise OnlineProviderError('INVALID_REQUEST', 'Đoạn vượt 480 byte; chia đoạn trước khi dùng MyMemory.')
        lang = {"zt": "zh-TW", "zh": "zh-CN"}.get(source, source)
        data = self.request("GET", "https://api.mymemory.translated.net/get",
                            params={"q": text, "langpair": f"{lang}|{target}", "mt": 1})
        details = str(data.get('responseDetails', '')).upper()
        if data.get('quotaFinished') is True or ('NEXT AVAILABLE IN' in details and 'LIMIT' in details):
            self.block(OnlineProviderError('QUOTA_EXCEEDED', 'MyMemory báo đã đạt hạn mức miễn phí.'))
        if str(data.get('responseStatus')) == '429':
            self.block(OnlineProviderError('RATE_LIMITED', 'MyMemory báo giới hạn tốc độ.'))
        if str(data.get('responseStatus')) in ('401', '403'):
            self.block(OnlineProviderError('AUTH_REQUIRED', 'MyMemory từ chối quyền truy cập.'))
        if str(data.get('responseStatus')) != '200':
            raise OnlineProviderError('PROVIDER_UNAVAILABLE', 'MyMemory từ chối yêu cầu/cặp ngôn ngữ.')
        payload = data.get('responseData')
        raw = payload.get('translatedText') if isinstance(payload, dict) else None
        if not isinstance(raw, str):
            raise OnlineProviderError('INVALID_RESPONSE', 'MyMemory thiếu văn bản dịch.')
        result = html.unescape(raw).strip()
        if not result or "MYMEMORY WARNING" in result.upper():
            raise OnlineProviderError('INVALID_RESPONSE', 'MyMemory không trả bản dịch hợp lệ.')
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
