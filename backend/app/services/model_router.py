"""Internal model-routing / consensus layer (V2 plan §5, Phase 4 groundwork).

Routes task classes to model tiers loaded from ``model_routes.json``:

* **T0 — Local**: single Ollama call, no cloud involvement.
* **T1 — Local + cloud fallback**: Ollama first; on failure escalate to the
  configured cloud fallback *only if* OpenRouter is configured, else fail.
* **T2 — Consensus**: run the same prompt on every configured-and-available
  model; if two answers agree (normalized similarity > 0.8) return the
  agreement, otherwise ask the judge model to reconcile. With only one model
  available it degrades to a single call.

Everything is fail-soft toward local: cloud unavailable → stay local;
local unavailable → raise the existing :class:`LLMException`.

KPI: ≥70% of LLM calls served locally — tracked by per-process counters
exposed via ``ModelRouter.stats()`` and GET /api/v1/models/router-stats.
"""

import asyncio
import difflib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

from app.core.exceptions import LLMException
from app.schemas.chat import Message
from app.services.ollama_service import OllamaService, OLLAMA_MODELS
from app.services.openrouter_service import OpenRouterService

logger = logging.getLogger(__name__)

ROUTES_PATH = Path(__file__).parent / "model_routes.json"

#: Similarity threshold above which two consensus answers count as agreeing.
AGREEMENT_THRESHOLD = 0.8

#: Used when a task class is missing from the routing table.
DEFAULT_ROUTE = {"tier": "T0", "model": "gemma-4b", "max_tokens": 300}


@dataclass
class RouterResult:
    content: str
    model_used: str
    tier: str
    escalated: bool
    calls: int


def _normalize(text: str) -> str:
    """Lowercase + collapse/strip whitespace for similarity comparison."""
    return " ".join(text.lower().split())


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


