import pytest

from app.services.chat_ai import (
    ChatAIService,
    _score_relevance,
    _retrieve_context,
    DEFAULT_MODEL,
)
from app.services.ollama_service import OLLAMA_MODELS
from app.schemas.ai import (
    AIChatRequest,
    SummarizeRequest,
    ActionsRequest,
    InlineMessage,
)
from app.schemas.conversation import ConversationCreate


# ── pure scoring / retrieval helpers ───────────────────────────────────

def test_score_relevance_overlap():
    score = _score_relevance("deploy production", "we should deploy to production now")
    assert score > 0


def test_score_relevance_no_overlap():
    assert _score_relevance("apples", "totally unrelated text") == 0.0


def test_score_relevance_empty():
    assert _score_relevance("", "anything") == 0.0
    assert _score_relevance("query", "") == 0.0


class _Msg:
    def __init__(self, role, content):
        self.role = role
        self.content = content


def test_retrieve_context_ranks_relevant():
    msgs = [
        _Msg("user", "talk about kubernetes deployment strategy"),
        _Msg("assistant", "the weather is nice today"),
        _Msg("system", "ignored system message"),
    ]
    out = _retrieve_context("kubernetes deployment", msgs, top_k=2)
    assert any("kubernetes" in s.lower() for s in out)
    # system messages are excluded
    assert all("ignored system" not in s for s in out)


def test_retrieve_context_fallback_to_recent():
    msgs = [
        _Msg("user", "aaa"),
        _Msg("assistant", "bbb"),
    ]
    out = _retrieve_context("zzz no match", msgs, top_k=5)
    # no keyword overlap -> falls back to recent messages
    assert len(out) == 2


# ── ChatAIService._pick_model ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_pick_model_known_and_default(db):
    svc = ChatAIService(db)
    known = next(iter(OLLAMA_MODELS.keys()))
    assert svc._pick_model(known) == OLLAMA_MODELS[known]
    assert svc._pick_model("nope") == DEFAULT_MODEL
    assert svc._pick_model(None) == DEFAULT_MODEL


# ── chat ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_without_context(db, monkeypatch):
    svc = ChatAIService(db)

    async def fake_chat(model, messages, temperature=0.7):
        return "copilot answer"

    monkeypatch.setattr(svc.ollama, "chat", fake_chat)
    resp = await svc.chat(AIChatRequest(query="hi", conversation_id=None))
    assert resp.answer == "copilot answer"
    assert resp.rag_chunks_used == 0
    assert resp.context_snippets == []


@pytest.mark.asyncio
async def test_chat_with_rag_context(db, monkeypatch):
    conv_repo = svc_conv = None
    svc = ChatAIService(db)
    conv = await svc.conv_repo.create(ConversationCreate(id="c-rag", title="t"))
    await svc.msg_repo.create(conv.id, "user", "discuss the database migration plan")
    await svc.msg_repo.create(conv.id, "assistant", "the database migration is scheduled")

    captured = {}

    async def fake_chat(model, messages, temperature=0.7):
        captured["messages"] = messages
        return "with context"

    monkeypatch.setattr(svc.ollama, "chat", fake_chat)
    resp = await svc.chat(
        AIChatRequest(
            query="database migration", conversation_id="c-rag", include_context=True
        )
    )
    assert resp.answer == "with context"
    assert resp.rag_chunks_used > 0
    assert resp.context_snippets  # populated since include_context=True
    # system prompt includes context block
    assert "CONVERSATION CONTEXT" in captured["messages"][0].content


# ── summarize ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_summarize_no_messages(db):
    svc = ChatAIService(db)
    resp = await svc.summarize(SummarizeRequest(conversation_id="empty"))
    assert resp.message_count == 0
    assert "No messages" in resp.summary


@pytest.mark.asyncio
async def test_summarize_from_inline_messages(db, monkeypatch):
    svc = ChatAIService(db)

    async def fake_chat(model, messages, temperature=0.7):
        return "  a concise summary  "

    monkeypatch.setattr(svc.ollama, "chat", fake_chat)
    resp = await svc.summarize(
        SummarizeRequest(
            conversation_id="not-in-db",
            messages=[
                InlineMessage(role="user", content="hello"),
                InlineMessage(role="assistant", content="hi back"),
            ],
        )
    )
    assert resp.summary == "a concise summary"
    assert resp.message_count == 2


@pytest.mark.asyncio
async def test_summarize_from_db_history(db, monkeypatch):
    svc = ChatAIService(db)
    conv = await svc.conv_repo.create(ConversationCreate(id="c-sum", title="t"))
    await svc.msg_repo.create(conv.id, "user", "what is the plan")
    await svc.msg_repo.create(conv.id, "assistant", "the plan is X")

    async def fake_chat(model, messages, temperature=0.7):
        return "summary text"

    monkeypatch.setattr(svc.ollama, "chat", fake_chat)
    resp = await svc.summarize(SummarizeRequest(conversation_id="c-sum"))
    assert resp.summary == "summary text"
    assert resp.message_count == 2


# ── extract_actions ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_actions_no_messages(db):
    svc = ChatAIService(db)
    resp = await svc.extract_actions(ActionsRequest(conversation_id="empty"))
    assert resp.actions == []


@pytest.mark.asyncio
async def test_extract_actions_parses_lines(db, monkeypatch):
    svc = ChatAIService(db)

    async def fake_chat(model, messages, temperature=0.7):
        return (
            "ACTION: Deploy app | PRIORITY: high | ASSIGNEE: Alice\n"
            "ACTION: Update docs | PRIORITY: bogus | ASSIGNEE: unassigned\n"
            "irrelevant line\n"
        )

    monkeypatch.setattr(svc.ollama, "chat", fake_chat)
    resp = await svc.extract_actions(
        ActionsRequest(
            conversation_id="x",
            messages=[InlineMessage(role="user", content="we need to deploy")],
        )
    )
    assert len(resp.actions) == 2
    assert resp.actions[0].text == "Deploy app"
    assert resp.actions[0].priority == "high"
    assert resp.actions[0].assignee == "Alice"
    # invalid priority normalized to medium, unassigned -> None
    assert resp.actions[1].priority == "medium"
    assert resp.actions[1].assignee is None
