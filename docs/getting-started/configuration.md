# Configuration

## Environment Variables

### Backend

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://postgres:postgres@localhost:5432/dclaw_chat` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `CORS_ORIGINS` | Allowed CORS origins | `*` |

### Frontend

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API base URL | `/api` |
| `NEXT_PUBLIC_APP_NAME` | App display name | `DClaw Chat` |

## Kubernetes Resources

Adjust resource limits in the DClawApp CRD:

```yaml
spec:
  resources:
    limits:
      cpu: 1000m
      memory: 2Gi
    requests:
      cpu: 250m
      memory: 512Mi
```
