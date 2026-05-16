---
tags: [meta, prd, revised, swarm]
version: 2.3
date: 2026-05-16
app_id: chat
app_name: DClaw Chat
category: Communication
status: P0
---

# 📘 DClaw Chat — Revised PRD v2.3

> **The single document every agent must read before writing code for this app.**
> Generated from DClaw Master PRD v2.2. Read the Master PRD first: https://raw.githubusercontent.com/dclawstack/dclaw-prd/main/DClaw-Master-PRD.md

---

## 1. Product Identity

| Field | Value |
|-------|-------|
| **App ID** | `chat` |
| **Name** | DClaw Chat |
| **Category** | Communication |
| **Tagline** | AI conversations that remember |
| **Color** | #3B82F6 |
| **Phase** | P0 |
| **Port (Frontend Dev)** | 3002 (Assigned) |
| **Port (Backend Dev)** | 8008 (Assigned) |
| **Maturity Tier** | 🟢 Tier 1 — Mature |

---

## 2. Current State Assessment

### 2.1 Scaffold Status
| Component | Status | Notes |
|-----------|--------|-------|
| `frontend/` | ❌ | Next.js 14+ app |
| `backend/` | ✅ | FastAPI + SQLAlchemy 2.0 |
| `docs/` | ✅ | getting-started, guides, reference, releases |
| `helm/` | ✅ | K8s deployment manifests |
| `.github/workflows/` | ✅ | CI/CD + Claude integration |
| `AGENTS.md` | ✅ | Per-repo agent instructions |
| `PLAN-v1.2.md` | ✅ | Feature roadmap |
| `docker-compose.yml` | ✅ | Local dev stack |
| `tests/` | ✅ | pytest + pytest-asyncio |
| `alembic/` | ✅ | Database migrations |
| `dclaw-manifest.json` | ❌ | DPanel registration |

### 2.2 Code Maturity
| Metric | Value |
|--------|-------|
| Python source files (backend) | ~53 |
| TypeScript/TSX files (frontend) | ~46 |
| Total source files | ~99 |
| Tests | ✅ Present |
| Alembic migrations | ✅ Present |
| DPanel manifest | ❌ Missing |

### 2.3 Feature Maturity
- **P0 Foundation:** Partially implemented
- **P1 Platform:** Not yet started
- **P2 Vertical:** Not yet started

---

## 3. Gap Analysis

| # | Gap | Severity | Fix |
|---|-----|----------|-----|
| 1 | Missing `frontend/` directory | 🔴 | Scaffold Next.js 14+ frontend with shadcn/ui |
| 2 | Missing `dclaw-manifest.json` | 🔴 | Create frontend/public/dclaw-manifest.json for DPanel |
| 3 | Frontend at repo root instead of `frontend/` — breaks canonical structure | 🔴 | Restructure into backend/ + frontend/ or document exception |

---

## 4. Sacred Architecture & Tech Stack

> **NON-NEGOTIABLE. Every DClaw product MUST use this exact stack.**

| Layer | Technology | Version |
|-------|------------|---------|
| **Frontend** | Next.js 14+ | App Router, Tailwind CSS, shadcn/ui |
| **Backend** | FastAPI | Pydantic v2, SQLAlchemy 2.0, asyncpg |
| **Database** | PostgreSQL 16 | CloudNativePG operator in K8s |
| **Vector DB** | Qdrant / pgvector | Only if RAG / semantic search |
| **Cache / Bus** | Redis | 7.x |
| **Object Storage** | MinIO | Latest |
| **Workflow** | Temporal.io | Only if automation/orchestration |
| **Auth** | Logto | JWT validation on all protected routes |
| **Billing** | Stripe | Metered or per-seat |
| **K8s Operator** | Go + controller-runtime | 0.18 |
| **LLM Local** | Ollama | Apple Silicon |
| **LLM Cloud** | OpenRouter + Kimi K2.5 | Fallback |
| **Monitoring** | Prometheus + Grafana | Latest |

### 4.1 Python Rules
- `ruff` formatting enforced
- Type hints on ALL public APIs
- `pydantic` v2 for schemas
- `sqlalchemy` 2.0 style (`Mapped`, `mapped_column`)
- `pytest` + `pytest-asyncio` for tests
- Functions < 50 lines
- No `print()` — use `structlog`

### 4.2 TypeScript / Next.js Rules
- Strict TypeScript (`strict: true`)
- Tailwind for ALL styling
- `cn()` utility for conditional classes
- No `any` without `// @ts-ignore`

### 4.3 Docker Standards
- Port mappings MUST match container listen port
- Healthchecks MUST use binaries present in base image
- `docker compose config` must pass before shipping
- Service type MUST be `ClusterIP`
- TLS required on all ingress

---

## 5. P0 Foundation Features (Must Have — Demo Ready)

> **Every P0 MUST include an AI Copilot per YC S25/W26 RFS.**

