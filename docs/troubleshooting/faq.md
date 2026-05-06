# FAQ

## General

**Q: Can I use DClaw Chat without an internet connection?**

A: Yes, if you run Ollama locally. Local models (Gemma, Qwen) work entirely offline. Cloud models require internet.

**Q: Is my data sent to third parties?**

A: Only if you use cloud models. Local models keep all data on your machine. For cloud models, ClawShield scrubs PII before sending.

**Q: What LLMs are supported?**

A: Any model available via Ollama or OpenRouter. Default setup includes Gemma 4B/27B, Qwen 32B, Claude 3.5 Sonnet, GPT-4o, and Kimi K2.5.

## Development

**Q: How do I add a new model?**

A: Edit `backend/app/services/chat_service.py` and add the model to `MODEL_PROVIDERS`. If it's a local model, also add it to `OLLAMA_MODELS` in `ollama_service.py`.

**Q: Can I use a different database?**

A: The repository pattern makes it possible, but you'll need to:
1. Update `backend/app/core/database.py`
2. Adjust SQLAlchemy dialect features
3. Update Alembic configuration

**Q: How do I run tests?**

A:
```bash
cd backend
source .venv/bin/activate
pytest --cov=app --cov-report=term-missing
```

## Deployment

**Q: What's the minimum Kubernetes cluster size?**

A: 3 nodes, 4 vCPU, 8 GB RAM. For local testing, use Minikube or Kind.

**Q: How do I update the app?**

A:
```bash
# Build new images
docker build -t ghcr.io/dclawstack/dclaw-chat:latest .
docker build -t ghcr.io/dclawstack/dclaw-chat-backend:latest -f backend/Dockerfile .

# Push
docker push ghcr.io/dclawstack/dclaw-chat:latest
docker push ghcr.io/dclawstack/dclaw-chat-backend:latest

# Rollout
kubectl rollout restart deployment/dclaw-chat-frontend -n dclaw-chat
kubectl rollout restart deployment/dclaw-chat-backend -n dclaw-chat
```

**Q: Can I deploy without Kubernetes?**

A: Yes, use Docker Compose:
```yaml
version: "3.8"
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: postgres
  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/dclaw_chat
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
```

## Security

**Q: How is authentication handled?**

A: JWT tokens from Logto. The backend validates signatures via JWKS. RBAC supports 5 roles: Owner, Admin, Developer, User, Guest.

**Q: Is there audit logging?**

A: Every API call is logged with user ID, endpoint, and timestamp. Check the backend logs for `audit` entries.
