#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${1:-chat.dclawstack.io}"
EMAIL="${2:-admin@dclawstack.io}"
APP_DIR="/opt/dclaw-chat"

echo "🚀 DClaw Chat VPS Setup"
echo "   Domain: $DOMAIN"
echo "   SSL Email: $EMAIL"
echo ""

apt-get update
apt-get install -y docker.io docker-compose-plugin nginx certbot python3-certbot-nginx git curl ufw

systemctl enable docker
systemctl start docker

ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

mkdir -p "$APP_DIR"
cd "$APP_DIR"
if [ ! -d ".git" ]; then
  git clone https://github.com/dclawstack/dclaw-chat.git .
fi

if [ ! -f ".env" ]; then
  cat > .env <<EOF
DB_PASSWORD=$(openssl rand -base64 32)
OPENROUTER_API_KEY=
NEXT_PUBLIC_API_URL=https://$DOMAIN/api
CORS_ORIGINS=https://$DOMAIN
LOGTO_ENDPOINT=
LOGTO_AUDIENCE=
EOF
fi
source .env

docker compose pull
docker compose build --no-cache
docker compose up -d

sleep 5
docker exec dclaw-chat-ollama ollama pull gemma4:latest || true

cp deploy/nginx.conf "/etc/nginx/sites-available/$DOMAIN"
sed -i "s/chat.dclawstack.io/$DOMAIN/g" "/etc/nginx/sites-available/$DOMAIN"
ln -sf "/etc/nginx/sites-available/$DOMAIN" /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" || true

sleep 5
curl -sf "https://$DOMAIN/api/v1/health" && echo "✅ Backend healthy" || echo "⚠️  Check backend logs: docker logs dclaw-chat-backend"

cat > /etc/cron.daily/dclaw-chat-update <<'CRON'
#!/bin/bash
cd /opt/dclaw-chat && git pull origin main && docker compose up -d --build
CRON
chmod +x /etc/cron.daily/dclaw-chat-update

echo ""
echo "✅ DClaw Chat is live at: https://$DOMAIN"
echo "   Add OPENROUTER_API_KEY to $APP_DIR/.env if using cloud models"
