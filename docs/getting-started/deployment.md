# Deployment

## Path A: VPS (Recommended)

**Total control. Local AI models. One server for all apps.**

### What You Get
- A single VPS running everything via Docker Compose
- Nginx reverse proxy with SSL (Let's Encrypt)
- PostgreSQL + Ollama on the same machine
- Auto-updates via cron
- ~$20-40/month for a 4 CPU / 8 GB RAM server

### Requirements
- Fresh Ubuntu 22.04/24.04 VPS (Hetzner, DigitalOcean, AWS, etc.)
- A domain pointed at the VPS IP
- SSH access as root or sudo user

### One-Command Deploy

```bash
ssh root@your-vps-ip
curl -fsSL https://raw.githubusercontent.com/dclawstack/dclaw-chat/main/deploy/vps-setup.sh | bash -s chat.dclawstack.io admin@yourdomain.com
```

Or manually:

```bash
git clone https://github.com/dclawstack/dclaw-chat.git /opt/dclaw-chat
cd /opt/dclaw-chat
chmod +x deploy/vps-setup.sh
./deploy/vps-setup.sh chat.dclawstack.io admin@yourdomain.com
```

This script will:
1. Install Docker, Nginx, Certbot
2. Clone the repo
3. Build and start all containers
4. Pull default Ollama models
5. Configure Nginx with SSL
6. Set up auto-update cron

### Architecture on VPS

```
User → Nginx (443) → { / → Next.js, /api → FastAPI }
                           ↓
                    ┌──────┴──────┐
                    ↓             ↓
              PostgreSQL      Ollama
              (dclaw_chat)    (gemma, qwen)
```

### Environment Variables

Edit `/opt/dclaw-chat/.env`:

```env
DB_PASSWORD=your-secure-password
OPENROUTER_API_KEY=sk-or-v1-xxx
NEXT_PUBLIC_API_URL=https://chat.dclawstack.io/api
CORS_ORIGINS=https://chat.dclawstack.io
LOGTO_ENDPOINT=https://logto.yourdomain.io
LOGTO_AUDIENCE=https://chat.dclawstack.io/api
```

Then restart:
```bash
docker compose up -d
```

### Add to DPanel

```bash
cd /opt/dclaw-chat
./deploy/add-to-dpanel.sh chat.dclawstack.io ../dclaw-platform/dpanel
```

---

## Path B: Vercel + Render (Quick Test)

**For rapid validation only. Not for production.**

| Service | Purpose | Cost |
|---------|---------|------|
| Vercel | Next.js frontend | Free |
| Render | FastAPI backend | $7/mo |
| Neon | PostgreSQL | Free |

See previous versions of this doc for detailed steps.

---

## Path C: Kubernetes (Enterprise)

For production K8s clusters with Helm.

```bash
cd helm/dclaw-chat
helm dependency build
helm upgrade --install dclaw-chat . \
  --namespace dclaw-chat \
  --create-namespace
```

Requires:
- cert-manager
- nginx ingress
- CloudNativePG operator

## Database Migrations (all paths)

Production schema is managed exclusively by Alembic. The backend **refuses to
start** in production (`ENVIRONMENT=production`) unless the database is at the
current migration head — a missed migration fails loudly at deploy time
instead of erroring at runtime.

Run migrations before starting (or restarting) the backend, on every upgrade:

```bash
cd backend
alembic upgrade head   # DATABASE_URL must point at the production DB
```

- **VPS / Docker Compose**: run the command inside the backend container (or
  from the repo with `DATABASE_URL` exported) after `git pull` and before
  `docker compose up -d`.
- **Kubernetes**: run it as an init step or one-off `kubectl exec`/Job against
  the backend image before rolling the Deployment to the new version.
- **Existing installs created before Alembic** (tables already present and
  current): stamp once with `alembic stamp head`, then use `alembic upgrade
  head` for all future upgrades.
