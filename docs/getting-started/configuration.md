# Configuration

DClaw Chat is configured via environment variables. Create a `.env` file in the `backend/` directory.

## Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/dclaw_chat` | PostgreSQL connection string |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OPENROUTER_API_KEY` | — | OpenRouter API key (required for cloud models) |
| `OPENROUTER_URL` | `https://openrouter.ai/api/v1` | OpenRouter base URL |

## Auth Settings (Logto)

| Variable | Default | Description |
|----------|---------|-------------|
| `LOGTO_ENDPOINT` | — | Logto server URL |
| `LOGTO_AUDIENCE` | — | Logto API resource identifier |
| `LOGTO_JWKS_URL` | — | Logto JWKS endpoint for JWT validation |

When auth is configured, all API endpoints (except `/health`) require a valid JWT Bearer token.

## CORS Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:3002,http://localhost:1420` | Comma-separated allowed origins |

## Frontend Environment

Create `frontend/.env.local`:

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |

## Model Configuration

Models are defined in `backend/app/services/chat_service.py`:

```python
MODEL_PROVIDERS = {
    "gemma-4b": "local",
    "gemma-27b": "local",
    "qwen-32b": "local",
    "kimi-k2.5": "cloud",
    "claude-3.5-sonnet": "cloud",
    "gpt-4o": "cloud",
}
```

To add a new model:
1. Add the entry to `MODEL_PROVIDERS`
2. If local, add the Ollama mapping in `ollama_service.py`
3. If cloud, add the OpenRouter mapping in `openrouter_service.py`

## Kubernetes / Helm

See `helm/dclaw-chat/values.yaml` for production configuration:
- Replica counts
- Resource limits
- Ingress hosts
- TLS settings
- Database storage
