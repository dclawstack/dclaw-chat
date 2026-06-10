import json

import httpx
import pytest

from app.services.command_parser import (
    ParsedCommand,
    parse_command,
    _builtin_help,
    dispatch_webhook,
    execute_command,
)


@pytest.fixture(autouse=True)
def _allow_webhook_urls(monkeypatch):
    # The SSRF guard's pinned resolver does a real DNS lookup that the mock
    # transport can't intercept; stub the resolver seam so these tests
    # exercise dispatch logic, not DNS. (SSRF blocking/pinning itself is
    # covered in test_ssrf.py.)
    monkeypatch.setattr(
        "app.core.ssrf.socket.getaddrinfo",
        lambda host, *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )


def test_parse_command_basic():
    cmd = parse_command("/deploy staging now")
    assert cmd is not None
    assert cmd.name == "deploy"
    assert cmd.args == ["staging", "now"]
    assert cmd.args_str == "staging now"
    assert cmd.raw == "/deploy staging now"


def test_parse_command_lowercases_name():
    cmd = parse_command("/HELP")
    assert cmd is not None
    assert cmd.name == "help"
    assert cmd.args == []


def test_parse_command_not_a_command():
    assert parse_command("hello world") is None
    assert parse_command("   no slash") is None


def test_parse_command_empty_after_slash():
    assert parse_command("/") is None
    assert parse_command("/   ") is None


def test_parsed_command_args_str_empty():
    pc = ParsedCommand(raw="/x", name="x", args=[])
    assert pc.args_str == ""


def test_builtin_help_none():
    assert _builtin_help(None) == "No commands configured for this bot."


def test_builtin_help_empty_list():
    assert _builtin_help("[]") == "No commands configured for this bot."


def test_builtin_help_invalid_json():
    assert _builtin_help("{not json") == "Could not load command list."


def test_builtin_help_renders_commands():
    payload = json.dumps(
        [{"name": "pr", "usage": "/pr [repo]", "description": "Show PRs"}]
    )
    out = _builtin_help(payload)
    assert "Available commands" in out
    assert "/pr [repo]" in out
    assert "Show PRs" in out


def test_builtin_help_default_usage():
    payload = json.dumps([{"name": "foo", "description": "Foo cmd"}])
    out = _builtin_help(payload)
    assert "/foo" in out


@pytest.mark.asyncio
async def test_dispatch_webhook_success(monkeypatch):
    def handler(request):
        body = json.loads(request.content)
        assert body["command"] == "deploy"
        assert body["channel_id"] == "chan-1"
        return httpx.Response(200, json={"text": "Deployed!"})

    transport = httpx.MockTransport(handler)
    orig_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        orig_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    cmd = parse_command("/deploy staging")
    reply = await dispatch_webhook(
        "https://hook.test/x", cmd, "chan-1", "u-1", "Alice"
    )
    assert reply == "Deployed!"


@pytest.mark.asyncio
async def test_dispatch_webhook_message_fallback(monkeypatch):
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"message": "hi there"})
    )
    orig_init = httpx.AsyncClient.__init__
    monkeypatch.setattr(
        httpx.AsyncClient,
        "__init__",
        lambda self, *a, **k: orig_init(self, *a, **{**k, "transport": transport}),
    )
    cmd = parse_command("/x")
    reply = await dispatch_webhook("https://hook.test/x", cmd, "c", "u", "n")
    assert reply == "hi there"


@pytest.mark.asyncio
async def test_dispatch_webhook_failure_returns_none(monkeypatch):
    transport = httpx.MockTransport(lambda req: httpx.Response(500))
    orig_init = httpx.AsyncClient.__init__
    monkeypatch.setattr(
        httpx.AsyncClient,
        "__init__",
        lambda self, *a, **k: orig_init(self, *a, **{**k, "transport": transport}),
    )
    cmd = parse_command("/x")
    reply = await dispatch_webhook("https://hook.test/x", cmd, "c", "u", "n")
    assert reply is None


@pytest.mark.asyncio
async def test_dispatch_webhook_goes_through_pinned_client(monkeypatch):
    # T1-03 call-site check: the webhook POST connects to the IP validated by
    # the pinned resolver (autouse fixture answers 93.184.216.34) while the
    # Host header keeps the original hostname.
    import app.services.command_parser as cp

    seen = {}

    def handler(req):
        seen["connect_host"] = req.url.host
        seen["host_header"] = req.headers["host"]
        return httpx.Response(200, json={"text": "pinned-ok"})

    real_factory = cp.safe_async_client
    monkeypatch.setattr(
        cp,
        "safe_async_client",
        lambda **kw: real_factory(transport=httpx.MockTransport(handler), **kw),
    )
    reply = await dispatch_webhook(
        "https://hook.test/x", parse_command("/x"), "c", "u", "n"
    )
    assert reply == "pinned-ok"
    assert seen["connect_host"] == "93.184.216.34"
    assert seen["host_header"] == "hook.test"


@pytest.mark.asyncio
async def test_dispatch_webhook_blocks_internal_resolution(monkeypatch):
    # Fail closed: webhook host resolving to an internal IP is rejected by
    # the pinned guard before any connection (no transport stub needed).
    monkeypatch.setattr(
        "app.core.ssrf.socket.getaddrinfo",
        lambda host, *a, **k: [(2, 1, 6, "", ("127.0.0.1", 0))],
    )
    reply = await dispatch_webhook(
        "https://internal.test/x", parse_command("/x"), "c", "u", "n"
    )
    assert reply is None


@pytest.mark.asyncio
async def test_execute_command_help_builtin():
    payload = json.dumps([{"name": "pr", "description": "d"}])
    out = await execute_command(
        parse_command("/help"), payload, None, "c", "u", "n"
    )
    assert "Available commands" in out


@pytest.mark.asyncio
async def test_execute_command_no_webhook_default_reply():
    out = await execute_command(
        parse_command("/poll"), None, None, "c", "u", "n"
    )
    assert "/poll" in out
    assert "received" in out


@pytest.mark.asyncio
async def test_execute_command_webhook_reply(monkeypatch):
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"text": "from-hook"})
    )
    orig_init = httpx.AsyncClient.__init__
    monkeypatch.setattr(
        httpx.AsyncClient,
        "__init__",
        lambda self, *a, **k: orig_init(self, *a, **{**k, "transport": transport}),
    )
    out = await execute_command(
        parse_command("/x arg"), None, "https://hook.test/x", "c", "u", "n"
    )
    assert out == "from-hook"


@pytest.mark.asyncio
async def test_execute_command_webhook_fails_falls_back(monkeypatch):
    transport = httpx.MockTransport(lambda req: httpx.Response(500))
    orig_init = httpx.AsyncClient.__init__
    monkeypatch.setattr(
        httpx.AsyncClient,
        "__init__",
        lambda self, *a, **k: orig_init(self, *a, **{**k, "transport": transport}),
    )
    out = await execute_command(
        parse_command("/x"), None, "https://hook.test/x", "c", "u", "n"
    )
    assert "received" in out
