# DClaw Chat — Development Swarm

## Agent Roles

| Agent | Domain | Repo Path | Current Status |
|-------|--------|-----------|----------------|
| **Frontend Agent** | Next.js UI, components, styling | `components/`, `app/` | ✅ Active — Kimi CLI |
| **Backend Agent** | FastAPI, DB schemas, API routes | `backend/` (create) | ⏳ Queued |
| **Desktop Agent** | Tauri v2, native integrations | `src-tauri/` | ⏳ Queued |
| **DevOps Agent** | Helm, K8s, CI/CD | `helm/`, `.github/` | ⏳ Queued |
| **Shield Agent** | PII detection, anonymization | `lib/swarm/agents/shield-agent.ts` | ✅ Active — Kimi CLI |

## Ownership Rules

1. **No cross-agent edits** — Each agent owns its directory. If Agent A needs a change in Agent B's domain, open a TODO comment, don't modify.
2. **Interface contracts** — Backend/Frontend communicate via `types/api.ts` (to be created). Never break the contract without both agents agreeing.
3. **Main branch protection** — All agents branch: `feat/<agent-id>/<description>`
4. **Daily sync** — Vault coordinator updates `Obsidian-Vault/04-PRODUCTS/01-DClaw-Chat/` with progress.

## Parallel Work Streams

```
Stream 1: Frontend + Backend (API contract first)
Stream 2: Desktop + DevOps (Tauri build pipeline)
Stream 3: Shield + Memory (local-only agents, no deps)
```

## Agent Handoff Protocol

When an agent hits a boundary, write a handoff block:

```typescript
// TODO[BackendAgent]: Implement POST /api/chat/completions
// Contract: Accepts { messages, model, stream? }
// Returns: { id, choices[], usage }
// See: types/api.ts line 45
```

## Current Blockers

| Blocker | Owner | Resolution |
|---------|-------|------------|
| Apple Developer Cert | User | Defer to v1.1 — unsigned builds for now |
| CloudNativePG types in operator | dclaw-platform | Add `postgresql.cnpg.io` import |
| Ollama local endpoint | Backend Agent | Standardize on `http://localhost:11434` |

## Quick Start for New Agents

```bash
# 1. Read this file
# 2. Check Obsidian Vault for latest specs
# 3. Claim a work stream by updating this file
# 4. Branch: git checkout -b feat/<agent-id>/task-name
# 5. Work in your domain only
# 6. Push PR, tag @frontend-agent for review
```
