# Best Practices

## Security

### 1. Always Use ClawShield for Sensitive Data

Before any message reaches a cloud LLM, ClawShield scrubs:
- Email addresses
- Phone numbers
- Credit card numbers
- API keys and tokens
- Social security numbers

**Verification:** Check logs for `shield.scrub` calls in `backend/app/services/ai_service.py`.

### 2. Validate JWT Tokens on Every Request

The auth middleware in `backend/app/core/deps.py` validates:
- Token signature (RS256 via Logto JWKS)
- Token expiration
- Audience claim
- User role for RBAC

### 3. Use HTTPS in Production

The Helm chart configures TLS via cert-manager:
```yaml
ingress:
  tls:
    enabled: true
    secretName: dclaw-chat-tls
```

### 4. Rotate OpenRouter API Keys

Set a calendar reminder to rotate keys every 90 days. Store them in Kubernetes secrets, never in Git.

## Performance

### 1. Connection Pooling

The asyncpg engine in `backend/app/core/database.py` handles connection pooling automatically. Tune with:
```python
create_async_engine(DATABASE_URL, pool_size=20, max_overflow=10)
```

### 2. Local-First AI

Default to Ollama for high-volume use cases. Only fall back to OpenRouter for:
- Complex reasoning tasks
- Models not available locally
- Burst traffic beyond local GPU capacity

### 3. Frontend Optimization

- Use `next/image` for optimized images
- Leverage React Server Components where possible
- Enable `standalone` output in `next.config.js` for Docker

## Reliability

### 1. Health Checks

The `/api/v1/health` endpoint returns:
```json
{
  "status": "ok",
  "service": "dclaw-chat-backend",
  "version": "1.0.0",
  "database": "ok"
}
```

Use this for Kubernetes liveness and readiness probes.

### 2. Graceful Degradation

If Ollama is offline, the app automatically tries OpenRouter. If both fail, the user sees a clear error message.

### 3. Database Backups

CloudNativePG handles automated backups. Verify with:
```bash
kubectl get scheduledbackup -n dclaw-chat
```

## Cost Optimization

| Strategy | Savings |
|----------|---------|
| Use Gemma 4B for 80% of queries | ~90% vs GPT-4o |
| Batch similar requests | Reduces API calls |
| Cache common responses | Redis integration ready |
| Set token limits | Prevents runaway costs |
