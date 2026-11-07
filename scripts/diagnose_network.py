"""Read-only network diagnostics. Never changes proxy, registry or pip settings."""
from __future__ import annotations

import concurrent.futures
import json
import os
import platform
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
import winreg
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
STAMP = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
DESTINATION = ROOT / 'logs' / ('network-diagnostics-' + STAMP)
DESTINATION.mkdir(parents=True, exist_ok=False)


def redact(value: str) -> str:
    try:
        parsed = urlparse(value if '://' in value else 'http://' + value)
        if parsed.username or parsed.password:
            host = parsed.hostname or ''
            if parsed.port:
                host += ':' + str(parsed.port)
            return urlunparse((parsed.scheme, '[redacted]@' + host, parsed.path, '', '', ''))
    except ValueError:
        return '[invalid/redacted proxy URL]'
    return value


def command(args: list[str]) -> dict:
    try:
        result = subprocess.run(args, capture_output=True, text=True, errors='replace', timeout=20)
        # Avoid recording user credentials in any pip/registry command output.
        import re
        output = result.stdout + result.stderr
        output = re.sub(r'(https?://)[^\s/@]+:[^\s/@]+@', r'\1[redacted]@', output)
        return {'args': args, 'exit_code': result.returncode, 'output': output}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'args': args, 'status': 'ERROR', 'type': type(exc).__name__}


def tcp(host: str, port: int) -> dict:
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=5):
            return {'status': 'PASS', 'seconds': round(time.monotonic()-started, 3)}
    except OSError as exc:
        return {'status': 'FAIL', 'type': type(exc).__name__, 'winerror': getattr(exc, 'winerror', None),
                'errno': exc.errno, 'seconds': round(time.monotonic()-started, 3)}


proxy_names = ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'PIP_PROXY', 'PIP_NO_INDEX',
               'PIP_INDEX_URL', 'PIP_EXTRA_INDEX_URL', 'PIP_CONFIG_FILE', 'CODEX_SANDBOX_NETWORK_DISABLED',
               'CODEX_SANDBOX', 'CODEX_MANAGED_BY_NPM']
env = {key: redact(os.environ[key]) if 'PROXY' in key and key != 'NO_PROXY' or 'INDEX_URL' in key else os.environ[key]
       for key in proxy_names if key in os.environ}
registry = {}
key_name = r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'
for label, hive in [('HKCU', winreg.HKEY_CURRENT_USER), ('HKLM', winreg.HKEY_LOCAL_MACHINE)]:
    registry[label] = {}
    try:
        with winreg.OpenKey(hive, key_name) as key:
            for name in ['ProxyEnable', 'ProxyServer', 'ProxyOverride', 'AutoConfigURL', 'AutoDetect']:
                try:
                    value = winreg.QueryValueEx(key, name)[0]
                    registry[label][name] = redact(value) if isinstance(value, str) else value
                except FileNotFoundError:
                    registry[label][name] = None
    except OSError as exc:
        registry[label]['error'] = type(exc).__name__

proxy_endpoints = {}
managed_disabled = os.environ.get('CODEX_SANDBOX_NETWORK_DISABLED', '').lower() in ('1', 'true')
for name in ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY']:
    value = os.environ.get(name)
    if not value:
        continue
    parsed = urlparse(value)
    if parsed.hostname:
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        endpoint = f'{parsed.hostname}:{port}'
        proxy_endpoints.setdefault(endpoint, {'variables': [], 'host': parsed.hostname, 'port': port})['variables'].append(name)
        if parsed.hostname in ('127.0.0.1', 'localhost', '::1') and port == 9:
            managed_disabled = True
for item in proxy_endpoints.values():
    item['probe'] = tcp(item['host'], item['port'])

dns = {}
hosts = ['pypi.org', 'files.pythonhosted.org', 'raw.githubusercontent.com', 'paddleocr.bj.bcebos.com', 'argos-net.com', 'api.mymemory.translated.net']
def resolve(host):
    try:
        return {'status': 'PASS', 'addresses': sorted({r[4][0] for r in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})}
    except OSError as exc:
        return {'status': 'FAIL', 'type': type(exc).__name__, 'errno': exc.errno}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for host, value in zip(hosts, pool.map(resolve, hosts)):
        dns[host] = value

effective_https = {}
try:
    with urllib.request.urlopen('https://pypi.org/simple/pip/', timeout=8) as response:
        effective_https = {'status': 'PASS', 'http_status': response.status, 'bytes_read': len(response.read(256))}
except OSError as exc:
    reason = getattr(exc, 'reason', exc)
    effective_https = {'status': 'FAIL', 'type': type(exc).__name__, 'reason_type': type(reason).__name__,
                       'winerror': getattr(reason, 'winerror', None), 'errno': getattr(reason, 'errno', None)}

# Do not remove sandbox-injected proxies to circumvent the managed network boundary.
if managed_disabled:
    direct_https = {'status': 'SKIPPED', 'reason': 'Managed sandbox network disabled / loopback discard proxy detected; requires a network-enabled execution environment.'}
else:
    try:
        with socket.create_connection(('pypi.org', 443), timeout=8) as stream:
            with ssl.create_default_context().wrap_socket(stream, server_hostname='pypi.org') as tls:
                direct_https = {'status': 'PASS', 'tls_version': tls.version(), 'cipher': tls.cipher()[0]}
    except OSError as exc:
        direct_https = {'status': 'FAIL', 'type': type(exc).__name__, 'winerror': getattr(exc, 'winerror', None), 'errno': exc.errno}

data = {'timestamp': datetime.now(timezone.utc).isoformat(), 'read_only': True, 'python': sys.version,
        'executable': sys.executable, 'platform': platform.platform(), 'environment': env, 'windows_proxy': registry,
        'winhttp': command(['netsh', 'winhttp', 'show', 'proxy']),
        'pip_version': command([str(ROOT/'.venv/Scripts/python.exe'), '-m', 'pip', '--version']),
        'pip_config': command([str(ROOT/'.venv/Scripts/python.exe'), '-m', 'pip', 'config', 'debug']),
        'proxy_endpoints': proxy_endpoints, 'dns': dns, 'effective_https_pypi': effective_https,
        'managed_network_disabled': managed_disabled, 'direct_https_pypi': direct_https,
        'system_configuration_changed': False}
(DESTINATION/'diagnostics.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(data, ensure_ascii=False, indent=2))
print('Evidence:', DESTINATION)
