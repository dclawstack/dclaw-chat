"""SSRF guard for user-supplied URLs."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_BLOCKED_NETS = [
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
        "169.254.0.0/16", "172.16.0.0/12", "192.0.0.0/24", "192.168.0.0/16",
        "198.18.0.0/15", "::1/128", "fc00::/7", "fe80::/10",
        "169.254.169.254/32",
    )
]


class SSRFError(ValueError):
    """Raised when a URL is unsafe to fetch server-side."""


def _ip_blocked(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise SSRFError(f"DNS resolution failed for host: {host}") from e
    for *_, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified
            or any(ip in net for net in _BLOCKED_NETS)
        ):
            return True
    return False


def assert_url_safe(url: str, *, allowed_schemes: tuple[str, ...] = ("https", "http")) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in allowed_schemes:
        raise SSRFError(f"URL scheme not allowed: {parsed.scheme!r}")
    if not parsed.hostname:
        raise SSRFError("URL has no host")
    if _ip_blocked(parsed.hostname):
        raise SSRFError("URL resolves to a blocked/internal address")
