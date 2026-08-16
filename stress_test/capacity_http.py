"""Standard-library HTTP clients used by the capacity runner."""

from __future__ import annotations

import http.client
import gzip
import json
import ssl
import threading
import time
from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


USER_AGENT = 'time-tracker-capacity-client/2.1'
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def resolve_target(value: str, *, allow_http=False):
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('TARGET_URL must be an absolute HTTP(S) URL')
    loopback = parsed.hostname in {'127.0.0.1', 'localhost', '::1'}
    if parsed.scheme != 'https' and not (allow_http or loopback):
        raise ValueError('TARGET_URL must use HTTPS for a remote server')
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('TARGET_URL must not contain credentials, query parameters, or a fragment')
    origin = f'{parsed.scheme}://{parsed.netloc}'
    if parsed.path.rstrip('/').endswith('/api/stress-test/probe'):
        probe_url = value.rstrip('/') + '/'
    elif parsed.path in {'', '/'}:
        probe_url = origin + '/api/stress-test/probe/'
    else:
        raise ValueError('TARGET_URL must be the site origin or the dedicated stress-test probe URL')
    return origin, probe_url


def _float_header(headers, name, *, scale=1.0):
    try:
        value = headers.get(name)
        # Nginx can emit comma-separated upstream values after retries.
        value = value.split(',')[-1].strip() if value else value
        return round(float(value) * scale, 3) if value not in {None, ''} else None
    except (TypeError, ValueError):
        return None


