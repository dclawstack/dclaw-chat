# Common Issues

## Backend

### `ModuleNotFoundError: No module named 'app'`

**Cause:** Running from wrong directory.

**Fix:**
```bash
cd backend
python -m uvicorn app.main:app --reload
```

### `sqlalchemy.exc.OperationalError: connection refused`

**Cause:** PostgreSQL is not running or DATABASE_URL is incorrect.

**Fix:**
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Or use Docker
 docker run -d --name pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:15
```

### `502 Bad Gateway` on chat completion

**Cause:** Ollama is not running.

**Fix:**
```bash
ollama serve
# In another terminal:
ollama pull gemma:4b
```

Or switch to a cloud model in the UI.

### `401 Unauthorized` on all API calls

**Cause:** Logto is not configured or token is expired.

**Fix:**
- For development, set a mock JWT or disable auth
- For production, verify `LOGTO_ENDPOINT` and `LOGTO_AUDIENCE`

## Frontend

### `npm run build` fails with "Cannot find module"

**Cause:** Dependencies not installed.

**Fix:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Blank page after build

**Cause:** `NEXT_PUBLIC_API_URL` not set.

**Fix:**
```bash
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > frontend/.env.local
```

## Kubernetes

### Pod stuck in `CrashLoopBackOff`

**Cause:** Backend can't connect to database.

**Fix:**
```bash
kubectl logs -n dclaw-chat deployment/dclaw-chat-backend
kubectl get clusters -n dclaw-chat  # Verify CloudNativePG cluster is ready
```

### Ingress returns 502

**Cause:** Backend service not ready.

**Fix:**
```bash
kubectl get pods -n dclaw-chat
kubectl describe ingress -n dclaw-chat
```
