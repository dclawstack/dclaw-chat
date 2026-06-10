"""Knowledge-graph API tests (V2 §4.2 Phase 3).

States probed: non-members get 403 on every graph route; members can search
entities, walk neighbors, and get a catch-me-up delta with citations; sending
a channel message fires the graph-indexing hook; the AI copilot returns graph
citations when given a workspace_id (and 403s non-members).
"""
import asyncio
import contextlib

import pytest

from app.core.deps import get_current_user, CurrentUser
from app.main import app
from app.repositories.graph_repo import GraphRepository
from app.services import graph_service
from app.services.graph_service import GraphService


@contextlib.contextmanager
def _as_user(user_id: str, email: str = "b@dclawstack.io"):
    async def _override():
        return CurrentUser(user_id=user_id, email=email, role="User")

    original = app.dependency_overrides[get_current_user]
    app.dependency_overrides[get_current_user] = _override
    try:
        yield
    finally:
        app.dependency_overrides[get_current_user] = original


async def _make_workspace(client) -> str:
    ws = await client.post("/api/v1/workspaces", json={"name": "Acme"})
    assert ws.status_code == 201
    return ws.json()["id"]


async def _seed_entities(db, ws_id: str):
    repo = GraphRepository(db)
    person = await repo.upsert_entity(
        ws_id, "person", "priya", source_type="message", source_id="m-1"
    )
    topic = await repo.upsert_entity(
        ws_id, "topic", "roadmap", source_type="message", source_id="m-1"
    )
    decision = await repo.upsert_entity(
        ws_id, "decision", "ship roadmap v2", source_type="message", source_id="m-2"
    )
    await repo.add_edge(ws_id, person.id, topic.id, "discussed_in", source_id="m-1")
    await repo.add_edge(ws_id, decision.id, person.id, "decided_by", source_id="m-2")
    return person, topic, decision


@pytest.mark.asyncio
async def test_non_member_gets_403_on_all_graph_routes(client, db):
    ws_id = await _make_workspace(client)
    person, _, _ = await _seed_entities(db, ws_id)

    with _as_user("outsider-1"):
        search = await client.get(f"/api/v1/graph/workspaces/{ws_id}/entities?q=ro")
        neighbors = await client.get(
            f"/api/v1/graph/workspaces/{ws_id}/entities/{person.id}/neighbors"
        )
        catchup = await client.get(f"/api/v1/graph/workspaces/{ws_id}/catch-me-up")
    assert search.status_code == 403
    assert neighbors.status_code == 403
    assert catchup.status_code == 403


@pytest.mark.asyncio
async def test_member_can_search_entities_with_kind_filter(client, db):
    ws_id = await _make_workspace(client)
    await _seed_entities(db, ws_id)

    resp = await client.get(f"/api/v1/graph/workspaces/{ws_id}/entities?q=roadmap")
    assert resp.status_code == 200
    names = {e["name"] for e in resp.json()}
    assert names == {"roadmap", "ship roadmap v2"}

    resp = await client.get(
        f"/api/v1/graph/workspaces/{ws_id}/entities?q=roadmap&kind=decision"
    )
    assert [e["kind"] for e in resp.json()] == ["decision"]