class ModelRouter:
    """Tiered model router with per-process usage counters."""

    # Per-process counters, shared across instances so the module-level
    # ``router`` and the stats endpoint observe the same numbers.
    _total_calls: int = 0
    _local_calls: int = 0
    _cloud_calls: int = 0

    def __init__(self, routes_path: Optional[Path] = None):
        self.routes_path = Path(routes_path) if routes_path else ROUTES_PATH
        self.routes = self._load_routes()
        self.ollama = OllamaService()
        self.openrouter = OpenRouterService()

    # ── routing table ────────────────────────────────────────────────────

    def _load_routes(self) -> dict:
        try:
            with open(self.routes_path) as f:
                routes = json.load(f)
            if not isinstance(routes, dict):
                raise ValueError("model_routes.json must be a JSON object")
            return routes
        except Exception as e:  # fail-soft: keep serving with the default
            logger.error(f"Failed to load model routes from {self.routes_path}: {e}")
            return {}

    def _route_for(self, task: str) -> dict:
        route = self.routes.get(task)
        if not isinstance(route, dict):
            logger.warning(f"No route for task '{task}', using default T0 route")
            return dict(DEFAULT_ROUTE)
        return route

    # ── availability / dispatch ──────────────────────────────────────────

    @staticmethod
    def _is_local(model: str) -> bool:
        return model in OLLAMA_MODELS

    def _cloud_configured(self) -> bool:
        return bool(self.openrouter.api_key)

    def _is_available(self, model: str) -> bool:
        return self._is_local(model) or self._cloud_configured()

    async def _call(
        self, model: str, messages: List[Message], temperature: float
    ) -> str:
        """Single provider call. Counts usage on success."""
        if self._is_local(model):
            content = await self.ollama.chat(model, messages, temperature)
            ModelRouter._total_calls += 1
            ModelRouter._local_calls += 1
            return content
        if not self._cloud_configured():
            raise LLMException(f"Cloud model '{model}' requested but OpenRouter is not configured")
        content = await self.openrouter.chat(model, messages, temperature)
        ModelRouter._total_calls += 1
        ModelRouter._cloud_calls += 1
        return content

    # ── public API ───────────────────────────────────────────────────────

    async def run(
        self,
        task: str,
        messages: List[Union[Message, dict]],
        temperature: float = 0.3,
        model_override: Optional[str] = None,
    ) -> RouterResult:
        msgs = [m if isinstance(m, Message) else Message(**m) for m in messages]
        route = self._route_for(task)
        tier = route.get("tier", "T0")

        if tier == "T2":
            return await self._run_consensus(task, route, msgs, temperature)
        if tier == "T1":
            return await self._run_with_fallback(task, route, msgs, temperature, model_override)
        return await self._run_local(task, route, msgs, temperature, model_override)

    async def _run_local(
        self,
        task: str,
        route: dict,
        messages: List[Message],
        temperature: float,
        model_override: Optional[str] = None,
    ) -> RouterResult:
        model = self._pick_primary(route, model_override)
        try:
            content = await self._call(model, messages, temperature)
        except LLMException:
            raise
        except Exception as e:
            logger.error(f"T0 local call failed for task '{task}' ({model}): {e}")
            raise LLMException(f"Local model unavailable for task '{task}': {e}")
        return RouterResult(
            content=content, model_used=model, tier="T0", escalated=False, calls=1
        )

    async def _run_with_fallback(
        self,
        task: str,
        route: dict,
        messages: List[Message],
        temperature: float,
        model_override: Optional[str] = None,
    ) -> RouterResult:
        model = self._pick_primary(route, model_override)
        calls = 0
        try:
            calls += 1
            content = await self._call(model, messages, temperature)
            return RouterResult(
                content=content, model_used=model, tier="T1", escalated=False, calls=calls
            )
        except Exception as primary_err:
            logger.warning(f"T1 primary '{model}' failed for task '{task}': {primary_err}")
            fallback = route.get("fallback")
            # Escalate only when a fallback exists AND it is actually usable
            # (cloud fallbacks need an API key; otherwise we stay local-only).
            if fallback and fallback != model and self._is_available(fallback):
                try:
                    calls += 1
                    content = await self._call(fallback, messages, temperature)
                    return RouterResult(
                        content=content,
                        model_used=fallback,
                        tier="T1",
                        escalated=True,
                        calls=calls,
                    )
                except Exception as fallback_err:
                    logger.error(
                        f"T1 fallback '{fallback}' also failed for task '{task}': {fallback_err}"
                    )
            raise LLMException(
                f"All providers failed for task '{task}': {primary_err}"
            )

    async def _run_consensus(
        self, task: str, route: dict, messages: List[Message], temperature: float
    ) -> RouterResult:
        configured = route.get("models") or [route.get("model", DEFAULT_ROUTE["model"])]
        available = [m for m in configured if self._is_available(m)]
        if not available:
            raise LLMException(f"No models available for consensus task '{task}'")

        # Degrade to a single call when consensus is impossible.
        if len(available) == 1:
            model = available[0]
            try:
                content = await self._call(model, messages, temperature)
            except LLMException:
                raise
            except Exception as e:
                raise LLMException(f"Model '{model}' failed for task '{task}': {e}")
            return RouterResult(
                content=content, model_used=model, tier="T2", escalated=False, calls=1
            )

        outcomes = await asyncio.gather(
            *(self._call(m, messages, temperature) for m in available),
            return_exceptions=True,
        )
        calls = len(available)
        results = [
            (m, out)
            for m, out in zip(available, outcomes)
            if not isinstance(out, BaseException)
        ]
        for m, out in zip(available, outcomes):
            if isinstance(out, BaseException):
                logger.warning(f"Consensus member '{m}' failed for task '{task}': {out}")

        if not results:
            raise LLMException(f"All consensus models failed for task '{task}'")
        if len(results) == 1:
            model, content = results[0]
            return RouterResult(
                content=content, model_used=model, tier="T2", escalated=False, calls=calls
            )

        # Pairwise agreement: two answers within similarity threshold settle it.
        for i in range(len(results)):
            for j in range(i + 1, len(results)):
                if _similarity(results[i][1], results[j][1]) > AGREEMENT_THRESHOLD:
                    model, content = results[i]
                    return RouterResult(
                        content=content,
                        model_used=f"consensus:{results[i][0]}+{results[j][0]}",
                        tier="T2",
                        escalated=False,
                        calls=calls,
                    )

        # Disagreement → judge reconciles (fail-soft to first answer if the
        # judge is unavailable or fails).
        judge = route.get("judge")
        if judge and self._is_available(judge):
            judge_prompt = self._build_judge_prompt(messages, results)
            try:
                content = await self._call(
                    judge, [Message(role="user", content=judge_prompt)], temperature
                )
                return RouterResult(
                    content=content,
                    model_used=f"judge:{judge}",
                    tier="T2",
                    escalated=True,
                    calls=calls + 1,
                )
            except Exception as e:
                logger.warning(f"Judge '{judge}' failed for task '{task}': {e}")

        model, content = results[0]
        return RouterResult(
            content=content, model_used=model, tier="T2", escalated=False, calls=calls
        )

    def _pick_primary(self, route: dict, model_override: Optional[str] = None) -> str:
        if model_override and self._is_available(model_override):
            return model_override
        return route.get("model") or DEFAULT_ROUTE["model"]

    @staticmethod
    def _build_judge_prompt(
        messages: List[Message], results: List[tuple]
    ) -> str:
        original = "\n".join(f"{m.role}: {m.content}" for m in messages)
        candidates = "\n\n".join(
            f"--- Candidate {i + 1} (from {model}) ---\n{content}"
            for i, (model, content) in enumerate(results)
        )
        return (
            "You are a judge reconciling answers from multiple AI models that "
            "disagree. Given the original request and the candidate answers, "
            "produce the single best, most accurate final answer. Output only "
            "the final answer, no commentary.\n\n"
            f"--- ORIGINAL REQUEST ---\n{original}\n\n{candidates}\n\n"
            "Final answer:"
        )

    # ── stats ────────────────────────────────────────────────────────────

    @classmethod
    def stats(cls) -> dict:
        total = cls._total_calls
        return {
            "total_calls": total,
            "local_calls": cls._local_calls,
            "cloud_calls": cls._cloud_calls,
            "local_fraction": (cls._local_calls / total) if total else 0.0,
        }

    @classmethod
    def reset_stats(cls) -> None:
        cls._total_calls = 0
        cls._local_calls = 0
        cls._cloud_calls = 0


#: Shared module-level router for service consumers (meeting summaries, etc.).
router = ModelRouter()
