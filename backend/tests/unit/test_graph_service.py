"""Unit tests for the knowledge-graph service + repository (V2 §4.2 Phase 3).

States probed:
* LLM path with a well-formed (fenced) JSON reply from the router
* keyword fallback when the router raises (extraction must fail soft)
* upsert/edge dedupe semantics (one entity row; weight bumps on new sources)
* catch-me-up returns citations for just-created entities
"""
from types import SimpleNamespace

import pytest

from app.repositories.graph_repo import GraphRepository
from app.services import graph_service
from app.services.graph_service import GraphService, _parse_extraction

WS = "ws-graph-unit"


def _msg(content: str, topic: str = None, msg_id: str = "msg-1") -> dict:
    return {
        "id": msg_id,
        "user_id": "u-alice",
        "user_name": "alice",
        "content": content,
        "topic": topic,
    }


@pytest.mark.asyncio
async def test_llm_extraction_persists_entities_and_relations(db, monkeypatch):
    reply = (
        "```json\n"
        '{"entities": [{"kind": "topic", "name": "deploy pipeline"},'
        ' {"kind": "decision", "name": "ship Friday"}],'
        ' "relations": [{"src": "alice", "dst": "deploy pipeline", "relation": "discussed_in"},'
        ' {"src": "ship Friday", "dst": "alice", "relation": "decided_by"}]}'
        "\n```"
    )

    async def _fake_run(task, messages, **kwargs):
        assert task == "classify"
        return SimpleNamespace(content=reply)

    monkeypatch.setattr(graph_service.router, "run", _fake_run)

    result = await GraphService.extract_from_message(db, WS, _msg("we ship friday"))
    assert result["method"] == "llm"

    repo = GraphRepository(db)
    ents = await repo.entities_for_source("message", "msg-1")
    by_kind = {(e.kind, e.name) for e in ents}
    assert ("person", "alice") in by_kind
    assert ("topic", "deploy pipeline") in by_kind
    assert ("decision", "ship Friday") in by_kind

    person = next(e for e in ents if e.kind == "person")
    neigh = await repo.neighbors(person.id)
    relations = {e.relation for e in neigh["edges"]}
    assert relations == {"discussed_in", "decided_by"}


@pytest.mark.asyncio
async def test_keyword_fallback_when_router_raises(db, monkeypatch):
    async def _boom(*args, **kwargs):
        raise RuntimeError("ollama is down")

    monkeypatch.setattr(graph_service.router, "run", _boom)

    msg = _msg("the api endpoint is broken", topic="backend", msg_id="msg-2")
    result = await GraphService.extract_from_message(db, WS, msg)
    assert result["method"] == "keyword"

    repo = GraphRepository(db)
    ents = await repo.entities_for_source("message", "msg-2")
    by_kind = {(e.kind, e.name) for e in ents}
    assert ("person", "alice") in by_kind
    assert ("topic", "backend") in by_kind  # reused the message's topic

    topic = next(e for e in ents if e.kind == "topic")
    neigh = await repo.neighbors(topic.id)
    assert [e.relation for e in neigh["edges"]] == ["discussed_in"]


@pytest.mark.asyncio
async def test_keyword_fallback_classifies_when_topic_missing(db, monkeypatch):
    async def _boom(*args, **kwargs):
        raise RuntimeError("no llm")

    monkeypatch.setattr(graph_service.router, "run", _boom)

    await GraphService.extract_from_message(
        db, WS, _msg("docker deploy pipeline failed in ci", msg_id="msg-3")
    )
    repo = GraphRepository(db)
    topics = await repo.search_entities(WS, "devops", kinds=["topic"])
    assert len(topics) == 1


@pytest.mark.asyncio
async def test_llm_garbage_output_falls_back(db, monkeypatch):
    async def _garbage(*args, **kwargs):
        return SimpleNamespace(content="Sure! Here are the entities I found:")

    monkeypatch.setattr(graph_service.router, "run", _garbage)

    result = await GraphService.extract_from_message(
        db, WS, _msg("hello there", msg_id="msg-4")
    )
    assert result["method"] == "keyword"
    repo = GraphRepository(db)
    assert await repo.entities_for_source("message", "msg-4")


