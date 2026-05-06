# API Reference

DClaw Chat exposes a REST API at `/api/v1`. Interactive docs are available at `/docs` when the backend is running.

## Authentication

All endpoints (except health checks) require a Bearer token:

```bash
Authorization: Bearer <jwt-token>
```

Tokens are issued by Logto. The backend validates them via JWKS.

## Endpoints

### Health

#### `GET /api/v1/health`

Basic health check.

**Response:**
```json
{
  "status": "ok",
  "service": "dclaw-chat-backend",
  "version": "1.0.0",
  "database": "ok"
}
```

#### `GET /api/v1/health/detailed`

Detailed health with sub-system checks.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "checks": {
    "database": {"status": "ok", "latency_ms": 2}
  }
}
```

### Conversations

#### `GET /api/v1/conversations`

List all conversations with message counts.

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "title": "Test Chat",
    "folder": null,
    "model": "gemma-4b",
    "created_at": "2026-05-07T00:00:00Z",
    "updated_at": "2026-05-07T01:00:00Z",
    "message_count": 12
  }
]
```

#### `POST /api/v1/conversations`

Create a new conversation.

**Request:**
```json
{
  "title": "New Chat",
  "folder": "Work",
  "model": "gemma-4b"
}
```

**Response:** `201 Created`

#### `GET /api/v1/conversations/{id}`

Get a single conversation with all messages.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "title": "Test Chat",
  "messages": [
    {"id": "uuid", "role": "user", "content": "Hello", "model": null, "created_at": "..."}
  ]
}
```

#### `PATCH /api/v1/conversations/{id}`

Update conversation metadata.

**Request:**
```json
{
  "title": "Renamed Chat",
  "folder": "Personal"
}
```

**Response:** `200 OK`

#### `DELETE /api/v1/conversations/{id}`

Delete a conversation and all its messages.

**Response:** `204 No Content`

### Chat Completions

#### `POST /api/v1/chat/completions`

Send a message and get an AI response.

**Request:**
```json
{
  "conversation_id": "uuid",
  "messages": [
    {"role": "user", "content": "What is the capital of France?"}
  ],
  "model": "gemma-4b",
  "stream": false,
  "temperature": 0.7
}
```

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "message": {
    "role": "assistant",
    "content": "The capital of France is Paris."
  },
  "model": "gemma-4b",
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0
  }
}
```

### Models

#### `GET /api/v1/models`

List available LLMs with availability status.

**Response:** `200 OK`
```json
[
  {
    "id": "gemma-4b",
    "name": "Gemma 4B",
    "provider": "local",
    "description": "Local Gemma 4B via Ollama",
    "available": true
  }
]
```

## Error Codes

| Status | Code | Description |
|--------|------|-------------|
| 400 | Bad Request | Invalid JSON or missing required fields |
| 401 | Unauthorized | Missing or invalid JWT token |
| 403 | Forbidden | Insufficient role permissions |
| 404 | Not Found | Conversation or message does not exist |
| 422 | Validation Error | Pydantic validation failed |
| 502 | Bad Gateway | LLM service (Ollama/OpenRouter) error |
