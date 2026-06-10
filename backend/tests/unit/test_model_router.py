"""Unit tests for the model-routing/consensus layer (Phase 4 groundwork).

Covers: routing-table loading, T0/T1/T2 tier behavior with monkeypatched
providers, fail-soft escalation, per-process stats, the router-stats endpoint,
and the benchmark harness's --dry-run path.
"""

import json

import pytest

from app.core.exceptions import LLMException
from app.schemas.chat import Message
from app.services.model_router import ModelRouter, RouterResult, ROUTES_PATH
from app.services.ollama_service import OllamaService
from app.services.openrouter_service import OpenRouterService

MSGS = [Message(role="user", content="hello team, what's the plan?")]


@pytest.fixture(autouse=True)
def _reset_stats():
    ModelRouter.reset_stats()
    yield
    ModelRouter.reset_stats()


def _router(cloud: bool = False) -> ModelRouter:
    r = ModelRouter()
    r.openrouter.api_key = "test-key" if cloud else ""
    return r


# ── routing table ────────────────────────────────────────────────────────────

def test_default_routes_file_is_valid_json():
    with open(ROUTES_PATH) as f:
        routes = json.load(f)
    for task in ("classify", "summarize", "extract_actions", "chat"):
        assert task in routes, f"missing task class: {task}"
        assert routes[task]["tier"] in ("T0", "T1", "T2")
    assert routes["classify"]["tier"] == "T0"
    assert routes["summarize"]["tier"] == "T1"
    assert "fallback" in routes["summarize"]
    assert routes["extract_actions"]["tier"] == "T2"
    assert isinstance(routes["extract_actions"]["models"], list)
    assert "judge" in routes["extract_actions"]


def test_router_loads_routes_on_init():
    r = ModelRouter()
    assert r.routes
    assert r.routes["classify"]["model"] == "gemma-4b"


# ── T0 ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t0_uses_ollama_and_never_calls_cloud(monkeypatch):
    async def fake_local(self, model, messages, temperature=0.7):
        return "bug"

    async def cloud_forbidden(self, model, messages, temperature=0.7):
        raise AssertionError("cloud must not be called for a T0 task")

    monkeypatch.setattr(OllamaService, "chat", fake_local)
    monkeypatch.setattr(OpenRouterService, "chat", cloud_forbidden)

    r = _router(cloud=True)  # even with a key configured, T0 stays local
    result = await r.run("classify", MSGS)

    assert isinstance(result, RouterResult)
    assert result.content == "bug"
    assert result.model_used == "gemma-4b"
    assert result.tier == "T0"
    assert result.escalated is False
    assert result.calls == 1
    stats = ModelRouter.stats()
    assert stats["local_calls"] == 1 and stats["cloud_calls"] == 0


# ── T1 ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t1_falls_back_to_cloud_when_local_fails(monkeypatch):
    async def broken_local(self, model, messages, temperature=0.7):
        raise RuntimeError("ollama down")

    async def fake_cloud(self, model, messages, temperature=0.7):
        return "cloud summary"

    monkeypatch.setattr(OllamaService, "chat", broken_local)
    monkeypatch.setattr(OpenRouterService, "chat", fake_cloud)

    r = _router(cloud=True)
    result = await r.run("summarize", MSGS)

    assert result.content == "cloud summary"
    assert result.model_used == "kimi-k2.5"
    assert result.tier == "T1"
    assert result.escalated is True
    assert result.calls == 2


@pytest.mark.asyncio
async def test_t1_raises_llm_exception_when_local_and_cloud_unavailable(monkeypatch):
    async def broken_local(self, model, messages, temperature=0.7):
        raise RuntimeError("ollama down")

    async def cloud_forbidden(self, model, messages, temperature=0.7):
        raise AssertionError("cloud must not be called when unconfigured")

    monkeypatch.setattr(OllamaService, "chat", broken_local)
    monkeypatch.setattr(OpenRouterService, "chat", cloud_forbidden)

    r = _router(cloud=False)
    with pytest.raises(LLMException):
        await r.run("summarize", MSGS)


@pytest.mark.asyncio
async def test_t1_stays_local_when_local_works(monkeypatch):
    async def fake_local(self, model, messages, temperature=0.7):
        return "local summary"

    async def cloud_forbidden(self, model, messages, temperature=0.7):
        raise AssertionError("cloud must not be called when local succeeds")

    monkeypatch.setattr(OllamaService, "chat", fake_local)
    monkeypatch.setattr(OpenRouterService, "chat", cloud_forbidden)

    r = _router(cloud=True)
    result = await r.run("summarize", MSGS)
    assert result.content == "local summary"
    assert result.escalated is False
    assert result.calls == 1


