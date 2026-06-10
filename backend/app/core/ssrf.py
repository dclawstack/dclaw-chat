"""SSRF guard for user-supplied URLs.

Two layers:

* :func:`assert_url_safe` — static check (scheme, host, resolved IPs). On its
  own it is TOCTOU/DNS-rebinding bypassable, because the HTTP client would
  re-resolve the host at connect time.
* :func:`safe_async_client` — an ``httpx.AsyncClient`` whose transport
  resolves the host exactly **once**, validates **every** returned address,
  and pins the connection to a validated IP (original hostname is kept for
  the ``Host`` header and TLS SNI/certificate verification). Redirects are
  always disabled. All server-side fetches of user-supplied URLs must go
  through this factory.

Everything fails closed: resolution errors or any blocked address raise
:class:`SSRFError`.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

ALLOWED_SCHEMES: tuple[str, ...] = ("https", "http")

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


def _addr_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_reserved or ip.is_multicast or ip.is_unspecified
        or any(ip in net for net in _BLOCKED_NETS)
    )


def is_blocked_ip(value: str) -> bool:
    """Return True if *value* is an IP literal in a blocked/internal range.

    Non-IP strings (hostnames) return False — this helper performs no DNS.
    """
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return _addr_blocked(ip)


def resolve_pinned(host: str) -> str:
    """Resolve *host* once, validate every returned address, return one IP.

    * IP literals are validated directly (no DNS).
    * Hostnames are resolved with a single ``getaddrinfo`` call; if **any**
      returned address is blocked the whole resolution is rejected.
    * IPv4 answers are preferred for the pinned connection.

    Raises :class:`SSRFError` on resolution failure or any blocked address.
    """
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if _addr_blocked(literal):
            raise SSRFError("URL resolves to a blocked/internal address")
        return host

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise SSRFError(f"DNS resolution failed for host: {host}") from e
    if not infos:
        raise SSRFError(f"DNS resolution returned no addresses for host: {host}")

    addrs: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for *_, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if _addr_blocked(ip):
            raise SSRFError("URL resolves to a blocked/internal address")
        addrs.append(ip)

    addrs.sort(key=lambda a: a.version)  # prefer IPv4
    return str(addrs[0])


def assert_url_safe(url: str, *, allowed_schemes: tuple[str, ...] = ALLOWED_SCHEMES) -> None:
    """Static URL check (scheme / host / resolved IPs).

    NOTE: check-time only — connect through :func:`safe_async_client` so the
    validated resolution is also the one used for the connection.
    """
    parsed = urlparse(url)
    if parsed.scheme not in allowed_schemes:
        raise SSRFError(f"URL scheme not allowed: {parsed.scheme!r}")
    if not parsed.hostname:
        raise SSRFError("URL has no host")
    resolve_pinned(parsed.hostname)


class _PinnedHostTransport(httpx.AsyncBaseTransport):
    """Transport that resolves+validates once and connects to the pinned IP.

    The request URL's host is rewritten to the validated IP so the underlying
    transport performs **no second DNS resolution** (no rebinding window).
    The already-built ``Host`` header keeps the original hostname, and for
    HTTPS the ``sni_hostname`` extension preserves TLS SNI + certificate
    hostname verification.
    """

    def __init__(self, inner: httpx.AsyncBaseTransport | None = None) -> None:
        self._inner = inner or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        if url.scheme not in ALLOWED_SCHEMES:
            raise SSRFError(f"URL scheme not allowed: {url.scheme!r}")
        if not url.host:
            raise SSRFError("URL has no host")
        pinned = resolve_pinned(url.host)
        if pinned != url.host:
            if url.scheme == "https":
                request.extensions = {**request.extensions, "sni_hostname": url.host}
            request.url = url.copy_with(host=pinned)
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


def safe_async_client(**kwargs) -> httpx.AsyncClient:
    """Build an ``httpx.AsyncClient`` that is SSRF-guarded on every request.

    * Every request's host is resolved once, all addresses validated, and the
      connection pinned to a validated IP (see :class:`_PinnedHostTransport`).
    * Redirects are force-disabled — callers cannot re-enable them, so a
      redirect to an internal target can never be followed.
    * A ``transport`` kwarg, if provided, is wrapped as the *inner* transport
      (it still sits behind the pinning guard); this is the injection seam
      for tests.
    """
    kwargs["follow_redirects"] = False
    inner = kwargs.pop("transport", None)
    kwargs["transport"] = _PinnedHostTransport(inner)
    return httpx.AsyncClient(**kwargs)
