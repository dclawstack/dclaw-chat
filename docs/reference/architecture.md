# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        User Browser                          │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼──────────────────────────────────┐
│                   Kubernetes Cluster                         │
│  ┌──────────────┐         ┌──────────────┐                  │
│  │   Ingress    │────────▶│  Frontend    │  Next.js 14     │
│  │   (nginx)    │         │  (3 replicas)│                  │
│  └──────────────┘         └──────┬───────┘                  │
│                                  │ API calls                 │
│  ┌──────────────┐         ┌──────▼───────┐                  │
│  │   Ingress    │────────▶│  Backend     │  FastAPI        │
│  │   (nginx)    │         │  (3 replicas)│                  │
│  └──────────────┘         └──────┬───────┘                  │
│                                  │ SQLAlchemy                │
│  ┌───────────────────────────────▼──────────┐               │
│  │         CloudNativePG Cluster            │               │
│  │    PostgreSQL 15 (3 instances)           │               │
│  └──────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ┌────────┐  ┌──────────┐  ┌──────────┐
         │ Ollama │  │OpenRouter│  │  Logto   │
         │ (local)│  │ (cloud)  │  │  (auth)  │
         └────────┘  └──────────┘  └──────────┘
```

## Data Flow

### 1. Sending a Message

1. User types message in React frontend
2. Frontend POSTs to `/api/v1/chat/completions`
3. Backend validates JWT via Logto
4. Message saved to PostgreSQL via SQLAlchemy
5. Backend routes to Ollama (local) or OpenRouter (cloud)
6. If cloud: ClawShield scrubs PII before sending
7. AI response saved to PostgreSQL
8. Response returned to frontend

### 2. Loading Conversation History

1. Frontend GETs `/api/v1/conversations/{id}`
2. Backend queries PostgreSQL with `selectinload` for messages
3. Response serialized via Pydantic models
4. Frontend renders message list with React

## Directory Structure

```
dclaw-chat/
├── frontend/              # Next.js 14 App Router
│   ├── src/app/           # Pages (chat, settings)
│   ├── src/components/    # Chat UI components
│   └── src/lib/           # API client, utilities
├── backend/               # FastAPI
│   ├── app/
│   │   ├── core/          # Config, database, auth, exceptions
│   │   ├── models/        # SQLAlchemy ORM
│   │   ├── schemas/       # Pydantic validation
│   │   ├── repositories/  # Data access layer
│   │   ├── services/      # Business logic + AI integration
│   │   ├── api/v1/        # HTTP routers
│   │   └── main.py        # App factory
│   └── tests/
│       ├── unit/          # Repository tests
│       └── integration/   # API endpoint tests
├── helm/                  # Kubernetes manifests
└── docs/                  # Documentation
```

## Design Decisions

### Why FastAPI + SQLAlchemy 2.0?

- **Async-first**: Handles many concurrent chat sessions
- **Type safety**: Pydantic + SQLAlchemy `Mapped[]` catches errors at dev time
- **Auto-docs**: OpenAPI spec generated from code

### Why Next.js App Router?

- **Server Components**: Reduce client JS bundle
- **Streaming**: React 18 Suspense for AI response streaming
- **SEO**: Static generation for landing pages

### Why Repository Pattern?

- **Testability**: Mock repositories in unit tests
- **Swapability**: Replace PostgreSQL with another DB without touching services
- **Clean architecture**: Business logic stays pure
