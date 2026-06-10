"""Knowledge-graph extraction service (V2 plan §4.2, Phase 3 groundwork).

Primary path: a T0 ``classify`` call through the :mod:`model_router` asks the
local model for compact JSON entities/relations. The whole LLM path is wrapped
in a try/except — on ANY failure (router down, garbage output, partial JSON)
we degrade to :func:`_keyword_extract`, which reuses the message's keyword
topic. Graph extraction must NEVER break message sending; callers additionally
fire-and-forget this from outside the request path.
"""
import json
import logging
import re
from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import ENTITY_KINDS, EDGE_RELATIONS
from app.repositories.graph_repo import GraphRepository
from app.services.model_router import router

logger = logging.getLogger(__name__)

#: Compact T0 prompt — asks for ≤300 output tokens of bare JSON.
EXTRACTION_SYSTEM_PROMPT = (
    "You extract a knowledge graph from one team-chat message. "
    "Reply with ONLY compact JSON, no prose, no markdown, in this shape:\n"
    '{"entities":[{"kind":"person|topic|decision|action_item|file|meeting",'
    '"name":"short canonical name"}],'
    '"relations":[{"src":"<entity name>","dst":"<entity name>",'
    '"relation":"discussed_in|decided_by|assigned_to|mentioned_with|supersedes"}]}\n'
    "At most 6 entities and 6 relations. Omit anything uncertain."
)

# Fallback keyword → topic map (mirrors the messaging.py classifier so the
# graph and the per-message `topic` badge agree).
_KEYWORD_TOPICS: dict[str, list[str]] = {
    "frontend": ["react", "css", "html", "ui", "component", "tailwind", "layout", "page", "frontend"],
    "backend": ["api", "server", "endpoint", "database", "sql", "fastapi", "schema", "query", "backend"],
    "devops": ["docker", "kubernetes", "k8s", "deploy", "pipeline", "helm", "nginx", "build", "ci"],
    "design": ["design", "ux", "figma", "wireframe", "mockup", "typography", "icon"],
    "bug": ["bug", "fix", "error", "crash", "issue", "broken", "fail", "exception"],
    "feature": ["feature", "implement", "build", "create", "enhance", "improve", "support"],
    "question": ["?", "how", "why", "what", "where", "when", "help"],
}


def _strip_fences(text: str) -> str:
    """Remove markdown code fences and isolate the outermost JSON object."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


def _parse_extraction(raw: str) -> dict:
    """Defensive parse of the LLM reply. Raises ValueError when hopeless;
    tolerates partial/extra keys otherwise."""
    data = json.loads(_strip_fences(raw))
    if not isinstance(data, dict):
        raise ValueError("extraction reply is not a JSON object")
    entities = data.get("entities") or []
    relations = data.get("relations") or []
    return {
        "entities": [e for e in entities if isinstance(e, dict)],
        "relations": [r for r in relations if isinstance(r, dict)],
    }


def _classify_topic(content: str) -> str:
    lower = content.lower()
    scores = {
        topic: sum(1 for kw in kws if kw in lower)
        for topic, kws in _KEYWORD_TOPICS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


class GraphService:
    """Stateless service: every method takes the caller's ``AsyncSession``."""

    # ── extraction ───────────────────────────────────────────────────────

    @staticmethod
    async def _llm_extract(author_name: str, content: str) -> dict:
        result = await router.run(
            "classify",
            [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Author: {author_name}\nMessage: {content[:800]}"},
            ],
            temperature=0.0,
        )
        return _parse_extraction(result.content)

    @staticmethod
    def _keyword_extract(author_name: str, message: dict) -> dict:
        """Zero-LLM fallback: reuse the message's classified ``topic`` (set by
        messaging.py) or re-derive it from the keyword map; link the author to
        that topic."""
        topic = message.get("topic") or _classify_topic(message.get("content") or "")
        return {
            "entities": [{"kind": "topic", "name": topic}],
            "relations": [
                {"src": author_name, "dst": topic, "relation": "discussed_in"}
            ],
        }

    @staticmethod
    async def extract_from_message(
        db: AsyncSession, workspace_id: Optional[str], message: dict
    ) -> dict:
        """Extract entities/relations from one message dict and persist them.

        Always upserts the author as a person entity and stamps every
        extracted entity with source_type="message"/source_id=<message id>.
        Returns a small summary dict (method used, counts).
        """
        msg_id = message.get("id")
        content = (message.get("content") or "").strip()
        author_name = (
            message.get("user_name") or message.get("user_id") or "unknown"
        ).strip()

        method = "llm"
        try:
            extraction = await GraphService._llm_extract(author_name, content)
        except Exception as e:
            logger.warning(
                f"LLM graph extraction failed for message {msg_id}, "
                f"falling back to keywords: {e}"
            )
            method = "keyword"
            extraction = GraphService._keyword_extract(author_name, message)

        repo = GraphRepository(db)
        author = await repo.upsert_entity(
            workspace_id, "person", author_name,
            source_type="message", source_id=msg_id,
        )
        by_name = {author_name.lower(): author}

        for item in extraction.get("entities", []):
            name = str(item.get("name") or "").strip()[:255]
            if not name:
                continue
            kind = item.get("kind")
            if kind not in ENTITY_KINDS:
                kind = "topic"
            if name.lower() in by_name:
                continue
            entity = await repo.upsert_entity(
                workspace_id, kind, name,
                source_type="message", source_id=msg_id,
            )
            by_name[name.lower()] = entity

        edge_count = 0
        for rel in extraction.get("relations", []):
            src = by_name.get(str(rel.get("src") or "").strip().lower())
            dst = by_name.get(str(rel.get("dst") or "").strip().lower())
            if not src or not dst or src.id == dst.id:
                continue
            relation = rel.get("relation")
            if relation not in EDGE_RELATIONS:
                relation = "mentioned_with"
            await repo.add_edge(
                workspace_id, src.id, dst.id, relation, source_id=msg_id
            )
            edge_count += 1

        return {"method": method, "entities": len(by_name), "edges": edge_count}

    # ── catch me up ──────────────────────────────────────────────────────

    @staticmethod
    async def catch_me_up(
        db: AsyncSession,
        workspace_id: str,
        since: Optional[datetime] = None,
    ) -> dict:
        """Graph-delta summary: recently updated entities (with citations
        back to their source message/meeting), split out by decisions and
        action items, plus the edges connecting them."""
        repo = GraphRepository(db)
        activity = await repo.recent_activity(workspace_id, since=since)

        def _cite(e) -> dict:
            return {
                "name": e.name,
                "kind": e.kind,
                "summary": e.summary,
                "source_type": e.source_type,
                "source_id": e.source_id,
                "updated_at": e.updated_at,
            }

        entities: List[dict] = [_cite(e) for e in activity["entities"]]
        return {
            "workspace_id": workspace_id,
            "since": since,
            "entities": entities,
            "decisions": [c for c in entities if c["kind"] == "decision"],
            "action_items": [c for c in entities if c["kind"] == "action_item"],
            "edges": activity["edges"],
        }
