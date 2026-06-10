"""Benchmark harness for the model-routing/consensus layer (V2 plan §5.2).

Runs every candidate model from ``app/services/model_routes.json`` against the
golden sets in ``benchmarks/golden/`` and prints a scorecard of quality,
output tokens, and quality-per-1k-tokens. With ``--write`` it regenerates the
routing table, preferring local models whenever they land within 10% of the
best quality (the local-first KPI).

NOT collected by pytest/CI — run manually:

    cd backend
    .venv/bin/python -m benchmarks.run_benchmarks --dry-run
    .venv/bin/python -m benchmarks.run_benchmarks            # needs Ollama (+ cloud keys for cloud rows)
    .venv/bin/python -m benchmarks.run_benchmarks --write    # regenerate model_routes.json
"""

import argparse
import asyncio
import json
import re
import sys
from collections import Counter
from pathlib import Path

BENCH_DIR = Path(__file__).parent
GOLDEN_DIR = BENCH_DIR / "golden"
DEFAULT_ROUTES_PATH = BENCH_DIR.parent / "app" / "services" / "model_routes.json"

TASKS = ("classify", "summarize", "extract_actions")

#: How close (fraction of best quality) a local model must get to win a route.
LOCAL_PREFERENCE_MARGIN = 0.9

# Local-model registry: prefer the live one from the app, fall back to a
# static set so --dry-run works without the app package importable.
try:
    from app.services.ollama_service import OLLAMA_MODELS as _OLLAMA

    LOCAL_MODELS = set(_OLLAMA.keys())
except Exception:  # pragma: no cover - import fallback
    LOCAL_MODELS = {
        "gemma-4b", "qwen2.5-7b", "qwen-32b",
        "nemotron-cascade-2", "glm-4.7-flash", "orpheus-3b",
    }

TOPICS = ["frontend", "backend", "devops", "design", "bug", "feature", "question", "general"]

# Mirrors app/api/v1/messaging.py _TOPIC_KEYWORDS — used only by the mock provider.
_TOPIC_KEYWORDS = {
    "frontend": ["react", "css", "html", "ui", "component", "tsx", "jsx", "tailwind", "next", "style", "button", "layout", "page"],
    "backend": ["api", "server", "endpoint", "database", "sql", "orm", "fastapi", "flask", "python", "route", "schema", "query"],
    "devops": ["docker", "kubernetes", "k8s", "ci", "cd", "deploy", "github", "pipeline", "helm", "nginx", "aws", "gcp", "build"],
    "design": ["design", "ux", "figma", "wireframe", "prototype", "color", "font", "typography", "mockup", "spacing", "icon"],
    "bug": ["bug", "fix", "error", "crash", "issue", "broken", "fail", "wrong", "exception", "traceback", "null", "undefined", "not working"],
    "feature": ["feature", "add", "implement", "build", "create", "new", "enhance", "improve", "upgrade", "support"],
    "question": ["?", "how", "why", "what", "where", "when", "who", "anyone", "help", "can someone", "does anyone"],
}


# ── prompts ──────────────────────────────────────────────────────────────────

def build_prompt(task: str, text: str) -> str:
    if task == "classify":
        return (
            "Classify the following team chat message into exactly one of these "
            f"topics: {', '.join(TOPICS)}. Reply with only the topic label, "
            f"nothing else.\n\nMessage: {text}"
        )
    if task == "summarize":
        return (
            "Summarize the following team chat thread as 3-5 concise key points, "
            "one per line, no numbering or commentary.\n\n"
            f"--- THREAD ---\n{text}\n---\n\nKey points:"
        )
    if task == "extract_actions":
        return (
            "Extract every action item from this team chat thread. Output one "
            "action per line in the form '<person> to <action>'. No commentary.\n\n"
            f"--- THREAD ---\n{text}\n---\n\nActions:"
        )
    raise ValueError(f"Unknown task: {task}")


# ── providers ────────────────────────────────────────────────────────────────