@pytest.mark.asyncio
async def test_member_can_walk_neighbors(client, db):
    ws_id = await _make_workspace(client)
    person, topic, decision = await _seed_entities(db, ws_id)

    resp = await client.get(
        f"/api/v1/graph/workspaces/{ws_id}/entities/{person.id}/neighbors?depth=1"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["entity"]["name"] == "priya"
    assert {e["id"] for e in body["entities"]} == {topic.id, decision.id}
    assert {e["relation"] for e in body["edges"]} == {"discussed_in", "decided_by"}

    # Entity from another workspace is invisible here
    other = await GraphRepository(db).upsert_entity("ws-other", "topic", "secret")
    resp = await client.get(
        f"/api/v1/graph/workspaces/{ws_id}/entities/{other.id}/neighbors"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_catch_me_up_returns_just_created_entities_with_citations(client, db):
    ws_id = await _make_workspace(client)
    await _seed_entities(db, ws_id)

    resp = await client.get(f"/api/v1/graph/workspaces/{ws_id}/catch-me-up")
    assert resp.status_code == 200
    body = resp.json()
    assert body["workspace_id"] == ws_id
    names = {c["name"] for c in body["entities"]}
    assert {"priya", "roadmap", "ship roadmap v2"} <= names
    decision = body["decisions"][0]
    assert decision["name"] == "ship roadmap v2"
    assert decision["source_type"] == "message"
    assert decision["source_id"] == "m-2"
    assert decision["updated_at"] is not None
    assert len(body["edges"]) == 2

    # since= in the future filters everything out
    resp = await client.get(
        f"/api/v1/graph/workspaces/{ws_id}/catch-me-up?since=2099-01-01T00:00:00"
    )
    assert resp.status_code == 200
    assert resp.json()["entities"] == []


@pytest.mark.asyncio
async def test_send_message_triggers_graph_indexing(client, db, monkeypatch):
    """REST send_message fires the fire-and-forget hook with the channel's
    workspace; running the extraction over that payload populates the graph."""
    from app.api.v1 import messaging

    captured = {}

    async def _capture(workspace_id, msg_dict):
        captured["workspace_id"] = workspace_id
        captured["msg"] = msg_dict

    monkeypatch.setattr(messaging, "_index_message_into_graph", _capture)

    async def _no_llm(*args, **kwargs):
        raise RuntimeError("LLM down in tests")

    monkeypatch.setattr(graph_service.router, "run", _no_llm)

    ws_id = await _make_workspace(client)
    ch = await client.post(
        "/api/v1/messaging/channels",
        json={"name": "eng", "workspace_id": ws_id},
    )
    ch_id = ch.json()["id"]
    resp = await client.post(
        f"/api/v1/messaging/channels/{ch_id}/messages",
        json={"content": "the api endpoint database query is broken"},
    )
    assert resp.status_code == 201
    msg_id = resp.json()["id"]

    # Let the created task run to completion deterministically.
    for _ in range(5):
        await asyncio.sleep(0)
    assert captured["workspace_id"] == ws_id
    assert captured["msg"]["id"] == msg_id

    # Extraction over the hook's payload lands rows in the graph.
    await GraphService.extract_from_message(db, ws_id, captured["msg"])
    repo = GraphRepository(db)
    ents = await repo.entities_for_source("message", msg_id)
    kinds = {(e.kind, e.name) for e in ents}
    assert ("person", "test") in kinds  # author from test@dclawstack.io
    assert ("topic", "backend") in kinds  # message's classified topic
    person = next(e for e in ents if e.kind == "person")
    neigh = await repo.neighbors(person.id)
    assert [e.relation for e in neigh["edges"]] == ["discussed_in"]


@pytest.mark.asyncio
async def test_ai_chat_returns_graph_citations_for_members(client, db, monkeypatch):
    async def _fake_chat(self, model, messages, temperature=0.7):
        return "the roadmap ships in Q3"

    from app.services.ollama_service import OllamaService

    monkeypatch.setattr(OllamaService, "chat", _fake_chat)

    ws_id = await _make_workspace(client)
    await _seed_entities(db, ws_id)

    resp = await client.post(
        "/api/v1/ai/chat",
        json={"query": "what is the roadmap status?", "workspace_id": ws_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "the roadmap ships in Q3"
    cited = {c["name"] for c in body["citations"]}
    assert "roadmap" in cited
    citation = next(c for c in body["citations"] if c["name"] == "roadmap")
    assert citation["kind"] == "topic"
    assert citation["source_type"] == "message"
    assert citation["source_id"] == "m-1"

    # Without workspace_id the field stays an empty list (back-compat).
    resp = await client.post("/api/v1/ai/chat", json={"query": "hello"})
    assert resp.status_code == 200
    assert resp.json()["citations"] == []


@pytest.mark.asyncio
async def test_ai_chat_403_for_non_member_workspace(client, db, monkeypatch):
    async def _fake_chat(self, model, messages, temperature=0.7):
        return "nope"

    from app.services.ollama_service import OllamaService

    monkeypatch.setattr(OllamaService, "chat", _fake_chat)

    ws_id = await _make_workspace(client)
    with _as_user("outsider-1"):
        resp = await client.post(
            "/api/v1/ai/chat",
            json={"query": "leak the roadmap", "workspace_id": ws_id},
        )
    assert resp.status_code == 403
