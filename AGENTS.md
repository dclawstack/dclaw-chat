# DClaw Chat — Agent Development Guide

> **Read this file first before making any code changes.**
> This document is the source of truth for architecture, anti-patterns, and development workflow.

## App Identity

**DClaw Chat** is an AI-native multi-model conversation app. Users chat with local LLMs (Ollama) or cloud LLMs (OpenRouter, Kimi) in a unified interface.

- **Backend Port:** `8000` (FastAPI)
- **Frontend Port:** `3000` (Next.js, served via nginx on port 80 in container)
- **Database:** `dclaw_chat` (PostgreSQL)
- **Base API Path:** `/api/v1`

## Architecture Lock — DO NOT CHANGE

These are non-negotiable. If an agent suggests changing them, reject it.

### Backend
- **FastAPI** with `lifespan` handler for startup/shutdown
- **SQLAlchemy 2.0** — `DeclarativeBase` from `app.models.base`, NOT `declarative_base()`
- **Pydantic v2** schemas with `ConfigDict(from_attributes=True)`
- **Async SQLAlchemy** — `create_async_engine` + `async_sessionmaker`
- **Repository pattern** — all DB access goes through `app/repositories/`
- **Dependency injection** — use `Depends(get_db)`, never instantiate `AsyncSession` manually
- **NO MOCK DATA** — never use in-memory `dict`s for persistence. Always create a repository.

### Frontend
- **Next.js 14+ App Router** — no Pages Router
- **Tailwind CSS** + **shadcn/ui** components in `src/components/ui/`
- **API client** in `src/lib/api.ts` — typed fetch wrapper, never inline `fetch` calls in pages
- **Environment variables** — `NEXT_PUBLIC_API_URL` is baked at build time. Frontend Dockerfile MUST declare `ARG NEXT_PUBLIC_API_URL`.

### Docker
- **Backend:** `python:3.11-slim`, non-root `appuser`, healthcheck with `python urllib.request.urlopen()`
- **Frontend:** `node:20-alpine` builder + nginx:alpine runner, port 80
- **Compose:** host port ≠ container port is OK, but container port MUST match `EXPOSE`/`ENV PORT`

## Directory Structure

```
dclaw-chat/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── main.py          # FastAPI factory
│   │   │   ├── routes/
│   │   │   └── v1/
│   │   │       ├── chat.py      # Message CRUD + streaming
│   │   │       ├── models.py    # LLM availability & selection
│   │   │       └── health.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py      # engine, get_db, init_db
│   │   │   └── logging.py
│   │   ├── models/
│   │   │   ├── base.py          # Base(DeclarativeBase)
│   │   │   ├── message.py
│   │   │   └── conversation.py
│   │   ├── repositories/        # CRUD layer
│   │   ├── schemas/             # Pydantic v2
│   │   └── services/
│   │       └── llm_service.py   # Ollama + OpenRouter proxy
│   ├── alembic/
│   ├── tests/
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router
│   │   ├── components/
│   │   │   ├── ui/              # shadcn/ui
│   │   │   └── chat/
│   │   └── lib/
│   │       └── api.ts
│   └── Dockerfile
├── docker-compose.yml
├── helm/
└── .env.example
```

## Anti-Patterns — NEVER DO

| Anti-Pattern | Why It Breaks Things | Correct Alternative |
|--------------|---------------------|---------------------|
| `declarative_base()` in `database.py` | Creates separate metadata registry → zero tables created | `from app.models.base import Base` |
| `curl` in healthcheck on `python:*-slim` | Image has no `curl` → healthcheck fails silently | `python -c "import urllib.request; urllib.request.urlopen(...)"` |
| In-memory `MOCK_*` dicts | Data lost on restart, no relationships, not testable | Create `app/repositories/{entity}_repo.py` |
| Missing `ARG NEXT_PUBLIC_API_URL` in frontend Dockerfile | Frontend bakes wrong API URL at build time | Add `ARG NEXT_PUBLIC_API_URL` before `RUN npm run build` |
| Manual `get_db()` with `__anext__()` | Session leaks, transaction bugs | `Depends(get_db)` in route signatures |
| Hardcoded `localhost:PORT` in `next.config.*` | Breaks in Docker, K8s, and any non-localhost deploy | Use `process.env.NEXT_PUBLIC_API_URL` |
| Frontend calling absolute `http://localhost:8000` directly | CORS issues, no proxy, breaks in prod | Use relative paths or `API_BASE` from env |

## Database Rules

1. All models MUST inherit from `Base` in `app.models.base` (which inherits `DeclarativeBase`)
2. All models MUST use `Mapped[...]` and `mapped_column()`
3. **Never use `default_factory=` in `mapped_column()`** — use `default=` instead (SQLAlchemy 2.0 style)
3. Relationships MUST specify `lazy="selectin"` for async safety
4. All new tables MUST get an alembic migration
5. `ondelete="CASCADE"` for child tables; `ondelete="SET NULL"` for optional refs

## How to Add a Feature

1. **Read this file** and `PLAN-v1.2.md` for context
2. **Backend:**
   - Add/update model in `app/models/`
   - Add/update schema in `app/schemas/`
   - Add repository in `app/repositories/`
   - Add/update router in `app/api/v1/`
   - Wire router in `app/api/v1/__init__.py` or `app/api/main.py`
   - Add tests in `tests/`
   - Generate alembic migration: `alembic revision --autogenerate -m "message"`
3. **Frontend:**
   - Add API types/functions to `src/lib/api.ts`
   - Add page in `src/app/` or component in `src/components/`
   - Use existing shadcn/ui components, don't invent new UI primitives
4. **Docker:**
   - Verify `docker compose config` passes
   - Verify `docker compose up -d` brings all services healthy
5. **Commit** with conventional commit message: `feat:`, `fix:`, `refactor:`

## Testing Requirements

- Every new repository MUST have at least one test file
- Every new router endpoint MUST be covered by a test
- Use `pytest-asyncio` with `async` test functions
- Use `httpx.AsyncClient` with `ASGITransport` for FastAPI integration tests
- Override `get_db` dependency with test database session

## Port Registry

| Service | Host Port | Container Port | Note |
|---------|-----------|----------------|------|
| chat-frontend | 3000 | 80 | nginx:alpine |
| chat-backend | 8000 | 8000 | uvicorn |
| chat-postgres | 5432 | 5432 | PostgreSQL |
