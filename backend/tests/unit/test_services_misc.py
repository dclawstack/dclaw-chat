import httpx
import pytest

from app.services.ollama_service import (
    OllamaService,
    OLLAMA_MODELS,
    OLLAMA_NAME_TO_ID,
)
from app.services.openrouter_service import OpenRouterService, OPENROUTER_MODELS
from app.services.nvidia_service import NvidiaService, NVIDIA_MODELS
from app.services.meeting_service import _parse_action_lines, MeetingService
from app.schemas.chat import Message


# ── Ollama helper methods ──────────────────────────────────────────────

def test_get_model_display_name_known():
    svc = OllamaService(base_url="http://x")
    assert svc.get_model_display_name("gemma4:e2b") == "Gemma 4B"


def test_get_model_display_name_unknown_passthrough():
    svc = OllamaService(base_url="http://x")
    assert svc.get_model_display_name("mystery:1b") == "mystery:1b"


def test_get_model_id_known_reverse():
    svc = OllamaService(base_url="http://x")
    assert svc.get_model_id("gemma4:latest") == "gemma-4b"


def test_get_model_id_unknown_normalizes():
    svc = OllamaService(base_url="http://x")
    assert svc.get_model_id("foo/bar:baz") == "foo-bar-baz"


def test_ollama_name_to_id_covers_models():
    for ollama_name in OLLAMA_MODELS.values():
        assert ollama_name in OLLAMA_NAME_TO_ID


def _patch_transport(monkeypatch, transport):
    orig_init = httpx.AsyncClient.__init__
    monkeypatch.setattr(
        httpx.AsyncClient,
        "__init__",
        lambda self, *a, **k: orig_init(self, *a, **{**k, "transport": transport}),
    )


@pytest.mark.asyncio
async def test_ollama_chat_returns_content(monkeypatch):
    captured = {}

    def handler(req):
        import json

        captured["body"] = json.loads(req.content)
        return httpx.Response(200, json={"message": {"content": "hi from ollama"}})

    _patch_transport(monkeypatch, httpx.MockTransport(handler))
    svc = OllamaService(base_url="http://ollama")
    out = await svc.chat("gemma-4b", [Message(role="user", content="yo")])
    assert out == "hi from ollama"
    # frontend id mapped to the ollama model name
    assert captured["body"]["model"] == OLLAMA_MODELS["gemma-4b"]


@pytest.mark.asyncio
async def test_ollama_chat_stream_yields_tokens(monkeypatch):
    lines = (
        b'{"message": {"content": "Hel"}}\n'
        b'{"message": {"content": "lo"}}\n'
        b'not-json\n'
        b'{"done": true}\n'
    )
    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=lines))
    _patch_transport(monkeypatch, transport)
    svc = OllamaService(base_url="http://ollama")
    tokens = []
    async for t in svc.chat_stream("gemma-4b", [Message(role="user", content="x")]):
        tokens.append(t)
    assert "".join(tokens) == "Hello"


@pytest.mark.asyncio
async def test_ollama_list_models_handles_error(monkeypatch):
    def boom(req):
        raise httpx.ConnectError("down")

    _patch_transport(monkeypatch, httpx.MockTransport(boom))
    svc = OllamaService(base_url="http://ollama")
    assert await svc.list_models() == []


@pytest.mark.asyncio
async def test_ollama_list_models_success(monkeypatch):
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"models": [{"name": "gemma4:e2b"}]})
    )
    _patch_transport(monkeypatch, transport)
    svc = OllamaService(base_url="http://ollama")
    models = await svc.list_models()
    assert models == [{"name": "gemma4:e2b"}]


# ── OpenRouter / NVIDIA error & happy paths ────────────────────────────

@pytest.mark.asyncio
async def test_openrouter_chat_no_key_raises():
    svc = OpenRouterService(api_key="")
    with pytest.raises(ValueError):
        await svc.chat("gpt-4o", [Message(role="user", content="hi")])


@pytest.mark.asyncio
async def test_openrouter_stream_no_key_raises():
    svc = OpenRouterService(api_key="")
    with pytest.raises(ValueError):
        async for _ in svc.chat_stream("gpt-4o", [Message(role="user", content="hi")]):
            pass


