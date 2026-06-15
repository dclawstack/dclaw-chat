import logging
import re
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.message_repo import MessageRepository
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.graph_repo import GraphRepository
from app.services.ollama_service import OllamaService, OLLAMA_MODELS
from app.schemas.chat import Message
from app.schemas.ai import (
    AIChatRequest,
    AIChatResponse,
    SummarizeRequest,
    SummarizeResponse,
    ActionsRequest,
    ActionsResponse,
    ExtractedAction,
    Citation,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = next(iter(OLLAMA_MODELS.values()), "gemma4:latest")

#: Words too generic to be useful as knowledge-graph search terms.
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "what", "who", "how",
    "why", "where", "when", "about", "are", "was", "you", "can", "does",
    "did", "have", "has", "any", "all", "our", "your", "tell",
}


def _score_relevance(query: str, text: str) -> float:
    """BM25-lite: score a message against the query by keyword overlap."""
    query_tokens = set(re.findall(r"\w+", query.lower()))
    text_tokens = re.findall(r"\w+", text.lower())
    if not query_tokens or not text_tokens:
        return 0.0
    hits = sum(1 for t in text_tokens if t in query_tokens)
    return hits / (len(text_tokens) ** 0.5)


def _retrieve_context(query: str, messages: list, top_k: int = 5) -> List[str]:
    """Return the top-k most relevant message snippets for RAG context."""
    scored = [
        (msg, _score_relevance(query, msg.content))
        for msg in messages
        if msg.role in ("user", "assistant")
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = [msg for msg, score in scored[:top_k] if score > 0]
    if not top:
        top = [msg for msg in messages[-top_k:] if msg.role in ("user", "assistant")]
    return [f"[{m.role.upper()}]: {m.content[:400]}" for m in top]


class ChatAIService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.msg_repo = MessageRepository(db)
        self.conv_repo = ConversationRepository(db)
        self.ollama = OllamaService()

    def _pick_model(self, model_id: Optional[str]) -> str:
        if model_id and model_id in OLLAMA_MODELS:
            return OLLAMA_MODELS[model_id]
        return DEFAULT_MODEL

    async def _get_messages(self, conversation_id: str):
        return await self.msg_repo.list_by_conversation(conversation_id, limit=200)

    async def _graph_citations(
        self, workspace_id: str, query: str, limit: int = 5
    ) -> List[Citation]:
        """Match terms from the user's question against the workspace
        knowledge graph and return entity citations. Fail-soft: any error
        yields no citations rather than a failed answer."""
        terms = [
            t
            for t in re.findall(r"\w+", query.lower())
            if len(t) > 2 and t not in _STOPWORDS
        ][:8]
        seen: dict[str, Citation] = {}
        try:
            repo = GraphRepository(self.db)
            for term in terms:
                for entity in await repo.search_entities(
                    workspace_id, term, limit=limit
                ):
                    seen.setdefault(
                        entity.id,
                        Citation(
                            name=entity.name,
                            kind=entity.kind,
                            source_type=entity.source_type,
                            source_id=entity.source_id,
                        ),
                    )
                if len(seen) >= limit:
                    break
            # Fallback: literal name matching is often thin (e.g. "what did we
            # decide?" shares no words with entity names). Ground the answer in
            # the workspace's salient memory — recent decisions/action-items
            # first, then any recent entity — so the copilot always cites.
            if len(seen) < limit:
                for kinds in (["decision", "action_item"], None):
                    if len(seen) >= limit:
                        break
                    for entity in await repo.search_entities(
                        workspace_id, "", kinds=kinds, limit=limit
                    ):
                        seen.setdefault(
                            entity.id,
                            Citation(
                                name=entity.name,
                                kind=entity.kind,
                                source_type=entity.source_type,
                                source_id=entity.source_id,
                            ),
                        )
                        if len(seen) >= limit:
                            break
        except Exception as e:
            logger.warning(f"Graph citation lookup failed: {e}")
        return list(seen.values())[:limit]

    async def chat(self, req: AIChatRequest) -> AIChatResponse:
        """Copilot chat — RAG over conversation history, then LLM answer."""
        ollama_model = self._pick_model(req.model)
        context_snippets: List[str] = []

        if req.conversation_id:
            history = await self._get_messages(req.conversation_id)
            context_snippets = _retrieve_context(req.query, history)

        if context_snippets:
            context_block = "\n".join(context_snippets)
            system_prompt = (
                "You are DClaw Copilot, an AI workspace assistant. "
                "You have access to the conversation history below. "
                "Use it to answer the user's question accurately.\n\n"
                f"--- CONVERSATION CONTEXT ---\n{context_block}\n---"
            )
        else:
            system_prompt = (
                "You are DClaw Copilot, an AI workspace assistant. "
                "Answer the user's question helpfully and concisely."
            )

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=req.query),
        ]

        logger.info(
            f"Copilot chat: model={ollama_model}, rag_chunks={len(context_snippets)}"
        )
        content = await self.ollama.chat(ollama_model, messages)

        citations: List[Citation] = []
        if req.workspace_id:
            citations = await self._graph_citations(req.workspace_id, req.query)

        return AIChatResponse(
            answer=content,
            model=ollama_model,
            rag_chunks_used=len(context_snippets),
            context_snippets=context_snippets if req.include_context else [],
            citations=citations,
        )

    async def summarize(self, req: SummarizeRequest) -> SummarizeResponse:
        """Summarize a conversation thread using the LLM."""
        history = await self._get_messages(req.conversation_id)
        if not history and req.messages:
            # Use client-provided messages when conversation isn't in DB yet
            from types import SimpleNamespace
            history = [SimpleNamespace(role=m.role, content=m.content) for m in req.messages]
        if not history:
            return SummarizeResponse(
                conversation_id=req.conversation_id,
                summary="No messages to summarize.",
                message_count=0,
            )

        transcript = "\n".join(
            f"{m.role.upper()}: {m.content[:600]}"
            for m in history
            if m.role in ("user", "assistant")
        )

        prompt = (
            "Summarize the following conversation thread concisely. "
            "Highlight key topics, decisions, and outcomes in 3-5 bullet points.\n\n"
            f"--- THREAD ---\n{transcript[:6000]}\n---\n\nSummary:"
        )

        ollama_model = self._pick_model(req.model)
        messages = [Message(role="user", content=prompt)]
        logger.info(f"Summarizing conversation {req.conversation_id}: {len(history)} msgs")
        summary_text = await self.ollama.chat(
            ollama_model, messages, temperature=0.3
        )

        return SummarizeResponse(
            conversation_id=req.conversation_id,
            summary=summary_text.strip(),
            message_count=len(history),
        )

    async def extract_actions(self, req: ActionsRequest) -> ActionsResponse:
        """Extract actionable items from a conversation."""
        history = await self._get_messages(req.conversation_id)
        if not history and req.messages:
            from types import SimpleNamespace
            history = [SimpleNamespace(role=m.role, content=m.content) for m in req.messages]
        if not history:
            return ActionsResponse(conversation_id=req.conversation_id, actions=[])

        transcript = "\n".join(
            f"{m.role.upper()}: {m.content[:600]}"
            for m in history
            if m.role in ("user", "assistant")
        )

        prompt = (
            "Extract all actionable items from this conversation. "
            "For each action, output a line in this exact format:\n"
            "ACTION: <action text> | PRIORITY: <low|medium|high> | ASSIGNEE: <name or 'unassigned'>\n\n"
            f"--- CONVERSATION ---\n{transcript[:6000]}\n---\n\nActions:"
        )

        ollama_model = self._pick_model(req.model)
        messages = [Message(role="user", content=prompt)]
        logger.info(f"Extracting actions from conversation {req.conversation_id}")
        raw = await self.ollama.chat(
            ollama_model, messages, temperature=0.2
        )

        actions: List[ExtractedAction] = []
        for line in raw.splitlines():
            if "ACTION:" not in line:
                continue
            try:
                parts = {
                    p.split(":")[0].strip(): p.split(":", 1)[1].strip()
                    for p in line.split("|")
                    if ":" in p
                }
                action_text = parts.get("ACTION", line.strip())
                priority = parts.get("PRIORITY", "medium").lower()
                if priority not in ("low", "medium", "high"):
                    priority = "medium"
                assignee = parts.get("ASSIGNEE", "unassigned")
                actions.append(
                    ExtractedAction(
                        text=action_text,
                        priority=priority,
                        assignee=assignee if assignee.lower() != "unassigned" else None,
                    )
                )
            except Exception:
                continue

        return ActionsResponse(
            conversation_id=req.conversation_id,
            actions=actions,
        )
