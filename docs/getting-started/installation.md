# Installation

## Via DPanel

1. Open DPanel at `https://panel.yourdomain.com`
2. Find **DClaw Chat** in the app grid
3. Click **Install**
4. The DClaw Operator will provision:
   - Namespace: `dclaw-chat`
   - Frontend deployment (Next.js)
   - Backend deployment (FastAPI)
   - PostgreSQL database (CloudNativePG)
   - Ingress with TLS

## Via kubectl

```bash
# Apply the DClawApp CRD
kubectl apply -f - <<EOF
apiVersion: platform.dclaw.io/v1
kind: DClawApp
metadata:
  name: chat
spec:
  appId: chat
  appName: DClaw Chat
  version: 0.2.0
  category: communication
  enabled: true
  frontend:
    image: ghcr.io/dclawstack/dclaw-chat:latest
    replicas: 2
  backend:
    image: ghcr.io/dclawstack/dclaw-chat-backend:latest
    replicas: 2
  database:
    enabled: true
    storage: 10Gi
  ingress:
    enabled: true
    host: chat.yourdomain.com
    tls: true
EOF
```

## Verify

```bash
kubectl get pods -n dclaw-chat
kubectl get ingress -n dclaw-chat
```
