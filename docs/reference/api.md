# API Reference

## Base URL

```
https://chat.yourdomain.com/api
```

## Authentication

API requests require a Bearer token:

```bash
curl -H "Authorization: Bearer $TOKEN"   https://chat.yourdomain.com/api/health
```

## Endpoints

### Health Check

```http
GET /health
```

**Response:**
```json
{"status": "ok"}
```

### App-Specific Endpoints

See the app's OpenAPI spec at `/openapi.json` for complete endpoint documentation.

## Error Handling

All errors follow the RFC 7807 Problem Details format:

```json
{
  "type": "https://api.dclawstack.io/errors/not-found",
  "title": "Resource not found",
  "status": 404,
  "detail": "The requested resource does not exist."
}
```
