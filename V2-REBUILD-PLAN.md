# DClaw Chat — v2.0 Rebuild Plan

**Date:** 2026-06-10 · **Status:** Draft for execution
**Inputs:** REVISED-PRD v2.3 · GAP-ANALYSIS-2026-06-09-v2 (security/SRE) · PLAN-v1.2 · pathb-bug-report.md · testforge-consensus.md · live competitor research (§3)
**Goal:** Evolve DClaw Chat from a feature-rich single-user demo to a YC-grade, autonomous, end-to-end multi-tenant product — **v2.0**.

---

## 1. v2.0 Thesis

**"AI conversations that remember"** becomes literal: a privacy-first team chat where a
workspace **knowledge graph** is the product's memory, **local-first LLMs** (Ollama +
ClawShield PII scrubbing) are the trust story, and an **internal consensus-model layer**
makes AI output cheap, domain-tuned, and verifiable.

What v2.0 is NOT: a Slack clone with more buttons. Breakout rooms, polling, white-label
embeds (P2 of the old PRD) are frozen.

---

## 2. Architecture Pivot — Serverless Infrastructure

> ⚠️ This **supersedes** the "Sacred Architecture" K8s/CloudNativePG mandate in
> REVISED-PRD §4 by explicit owner decision (2026-06-10). The Helm/K8s path is retained
> only as a future on-prem/enterprise distribution, not the primary deploy target.

### 2.1 Target topology

