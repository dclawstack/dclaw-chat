# Technology Stack

## Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js | 14.2.3 | React framework with App Router |
| React | 18.3.1 | UI library |
| TypeScript | 5.4.5 | Type safety |
| Tailwind CSS | 3.4.3 | Utility-first styling |
| Lucide React | 0.378.0 | Icon library |
| class-variance-authority | 0.7.0 | Component variants |

### Build Output

- `next.config.js` uses `output: "standalone"` for minimal Docker images
- Tauri v2 desktop wrapper included for native builds

## Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Runtime |
| FastAPI | 0.110+ | Web framework |
| SQLAlchemy | 2.0+ | ORM |
| asyncpg | 0.29+ | Async PostgreSQL driver |
| Pydantic | 2.6+ | Data validation |
| pydantic-settings | 2.2+ | Environment config |
| httpx | 0.27+ | Async HTTP client |
| PyJWT | 2.8+ | JWT validation |
| cryptography | 42.0+ | Crypto primitives |

### Dev Dependencies

| Technology | Version | Purpose |
|------------|---------|---------|
| pytest | 8.0+ | Test framework |
| pytest-asyncio | 0.23+ | Async test support |
| pytest-cov | 5.0+ | Coverage reporting |
| aiosqlite | 0.20+ | Test database (SQLite) |

## Database

| Technology | Version | Purpose |
|------------|---------|---------|
| PostgreSQL | 15+ | Primary database |
| CloudNativePG | 1.22+ | K8s PostgreSQL operator |

## Infrastructure

| Technology | Version | Purpose |
|------------|---------|---------|
| Kubernetes | 1.28+ | Container orchestration |
| Helm | 3.14+ | Package management |
| nginx | 1.25+ | Ingress controller |
| cert-manager | 1.14+ | TLS certificate automation |

## AI / LLM

| Technology | Purpose |
|------------|---------|
| Ollama | Local LLM inference |
| OpenRouter | Cloud LLM aggregation |
| ClawShield | PII detection & scrubbing |

## Auth

| Technology | Purpose |
|------------|---------|
| Logto | Identity provider + JWT issuance |
| RBAC | Owner / Admin / Developer / User / Guest |
