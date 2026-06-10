import pytest

from app.services.chat_service import ChatService, MODEL_PROVIDERS
from app.services.meeting_service import WhisperService, MeetingService
from app.schemas.chat import Message, ChatCompletionRequest
from app.core.exceptions import LLMException


def test_model_providers_routing_table():
    assert MODEL_PROVIDERS["gemma-4b"] == "local"
    assert MODEL_PROVIDERS["gpt-4o"] == "cloud"
    assert MODEL_PROVIDERS["deepseek-v4"] == "nvidia"


@pytest.mark.asyncio
async def test_complete_creates_conversation_and_stores_messages(db, monkeypatch):
    svc = ChatService(db)

    async def fake_chat(model, messages, temperature):
        return "assistant says hello"

    monkeypatch.setattr(svc.ollama, "chat", fake_chat)

    req = ChatCompletionRequest(
        conversation_id="conv-abc",
        model="gemma-4b",
        messages=[Message(role="user", content="hi there what is up")],
        temperature=0.5,
    )
    resp = await svc.complete(req)
    assert resp.message.content == "assistant says hello"
    assert resp.model == "gemma-4b"

    # conversation got created
    conv = await svc.conv_repo.get_by_id("conv-abc")
    assert conv is not None
    # user + assistant messages stored
    msgs = await svc.msg_repo.list_by_conversation("conv-abc")
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[1].role == "assistant"
    assert msgs[1].content == "assistant says hello"


@pytest.mark.asyncio
async def test_complete_routes_to_nvidia(db, monkeypatch):
    svc = ChatService(db)

    async def fake_nv(model, messages, temperature):
        return "from nvidia"

    monkeypatch.setattr(svc.nvidia, "chat", fake_nv)
    req = ChatCompletionRequest(
        conversation_id="c-nv",
        model="deepseek-v4",
        messages=[Message(role="user", content="hello")],
    )
    resp = await svc.complete(req)
    assert resp.message.content == "from nvidia"


@pytest.mark.asyncio
async def test_complete_routes_to_cloud(db, monkeypatch):
    svc = ChatService(db)

    async def fake_or(model, messages, temperature):
        return "from openrouter"

    monkeypatch.setattr(svc.openrouter, "chat", fake_or)
    req = ChatCompletionRequest(
        conversation_id="c-or",
        model="gpt-4o",
        messages=[Message(role="user", content="hello")],
    )
    resp = await svc.complete(req)
    assert resp.message.content == "from openrouter"


@pytest.mark.asyncio
async def test_complete_provider_error_raises_llm_exception(db, monkeypatch):
    svc = ChatService(db)

    async def boom(model, messages, temperature):
        raise RuntimeError("upstream 500")

    monkeypatch.setattr(svc.ollama, "chat", boom)
    req = ChatCompletionRequest(
        conversation_id="c-err",
        model="gemma-4b",
        messages=[Message(role="user", content="hello")],
    )
    with pytest.raises(LLMException):
        await svc.complete(req)


@pytest.mark.asyncio
async def test_stream_complete_collects_and_persists(db, monkeypatch):
    svc = ChatService(db)

    async def fake_stream(model, messages, temperature):
        for tok in ["Hel", "lo!"]:
            yield tok

    monkeypatch.setattr(svc.ollama, "chat_stream", fake_stream)
    req = ChatCompletionRequest(
        conversation_id="c-stream",
        model="gemma-4b",
        messages=[Message(role="user", content="stream please")],
    )
    collected = [tok async for tok in svc.stream_complete(req)]
    assert "".join(collected) == "Hello!"

    msgs = await svc.msg_repo.list_by_conversation("c-stream")
    assert msgs[-1].content == "Hello!"
    assert msgs[-1].role == "assistant"


@pytest.mark.asyncio
async def test_stream_complete_error_raises(db, monkeypatch):
    svc = ChatService(db)

    async def boom(model, messages, temperature):
        raise RuntimeError("dead")
        yield  # pragma: no cover

    monkeypatch.setattr(svc.ollama, "chat_stream", boom)
    req = ChatCompletionRequest(
        conversation_id="c-stream-err",
        model="gemma-4b",
        messages=[Message(role="user", content="x")],
    )
    with pytest.raises(LLMException):
        async for _ in svc.stream_complete(req):
            pass


@pytest.mark.asyncio
async def test_list_models_includes_cloud_and_local(db, monkeypatch):
    svc = ChatService(db)

    async def fake_list():
        return [
            {"name": "gemma4:e2b", "size": 5_000_000_000},
            {"name": "nomic-embed-text", "size": 100},  # filtered out
        ]

    monkeypatch.setattr(svc.ollama, "list_models", fake_list)
    # force known api keys for deterministic availability
    svc.openrouter.api_key = "sk-or"
    svc.nvidia.api_key = "nv"

    models = await svc.list_models()
    ids = {m["id"] for m in models}
    # embed model filtered out
    assert all("embed" not in mid for mid in ids)
    # cloud models present and available
    cloud = {m["id"]: m for m in models if m["provider"] == "cloud"}
    assert cloud["gpt-4o"]["available"] is True
    assert cloud["deepseek-v4"]["available"] is True
    # at least one local model
    assert any(m["provider"] == "local" for m in models)


@pytest.mark.asyncio
async def test_list_models_cloud_unavailable_without_keys(db, monkeypatch):
    svc = ChatService(db)

    async def fake_list():
        return []

    monkeypatch.setattr(svc.ollama, "list_models", fake_list)
    svc.openrouter.api_key = ""
    svc.nvidia.api_key = ""
    models = await svc.list_models()
    cloud = [m for m in models if m["provider"] == "cloud"]
    assert all(m["available"] is False for m in cloud)
    # fallback local entries appear (not installed)
    local = [m for m in models if m["provider"] == "local"]
    assert any(m["available"] is False for m in local)


# ── WhisperService ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_whisper_no_key_returns_placeholder(tmp_path):
    svc = WhisperService()
    svc.api_key = ""
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"fake audio")
    out = await svc.transcribe(audio, "audio/mpeg")
    assert "Transcription unavailable" in out


# ── MeetingService._transcribe guards ──────────────────────────────────

@pytest.mark.asyncio
async def test_meeting_transcribe_no_file_raises(db):
    from app.models.meeting import MeetingORM

    svc = MeetingService(db)
    meeting = MeetingORM(id="m1", title="t", status="pending")
    with pytest.raises(ValueError):
        await svc._transcribe(meeting)


@pytest.mark.asyncio
async def test_meeting_transcribe_missing_file_raises(db):
    from app.models.meeting import MeetingORM

    svc = MeetingService(db)
    meeting = MeetingORM(
        id="m2", title="t", status="pending",
        file_id="nope", filename="x.mp3", mime_type="audio/mpeg",
    )
    with pytest.raises(FileNotFoundError):
        await svc._transcribe(meeting)