class MockProvider:
    """Deterministic offline provider so the harness is testable without Ollama.

    Uses trivial heuristics (keyword classify, turn-based bullets) so scores
    are plausible but the pipeline never touches the network.
    """

    async def chat(self, model: str, task: str, text: str) -> str:
        if task == "classify":
            lower = text.lower()
            scores = {t: sum(1 for kw in kws if kw in lower) for t, kws in _TOPIC_KEYWORDS.items()}
            best = max(scores, key=scores.get)
            return best if scores[best] > 0 else "general"
        turns = [t.strip() for t in re.split(r"(?=\b\w+:\s)", text) if t.strip()]
        if task == "summarize":
            points = []
            for turn in turns[:5]:
                body = turn.split(":", 1)[-1].strip()
                points.append(" ".join(body.split()[:12]))
            return "\n".join(points)
        if task == "extract_actions":
            actions = []
            for turn in turns:
                speaker, _, body = turn.partition(":")
                for marker in ("i'll ", "i will ", "i can ", "i'm "):
                    idx = body.lower().find(marker)
                    if idx != -1:
                        action = body[idx + len(marker):].split(".")[0].strip()
                        actions.append(f"{speaker.strip().lower()} to {action.lower()}")
                        break
            return "\n".join(actions) if actions else "no actions found"
        raise ValueError(f"Unknown task: {task}")


class LiveProvider:
    """Calls real providers: Ollama for local models, OpenRouter for cloud."""

    def __init__(self):
        from app.services.ollama_service import OllamaService
        from app.services.openrouter_service import OpenRouterService

        self.ollama = OllamaService()
        self.openrouter = OpenRouterService()

    def available(self, model: str) -> bool:
        return model in LOCAL_MODELS or bool(self.openrouter.api_key)

    async def chat(self, model: str, task: str, text: str) -> str:
        from app.schemas.chat import Message

        messages = [Message(role="user", content=build_prompt(task, text))]
        if model in LOCAL_MODELS:
            return await self.ollama.chat(model, messages, temperature=0.1)
        return await self.openrouter.chat(model, messages, temperature=0.1)


# ── scoring (plain python, no deps) ─────────────────────────────────────────

def _tokens(text: str) -> list:
    return re.findall(r"[a-z0-9']+", text.lower())


def _expected_text(expected) -> str:
    if isinstance(expected, list):
        return "\n".join(str(x) for x in expected)
    return str(expected)


def score_classify(prediction: str, expected) -> float:
    pred = prediction.strip().lower()
    # tolerate models replying with a sentence: keep the first known label found
    for topic in TOPICS:
        if pred == topic:
            return 1.0 if topic == str(expected).strip().lower() else 0.0
    found = [t for t in TOPICS if t in pred]
    label = found[0] if found else pred.split()[0] if pred.split() else ""
    return 1.0 if label == str(expected).strip().lower() else 0.0


def score_overlap_f1(prediction: str, expected) -> float:
    pred_tokens = Counter(_tokens(prediction))
    exp_tokens = Counter(_tokens(_expected_text(expected)))
    if not pred_tokens or not exp_tokens:
        return 0.0
    overlap = sum((pred_tokens & exp_tokens).values())
    if overlap == 0:
        return 0.0
    precision = overlap / sum(pred_tokens.values())
    recall = overlap / sum(exp_tokens.values())
    return 2 * precision * recall / (precision + recall)


def score(task: str, prediction: str, expected) -> float:
    if task == "classify":
        return score_classify(prediction, expected)
    return score_overlap_f1(prediction, expected)


# ── harness ──────────────────────────────────────────────────────────────────

