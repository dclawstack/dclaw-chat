# DClaw Chat

> **AI conversations that remember.**
>
> A multi-model AI chat interface with persistent memory, voice input, and local or cloud LLM support. Switch between Ollama, OpenRouter, Claude, and GPT-4 on the fly.

[![Version](https://img.shields.io/badge/version-1.0.0-blue)](https://github.com/dclawstack/dclaw-chat)
[![Tests](https://img.shields.io/badge/tests-17%2F17%20passing-brightgreen)](./backend/tests)
[![Stack](https://img.shields.io/badge/stack-Next.js%2014%20%2B%20FastAPI%20%2B%20PostgreSQL-purple)](./docs/reference/stack.md)

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Design System](#design-system)
- [Quick Start](#quick-start)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [API Reference](#api-reference)
- [Architecture](#architecture)
- [Environment Variables](#environment-variables)
- [Contributing](#contributing)

---

## Features

| Feature | Description |
|---------|-------------|
| **Multi-Model Chat** | Switch between local (Ollama) and cloud (OpenRouter) LLMs |
| **Persistent History** | All conversations stored in PostgreSQL |
| **Voice Input** | Speech-to-text for hands-free chatting |
| **Folder Organization** | Group conversations by project or topic |
| **PII Shield** | Automatic scrubbing before cloud API calls |
| **Dark Mode** | DKube design system with deep purple neutrals |
| **Desktop App** | Tauri wrapper for native builds |
| **JWT Auth** | Logto integration with RBAC |

---

## Tech Stack

### Frontend
- [Next.js](https://nextjs.org/) 14 — App Router, React Server Components
- [Tailwind CSS](https://tailwindcss.com/) 3 — Utility-first styling
- [TypeScript](https://www.typescriptlang.org/) — Type safety
- [Lucide React](https://lucide.dev/) — Icons

### Backend
- [FastAPI](https://fastapi.tiangolo.com/) — Async Python web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) 2.0 — ORM with `Mapped[]` syntax
- [Pydantic](https://docs.pydantic.dev/) v2 — Data validation
- [asyncpg](https://magicstack.github.io/asyncpg/) — Async PostgreSQL driver

### Infrastructure
- [PostgreSQL](https://www.postgresql.org/) 15 — Primary database
- [Ollama](https://ollama.com/) — Local LLM inference
- [OpenRouter](https://openrouter.ai/) — Cloud LLM aggregation
- [Docker](https://www.docker.com/) + [Docker Compose](https://docs.docker.com/compose/) — Containerization
- [Nginx](https://nginx.org/) — Reverse proxy
- [Let's Encrypt](https://letsencrypt.org/) — Free SSL

### Testing
- [pytest](https://docs.pytest.org/) — Test framework
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) — Async test support
- [httpx](https://www.python-httpx.org/) — HTTP client for integration tests

---

## Design System

DClaw Chat uses the **DKube Design System** — shared across all DClaw apps.

| Token | Value | Usage |
|-------|-------|-------|
| Brand Purple | `#6B53A3` | Primary actions, links |
| Purple Light | `#9985BF` | Hover states |
| Purple Deep | `#4A3A7A` | Pressed states |
| Surface | `#0E0E10` | Page background |
| Surface Raised | `#1F1F23` | Cards, panels |
| Body | `#F4F2F8` | Primary text |
| Muted | `#9E9AAB` | Secondary text |

**Fonts:** Manrope (display), Inter (body), JetBrains Mono (code)

See [`../dclaw-platform/design-system/`](../dclaw-platform/design-system/) for the full token set.

---

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.11+
- PostgreSQL 15+ (or Docker)

### 1. Clone

```bash
git clone https://github.com/dclawstack/dclaw-chat.git
cd dclaw-chat
```

### 2. Backend

```bash
cd backend
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

Set up PostgreSQL and run:

```bash
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/dclaw_chat"
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Development

### Backend Structure

```
backend/
├── app/
│   ├── core/           # Config, database, auth, exceptions
│   ├── models/         # SQLAlchemy ORM
│   ├── schemas/        # Pydantic validation
│   ├── repositories/   # Data access layer
│   ├── services/       # Business logic + AI integration
│   ├── api/v1/         # HTTP routers
│   └── main.py         # App factory
└── tests/
    ├── unit/           # Repository tests
    └── integration/    # API endpoint tests
```

### Run Tests

```bash
cd backend
source .venv/bin/activate
pytest --cov=app --cov-report=term-missing
```

### Lint

```bash
ruff check app/
mypy app/
```

---

## Testing

| Layer | Count | Coverage |
|-------|-------|----------|
| Unit (repositories) | 8 | — |
| Integration (API) | 9 | — |
| **Total** | **17** | **All passing** |

```bash
cd backend && pytest -v
```

---

## Deployment

### Option A: VPS (Recommended)

One server. Total control. Local AI models.

```bash
ssh root@your-vps
curl -fsSL https://raw.githubusercontent.com/dclawstack/dclaw-chat/main/deploy/vps-setup.sh | bash -s chat.yourdomain.com you@email.com
```

Or manually:

```bash
git clone https://github.com/dclawstack/dclaw-chat.git /opt/dclaw-chat
cd /opt/dclaw-chat
./deploy/vps-setup.sh chat.yourdomain.com you@email.com
```

**What it sets up:**
- Docker + Docker Compose
- PostgreSQL + Ollama + FastAPI + Next.js
- Nginx reverse proxy with SSL (Let's Encrypt)
- Auto-update cron job

See [`docs/getting-started/deployment.md`](./docs/getting-started/deployment.md) for full details.

### Option B: Docker Compose (Local/Server)

```bash
docker compose up -d
```

Services:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Option C: Kubernetes

```bash
cd helm/dclaw-chat
helm dependency build
helm upgrade --install dclaw-chat . --namespace dclaw-chat --create-namespace
```

---

## API Reference

Interactive docs: `http://localhost:8000/docs`

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/health/detailed` | Detailed health with DB status |
| `GET` | `/api/v1/models` | List available LLMs |
| `POST` | `/api/v1/chat/completions` | Send a message |
| `GET` | `/api/v1/conversations` | List conversations |
| `POST` | `/api/v1/conversations` | Create conversation |
| `GET` | `/api/v1/conversations/{id}` | Get conversation with messages |
| `PATCH` | `/api/v1/conversations/{id}` | Update conversation |
| `DELETE` | `/api/v1/conversations/{id}` | Delete conversation |

All endpoints (except health) require a JWT Bearer token from Logto.

See [`docs/reference/api.md`](./docs/reference/api.md) for full spec.

---

## Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│   Nginx     │────▶│  Next.js        │────▶│  FastAPI    │
│  (443/SSL)  │     │  (Frontend)     │     │  (Backend)  │
└─────────────┘     └─────────────────┘     └──────┬──────┘
                                                    │
                                           ┌────────┴────────┐
                                           ↓                 ↓
                                      PostgreSQL          Ollama/
                                      (dclaw_chat)        OpenRouter
```

See [`docs/reference/architecture.md`](./docs/reference/architecture.md) for the full system diagram.

---

## Environment Variables

### Required

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL connection string |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://localhost:11434` | Local LLM endpoint |
| `OPENROUTER_API_KEY` | — | Cloud LLM API key |
| `LOGTO_ENDPOINT` | — | Auth server URL |
| `LOGTO_AUDIENCE` | — | JWT audience |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed frontend origins |

See [`docs/getting-started/configuration.md`](./docs/getting-started/configuration.md) for the full list.

---

## Contributing

1. Fork the repo
2. Create a branch: `git checkout -b feat/your-feature`
3. Write tests first
4. Make changes
5. Run tests: `pytest`
6. Commit: `git commit -m "feat: description"`
7. Push and open a PR

### Commit Convention

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `test:` Tests
- `chore:` Maintenance

---

## Code Manager

| Name | Role |
|------|------|
| Tharuni | Code Manager |

---

## License

MIT — see [LICENSE](./LICENSE) for details.

---

## Links

- [Docs](https://docs.dclawstack.io/apps/chat)
- [DPanel](https://panel.dclawstack.io)
- [Issues](https://github.com/dclawstack/dclaw-chat/issues)
- [DClaw Platform](https://github.com/dclawstack/dclaw-platform)
