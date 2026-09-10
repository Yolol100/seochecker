#!/usr/bin/env python3
"""Small fail-closed HTTP(S) client for public SEO evidence.

Every hop is resolved and pinned to a validated public IP before the TCP connection is made.
This removes the DNS-rebinding time-of-check/time-of-use gap present in validate-then-urllib flows.
"""
from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

DEFAULT_USER_AGENT = "WebactueelSEOChecker/1.4 (+https://github.com/Yolol100/seochecker)"
REDIRECT_CODES = {301, 302, 303, 307, 308}


@dataclass
class SafeResponse:
    status: int
    url: str
    headers: http.client.HTTPMessage
    body: bytes
    connected_ip: str


def _validated_url(url: str):
    parsed = urlsplit(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Gebruik een volledige http:// of https:// URL.")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in de URL zijn niet toegestaan.")
    return parsed


def resolve_public_ips(url: str) -> list[str]:
    parsed = _validated_url(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Host kan niet worden opgelost: {exc}") from exc
    ips = []
    for info in infos:
        raw = info[4][0]
        ip = ipaddress.ip_address(raw)
        if not ip.is_global:
            raise ValueError(f"Niet-publiek doeladres geweigerd: {ip}")
        text = str(ip)
        if text not in ips:
            ips.append(text)
    if not ips:
        raise ValueError("Host heeft geen bruikbaar publiek IP-adres.")
    return ips


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, hostname: str, port: int, pinned_ip: str, timeout: float):
        super().__init__(hostname, port=port, timeout=timeout)
        self._pinned_ip = pinned_ip

    def connect(self):
        self.sock = socket.create_connection((self._pinned_ip, self.port), self.timeout, self.source_address)
        if self._tunnel_host:
            self._tunnel()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname: str, port: int, pinned_ip: str, timeout: float, context: ssl.SSLContext | None = None):
        super().__init__(hostname, port=port, timeout=timeout, context=context or ssl.create_default_context())
        self._pinned_ip = pinned_ip

    def connect(self):
        sock = socket.create_connection((self._pinned_ip, self.port), self.timeout, self.source_address)
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()
            sock = self.sock
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _host_header(parsed) -> str:
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    default_port = 443 if parsed.scheme == "https" else 80
    if parsed.port and parsed.port != default_port:
        return f"{host}:{parsed.port}"
    return host


def fetch_bytes(url: str, *, timeout: float = 20, max_bytes: int = 8_000_000, headers: dict[str, str] | None = None, max_redirects: int = 10) -> SafeResponse:
    if max_bytes < 0:
        raise ValueError("max_bytes must be non-negative")
    current = str(url).strip()
    request_headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "*/*"}
    request_headers.update(headers or {})
    for hop in range(max_redirects + 1):
        parsed = _validated_url(current)
        ips = resolve_public_ips(current)
        last_exc = None
        response = None
        connected_ip = ""
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        hop_headers = dict(request_headers)
        hop_headers["Host"] = _host_header(parsed)
        hop_headers.setdefault("Connection", "close")
        for ip in ips:
            conn = None
            try:
                conn = _PinnedHTTPSConnection(parsed.hostname or "", port, ip, timeout) if parsed.scheme == "https" else _PinnedHTTPConnection(parsed.hostname or "", port, ip, timeout)
                conn.request("GET", path, headers=hop_headers)
                raw = conn.getresponse()
                body = raw.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise ValueError(f"response exceeds max_bytes={max_bytes}: {current}")
                response = SafeResponse(raw.status, current, raw.headers, body, ip)
                connected_ip = ip
                break
            except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
                last_exc = exc
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
        if response is None:
            raise OSError(f"Geen verbinding mogelijk met gevalideerde publieke IP-adressen voor {current}: {last_exc}")
        if response.status in REDIRECT_CODES:
            location = response.headers.get("Location")
            if not location:
                return response
            if hop >= max_redirects:
                raise ValueError(f"te veel redirects (>{max_redirects}) voor {url}")
            current = urljoin(current, location)
            _validated_url(current)
            continue
        response.url = current
        response.connected_ip = connected_ip
        return response
    raise ValueError(f"te veel redirects voor {url}")


def fetch_text(url: str, *, timeout: float = 20, max_bytes: int = 8_000_000, headers: dict[str, str] | None = None) -> SafeResponse:
    response = fetch_bytes(url, timeout=timeout, max_bytes=max_bytes, headers=headers)
    content_type = response.headers.get("Content-Type", "")
    charset = "utf-8"
    for part in content_type.split(";")[1:]:
        key, sep, value = part.strip().partition("=")
        if sep and key.lower() == "charset" and value.strip():
            charset = value.strip().strip('"\'')
            break
    try:
        text = response.body.decode(charset, errors="replace")
    except LookupError:
        text = response.body.decode("utf-8", errors="replace")
    response.body = text
    return response
