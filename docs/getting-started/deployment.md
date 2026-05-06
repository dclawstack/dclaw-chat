# Deployment

This guide covers two deployment paths:

1. **Failsafe Path** (recommended for validation) — Vercel frontend + Render backend
2. **Production Path** — Kubernetes with Helm

---

## Failsafe Path — Get Online in 10 Minutes

### Architecture

```
User → Vercel (Next.js frontend) → Render (FastAPI backend) → Neon (PostgreSQL)
```

### Step 1: Database (Neon)

1. Go to [neon.tech](https://neon.tech) and sign up
2. Create a project named `dclaw-chat`
3. Copy the connection string:
   ```
   postgresql+asyncpg://user:pass@ep-xxx.us-east-1.aws.neon.tech/dclaw_chat?ssl=require
   ```

### Step 2: Backend (Render)

1. Go to [render.com](https://render.com) and connect your GitHub
2. **New Web Service** → select `dclawstack/dclaw-chat`
3. Configure:
   - **Root Directory**: `backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -e .`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables:
   - `DATABASE_URL` = Neon connection string
   - `OPENROUTER_API_KEY` = your key
   - `CORS_ORIGINS` = your Vercel domain (see Step 3)
5. Deploy

Your backend will be live at `https://dclaw-chat-backend.onrender.com`.

### Step 3: Frontend (Vercel)

1. Go to [vercel.com](https://vercel.com) and import `dclawstack/dclaw-chat`
2. Vercel auto-detects Next.js — just click **Deploy**
3. Add environment variable:
   - `NEXT_PUBLIC_API_URL` = `https://dclaw-chat-backend.onrender.com`
4. Redeploy if needed

Your frontend will be live at `https://dclaw-chat.vercel.app`.

### Step 4: Verify

```bash
curl https://dclaw-chat-backend.onrender.com/api/v1/health
curl https://dclaw-chat.vercel.app
```

Both should return healthy responses.

### Step 5: Feature Freeze

Once the app works online, tag it:

```bash
git tag v1.0.0
git push origin v1.0.0
```

This marks the feature freeze. Only bug fixes after this point.

### Step 6: Add to DPanel

1. Update DPanel `lib/apps.ts`:
   - Set Chat status to `"live"`
   - Add the Vercel URL as the public domain
2. Push and deploy DPanel

### Cost

| Service | Tier | Monthly Cost |
|---------|------|-------------|
| Vercel | Hobby (free) | $0 |
| Render | Starter | $7 |
| Neon | Free Tier | $0 |
| **Total** | | **$7** |

---

## Production Path — Kubernetes

For enterprise use, deploy to your own K8s cluster.

### Prerequisites

- Kubernetes 1.28+
- Helm 3.14+
- cert-manager
- nginx ingress controller

### Deploy

```bash
cd helm/dclaw-chat

# Update values for your domain
# values.yaml:
#   ingress.host = chat.dclawstack.io

helm dependency build
helm upgrade --install dclaw-chat . \
  --namespace dclaw-chat \
  --create-namespace \
  --values values.prod.yaml
```

### Verify

```bash
kubectl get pods -n dclaw-chat
kubectl get ingress -n dclaw-chat
```

---

## Migration: Failsafe → Production

When ready to move from Vercel/Render to K8s:

1. **Database**: Export from Neon, import to CloudNativePG
2. **Backend**: Update Docker image tag, rollout deployment
3. **Frontend**: Update `NEXT_PUBLIC_API_URL` to K8s ingress, rebuild
4. **DNS**: Point `chat.dclawstack.io` to your K8s ingress IP
5. **Vercel/Render**: Keep as staging environments

---

## One-Click Deploy Buttons

### Vercel

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/dclawstack/dclaw-chat)

### Render

Use the `backend/render.yaml` in this repo for blueprint deploy.
