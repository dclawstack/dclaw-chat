---
tags: [product, chat, spec, p0]
status: in_progress
priority: 10
owner: frontend-agent + backend-agent
product: DClaw Chat
target_date: 2026-05-15
progress: 40%
---

# 💬 DClaw Chat PRD

**App ID:** `chat`
**Category:** communication
**Tagline:** "AI conversations that remember"
**Primary Color:** `#3B82F6`
**Domain:** chat.dclawstack.io

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  Tauri Desktop (macOS/Win/Linux)            │
│  └── WebView → Next.js 14 App               │
├─────────────────────────────────────────────┤
│  Next.js Frontend (Vercel / static export)  │
│  ├── components/chat/ (UI)                  │
│  ├── components/swarm/ (agent panel)        │
│  └── lib/swarm/ (runtime)                   │
├─────────────────────────────────────────────┤
│  FastAPI Backend (K8s: dclaw-chat)          │
│  ├── /api/v1/chat (completions)             │
│  ├── /api/v1/conversations (CRUD)           │
│  ├── /api/v1/models (list local/cloud)      │
│  └── /api/v1/export (PDF, Markdown)         │
├─────────────────────────────────────────────┤
│  Infrastructure                             │
│  ├── PostgreSQL (CloudNativePG)             │
│  ├── Redis (message bus + cache)            │
│  └── Ollama (local LLMs on M4)              │
└─────────────────────────────────────────────┘
```

---

## Completed (40%)

| Component | Status | Location |
|-----------|--------|----------|
| Next.js project scaffold | ✅ | `package.json` |
| MessageList + MessageItem | ✅ | `components/chat/MessageList.tsx` |
| ChatInput (voice, attach) | ✅ | `components/chat/ChatInput.tsx` |
| Sidebar (folders, history) | ✅ | `components/chat/Sidebar.tsx` |
| ModelSelector (local/cloud) | ✅ | `components/chat/ModelSelector.tsx` |
| VoiceButton (Web Speech API) | ✅ | `components/chat/VoiceButton.tsx` |
| Tauri v2 shell + CI | ✅ | `src-tauri/`, `.github/workflows/build-unsigned.yml` |
| Agent Swarm runtime | ✅ | `lib/swarm/` |
| ClawShield PII agent | ✅ | `lib/swarm/agents/shield-agent.ts` |
| App icons (placeholder) | ✅ | `src-tauri/icons/` |

---

## In Progress

| Component | Owner | Target |
|-----------|-------|--------|
| FastAPI backend | backend-agent | 2026-05-06 |
| PostgreSQL schema | backend-agent | 2026-05-06 |
| Ollama proxy endpoint | backend-agent | 2026-05-07 |
| Helm chart | devops-agent | 2026-05-07 |

---

## Backlog (P0)

| Feature | Priority | Notes |
|---------|----------|-------|
| SSO (Logto) | P0.5 | Enterprise requirement |
| Conversation export (PDF/MD) | P0.5 | User request |
| Desktop auto-updater | P1 | Tauri updater plugin |
| Voice output (TTS) | P1 | Coqui TTS integration |
| "Hey DClaw" wake word | P1 | Porcupine integration |
| Enterprise RBAC | P2 | Shield extension |

---

## API Contract (Frontend ↔ Backend)

```typescript
// POST /api/v1/chat/completions
interface ChatCompletionRequest {
  conversation_id: string;
  messages: { role: string; content: string }[];
  model: string;           // "gemma-4b" | "kimi-k2.5" | ...
  stream?: boolean;
  temperature?: number;
}

interface ChatCompletionResponse {
  id: string;
  message: { role: string; content: string };
  model: string;
  usage: { prompt_tokens: number; completion_tokens: number };
}

// GET /api/v1/conversations
// GET /api/v1/conversations/:id
// POST /api/v1/conversations
// DELETE /api/v1/conversations/:id

// GET /api/v1/models
interface ModelInfo {
  id: string;
  name: string;
  provider: "local" | "cloud";
  available: boolean;
}
```

---

## K8s Resources

| Resource | Spec |
|----------|------|
| Namespace | `dclaw-chat` |
| Frontend Replicas | 2 |
| Backend Replicas | 2 |
| CPU Request | 250m |
| Memory Request | 512Mi |
| Database | CloudNativePG cluster `dclaw-chat-db` |
| Ingress | `chat.dclawstack.io` |

---

## Docker & VPS Deployment

### Local / Single Server

```bash
docker compose up -d
```

Services:
- Frontend: http://localhost:3000 (maps to container port 80 via nginx)
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

### VPS (One-Liner)

```bash
curl -fsSL https://raw.githubusercontent.com/dclawstack/dclaw-chat/main/deploy/vps-setup.sh | bash -s chat.yourdomain.com you@email.com
```

### Compose Port Mapping

| Service | Host Port | Container Port | Reason |
|---------|-----------|----------------|--------|
| frontend | 3000 | 80 | `Dockerfile.frontend` uses `nginx:alpine` (port 80) |
| backend | 8000 | 8000 | `backend/Dockerfile` exposes 8000 |
| db | 5432 | 5432 | PostgreSQL default |
| ollama | 11434 | 11434 | Ollama default |

### Healthcheck

Backend uses `python -c urllib.request` (not `curl`) because `python:3.13-slim` does not include `curl`.

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"]
  interval: 10s
  timeout: 5s
  retries: 3
```

### Nginx Reverse Proxy

- `/` → `127.0.0.1:3000` (frontend)
- `/api/` → `127.0.0.1:8000` (backend)
- `/docs` → `127.0.0.1:8000/docs`

---

## Links

- Repo: https://github.com/dclawstack/dclaw-chat
- Frontend: `npm run dev` (port 3000)
- Desktop: `npm run tauri:dev`
- DEVELOPMENT-SWARM: [DEVELOPMENT-SWARM.md](./DEVELOPMENT-SWARM.md)
