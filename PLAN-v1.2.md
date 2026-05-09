# DClaw Chat — v1.2 Feature Roadmap

> Based on: Y Combinator vertical SaaS principles, trending GitHub repos (mattermost, zulip), AI product research (Slack, Discord, Twist, Rocket.Chat)

## Pre-Flight Checklist

- [ ] `frontend/package-lock.json` committed after any `npm install` / dependency change
- [ ] `frontend/next-env.d.ts` exists and is committed
- [ ] `docker-compose.yml` healthchecks correct
- [ ] `frontend/Dockerfile` declares `ARG NEXT_PUBLIC_API_URL` before `RUN npm run build`

## v1.0 Feature Inventory (Current)

- [ ] Channel/DM messaging
- [ ] File sharing
- [ ] Search
- [ ] Notifications
- [ ] Real backend CRUD (no mocks)
- [ ] Docker + Helm deployment
- [ ] Alembic migrations
- [ ] Backend tests

---

## v1.2 Roadmap

### P0 — Must Have (Ship in v1.0, demo-ready)

#### 1. AI Chat Copilot (Workspace Assistant)
**Description:** AI assistant in every channel that answers questions, summarizes threads, and suggests actions. "Summarize what I missed in #engineering this week."
- **AI Angle:** RAG over channel history. Thread summarization. Action extraction.
- **Backend:** `/api/v1/ai/chat` endpoint. Message indexing for RAG.
- **Frontend:** AI sidebar in channels. Thread summary cards.
- **Files:** `backend/app/services/chat_ai.py`, `frontend/src/components/chat-copilot.tsx`

#### 2. Real-Time Messaging (Channels & DMs)
**Description:** Instant messaging with channels, threads, direct messages, and group chats.
- **Backend:** WebSocket server with message persistence. Threading model.
- **Frontend:** Message list with threads. Typing indicators.
- **Files:** `backend/app/services/messaging.py`

#### 3. Threading & Topic Organization
**Description:** Organize conversations into threads. Topic-based channels with auto-summaries.
- **Backend:** Thread model with nesting. Topic extraction.
- **Frontend:** Thread panel. Topic badges.
- **Files:** `frontend/src/components/thread-view.tsx`

#### 4. File Sharing & Rich Embeds
**Description:** Share files, images, videos, and links with rich previews. Search within files.
- **Backend:** File storage with preview generation. Link unfurling.
- **Frontend:** Media gallery. Link previews.
- **Files:** `backend/app/services/files.py`

### P1 — Should Have (v1.1–1.2)

#### 5. AI Meeting Summaries
**Description:** Auto-transcribe and summarize voice/video calls. Extract action items.
- **AI Angle:** Whisper STT + LLM summarization + action item extraction.
- **Backend:** Meeting recording + processing pipeline.
- **Frontend:** Meeting recap with transcript and action items.

#### 6. Workflow Automation (Bots & Commands)
**Description:** Custom bots, slash commands, and webhook integrations.
- **Backend:** Bot framework. Command parser.
- **Frontend:** Bot marketplace. Command builder.

#### 7. Voice & Video Calls
**Description:** One-click voice and video calls with screen sharing. Group calls up to 50.
- **Backend:** WebRTC signaling server. Recording option.
- **Frontend:** Call UI with screen share controls.

#### 8. Huddles & Spontaneous Rooms
**Description:** Quick audio rooms for spontaneous collaboration. No scheduling required.
- **Backend:** Room management. Presence tracking.
- **Frontend:** Room list with active speakers.

### P2 — Could Have (v1.3+)

#### 9. AI-Powered Sentiment Monitoring
**Description:** Track team sentiment across channels. Alert on morale drops.

#### 10. Knowledge Base Auto-Build from Chat
**Description:** Auto-extract FAQs and documentation from channel conversations.

#### 11. External Guest Access
**Description:** Secure guest channels for client/vendor collaboration.

#### 12. AI Conversation Coaching
**Description:** Suggest more inclusive language and communication improvements in real-time.

---

## Implementation Priority

1. **Week 1–2:** AI Chat Copilot (P0.1) + Real-Time Messaging (P0.2)
2. **Week 3–4:** Threading (P0.3) + File Sharing (P0.4)
3. **Week 5–6:** Meeting Summaries (P1.5) + Workflow Automation (P1.6)
4. **Week 7–8:** Voice/Video Calls (P1.7) + Huddles (P1.8)
