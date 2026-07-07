# Installation

## Clone the Repository

```bash
git clone https://github.com/dclawstack/dclaw-chat.git
cd dclaw-chat
```

## Backend Setup

### 1. Create Virtual Environment

We recommend **uv** for fast dependency resolution:

```bash
cd backend
uv venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows
```

Or with standard **venv**:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
uv pip install -e ".[dev]"
```

Or with pip:

```bash
pip install -e ".[dev]"
```

### 3. Set Up PostgreSQL

#### Option A: Local PostgreSQL

```bash
createdb dclaw_chat
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/dclaw_chat"
```

#### Option B: Docker PostgreSQL

```bash
docker run -d \
  --name dclaw-chat-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=dclaw_chat \
  -p 5432:5432 \
  postgres:15-alpine
```

#### Option C: CloudNativePG (Production)

See the [Helm deployment](#kubernetes-deployment) section for CloudNativePG setup.

### 4. Run Database Migrations

The schema is managed by Alembic. In development (`ENVIRONMENT=development`)
the app also auto-creates tables on startup, so this step is optional locally
— but in production the app **refuses to start** unless the database is at the
current migration head.

```bash
cd backend
alembic upgrade head
```

Upgrading an install that predates Alembic (tables already exist and match
the current schema)? Stamp it once instead of migrating:

```bash
alembic stamp head
```

### 5. Start the Backend

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000` with interactive docs at `/docs`.

## Frontend Setup

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Set Environment Variables

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Start the Development Server

```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`.

## Verify Installation

```bash
# Backend health check
curl http://localhost:8000/api/v1/health

# List available models
curl http://localhost:8000/api/v1/models
```

Both should return JSON responses.

## Next Steps

- [Quickstart](./quickstart) — Send your first message
- [Configuration](./configuration) — Customize models, auth, and more