| # | Feature | Description | AI Component | Acceptance Criteria |
|---|---------|-------------|--------------|---------------------|
| P0.1 | **AI Chat Copilot** | Workspace assistant in every channel that answers questions, summarizes threads, suggests actions. | LLM-powered thread summarization + action suggestion | Summarizes 100+ message threads in <2s; suggests 3 actionable items |
| P0.2 | **Channel & DM Messaging** | Real-time channels and direct messages with persistence. | AI-powered smart replies + tone adjustment | Create/join channels; send DMs; message history persists in PostgreSQL |
| P0.3 | **File Sharing & Search** | Upload, preview, and full-text search across all shared files. | AI document summarization + OCR extraction | Upload files up to 50MB; search returns results in <500ms |
| P0.4 | **Notifications & Mentions** | Smart notification system with @mentions, threads, and do-not-disturb. | AI priority ranking + quiet-hours optimization | @mentions trigger push; DND mode suppresses non-urgent alerts |

---

## 6. P1 Platform Features (Should Have — v1.1–1.2)

| # | Feature | Description | AI Component | Acceptance Criteria |
|---|---------|-------------|--------------|---------------------|
| P1.1 | **Meeting Summaries** | Auto-generate meeting summaries from voice channel recordings. | Whisper transcription + LLM summarization | Record voice channel → transcript → summary within 60s of end |
| P1.2 | **Breakout Rooms** | Host can split channel into breakout rooms for focused discussions. | AI room topic suggestion + auto-grouping | Create 2-8 breakout rooms; participants auto-assigned by topic |
| P1.3 | **Workflow Integrations** | Connect Chat to Flow, Task, and Calendar for automated actions. | Agent-triggered workflow execution | Send message → auto-create task in DClaw Task; bidirectional sync |
| P1.4 | **SSO & Enterprise Auth** | Logto-powered SSO with SAML/OIDC enterprise connectors. | AI admin assistant for permission recommendations | SAML 2.0 + OIDC support; RBAC with 4 default roles |

---

## 7. P2 Vertical / Scale Features (Could Have — v1.3+)

| # | Feature | Description | AI Component | Acceptance Criteria |
|---|---------|-------------|--------------|---------------------|
| P2.1 | **Polling & Q&A** | Live polls and moderated Q&A sessions in channels. | AI poll question generation + sentiment analysis | Create polls with up to 10 options; Q&A upvotes sort questions |
| P2.2 | **Recording & Playback** | Record voice/video channels with searchable playback. | AI chapterization + key-moment detection | Recordings stored in MinIO; searchable transcript with timestamps |
| P2.3 | **White-Label Embeds** | Embed chat widgets into external websites with custom branding. | AI greeting message customization | IFrame embed code; custom CSS + logo upload |
| P2.4 | **E2E Encryption** | Optional end-to-end encryption for DMs and sensitive channels. | AI key-rotation scheduling | Signal Protocol implementation; key verification via QR code |

---

## 8. Scaffold Checklist

Before marking this app "shipped", confirm:

- [ ] `frontend/` with Next.js 14+, Tailwind, shadcn/ui
- [ ] `backend/` with FastAPI, Pydantic v2, SQLAlchemy 2.0, asyncpg
- [ ] `docs/` with getting-started, guides, reference, releases, troubleshooting
- [ ] `helm/` with Chart.yaml, values.yaml, templates (deployment, service, ingress, cloudnativepg)
- [ ] `.github/workflows/` with build-backend.yml, build-frontend.yml, deploy.yml, claude.yml
- [ ] `frontend/public/dclaw-manifest.json` for DPanel registration
- [ ] `backend/tests/` with pytest + pytest-asyncio
- [ ] `backend/alembic/` with initial migration
- [ ] `Dockerfile` + `docker-compose.yml` with correct healthchecks
- [ ] Health endpoint at `/health` returning `{"status":"ok"}`
- [ ] `AGENTS.md` with per-repo instructions
- [ ] `PLAN-v1.2.md` with feature roadmap
- [ ] Port assigned from registry and documented
- [ ] No hardcoded secrets — use `.env.example` + K8s Secrets
- [ ] Non-root containers in Dockerfile

---

## 9. AI Copilot Mandate (YC S25/W26 Requirement)

Every DClaw app MUST have an AI Copilot as its first P0 feature. The copilot must:
1. Be contextually aware of the app's domain data
2. Use RAG over the app's knowledge base where applicable
3. Suggest next actions, not just answer questions
4. Be accessible from every page via floating chat or sidebar
5. Fall back to local Ollama when cloud is unavailable

---

## 10. Next Tasks for Vibe Coders

1. **Audit current state**: Verify all P0 features are complete and documented.
2. **Implement P1 features**: Build the 4 P1 features to reach v1.1 platform readiness.
3. **Add advanced features**: Begin P2 features for competitive differentiation.
4. **Optimize and scale**: Improve test coverage, add performance monitoring, and refine UX.

---

## 11. Domain Research Notes

Inspired by Mattermost, Zulip, Slack, Discord. YC vertical SaaS: high-frequency usage + team stickiness.

---

## 12. Links & Resources

| Resource | URL |
|----------|-----|
| **Master PRD** | https://raw.githubusercontent.com/dclawstack/dclaw-prd/main/DClaw-Master-PRD.md |
| **GitHub Org** | https://github.com/dclawstack |
| **DPanel** | https://dpanel.dclawstack.io |
| **Port Registry** | See `dclaw-platform/PORT_REGISTRY.md` |
| **App PRD Template** | Obsidian Vault → `00-META/📐 App PRD Template.md` |
| **Scaffold Source** | `dclaw-scaffold/` in DClaw-Stack |

---

*Revised PRD version: 2.3*
*Generated: 2026-05-16 by DClaw Stack Generator*
*Next review: When P0 features are complete or architecture changes*
