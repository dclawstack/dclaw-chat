# Consensus Bug Report — dclaw-chat

**Auditors:** opus-4.8 + sonnet-4.6 (independent) · reconciled by opus-4.8.
**Confirmed by both models: 7** · Opus: 15 · Sonnet: 15

## 🔴 Confirmed bugs (found by both models)

#### 1. 🟧 [HIGH/security] Unauthenticated admin seed/clear endpoints wipe all data
- **Location:** `backend/app/api/v1/admin.py:42`
- **Problem:** Both /admin/seed and /admin/clear lack a get_current_user dependency. /clear calls _wipe_all which deletes every row from every table. Any anonymous caller can destroy all production data; the rate limiter does not prevent this.
- **Fix:** Require authentication/authorization (admin role) on these endpoints, or remove the admin router in production builds.

#### 2. 🟧 [HIGH/security] WebSocket endpoints accept user identity from query params with no auth
- **Location:** `backend/app/api/v1/messaging.py:463`
- **Problem:** The messaging websocket takes user_id/user_name from query params with defaults of 'dev-user'/'You' and no authentication, so any client can impersonate any user and post messages as them. The calls and huddles WS endpoints share the same flaw.
- **Fix:** Authenticate the WebSocket (validate a token in the query/cookie) and derive user_id/user_name from the verified identity, not client-supplied params.

#### 3. 🟧 [HIGH/security] SSRF via bot webhook_url with no validation
- **Location:** `backend/app/services/command_parser.py:56`
- **Problem:** execute_command POSTs command payloads to bot.webhook_url, which is user-supplied via create/update bot endpoints with no validation. An authenticated user can register a bot with webhook_url pointing at internal infrastructure and trigger server-side requests; the webhook response is returned to chat.
- **Fix:** Validate webhook_url scheme and resolved IP against an allowlist / block private and loopback ranges before dispatching; disallow redirects.

#### 4. 🟧 [HIGH/security] SSRF in URL unfurl endpoint — no host/IP validation
- **Location:** `backend/app/services/files.py:79`
- **Problem:** The /unfurl endpoint fetches an arbitrary user-supplied URL server-side with follow_redirects=True and no validation of host or resolved IP. An attacker can target internal services (metadata endpoint, localhost, internal APIs) and exfiltrate responses. Classic SSRF.
- **Fix:** Validate scheme is http/https, resolve the hostname and reject private/loopback/link-local IP ranges, and disable or constrain redirects.

#### 5. 🟧 [HIGH/security] Path traversal in file serving endpoint — arbitrary file read
- **Location:** `backend/app/services/files.py:53`
- **Problem:** The file serving endpoint constructs UPLOAD_DIR / file_id / filename from URL path params without verifying the resolved path stays within UPLOAD_DIR. file_path() only checks existence, so '..' segments could escape the upload directory and allow arbitrary file read.
- **Fix:** Resolve the final path and verify it is contained within UPLOAD_DIR (path.resolve().is_relative_to(UPLOAD_DIR.resolve())); reject any '..' or absolute components.

#### 6. 🟨 [MEDIUM/security] Missing authorization check on get_meeting — IDOR
- **Location:** `backend/app/api/v1/meetings.py:121`
- **Problem:** get_meeting returns any meeting by id with no created_by ownership check (unlike update/delete which do check). Any authenticated user can read transcripts/summaries/action items of other users' meetings.
- **Fix:** Add `if meeting.created_by and meeting.created_by != user.user_id: raise HTTPException(403)` after the 404 check.

#### 7. ⬜ [LOW/concurrency] Race condition in reply_count increment — lost updates
- **Location:** `backend/app/api/v1/messaging.py:515`
- **Problem:** reply_count is incremented via read-modify-write (parent.reply_count += 1) in send_message, the WebSocket handler, and _generate_ai_reply without a lock or atomic update, so concurrent replies can lose increments.
- **Fix:** Use a SQL-level atomic increment: UPDATE ... SET reply_count = reply_count + 1.