def test_parse_extraction_tolerates_partial_and_fences():
    parsed = _parse_extraction('```json\n{"entities": [{"kind": "topic", "name": "x"}]}\n```')
    assert parsed == {"entities": [{"kind": "topic", "name": "x"}], "relations": []}
    # prose around the JSON object is stripped
    parsed = _parse_extraction('Answer: {"relations": null} thanks')
    assert parsed == {"entities": [], "relations": []}
    with pytest.raises(Exception):
        _parse_extraction("not json at all")


@pytest.mark.asyncio
async def test_upsert_entity_dedupes_and_bumps(db):
    repo = GraphRepository(db)
    first = await repo.upsert_entity(WS, "topic", "Roadmap", source_id="s1")
    again = await repo.upsert_entity(
        WS, "topic", "roadmap", summary="Q3 plan", source_id="s2"
    )
    assert again.id == first.id  # case-insensitive dedupe → one row
    assert again.summary == "Q3 plan"
    assert again.source_id == "s2"
    rows = await repo.search_entities(WS, "roadmap")
    assert len(rows) == 1

    # Different workspace → distinct entity
    other = await repo.upsert_entity("ws-other", "topic", "Roadmap")
    assert other.id != first.id


@pytest.mark.asyncio
async def test_add_edge_dedupes_same_source_and_weights_new_source(db):
    repo = GraphRepository(db)
    a = await repo.upsert_entity(WS, "person", "alice")
    t = await repo.upsert_entity(WS, "topic", "backend")

    e1 = await repo.add_edge(WS, a.id, t.id, "discussed_in", source_id="m1")
    assert e1.weight == 1
    # Identical (src, dst, relation, source_id) → dedupe, weight unchanged
    e2 = await repo.add_edge(WS, a.id, t.id, "discussed_in", source_id="m1")
    assert e2.id == e1.id and e2.weight == 1
    # Same edge observed from a new source → weight increments, still one row
    e3 = await repo.add_edge(WS, a.id, t.id, "discussed_in", source_id="m2")
    assert e3.id == e1.id and e3.weight == 2

    neigh = await repo.neighbors(a.id)
    assert len(neigh["edges"]) == 1


@pytest.mark.asyncio
async def test_neighbors_depth_two(db):
    repo = GraphRepository(db)
    a = await repo.upsert_entity(WS, "person", "alice")
    t = await repo.upsert_entity(WS, "topic", "backend")
    d = await repo.upsert_entity(WS, "decision", "use postgres")
    await repo.add_edge(WS, a.id, t.id, "discussed_in")
    await repo.add_edge(WS, d.id, t.id, "mentioned_with")

    one_hop = await repo.neighbors(a.id, depth=1)
    assert {e.id for e in one_hop["entities"]} == {t.id}
    two_hop = await repo.neighbors(a.id, depth=2)
    assert {e.id for e in two_hop["entities"]} == {t.id, d.id}


@pytest.mark.asyncio
async def test_catch_me_up_returns_citations(db, monkeypatch):
    async def _boom(*args, **kwargs):
        raise RuntimeError("no llm")

    monkeypatch.setattr(graph_service.router, "run", _boom)
    await GraphService.extract_from_message(
        db, WS, _msg("fix the login bug", topic="bug", msg_id="msg-cm")
    )
    repo = GraphRepository(db)
    await repo.upsert_entity(
        WS, "action_item", "patch login", source_type="message", source_id="msg-cm"
    )

    summary = await GraphService.catch_me_up(db, WS)
    names = {c["name"] for c in summary["entities"]}
    assert {"alice", "bug", "patch login"} <= names
    # citations carry the source pointer back to the message
    cited = next(c for c in summary["entities"] if c["name"] == "bug")
    assert cited["source_type"] == "message"
    assert cited["source_id"] == "msg-cm"
    assert cited["updated_at"] is not None
    assert [c["name"] for c in summary["action_items"]] == ["patch login"]
    assert summary["edges"]  # alice -discussed_in-> bug