class ControlClient:
    def __init__(self, probe_url: str, key: str, timeout_seconds: float):
        self.probe_url = probe_url
        self.key = key
        self.timeout_seconds = timeout_seconds

    def action(self, action: str, **values):
        body = json.dumps({'action': action, **values}, separators=(',', ':')).encode()
        request = Request(
            self.probe_url,
            method='POST',
            data=body,
            headers={
                'Authorization': f'Bearer {self.key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': USER_AGENT,
            },
        )
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(MAX_RESPONSE_BYTES)
                status = response.status
        except HTTPError as exc:
            raw = exc.read(64 * 1024)
            status = exc.code
        except (URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f'Control request failed: {exc.__class__.__name__}') from exc
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        try:
            payload = json.loads(raw.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RuntimeError(f'Control endpoint returned invalid JSON (HTTP {status}).') from exc
        if not 200 <= status < 300:
            raise RuntimeError(f'Control action {action} failed (HTTP {status}): {payload.get("detail", "unknown error")}')
        payload['_client_latency_ms'] = elapsed_ms
        return payload


@dataclass
class RequestSpec:
    endpoint: str
    method: str
    path: str
    body: dict[str, Any] | None = None
    authenticated: bool = True


class VirtualUser:
    def __init__(self, origin: str, *, session_key: str | None,
                 run_token: str, timeout_seconds: float, username='anonymous'):
        self.origin = origin.rstrip('/') + '/'
        self.run_token = run_token
        self.timeout_seconds = timeout_seconds
        self.username = username
        self.session_key = session_key
        parsed = urlsplit(self.origin)
        self.scheme = parsed.scheme
        self.host = parsed.hostname or ''
        self.port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        self.cookies = {'sessionid': session_key} if session_key else {}
        self._connection = None
        self._connection_lock = threading.Lock()

    def _new_connection(self):
        if self.scheme == 'https':
            return http.client.HTTPSConnection(
                self.host,
                self.port,
                timeout=self.timeout_seconds,
                context=ssl.create_default_context(),
            )
        return http.client.HTTPConnection(
            self.host, self.port, timeout=self.timeout_seconds,
        )

    def _close_connection(self):
        if self._connection is not None:
            try:
                self._connection.close()
            finally:
                self._connection = None

    def _set_response_cookies(self, headers):
        for value in headers.get_all('Set-Cookie') or []:
            parsed = SimpleCookie()
            try:
                parsed.load(value)
            except Exception:
                continue
            for name, morsel in parsed.items():
                if morsel['max-age'] == '0' or not morsel.value:
                    self.cookies.pop(name, None)
                else:
                    self.cookies[name] = morsel.value

    def _csrf(self):
        return self.cookies.get('csrftoken', '')

    def request(self, spec: RequestSpec, *, stage: str, scenario: str,
                offered_qps: float, offset_seconds: float, parse_json=False):
        url = urljoin(self.origin, spec.path.lstrip('/'))
        body = json.dumps(spec.body, separators=(',', ':')).encode() if spec.body is not None else None
        headers = {
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip',
            'User-Agent': USER_AGENT,
            'X-Load-Test-Run': self.run_token,
        }
        if spec.authenticated and self.session_key:
            headers['Cookie'] = '; '.join(
                f'{name}={value}' for name, value in self.cookies.items()
            )
        if body is not None:
            headers['Content-Type'] = 'application/json'
        csrf = self._csrf()
        if csrf and spec.method.upper() not in {'GET', 'HEAD', 'OPTIONS'}:
            headers['X-CSRFToken'] = csrf
        parsed_url = urlsplit(url)
        request_target = parsed_url.path or '/'
        if parsed_url.query:
            request_target += '?' + parsed_url.query
        started = time.perf_counter()
        raw = b''
        error = None
        response_headers = {}
        with self._connection_lock:
            try:
                if self._connection is None:
                    self._connection = self._new_connection()
                self._connection.request(
                    spec.method.upper(), request_target, body=body, headers=headers,
                )
                response = self._connection.getresponse()
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                status = response.status
                response_headers = response.headers
                self._set_response_cookies(response_headers)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raw = raw[:MAX_RESPONSE_BYTES]
                    error = 'response_too_large'
                    self._close_connection()
                elif not 200 <= status < 400:
                    error = f'HTTP {status}'
            except (http.client.HTTPException, TimeoutError, OSError) as exc:
                status = 0
                error = exc.__class__.__name__
                self._close_connection()
        total_ms = round((time.perf_counter() - started) * 1000, 3)
        payload = None
        decoded_raw = raw
        if raw and response_headers.get('Content-Encoding', '').lower() == 'gzip':
            try:
                decoded_raw = gzip.decompress(raw)
            except (OSError, EOFError):
                error = error or 'invalid_gzip'
                decoded_raw = b''
        if len(decoded_raw) > MAX_RESPONSE_BYTES:
            error = error or 'decoded_response_too_large'
            decoded_raw = b''
        if parse_json and decoded_raw:
            try:
                payload = json.loads(decoded_raw.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                error = error or 'invalid_json'
        nginx_upstream_response_ms = _float_header(
            response_headers, 'X-Load-Test-Nginx-Upstream-Response', scale=1000,
        )
        app_wall_ms = _float_header(response_headers, 'X-Load-Test-App-Wall-Ms')
        db_ms = _float_header(response_headers, 'X-Load-Test-DB-Ms')
        return {
            'offset_seconds': round(offset_seconds, 3),
            'stage': stage,
            'scenario': scenario,
            'endpoint': spec.endpoint,
            'method': spec.method.upper(),
            'status': status,
            'error': error,
            'offered_qps': offered_qps,
            'total_ms': total_ms,
            'queue_ms': _float_header(response_headers, 'X-Load-Test-Queue-Ms'),
            'app_wall_ms': app_wall_ms,
            'cpu_ms': _float_header(response_headers, 'X-Load-Test-App-CPU-Ms'),
            'cpu_user_ms': _float_header(response_headers, 'X-Load-Test-CPU-User-Ms'),
            'cpu_system_ms': _float_header(response_headers, 'X-Load-Test-CPU-System-Ms'),
            'db_ms': db_ms,
            'app_non_db_wall_ms': (
                round(max(0, app_wall_ms - db_ms), 3)
                if app_wall_ms is not None and db_ms is not None else None
            ),
            'db_queries': _float_header(response_headers, 'X-Load-Test-DB-Queries'),
            'db_writes': _float_header(response_headers, 'X-Load-Test-DB-Writes'),
            'json_render_ms': _float_header(
                response_headers, 'X-Load-Test-JSON-Render-Ms',
            ),
            'cache': response_headers.get('X-Load-Test-Cache'),
            'nginx_upstream_connect_ms': _float_header(
                response_headers, 'X-Load-Test-Nginx-Upstream-Connect', scale=1000,
            ),
            'nginx_upstream_header_ms': _float_header(
                response_headers, 'X-Load-Test-Nginx-Upstream-Header', scale=1000,
            ),
            'nginx_upstream_response_ms': nginx_upstream_response_ms,
            'client_edge_residual_ms': (
                round(max(0, total_ms - nginx_upstream_response_ms), 3)
                if nginx_upstream_response_ms is not None else None
            ),
            'request_bytes': len(body or b''),
            'response_bytes': len(raw),
            'payload': payload,
        }

    def bootstrap(self):
        result = self.request(
            RequestSpec('auth_bootstrap', 'GET', '/api/auth/session/'),
            stage='bootstrap',
            scenario='setup',
            offered_qps=0,
            offset_seconds=0,
            parse_json=True,
        )
        if result['status'] != 200 or not (result.get('payload') or {}).get('authenticated'):
            raise RuntimeError(
                f'Failed to bootstrap isolated user {self.username} '
                f'(HTTP {result["status"]}, authenticated='
                f'{bool((result.get("payload") or {}).get("authenticated"))}).'
            )
        result.pop('payload', None)
        return result
