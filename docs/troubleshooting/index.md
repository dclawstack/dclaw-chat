# Troubleshooting

Common issues and solutions for DClaw Chat.

## Quick Diagnostics

```bash
# Check app pods
kubectl get pods -n dclaw-chat

# Check logs
kubectl logs -n dclaw-chat deployment/dclaw-chat-backend

# Check database
kubectl get clusters -n dclaw-chat
```

## Sections

- [Common Issues](./common-issues)
- [FAQ](./faq)