@pytest.mark.asyncio
async def test_openrouter_chat_success(monkeypatch):
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200, json={"choices": [{"message": {"content": "cloud reply"}}]}
        )
    )
    _patch_transport(monkeypatch, transport)
    svc = OpenRouterService(api_key="sk-test", base_url="http://or")
    out = await svc.chat("gpt-4o", [Message(role="user", content="hi")])
    assert out == "cloud reply"


@pytest.mark.asyncio
async def test_openrouter_stream_success(monkeypatch):
    body = (
        b'data: {"choices": [{"delta": {"content": "A"}}]}\n'
        b'data: {"choices": [{"delta": {"content": "B"}}]}\n'
        b'data: garbage\n'
        b'data: [DONE]\n'
    )
    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=body))
    _patch_transport(monkeypatch, transport)
    svc = OpenRouterService(api_key="sk-test", base_url="http://or")
    tokens = [
        t async for t in svc.chat_stream("gpt-4o", [Message(role="user", content="x")])
    ]
    assert "".join(tokens) == "AB"


def test_openrouter_model_map():
    assert OPENROUTER_MODELS["gpt-4o"] == "openai/gpt-4o"


@pytest.mark.asyncio
async def test_nvidia_chat_no_key_raises():
    svc = NvidiaService(api_key="")
    with pytest.raises(ValueError):
        await svc.chat("deepseek-v4", [Message(role="user", content="hi")])


@pytest.mark.asyncio
async def test_nvidia_chat_success(monkeypatch):
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200, json={"choices": [{"message": {"content": "nv reply"}}]}
        )
    )
    _patch_transport(monkeypatch, transport)
    svc = NvidiaService(api_key="nv-test")
    out = await svc.chat("deepseek-v4", [Message(role="user", content="hi")])
    assert out == "nv reply"


@pytest.mark.asyncio
async def test_nvidia_stream_no_key_raises():
    svc = NvidiaService(api_key="")
    with pytest.raises(ValueError):
        async for _ in svc.chat_stream("deepseek-v4", [Message(role="user", content="x")]):
            pass


@pytest.mark.asyncio
async def test_nvidia_stream_success(monkeypatch):
    body = (
        b'data: {"choices": [{"delta": {"content": "X"}}]}\n'
        b'data: [DONE]\n'
    )
    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=body))
    _patch_transport(monkeypatch, transport)
    svc = NvidiaService(api_key="nv-test")
    tokens = [
        t async for t in svc.chat_stream("deepseek-v4", [Message(role="user", content="x")])
    ]
    assert tokens == ["X"]


def test_nvidia_model_map():
    assert NVIDIA_MODELS["deepseek-v4"] == "deepseek-ai/deepseek-v4-pro"


# ── meeting action-line parsing ────────────────────────────────────────

def test_parse_action_lines_basic():
    raw = (
        "Some intro line\n"
        "ACTION: Ship the release | PRIORITY: high | ASSIGNEE: Alice\n"
        "ACTION: Write docs | PRIORITY: low | ASSIGNEE: unassigned\n"
    )
    items = _parse_action_lines(raw)
    assert len(items) == 2
    assert items[0].text == "Ship the release"
    assert items[0].priority == "high"
    assert items[0].assignee == "Alice"
    assert items[1].assignee is None


def test_parse_action_lines_invalid_priority_defaults_medium():
    raw = "ACTION: Do thing | PRIORITY: urgent | ASSIGNEE: Bob"
    items = _parse_action_lines(raw)
    assert items[0].priority == "medium"


def test_parse_action_lines_ignores_non_action():
    assert _parse_action_lines("no actions here\njust text") == []


def test_parse_action_lines_missing_fields():
    raw = "ACTION: Quick task"
    items = _parse_action_lines(raw)
    assert len(items) == 1
    assert items[0].text == "Quick task"
    assert items[0].priority == "medium"


# ── MeetingService._pick_model ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_meeting_service_pick_model(db):
    svc = MeetingService(db)
    known = next(iter(OLLAMA_MODELS.keys()))
    assert svc._pick_model(known) == known
    # unknown / None fall back to the same default model
    fallback = svc._pick_model(None)
    assert svc._pick_model("does-not-exist") == fallback
    assert fallback in OLLAMA_MODELS or fallback == "gemma-4b"
