# DClaw Chat — v1.2 Feature Roadmap

> **For coding agents:** Pick features from this list, implement them fully, and update this doc with a checkmark.
> **Do NOT change the basic stack.** See `AGENTS.md` for architecture lock.

## v1.0 Feature Inventory (Current)

- [x] Multi-model chat (Ollama local + OpenRouter cloud)
- [x] Message persistence (PostgreSQL)
- [x] Conversation history sidebar
- [x] Model availability detection
- [x] Basic responsive UI (shadcn/ui)
- [x] Docker + Helm deployment
- [x] Health checks

---

## v1.2 Roadmap

### P0 — Must Have

#### 1. Streaming Responses (SSE)
**Description:** Instead of waiting for the full LLM response, stream tokens to the frontend in real-time.
- **Backend:** Add `POST /api/v1/chat/stream` endpoint using FastAPI `StreamingResponse` with SSE format (`text/event-stream`). Connect to Ollama's streaming API and OpenRouter's SSE format.
- **Frontend:** Add a streaming message component that appends tokens as they arrive. Update `src/lib/api.ts` with an `EventSource`-based streaming client.
- **AI/LLM:** No LLM changes needed — just wire existing endpoints to stream.
- **Files to touch:** `backend/app/api/v1/chat.py`, `backend/app/services/llm_service.py`, `frontend/src/components/chat/ChatContainer.tsx`, `frontend/src/lib/api.ts`

#### 2. File Attachments
**Description:** Allow users to attach images, PDFs, and text files to messages.
- **Backend:** Add `Attachment` model (`id`, `message_id`, `file_name`, `file_type`, `file_size`, `storage_path`). Use `python-multipart` for uploads. Store files in a local `uploads/` directory (MinIO in production). Add `POST /api/v1/chat/attachments` upload endpoint.
- **Frontend:** Add drag-and-drop file upload in the chat input. Show file thumbnails/previews. Include attachment IDs in message create requests.
- **AI/LLM:** For image attachments, detect if the selected model supports vision (GPT-4V, Gemini, etc.) and send base64 image data. For PDFs/text, extract text and prepend to the prompt.
- **Files to touch:** `backend/app/models/attachment.py`, `backend/app/repositories/attachment_repo.py`, `backend/app/api/v1/chat.py`, `frontend/src/components/chat/ChatInput.tsx`

#### 3. Chat Folders / Organization
**Description:** Let users organize conversations into folders.
- **Backend:** Add `Folder` model (`id`, `user_id`, `name`, `color`). Add `folder_id` to `Conversation`. Endpoints: `GET/POST/PUT/DELETE /api/v1/chat/folders`.
- **Frontend:** Add folder tree in the sidebar. Drag-and-drop conversations into folders. Collapsible folder sections.
- **Files to touch:** `backend/app/models/folder.py`, `backend/app/repositories/folder_repo.py`, `backend/app/api/v1/chat.py`, `frontend/src/components/sidebar/ConversationSidebar.tsx`

#### 4. System Prompts / Personas
**Description:** Pre-defined system prompts (e.g., "You are a Python expert", "You are a creative writer"). Users can select or create custom personas.
- **Backend:** Add `Persona` model (`id`, `name`, `system_prompt`, `icon`, `is_builtin`). Add `persona_id` to `Conversation`. Endpoints: `GET/POST/DELETE /api/v1/chat/personas`.
- **Frontend:** Persona selector dropdown above the chat input. Persona management page.
- **Files to touch:** `backend/app/models/persona.py`, `backend/app/repositories/persona_repo.py`, `backend/app/api/v1/chat.py`, `frontend/src/app/personas/page.tsx`

### P1 — Should Have

#### 5. Search Across Conversations
**Description:** Full-text search through all message content.
- **Backend:** Use PostgreSQL `tsvector` for full-text search. Add `GET /api/v1/chat/search?q=query`.
- **Frontend:** Search bar in the sidebar with highlighted results.
- **Files to touch:** `backend/app/models/message.py` (add tsvector), `backend/app/api/v1/chat.py`, `frontend/src/components/sidebar/SearchBar.tsx`

#### 6. Export Conversations
**Description:** Export a conversation as Markdown or JSON.
- **Backend:** Add `GET /api/v1/chat/conversations/{id}/export?format=markdown|json`.
- **Frontend:** Export button in conversation header. Trigger file download.
- **Files to touch:** `backend/app/api/v1/chat.py`, `frontend/src/components/chat/ChatHeader.tsx`

#### 7. Voice Input (Speech-to-Text)
**Description:** Microphone button that transcribes speech to text.
- **Backend:** Add `POST /api/v1/chat/transcribe` using OpenAI Whisper API or local Whisper model.
- **Frontend:** Record audio in browser, send blob to backend, insert transcribed text into input.
- **Files to touch:** `backend/app/api/v1/chat.py`, `backend/app/services/stt_service.py`, `frontend/src/components/chat/VoiceInput.tsx`

#### 8. Message Reactions / Ratings
**Description:** Thumbs up/down on assistant messages to collect feedback for RLHF.
- **Backend:** Add `MessageFeedback` model (`message_id`, `rating`, `comment`).
- **Frontend:** Rating buttons below each assistant message.
- **Files to touch:** `backend/app/models/feedback.py`, `frontend/src/components/chat/MessageBubble.tsx`

### P2 — Could Have

#### 9. Shared Public Conversations
**Description:** Generate a public shareable link for a conversation (read-only).
- **Backend:** Add `share_token` to `Conversation`. Add `GET /api/v1/chat/shared/{token}`.
- **Frontend:** "Share" button that copies a public URL.

#### 10. Agent Mode (Tool Calling)
**Description:** The LLM can call tools (web search, calculator, code execution) to answer questions.
- **Backend:** Implement OpenAI-style function calling schema. Tool registry in `app/services/tools/`. Execute tools and feed results back to LLM.
- **Frontend:** Show tool execution steps in the UI (collapsible).

---

## Implementation Priority

1. Streaming Responses (highest user impact)
2. File Attachments (differentiates from basic chat)
3. Chat Folders (scalability)
4. System Prompts / Personas (power user feature)
5. Search Across Conversations (discoverability)
6. Export Conversations (utility)
7. Voice Input (accessibility)
8. Message Reactions (data collection)
9. Shared Public Conversations (growth)
10. Agent Mode (platform play)