def load_routes(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def candidate_models(routes: dict) -> list:
    """Union of every model mentioned anywhere in the routing table."""
    models = []
    for cfg in routes.values():
        if not isinstance(cfg, dict):
            continue
        for key in ("model", "fallback", "judge"):
            if cfg.get(key):
                models.append(cfg[key])
        for m in cfg.get("models", []) or []:
            models.append(m)
    seen, ordered = set(), []
    for m in models:
        if m not in seen:
            seen.add(m)
            ordered.append(m)
    return ordered


def load_golden(task: str) -> list:
    path = GOLDEN_DIR / f"{task}.jsonl"
    examples = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


async def run_task(provider, task: str, model: str, examples: list) -> dict:
    total_quality = 0.0
    total_out_tokens = 0
    failures = 0
    for ex in examples:
        try:
            if isinstance(provider, MockProvider):
                output = await provider.chat(model, task, ex["input"])
            else:
                output = await provider.chat(model, task, ex["input"])
        except Exception as e:
            print(f"  ! {model}/{task} example failed: {e}", file=sys.stderr)
            failures += 1
            continue
        total_quality += score(task, output, ex["expected"])
        total_out_tokens += len(output.split())
    n = len(examples)
    quality = total_quality / n if n else 0.0
    qp1k = quality / (total_out_tokens / 1000) if total_out_tokens else 0.0
    return {
        "task": task,
        "model": model,
        "quality": quality,
        "out_tokens": total_out_tokens,
        "quality_per_1k": qp1k,
        "failures": failures,
        "local": model in LOCAL_MODELS,
    }


def print_scorecard(rows: list) -> None:
    print()
    print("=" * 78)
    print("MODEL ROUTING SCORECARD")
    print("=" * 78)
    header = f"{'task':<17}{'model':<22}{'where':<7}{'quality':>8}{'out_tok':>9}{'q/1k tok':>10}"
    print(header)
    print("-" * len(header))
    for r in rows:
        where = "local" if r["local"] else "cloud"
        print(
            f"{r['task']:<17}{r['model']:<22}{where:<7}"
            f"{r['quality']:>8.3f}{r['out_tokens']:>9}{r['quality_per_1k']:>10.2f}"
        )
    print("=" * 78)


def pick_routes(rows: list, routes: dict) -> dict:
    """Regenerate the routing table from scorecard rows, local-first.

    A local model wins a task if its quality is within 10% of the best model's
    quality; otherwise the best model wins. Tier shape is preserved.
    """
    new_routes = json.loads(json.dumps(routes))  # deep copy
    by_task: dict = {}
    for r in rows:
        by_task.setdefault(r["task"], []).append(r)

    for task, task_rows in by_task.items():
        cfg = new_routes.get(task)
        if not isinstance(cfg, dict) or not task_rows:
            continue
        best = max(task_rows, key=lambda r: r["quality"])
        locals_ok = [
            r for r in task_rows
            if r["local"] and r["quality"] >= best["quality"] * LOCAL_PREFERENCE_MARGIN
        ]
        chosen = max(locals_ok, key=lambda r: r["quality"]) if locals_ok else best
        clouds = [r for r in task_rows if not r["local"]]
        best_cloud = max(clouds, key=lambda r: r["quality"]) if clouds else None

        tier = cfg.get("tier", "T0")
        if tier == "T2":
            members = [chosen["model"]]
            others = sorted(
                (r for r in task_rows if r["model"] != chosen["model"]),
                key=lambda r: r["quality"],
                reverse=True,
            )
            if others:
                members.append(others[0]["model"])
            cfg["models"] = members
            if best_cloud:
                cfg["judge"] = best_cloud["model"]
        else:
            cfg["model"] = chosen["model"]
            if tier == "T1" and best_cloud and best_cloud["model"] != chosen["model"]:
                cfg["fallback"] = best_cloud["model"]
    return new_routes


async def _amain(args) -> list:
    routes_path = Path(args.routes)
    routes = load_routes(routes_path)
    models = candidate_models(routes)
    tasks = args.tasks or list(TASKS)

    provider = MockProvider() if args.dry_run else LiveProvider()
    if args.dry_run:
        print("(dry run: mocked provider, no network calls)")

    rows = []
    for task in tasks:
        examples = load_golden(task)
        for model in models:
            if not args.dry_run and not provider.available(model):
                print(f"  - skipping {model} for {task}: provider not configured")
                continue
            rows.append(await run_task(provider, task, model, examples))

    print_scorecard(rows)

    if args.write:
        new_routes = pick_routes(rows, routes)
        with open(routes_path, "w") as f:
            json.dump(new_routes, f, indent=2)
            f.write("\n")
        print(f"\nWrote regenerated routing table → {routes_path}")
        for task in tasks:
            cfg = new_routes.get(task, {})
            print(f"  {task}: {json.dumps(cfg)}")
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="Benchmark candidate models per task class.")
    parser.add_argument("--dry-run", action="store_true", help="use a mocked provider (no Ollama/network)")
    parser.add_argument("--write", action="store_true", help="regenerate model_routes.json local-first")
    parser.add_argument("--routes", default=str(DEFAULT_ROUTES_PATH), help="path to model_routes.json")
    parser.add_argument("--tasks", nargs="*", choices=list(TASKS), help="subset of task classes to run")
    args = parser.parse_args(argv)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    main()