| Layer | v1 (current) | v2.0 (target) | Why |
|---|---|---|---|
| Frontend | Next.js static export + nginx container | **Next.js on Vercel** (App Router, server components, streaming) | Git-push deploys, preview URLs, edge network, drops nginx/CSP hand-rolling |
| Database | Postgres container / CloudNativePG | **Neon serverless Postgres** + pgvector | Branch-per-PR preview DBs, scale-to-zero, no DB ops |
| API | FastAPI on K8s | **FastAPI runs LOCALLY** (owner decision 2026-06-10: no cloud backend hosting; uvicorn/docker compose on the user's machine), Neon-backed | Local-first is the product thesis — the backend lives where the data and Ollama live; remote users reach it via a tunnel (cloudflared/Tailscale) if ever needed |
| Realtime (WS) | Per-process dict managers (broken at >1 pod, GAP T3-01) | **In-process managers are now CORRECT** — a single local backend instance has no multi-pod problem; T3-01/02 are moot for this deployment shape | Backplane only revisited if a hosted multi-instance path returns |
| Rate limit / cache | None deployed (GAP T3-02/07) | Per-process slowapi limits (single instance = accurate); local Redis optional | No Upstash needed |
| Files | Local `uploads/` dir | **Local disk stays** — serve route is now authed + attachment/nosniff (Phase 0) | Blob storage only if a hosted path returns |
| Auth | Logto (backend-only; frontend sends nothing, T3-08) | **Logto end-to-end** (or Clerk if velocity wins) | Working login is a v2.0 gate |
| Deploy | docker compose / Helm | **Git deployment**: push → Vercel preview (frontend) + Neon branch (DB) + Fly preview (API); merge → prod | Every PR is a full running stack |

### 2.2 Git-deployment pipeline (per PR)
1. Push branch → GitHub Actions
   - lint + typecheck + pytest (state-coverage suite, §6.4)
   - `graphify update .` → commit refreshed `graphify-out/` (graph stays current)
2. Vercel builds preview frontend; Neon branches the DB; API preview deploy
3. E2E smoke (two-user auth flow) runs against the preview stack
4. Merge to `main` → prod deploy + Alembic migration job + Sentry release

---

## 3. Competitive Gap Analysis (YC market)

*Live web research, June 2026. Sources in the underlying research; uncertain items flagged.*

### 3.1 Incumbents — all-cloud AI, pricing pressure, fresh trust wounds

| Product | AI shipped | Pricing | Exploitable weakness |
|---|---|---|---|
| **Slack** | Slackbot agent, AI search, summaries, recaps, huddle notes; 30+ AI features announced Mar 2026 | AI bundled: Pro $7.25, Business+ $15/u/mo (raised) | Cloud-only; **May 2025 API ToS lockdown** blocks customers' own AI tools from bulk data (broke Glean et al.) — live data-sovereignty resentment |
| **MS Teams** | Intelligent recap, in-meeting Copilot, custom AI summaries, Interpreter Agent | Premium $10 + Copilot $30/u/mo add-on stack | Expensive double add-on; AI value locked to M365 graph |
| **Zoom** | AI Companion 3.0: agentic retrieval, cross-platform meeting join, AI Studio agents | Included in paid plans; +$12 custom add-on | Meeting-centric, weak chat product; sets "AI included" price anchor |
| **Discord** | Minimal first-party (summaries, AutoMod) | — | Privacy backlash over data-for-AI policies; proves user distrust of platforms training on messages |

### 3.2 Open-source / self-hosted — local AI exists but is a bolt-on
- **Mattermost** (closest architectural comp): Agents plugin, Ollama/vLLM support — but best AI gated behind Enterprise license, bolt-on UX, no PII-shielded hybrid routing, no consensus
- **Rocket.Chat**: BYO-LLM RAG app for gov/air-gapped; high setup friction, AI not core identity
- **Zulip**: deliberate AI minimalism (beta topic summaries only)
- **Element/Matrix**: winning gov deals on E2EE, but **E2EE blocks server-side AI entirely** — only client-side/local inference can serve that segment

### 3.3 AI-native startups — what the market just proved
- **Tanka** ($-backed, 2025): "AI messenger with long-term memory" (MemGraph) — validates the *exact* "chat that remembers" positioning; cloud-based, thin traction → the **private/local variant is open**
- **Granola**: $125M Series C at **$1.5B** (Mar 2026) pivoting from meeting notes to "enterprise AI context" — bot-less *local* audio capture was the wedge; meetings-as-memory is unicorn-scale
- **Glean**: **$7.2B**, ARR $100M→$200M in 9 months on a knowledge-graph moat — and just lost deep Slack access; *the platform that owns the chat data wins*
- **Dust**: $40M Series B, 240% NRR — *team-level* ("multiplayer") AI is the framing investors back
- **Otter.ai**: federal class action (Aug 2025) for surreptitious recording — consent is now legal risk; tailwind for on-device processing
- **Local-LLM ecosystem** (Ollama, Jan, LM Studio, vLLM): production-viable substrate, but all single-user infra — **no team product**
- **PII shielding** (Presidio, Skyflow): proven tech, sold only as infra — never as a built-in chat feature
- **Routing/consensus** (OpenRouter, Not Diamond, Martian): commoditized as hidden infra; consensus as a *user-facing trust signal* is unclaimed (documented 7–15pt accuracy lift over best single model)
- **Notably sparse:** no breakout AI-native team-chat startup in 2024–26 YC batches — either open field or switching-cost graveyard; mitigations observed: integrate-don't-replace (Tanka), land-via-meetings (Granola)

### 3.4 YC signal (current RFS)
- **"Company Brain"** — unified knowledge system extracting company wisdom for AI automation: near-verbatim DClaw's graph-memory pitch
- **"AI Operating System for Companies"**, **"SaaS Challengers"** (AI-native replacements of legacy enterprise software), agent infrastructure ~50% of recent batches
- Local/private AI is *not* an RFS theme — that angle is ours, backed instead by market events (Slack lockdown, Otter lawsuit, EU sovereignty)

### 3.5 Ranked gap opportunities → action plan mapping

| # | Gap (evidence-backed) | DClaw answer | Phase |
|---|---|---|---|
| 1 | **Local-first team AI with consumer UX** — nobody ships "install, team AI runs on your hardware by default" | Ollama T0 default + one-command setup | 3, 4 |
| 2 | **Data sovereignty vs Slack lockdown** — "your chat, your data, your models, exportable forever" | Open export, BYO-model, graph you own | 2, 3 |
| 3 | **PII shielding as product feature** — infra exists (Presidio), no chat product markets it | ClawShield visible in UI before every cloud call | 3 |
| 4 | **Consensus as user-facing trust** — routing commoditized, trust signal unclaimed | "N models agreed" badge on graph answers (feature, not company) | 4 |
| 5 | **Graph memory natively in chat** — Tanka (positioning) + Glean (graph) + Granola (meetings) each hold ⅓ | Workspace knowledge graph over messages+meetings+files | 3 |
| 6 | **Meeting AI without consent liability** — Otter lawsuit; Granola won on local capture | On-device transcription, "recording never leaves your machine" | 3 |
| 7 | **Pricing arbitrage** — Slack $15, Teams $10+$30; local inference ≈ zero marginal AI cost | Flat all-inclusive pricing cloud rivals can't match | 5 |
| 8 | **AI for E2EE/gov segment** — Element wins gov but E2EE blocks server AI; only local inference works there | Enterprise/on-prem Helm path (deferred) | post-2.0 |

### 3.6 Risks the data surfaces
- Slack's Mar 2026 AI blitz means "Slack but AI-native" decays fast — **local/private must carry the differentiation**, not AI-ness alone
- Empty AI-native-chat field may be a switching-cost graveyard → adopt both observed mitigations: **integrate-don't-replace** (Slack/import bridges) and **land-via-meetings** (the consent-safe meeting wedge as the bottoms-up entry)

---

## 4. Knowledge Graph (created today + product roadmap)

### 4.1 Dev-side graph — DONE (2026-06-10)
- Built with `graphify update .`: **5,832 nodes · 13,594 edges · 208 communities**, 96% AST-extracted, zero token cost → `graphify-out/`
- Use `graphify query/path/explain` instead of grep for cross-module questions
- CI keeps it fresh (§2.2); agents read `GRAPH_REPORT.md` before touching code

### 4.2 Product-side graph — the v2.0 differentiator
The copilot's memory becomes a **workspace knowledge graph**, not just vector RAG:
- **Entities:** people, topics, decisions, action items, files, meetings, bots
- **Edges:** `discussed-in`, `decided-by`, `assigned-to`, `supersedes`, `mentioned-with`
- **Extraction:** Tier-0 local model (cheap, private — §5) tags entities per message;
  nightly Tier-1 pass consolidates communities ("what does this team know about X")
- **Storage:** Postgres tables + pgvector embeddings on Neon (no new infra); graph
  traversal in SQL (recursive CTEs) — Apache AGE only if scale demands
- **Surfaces:**
  - Copilot answers cite graph paths ("decided in #eng on May 3 by Priya → superseded May 20")
  - "Catch me up" = graph-delta since last seen, not a raw summary
  - Auto-built team wiki (old P2.10) falls out of the graph for free
- **Moat logic:** chat history × entity graph compounds with usage; switching cost = losing the team's memory

---

## 5. Internal Consensus-Model Layer (benchmarked, low-token, domain-specific)

Builds on what already exists: multi-provider services (`ollama_service`, `openrouter_service`,
`nvidia_service`), the swarm runtime (`lib/swarm/`), and the 2–3-model consensus practice
proven in `pathb-bug-report.md` / `testforge-consensus.md`.

### 5.1 Routing tiers
| Tier | Models | Used for | Token budget |
|---|---|---|---|
| **T0 — Local** | Ollama small (gemma/llama class) | intent classification, smart replies, PII detection, entity tagging, routing decisions | ≤300 tok/call, $0 |
| **T1 — Single cloud** | One mid model via OpenRouter (benchmark-selected) | thread/meeting summaries, copilot answers | ≤2k tok/call |
| **T2 — Consensus** | 2–3 diverse models, vote → reconcile (disagreement → judge) | action-item extraction, security-sensitive admin suggestions, anything user-visible as "fact" | reserved for high stakes |

Escalation: T0 emits a confidence score; low confidence or task-class policy escalates.
Fallback: cloud unreachable → degrade to T0 + "local mode" badge (the privacy story, not an error).

### 5.2 Benchmark harness (decides the routing table; no vibes)
- `backend/benchmarks/` golden sets per domain task: summarization, action extraction,
  intent classification, entity tagging (seed ~50 examples each from real usage)
- Score = task quality (exact-match where possible, LLM-judge otherwise) **per 1k tokens**
- Output: a generated `model_routes.json` the router loads — model choice is a build
  artifact, not a hardcoded constant (today's hardcoded `OPENROUTER_MODELS` dict dies)
- Re-run on model-catalog changes; CI publishes a scorecard diff
- KPI: ≥70% of all LLM calls served by T0 local; cloud spend per workspace metered (feeds billing)

---

## 6. Phase Plan to v2.0

### Phase 0 — Trust floor · ✅ **COMPLETE 2026-06-10**
- Conversations ownership: `created_by` column + migration, owner-filtered list, 403 on foreign access; authorize `conversation_id` in chat routes (GAP T2-01/02)
- Frontend auth: Logto login, `Bearer` on REST, `?token=` on WS; delete `?user_id=` params (T3-08)
- `ENVIRONMENT=production` set in every deploy manifest + CI render assertion (T3-05)
- `serve_file`: auth + access check, `Content-Disposition: attachment`, nosniff, SVG blocked (T1-01/02)
- **Gate:** two-user E2E passes with `DEBUG=false`

### Phase 1 — Infrastructure migration · ✅ **COMPLETE 2026-06-10** (revised scope: local-backend decision)
> Neon live (PostgreSQL 17.10, 14 tables migrated via lifespan; asyncpg URL normalized);
> API boots against Neon — health 200, anonymous 401 under DEBUG=false. Vercel via
> authenticated CLI; frontend deploy deferred (hosted frontend can't reach a local
> backend — frontend runs locally/Tauri). Dropped per owner decision: Fly/Railway,
> Upstash, managed realtime, blob storage. Original spec below kept for history:
- Neon: migrate schema via Alembic; pgvector enabled; branch-per-PR wired
- Vercel: frontend off static-export/nginx onto native Next.js; env via Vercel project
- API service to Fly/Railway; Upstash Redis for rate limiting (per-user keys on LLM routes — also the cost cap, T2-08)
- Realtime: channels/presence/calls signaling onto managed realtime; delete the three in-process WS managers (T3-01..04 class eliminated)
- Files to Blob/S3 signed URLs
- **Gate:** PR opens → full preview stack URL in the PR comment

### Phase 2 — Multi-tenant product · ✅ backend **COMPLETE 2026-06-10** (325→354 suite)
> Residual: signup/onboarding UI (needs Logto tenant).
- `Workspace` + `WorkspaceMember(role)` model; scope channels/conversations/files/bots/meetings
- Invite-by-email; signup → create-or-join onboarding
- Membership enforced on every channel route + realtime join; bot ownership; token-derived identity in command-execute (T2-04..07)
- Repair + apply `require_role` RBAC (Owner/Admin/Member/Guest)
- Remaining security P1s: SSRF IP-pinning, unfurl streaming cap, og:image validation, schema bounds, magic-byte sniff
- **Gate:** GAP v2 §4 state-coverage suite fully green in CI

### Phase 3 — Knowledge-graph memory + copilot · ✅ backend **COMPLETE 2026-06-10**
> Done: graph_entities/graph_edges, fail-soft ModelRouter extraction on every message,
> /graph search/neighbors/catch-me-up (membership-gated), copilot citations in /ai/chat.
> Residual: frontend surfaces for citations/catch-me-up; meeting→graph wiring polish.
- Product graph schema + T0 entity-tagging pipeline (§4.2)
- Copilot v2: graph-RAG answers with citations; "catch me up" graph-delta; ClawShield PII scrub visible in UI before every cloud call
- Meeting pipeline hardened (lowest coverage, 62%): record → Whisper → summary + action items <60s, action items land in the graph
- Workspace-scoped full-text + semantic search (<500ms PRD target)
- **Gate:** the 3-minute demo — invite → chat → copilot cites graph → meeting auto-summarized → action item tracked

### Phase 4 — Consensus layer + benchmarks · ✅ **COMPLETE 2026-06-10** · KPI MET
> ModelRouter T0/T1/T2 + judge reconciliation, model_routes.json artifact, router-stats
> endpoint, benchmarks/ harness with golden sets + --write regeneration. Live-verified
> T0 against local Ollama (gemma-4b→gemma4:e2b, local_fraction 1.0).
>
> **Measured scorecard (2026-06-10, live gemma-4b local vs kimi-k2.5 via OpenRouter):**
> classify 0.833 = 0.833 (parity) · summarize 0.605 vs 0.662 (91.4%) ·
> extract_actions 0.837 vs 0.846 (98.9%). All three tasks within the 10% local-preference
> margin → routing table keeps **100% of routed calls local**, exceeding the ≥70% goal
> at benchmark-equal quality.
- ModelRouter service with T0/T1/T2 tiers + escalation policy (§5.1)
- Benchmark harness + golden sets; generated `model_routes.json`; CI scorecard (§5.2)
- Per-workspace token metering (feeds billing + the pricing page "70% local" claim)
- **Gate:** ≥70% calls on T0 local at equal-or-better golden-set quality

### Phase 5 — Monetization & launch · 🔧 scaffolding **COMPLETE 2026-06-10**, awaiting keys
> Done: Stripe per-seat checkout (Owner/Admin-gated), signature-verified webhook with
> full subscription lifecycle, workspace_billing model, plan gating helper, Upgrade UI.
> All mocked-tested (suite 371). Remaining: STRIPE_SECRET_KEY + STRIPE_PRICE_PRO +
> webhook secret (config-only), Clerk keys for live signup, then the end-to-end
> stranger→signup→invite→chat→cited-answer→pay demo run = **v2.0**.
- Stripe per-seat: Free (capped AI, 1 workspace) / Pro (consensus tier, unlimited graph memory) / Enterprise (on-prem Helm path, SSO)
- Self-serve funnel instrumented (PostHog): signup → invite → activation → retention curves
- Security page + the gap-analysis lineage as diligence collateral; `dclaw-manifest.json`
- **v2.0 release criteria:** a stranger signs up, invites a teammate, the copilot answers from the team's graph, hits the paywall, pays — with every step on dashboards

---

## 7. Access & Credentials Request (structured)

> Fill `Value/Where` and I can execute end-to-end. Storage: local `.env` (gitignored),
> GitHub Actions secrets, and Vercel/Fly env — never committed.

| # | Credential | Purpose | Scope needed | Phase | Store in |
|---|---|---|---|---|---|
| 1 | GitHub access (`gh auth login` or PAT) | push branches/PRs to `dclawstack/dclaw-chat`, Actions secrets | `repo`, `workflow` | 0 | local keychain |
| 2 | Neon API key + project `DATABASE_URL` | schema migration, branch-per-PR | project admin | 1 | `.env`, GH secrets |
| 3 | Vercel — ✅ **via CLI** (logged in as `tharuni-01`, owner decision: no token) | frontend deploys via `vercel` CLI | CLI session | 1 | local keychain |
| 4 | ~~Fly.io/Railway token~~ | **DROPPED** — backend runs locally (owner decision 2026-06-10) | — | — | — |
| 5 | ~~Upstash Redis~~ | **DROPPED** — single local instance, per-process limits accurate | — | — | — |
| 6 | ~~Managed realtime keys~~ | **DROPPED** — in-process WS managers correct for one instance | — | — | — |
| 7 | ~~Blob storage~~ | **DROPPED** — local disk + authed serve route | — | — | — |
| 8 | Logto tenant (endpoint, app ID/secret, JWKS URL, audience, issuer) | end-to-end auth | one app config | 0 | frontend + API env |
| 9 | OpenRouter API key | T1/T2 cloud models | standard | 0 (exists in `.env.example` slot) | API env |
| 10 | NVIDIA NIM key | DeepSeek tier (optional) | standard | 4 | API env |
| 11 | Stripe test + live keys, webhook secret | billing | restricted key | 5 | API env, GH secrets |
| 12 | Sentry DSN | error tracking (required in prod) | project DSN | 1 | API + frontend env |
| 13 | PostHog key | product analytics | project key | 5 | frontend env |

Minimum to start **today**: #1 (GitHub) — Phase 0 is pure code on the current stack.
Minimum for Phase 1: #2, #3, #4.

---

## 8. Autonomy Model (how this gets executed end-to-end)

- Work proceeds phase-gated; each phase = one PR train on a `v2/<phase>` branch series
- Dev agents follow `AGENTS.md` + this plan; the graphify graph is the shared map; consensus review (the `pathb` pattern) gates security-touching PRs
- Every phase's exit gate is an automated check, not a judgment call
- Standing cadence: nightly `graphify update`, benchmark scorecard on model changes, Sentry/analytics review weekly

*Supersedes PLAN-v1.2 scheduling. REVISED-PRD v2.3 feature definitions remain the product source of truth except where §2 (infra) and §1 (P2 freeze) override.*

> §7 #1 GitHub access: ✅ confirmed 2026-06-10 (account `tharuni-01`, repo+workflow scopes).
