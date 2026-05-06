# Quickstart

Get DClaw Chat running and send your first AI message in under 5 minutes.

## 1. Start Everything

Make sure both backend and frontend are running:

```bash
# Terminal 1: Backend
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

## 2. Open the App

Navigate to `http://localhost:3000` in your browser.

## 3. Create a Conversation

Click **"New Chat"** in the sidebar. A new conversation thread is created automatically.

## 4. Send a Message

Type a message in the input box and press **Enter** (or click the send button).

The app will:
1. Store your message in PostgreSQL
2. Route it to the selected LLM (Ollama local or OpenRouter cloud)
3. Stream the AI response back
4. Save the assistant's reply to the database

## 5. Switch Models

Use the model selector in the top bar to switch between:
- **Gemma 4B** — Fast, local, privacy-preserving
- **Claude 3.5 Sonnet** — Powerful reasoning (cloud)
- **GPT-4o** — General purpose (cloud)

## 6. Organize Conversations

- **Rename**: Click the conversation title to edit
- **Folders**: Drag conversations into folders
- **Delete**: Hover and click the trash icon

## Example API Call

You can also interact via the REST API directly:

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "conversation_id": "conv-123",
    "messages": [{"role": "user", "content": "Hello, DClaw!"}],
    "model": "gemma-4b"
  }'
```

## What's Next?

- [Best Practices](../guides/best-practices) — Security and performance tips
- [Use Cases](../guides/use-cases) — Real-world scenarios
