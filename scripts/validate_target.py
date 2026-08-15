#!/usr/bin/env python3
import argparse
import ipaddress
import socket
from urllib.parse import urlparse


def validate_target(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Gebruik een volledige http:// of https:// URL.")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in de URL zijn niet toegestaan.")
    host = parsed.hostname
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise ValueError(f"Host kan niet worden opgelost: {exc}") from exc
    if not addresses:
        raise ValueError("Host heeft geen bruikbaar IP-adres.")
    for raw in addresses:
        ip = ipaddress.ip_address(raw)
        if not ip.is_global:
            raise ValueError(f"Niet-publiek doeladres geweigerd: {ip}")
    return url


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a public SEO audit target URL")
    parser.add_argument("url")
    args = parser.parse_args()
    try:
        validate_target(args.url)
    except ValueError as exc:
        parser.error(str(exc))
    print(args.url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
