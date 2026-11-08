from sources.contracts import InvalidURL, UnsupportedWebsite
from sources.kuaikan import KuaikanAdapter
from sources.security import https_url

ADAPTERS=(KuaikanAdapter(),)


def resolve_adapter(url: str):
    parsed=https_url(url)
    for adapter in ADAPTERS:
        if parsed.hostname.lower() in adapter.hosts:
            adapter.normalize_url(url)
            return adapter
    raise UnsupportedWebsite('Website này chưa có adapter được đăng ký.')
