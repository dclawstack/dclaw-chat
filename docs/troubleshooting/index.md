# Troubleshooting

Common issues and their solutions.

## Quick Diagnostics

```bash
# Backend health
curl http://localhost:8000/api/v1/health

# Database connectivity
curl http://localhost:8000/api/v1/health/detailed

# Frontend build
cd frontend && npm run build

# Backend tests
cd backend && pytest
```

## Categories

- [Common Issues](./common-issues)
- [FAQ](./faq)