# ── T2 consensus ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t2_agreement_skips_judge(monkeypatch):
    cloud_calls = []

    async def fake_local(self, model, messages, temperature=0.7):
        return "Alice to update the helm chart."

    async def fake_cloud(self, model, messages, temperature=0.7):
        cloud_calls.append(model)
        return "alice to update the helm chart"  # similar after normalization

    monkeypatch.setattr(OllamaService, "chat", fake_local)
    monkeypatch.setattr(OpenRouterService, "chat", fake_cloud)

    r = _router(cloud=True)
    result = await r.run("extract_actions", MSGS)

    assert result.tier == "T2"
    assert result.escalated is False
    assert result.calls == 2
    assert result.model_used.startswith("consensus:")
    assert "helm chart" in result.content.lower()
    assert len(cloud_calls) == 1, "judge must not run when models agree"


@pytest.mark.asyncio
async def test_t2_disagreement_invokes_judge(monkeypatch):
    cloud_calls = []

    async def fake_local(self, model, messages, temperature=0.7):
        return "Alice to update the helm chart before Friday."

    async def fake_cloud(self, model, messages, temperature=0.7):
        cloud_calls.append(model)
        if len(cloud_calls) == 1:
            return "Zoe must rotate every database credential immediately."
        return "judged final answer"

    monkeypatch.setattr(OllamaService, "chat", fake_local)
    monkeypatch.setattr(OpenRouterService, "chat", fake_cloud)

    r = _router(cloud=True)
    result = await r.run("extract_actions", MSGS)

    assert result.content == "judged final answer"
    assert result.model_used == "judge:kimi-k2.5"
    assert result.escalated is True
    assert result.calls == 3
    assert len(cloud_calls) == 2, "expected one member call + one judge call"


@pytest.mark.asyncio
async def test_t2_single_available_model_degrades_to_single_call(monkeypatch):
    async def fake_local(self, model, messages, temperature=0.7):
        return "solo answer"

    async def cloud_forbidden(self, model, messages, temperature=0.7):
        raise AssertionError("cloud unconfigured: must be skipped, not called")

    monkeypatch.setattr(OllamaService, "chat", fake_local)
    monkeypatch.setattr(OpenRouterService, "chat", cloud_forbidden)

    r = _router(cloud=False)
    result = await r.run("extract_actions", MSGS)

    assert result.content == "solo answer"
    assert result.model_used == "gemma-4b"
    assert result.tier == "T2"
    assert result.escalated is False
    assert result.calls == 1


# ── stats ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stats_local_fraction_after_mixed_sequence(monkeypatch):
    local_ok = True

    async def fake_local(self, model, messages, temperature=0.7):
        if not local_ok:
            raise RuntimeError("ollama down")
        return "ok"

    async def fake_cloud(self, model, messages, temperature=0.7):
        return "cloud ok"

    monkeypatch.setattr(OllamaService, "chat", fake_local)
    monkeypatch.setattr(OpenRouterService, "chat", fake_cloud)

    r = _router(cloud=True)
    await r.run("classify", MSGS)   # local
    await r.run("summarize", MSGS)  # local
    local_ok = False
    await r.run("summarize", MSGS)  # local fails (not counted) → cloud

    stats = ModelRouter.stats()
    assert stats["total_calls"] == 3
    assert stats["local_calls"] == 2
    assert stats["cloud_calls"] == 1
    assert stats["local_fraction"] == pytest.approx(2 / 3)


def test_stats_zero_calls_has_zero_fraction():
    stats = ModelRouter.stats()
    assert stats == {
        "total_calls": 0,
        "local_calls": 0,
        "cloud_calls": 0,
        "local_fraction": 0.0,
    }


# ── endpoint ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_router_stats_endpoint(client):
    resp = await client.get("/api/v1/models/router-stats")
    assert resp.status_code == 200
    data = resp.json()
    for field in ("total_calls", "local_calls", "cloud_calls", "local_fraction"):
        assert field in data
    assert isinstance(data["local_fraction"], float)


# ── benchmark harness ────────────────────────────────────────────────────────

def test_benchmark_runner_dry_run_emits_scorecard(capsys):
    from benchmarks.run_benchmarks import main

    rows = main(["--dry-run"])
    out = capsys.readouterr().out
    assert "MODEL ROUTING SCORECARD" in out
    assert "(dry run" in out
    assert rows, "dry run should produce scorecard rows"
    tasks = {r["task"] for r in rows}
    assert tasks == {"classify", "summarize", "extract_actions"}
    for r in rows:
        assert 0.0 <= r["quality"] <= 1.0
        assert r["out_tokens"] >= 0
