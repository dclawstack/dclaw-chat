# Benchmarks — model routing scorecard

Benchmark harness for the internal model-routing/consensus layer
(`app/services/model_router.py`, V2-REBUILD-PLAN §5.2). It scores every
candidate model named in `app/services/model_routes.json` against the golden
sets and decides the routing table with data, not vibes.

**Not part of CI** — pytest only collects `tests/`, so nothing here runs by
default. A single unit test imports the runner with `--dry-run` to keep the
pipeline from rotting.

## Layout

```
benchmarks/
├── golden/
│   ├── classify.jsonl          # {"input": message, "expected": topic-label}
│   ├── summarize.jsonl         # {"input": thread, "expected": [key points]}
│   └── extract_actions.jsonl   # {"input": thread, "expected": [action items]}
├── run_benchmarks.py
└── README.md
```

Topic labels in `classify.jsonl` match `_TOPIC_KEYWORDS` in
`app/api/v1/messaging.py` (frontend, backend, devops, design, bug, feature,
question, general).

## Running

```bash
cd backend

# Offline smoke test — mocked provider, no Ollama or network needed:
.venv/bin/python -m benchmarks.run_benchmarks --dry-run

# Real run — needs Ollama up; cloud models are skipped unless
# OPENROUTER_API_KEY is configured:
.venv/bin/python -m benchmarks.run_benchmarks

# Subset of tasks:
.venv/bin/python -m benchmarks.run_benchmarks --tasks classify summarize
```

## Scoring

| Task | Metric |
|---|---|
| classify | exact-match accuracy (tolerates label embedded in a sentence) |
| summarize | token-overlap F1 vs the expected key points |
| extract_actions | token-overlap F1 vs the expected action list |

Each row also reports total **output tokens** (whitespace tokens) and
**quality per 1k output tokens** — the cost-aware number the routing decision
uses alongside raw quality.

## Regenerating the routing table

```bash
.venv/bin/python -m benchmarks.run_benchmarks --write
```

`--write` rewrites `app/services/model_routes.json` in place:

- Per task, the **best local model wins if its quality is within 10% of the
  overall best** (`LOCAL_PREFERENCE_MARGIN = 0.9`) — this is how the ≥70%
  local-call KPI is enforced at the table level.
- Tier shape is preserved: T0/T1 get `model` (T1 also gets the best cloud
  model as `fallback`); T2 gets the winner first in `models` plus the
  next-best model, and the best cloud model as `judge`.
- The router (`ModelRouter`) loads the file at startup, so a regenerated
  table takes effect on the next process start.

Don't combine `--write` with `--dry-run` for real decisions — the mocked
provider's scores are only meant to exercise the pipeline.

## Adding golden examples

Append JSONL lines to the files in `golden/`. Keep examples realistic
(team-chat shaped), 8–50 per task. Re-run the benchmark after model-catalog
changes and commit the regenerated `model_routes.json` together with the
scorecard output in the PR description.
