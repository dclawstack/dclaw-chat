"""Regression tests for the SSRF guard (consensus bugs #3/#4, gap T1-03)."""
import httpx
import pytest

from app.core import ssrf
from app.core.ssrf import SSRFError, assert_url_safe, safe_async_client


def _addrinfo(*ips: str):
    return [(2, 1, 6, "", (ip, 0)) for ip in ips]


def _stub_resolve(monkeypatch, ip: str):
    """Force getaddrinfo to resolve every host to ``ip``."""
    monkeypatch.setattr(
        ssrf.socket,
        "getaddrinfo",
        lambda host, *a, **k: _addrinfo(ip),
    )


@pytest.mark.parametrize("scheme", ["file", "gopher", "ftp", "data"])
def test_rejects_non_http_schemes(scheme):
    with pytest.raises(SSRFError):
        assert_url_safe(f"{scheme}://example.com/x")


def test_rejects_missing_host():
    with pytest.raises(SSRFError):
        assert_url_safe("http:///nohost")


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",       # loopback
        "10.1.2.3",        # private
        "192.168.1.1",     # private
        "172.16.5.4",      # private
        "169.254.169.254", # cloud metadata / link-local
        "::1",             # IPv6 loopback
    ],
)
def test_blocks_internal_addresses(monkeypatch, ip):
    _stub_resolve(monkeypatch, ip)
    with pytest.raises(SSRFError):
        assert_url_safe("https://malicious.example/")


def test_allows_public_address(monkeypatch):
    _stub_resolve(monkeypatch, "93.184.216.34")  # example.com
    assert_url_safe("https://example.com/page")  # no raise


def test_fails_closed_on_dns_error(monkeypatch):
    def _boom(*a, **k):
        raise ssrf.socket.gaierror("no such host")

    monkeypatch.setattr(ssrf.socket, "getaddrinfo", _boom)
    with pytest.raises(SSRFError):
        assert_url_safe("https://does-not-resolve.invalid/")


def test_blocks_if_any_resolved_address_is_internal(monkeypatch):
    # Every returned IP must be validated, not just the first.
    monkeypatch.setattr(
        ssrf.socket,
        "getaddrinfo",
        lambda host, *a, **k: _addrinfo("93.184.216.34", "169.254.169.254"),
    )
    with pytest.raises(SSRFError):
        assert_url_safe("https://half-evil.example/")


# ── Pinned-resolution client (T1-03 TOCTOU / DNS rebinding) ──────────────────


def _counting_resolver(monkeypatch, answers: list[list]):
    """getaddrinfo stub returning successive *answers*; tracks call count."""
    calls: list[str] = []

    def fake_getaddrinfo(host, *a, **k):
        calls.append(host)
        return answers[min(len(calls) - 1, len(answers) - 1)]

    monkeypatch.setattr(ssrf.socket, "getaddrinfo", fake_getaddrinfo)
    return calls


@pytest.mark.asyncio
async def test_pinned_client_connects_to_validated_ip_without_re_resolving(monkeypatch):
    # Rebinding simulation: DNS answers a public IP at check time and would
    # answer the metadata IP on any *second* lookup. The pinned client must
    # resolve exactly once and connect to the validated IP.
    calls = _counting_resolver(
        monkeypatch,
        [_addrinfo("93.184.216.34"), _addrinfo("169.254.169.254")],
    )
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["connect_host"] = request.url.host
        seen["host_header"] = request.headers["host"]
        return httpx.Response(200, text="ok")

    async with safe_async_client(transport=httpx.MockTransport(handler)) as client:
        resp = await client.get("https://rebind.example/path?q=1")

    assert resp.status_code == 200
    # The connection went to the IP validated at check time…
    assert seen["connect_host"] == "93.184.216.34"
    # …while the Host header still names the original host.
    assert seen["host_header"] == "rebind.example"
    # …and there was no second resolution for the rebind to exploit.
    assert calls == ["rebind.example"]


@pytest.mark.asyncio
async def test_pinned_client_sets_sni_to_original_host(monkeypatch):
    _counting_resolver(monkeypatch, [_addrinfo("93.184.216.34")])
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["sni"] = request.extensions.get("sni_hostname")
        return httpx.Response(200)

    async with safe_async_client(transport=httpx.MockTransport(handler)) as client:
        await client.get("https://pinned.example/")

    assert seen["sni"] == "pinned.example"


@pytest.mark.asyncio
async def test_pinned_client_rejects_if_any_resolved_ip_blocked(monkeypatch):
    _counting_resolver(
        monkeypatch, [_addrinfo("93.184.216.34", "127.0.0.1")]
    )
    transport = httpx.MockTransport(lambda req: httpx.Response(200))
    async with safe_async_client(transport=transport) as client:
        with pytest.raises(SSRFError):
            await client.get("https://half-evil.example/")


@pytest.mark.asyncio
async def test_pinned_client_blocks_ip_literal_without_dns(monkeypatch):
    calls = _counting_resolver(monkeypatch, [_addrinfo("93.184.216.34")])
    transport = httpx.MockTransport(lambda req: httpx.Response(200))
    async with safe_async_client(transport=transport) as client:
        with pytest.raises(SSRFError):
            await client.get("http://169.254.169.254/latest/meta-data/")
    assert calls == []  # IP literal validated directly, no DNS at all


@pytest.mark.asyncio
async def test_pinned_client_fails_closed_on_dns_error(monkeypatch):
    def _boom(*a, **k):
        raise ssrf.socket.gaierror("no such host")

    monkeypatch.setattr(ssrf.socket, "getaddrinfo", _boom)
    transport = httpx.MockTransport(lambda req: httpx.Response(200))
    async with safe_async_client(transport=transport) as client:
        with pytest.raises(SSRFError):
            await client.get("https://does-not-resolve.invalid/")


@pytest.mark.asyncio
async def test_safe_client_forces_redirects_off():
    client = safe_async_client(follow_redirects=True)
    try:
        assert client.follow_redirects is False
    finally:
        await client.aclose()
