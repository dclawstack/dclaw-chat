# Deep Gap Analysis v2 — dclaw-chat (post-remediation)

**Date:** 2026-06-09  ·  **Branch:** `security/fix-3model-consensus-bugs`
**Method:** Manual tiered analysis (Tier 1/2/3), **no TestForge**. Every CRITICAL/HIGH was verified by reading the cited source lines directly.
**Lens:** antirez, *"A new era for software testing"* — tests give **code coverage, not state coverage**. Each finding therefore names the runtime *state* the current suite never reaches, and the report closes with an AI-QA testing strategy.

> This supersedes `GAP-ANALYSIS-2026-06-09.md` (v1), which was written *before* the P0/P1/P3 fixes and is now stale. v2 re-verifies everything against current source.

---

## 0. Executive summary

**Branch is green:** `245 passed`, **80% coverage** (up from v1's red 5-failing / 76%). The previously worst-covered files — `messaging.py`, `deps.py` — are now well covered; `meeting_service.py` (62%) is now the lowest.

**What's been fixed since v1 (verified):** JWT signature verification (RS256/JWKS, fail-closed); calls/huddles/messaging WS identity now from verified token; `get_meeting` IDOR; admin endpoints now Owner-gated; upload 25 MiB streaming cap; path-traversal guard; prod DEBUG startup assert; docs disabled in prod; CSP/HSTS headers; TLS+redirect; required DB password; image-digest pinning mechanism.

**The headline now:** the auth *primitives* are fixed, but **authorization is still missing on the core data model.** Specifically:

> **CRITICAL — Conversations have no owner.** `ConversationORM` has no `created_by`/owner column at all, and `conversation_repo.list_all()` applies no owner filter. Any authenticated user can read, edit, and delete *every other user's* conversations and messages. The JWT fix correctly establishes *who you are* — but the app's central resource never checks *what you're allowed to touch*. This nullifies the value of the identity work for the product's primary data type.

**The four interacting system risks** (Tier 3): the **token-less frontend (T3-08)** can only function with `DEBUG=true`, which re-enables the unauthenticated Owner backdoor; the **prod fail-closed guard is inert (T3-05)** because no deployment sets `ENVIRONMENT=production`, so nothing stops that; and at `replicaCount: 2` the **WS managers (T3-01)** and **rate limiter (T3-02)** are per-process with no Redis backplane, so chat/calls silently break and throttles are bypassable. These compound: token-less client → pressure to enable DEBUG → guard won't block it → multi-pod state doesn't exist anyway.

**Fix order:** P0 = conversations ownership (T2-01/T2-02) + frontend token/`ENVIRONMENT=production` (T3-08/T3-05). P1 = file-serve auth+inline-XSS (T1-01/02), SSRF TOCTOU (T1-03), WS room membership (T2-07), bots body-identity (T2-04), WS backplane + Redis rate limit (T3-01/02). P2/P3 below.

---

## 1. Tier 1 — Static / unit-level findings

### T1-01 · Stored XSS via inline-served uploads (SVG/HTML, no Content-Disposition) — HIGH
- **Location:** `app/api/v1/messaging.py:218-223` (`serve_file`), `app/services/files.py:74-81`, `:20`
- **Verified present:** yes. `return FileResponse(path)` with no `media_type` override and no `Content-Disposition`; `IMAGE_MIMES` includes `image/svg+xml`.
- **Issue:** `FileResponse` guesses content-type from the on-disk filename and serves **inline**. An attacker uploads `evil.svg`/`evil.html`; a victim opening `/api/v1/messaging/files/<id>/evil.svg` renders it on the API origin and executes embedded `<script>`.
- **Impact:** Stored XSS on the application origin → session/JWT/cookie theft.
- **Fix:** Serve with `Content-Disposition: attachment` + `X-Content-Type-Options: nosniff`; force `application/octet-stream` for non-allowlisted types; drop/​sanitize SVG.
- **State-coverage gap:** Tests assert a file is *classified* and *written*, never the **response headers** of the serve route.

### T1-02 · `serve_file` has no authentication / authorization — HIGH  *(= T2-03)*
- **Location:** `app/api/v1/messaging.py:218-223`
- **Verified present:** yes — route has **no** `Depends(get_current_user)`, unlike `upload_file` (`:213`) and `unfurl_url` (`:229`).
- **Issue/Impact:** Anyone with a `file_id`+`filename` (leaks via message bodies, the upload `url`, logs, referrers) downloads it unauthenticated — including private meeting audio and chat attachments (shared `uploads/` store). No channel-membership check either.
- **Fix:** Add `Depends(get_current_user)` and verify the caller has access to the owning channel/meeting.
- **State-coverage gap:** No test asserts an anonymous/non-member request is rejected.

### T1-03 · SSRF guard is TOCTOU / DNS-rebinding bypassable — HIGH
- **Location:** `app/core/ssrf.py:25` (resolve to validate) → `app/services/files.py:113` (httpx re-resolves to connect); consumer `command_parser.py:57-63` too.
- **Verified present:** yes — `assert_url_safe(url)` runs `getaddrinfo` once, then `client.get(url)` resolves the host **again** at connect time.
- **Issue/Impact:** DNS rebinding / short-TTL flip returns a public IP to the check and `169.254.169.254`/`127.0.0.1` to the connect. Authenticated user supplies a webhook/unfurl URL → cloud-metadata credential theft / internal-service access.
- **Fix:** Resolve once, validate **every** returned IP, then connect to the validated IP (pinned-resolution transport / connect-by-IP with `Host` header). Re-run the guard on any redirect target.
- **State-coverage gap:** `test_ssrf.py` stubs `getaddrinfo` to one fixed IP, forcing check-time == connect-time — it can never observe the rebinding state.

### T1-04 · Unfurl downloads unbounded response body into memory — MEDIUM
- **Location:** `app/services/files.py:111-116`
- **Verified present:** yes — `client.get(...)` buffers the full body before `resp.text[:60_000]`; content-type checked *after* download. (Uploads are capped at 25 MiB; unfurl is not.)
- **Impact:** Attacker server streams a multi-GB `text/html` body → memory-exhaustion DoS (5 s timeout doesn't bound bytes).
- **Fix:** `client.stream(...)`, check `Content-Type`/`Content-Length` headers first, read ≤64 KiB via `aiter_bytes`, abort past the cap.
- **State-coverage gap:** Unfurl tests use tiny mock bodies; none asserts a huge body is capped.

### T1-05 · Extracted `og:image`/`favicon` returned without scheme/SSRF validation — MEDIUM
- **Location:** `app/services/files.py:129-145`
- **Verified present:** yes — `og.get("image")` returned verbatim; `favicon` may be any absolute URL.
- **Impact:** Page returns `og:image` = `data:text/html;...` or internal `http://169.254.169.254/...`; client renders it → client-side SSRF/XSS / internal probe via the preview.
- **Fix:** Require absolute `http(s)`, reject `javascript:`/`data:`, ideally apply the host policy.
- **State-coverage gap:** `test_unfurl_parses_og_tags` pins the pass-through (vulnerable) behavior.

### T1-06 · Meeting upload type filter bypassed via `application/octet-stream` — MEDIUM
- **Location:** `app/api/v1/meetings.py:64-66`
- **Verified present:** yes — allowlist explicitly includes `application/octet-stream`, and `content_type` is client-supplied.
- **Impact:** Any file passes by declaring `Content-Type: application/octet-stream`; feeds non-audio bytes to Whisper and (with T1-01) gets served later.
- **Fix:** Sniff magic bytes; drop `application/octet-stream` from the allowlist.
- **State-coverage gap:** No test rejects a non-audio file mislabeled as octet-stream.

### T1-07 · `meeting_service` reads whole audio into memory + bypasses path guard — LOW
- **Location:** `app/services/meeting_service.py:44`, `:96-105`
- **Verified present:** yes — `file_path.read_bytes()` loads the full file; path built directly as `UPLOAD_DIR / file_id / filename`, not via the guarded `FileService.file_path`.
- **Impact:** Memory pressure under concurrency; latent traversal if `file_id`/`filename` provenance changes.
- **Fix:** Route through `self.files.file_path(...)` and stream to httpx.
- **State-coverage gap:** Lowest-coverage module (62%); no test confines the path to `UPLOAD_DIR`.

### T1-08 · Missing field validation / bounds on schemas — LOW
- **Location:** `app/schemas/*.py`
- **Verified present:** yes — `UnfurlRequest.url: str` (no `HttpUrl`); `title`/`name` fields have no `max_length`; `CallRoomCreate.max_participants: int = 50` has no `ge`/`le` (accepts 0/negative/1e9); loose `role: str` in `ai.py:20`.
- **Fix:** `Field(max_length=...)`, `Field(ge=1, le=500)`, `pattern=...` on role.
- **State-coverage gap:** No schema test rejects oversized titles or out-of-range `max_participants`.

### T1-09 · Silent exception swallowing hides failures — LOW
- **Location:** `app/services/files.py:100-101` (`extract_text`), `command_parser.py:67-78`, `meeting_service` parsers, `schemas/meeting.py:37-38`
- **Issue:** `except Exception: pass; return ""` conflates "no content" with "processing failed" (corrupt/huge PDF → silent empty AI context).
- **Fix:** Catch specific exceptions, `logger.warning`, bound PDF size/pages.
- **State-coverage gap:** Tests assert `== ""` for *missing* file, never for *failed-parse* state.

---

## 2. Tier 2 — Integration / endpoint-auth findings

**Auth model:** `Depends(get_current_user)` = Bearer JWT (RS256/JWKS in prod; DEBUG → `dev-user`/Owner). WS = `authenticate_websocket` (verified token). "Ownership" = handler compares resource owner to caller.

| Route | Method | Auth? | Ownership? | Notes |
|---|---|---|---|---|
| conversations (list/get/patch/delete) | * | Yes | **No** | **No owner column** — full IDOR (T2-01) |
| conversations (create) | POST | Yes | n/a | No `created_by` recorded |
| chat/completions, chat/stream | POST | Yes | **No** | Writes into any `conversation_id` (T2-02) |
| ai/chat, ai/summarize, ai/actions | POST | Yes | **No** | LLM; no per-route limit (T2-08) |
| bots (create/get/put/delete/install) | * | Yes | **No** | Global namespace (T2-05) |
| bots/commands/execute | POST | Yes | **No** | Identity from body (T2-04) |
| messaging channels (list/get/post) | * | Yes | **No** | No membership model (T2-06) |
| messaging .../messages, thread, topics | * | Yes | **No** | Cross-channel read + destructive topic edit (T2-06) |
| **messaging/files/{id}/{name}** | GET | **No** | **No** | **Unauthenticated serve** (T1-02/T2-03) |
| messaging/unfurl | POST | Yes | n/a | SSRF-guarded; no per-route limit |
| messaging/calls/huddles WS | WS | Yes | **No membership** | Any authed user joins any room (T2-07) |
| meetings (all) | * | Yes | **Yes** | ✅ fixed |
| calls/huddles end/close/delete | * | Yes | **Yes** (host/creator) | ✅ (NULL-owner edge T2-09) |
| admin/seed, admin/clear | POST | Yes (**Owner**+flag) | n/a | ✅ fixed |

### T2-01 · Conversations have no owner — cross-user read/write/delete IDOR — CRITICAL
- **Location:** `app/api/v1/conversations.py:19-124`; `app/repositories/conversation_repo.py:23-33`; `app/models/conversation.py` (no owner column — **verified**).
- **Verified present:** yes. `list_all()` selects all conversations with no owner `where`; get/patch/delete fetch by id only; the ORM has no `created_by` to even record an owner.
- **Impact:** User A `GET /api/v1/conversations` → every user's titles; `/{id}` → full message bodies; `PATCH`/`DELETE` → tamper/destroy any conversation. Clearest cross-tenant hole in the codebase.
- **Fix:** Add `created_by` to `ConversationORM` (+ migration); set from `user.user_id` on create; owner-filter `list_all`; 403/404 on foreign owner in get/patch/delete (mirror `meetings.py:95/131/147/162`).
- **State-coverage gap:** `test_conversations_api.py` is single-user happy-path only; the foreign-owner state is never exercised.

### T2-02 · Chat completions/stream write into any conversation_id — HIGH
- **Location:** `app/api/v1/chat.py:14-47`; `app/services/chat_service.py` (get_by_id then create with client id; persist with `conversation_id=req.conversation_id`).
- **Impact:** A injects messages into B's history / squats conversation ids; combined with T2-01 read, exfiltrates context.
- **Fix:** Once conversations carry `created_by`, reject foreign target ids; bind new conversations to caller.
- **State-coverage gap:** No test drives chat with another user's `conversation_id`.

### T2-03 · Unauthenticated file serving — HIGH  *(see T1-02)*

### T2-04 · `/bots/commands/execute` trusts body `user_id`/`user_name` — MEDIUM
- **Location:** `app/api/v1/bots.py:95-96` (schema defaults `"dev-user"`/`"You"`), `:383-390` (forwarded verbatim; authenticated `user` ignored — **verified**).
- **Impact:** A authenticates as themselves but spoofs `user_id="<victim>"`; the persisted reply and outbound webhook carry the spoofed actor. `channel_id` also unvalidated → inject bot reply into any channel.
- **Fix:** Remove `user_id`/`user_name` from the schema; derive from `user`. Validate `channel_id` membership.
- **State-coverage gap:** No test sends a forged `user_id` and asserts the server overrides it.

### T2-05 · Bots are a global namespace — any user mutates/deletes any bot — MEDIUM
- **Location:** `app/api/v1/bots.py:212-319`; `BotORM` has no owner column.
- **Impact:** A repoints B's bot `webhook_url` to an attacker endpoint (exfil of every command invocation) or deletes/disables shared bots.
- **Fix:** Gate create/update/delete behind `require_role("Owner")` (admin-managed) or add `created_by`; at minimum restrict `webhook_url` mutation.
- **State-coverage gap:** No cross-user bot-mutation test.

### T2-06 · Channel messages/topics: cross-channel read + destructive edit, no membership — MEDIUM
- **Location:** `app/api/v1/messaging.py:139-157,191-206,234-302` (no membership model on `ChannelORM`).
- **Impact:** Any authed user reads every channel's history, runs `delete_topic` (`UPDATE topic=NULL`) over others' messages, and runs LLM summaries over arbitrary channels.
- **Fix:** Introduce channel membership; check on every channel-scoped route and WS join (T2-07).
- **State-coverage gap:** No non-member read/mutate test.

### T2-07 · WS endpoints authenticate identity but never authorize membership — MEDIUM
- **Location:** `calls.py:157-216`, `huddles.py:217-276`, `messaging.py:468-560` — all verify token, none check participant/membership.
- **Impact:** Any authed user who knows/enumerates a `room_id`/`channel_id` joins B's private call signaling (receives SDP/ICE), huddle, or live channel stream + 50-message history.
- **Fix:** After `authenticate_websocket`, verify membership (or public room) before `connect`; else close 1008.
- **State-coverage gap:** `test_ws_auth.py` covers missing/invalid token, never valid-but-non-member.

### T2-08 · No per-route rate limit on expensive LLM/unfurl endpoints — MEDIUM
- **Location:** only `admin/clear` has `@limiter.limit`; all LLM/unfurl/summary routes inherit the global `200/min`/IP.
- **Impact:** Sustained LLM cost-abuse and unfurl fetch-amplification within the global budget.
- **Fix:** Tight `@limiter.limit` per LLM/unfurl/summary route, keyed on `user.user_id` for authed routes.
- **State-coverage gap:** No 429 test for rapid LLM/unfurl calls.

### T2-09 · NULL-owner resources fail open — LOW
- **Location:** `meetings.py:95/131/147/162`, `calls.py:132/150`, `huddles.py:193/210` — checks guarded `if owner and owner != caller`.
- **Impact:** Legacy/seeded NULL-owner rows are globally accessible/deletable.
- **Fix:** Treat NULL owner as deny / backfill + non-null column.

---

## 3. Tier 3 — System / architectural findings

### Concurrency / horizontal scale
**T3-01 · WS managers are per-process; no Redis backplane — HIGH.** `services/messaging.py` (`manager`), `calls.py` (`_signaling`), `huddles.py` (`_presence`) are dict-backed singletons; Helm runs `replicaCount: 2`. → Users on different pods never see each other's messages / `peer-joined` / `speaking` events; WebRTC signaling fails to mesh (calls connect to an empty room); `online_count`/​"room full" checks are per-pod. **Fix:** Redis (or NATS) pub/sub behind a single broadcast interface; until then `replicaCount: 1` + single worker, documented. *Gap:* no 2-instance test that a publish on A reaches a subscriber on B.

**T3-02 · Rate limiter falls back to per-process memory; no `REDIS_URL` in any deploy — HIGH.** `ratelimit.py` uses Redis only `if _REDIS_URL`, but neither compose nor Helm sets it and there's no Redis service. → effective limit = `200/min × pods × workers`, resets on restart; the `5/min` admin-clear throttle is bypassable across pods. **Fix:** add Redis + wire `REDIS_URL`; fail closed when unset and `replicaCount > 1`.

**T3-03 · calls/huddles `_broadcast` iterates the live room dict — mutation race — MEDIUM.** `calls.py:62-74`, `huddles.py:61-75` `for uid, ws in room.items(): await ws.send_text(...)` over the live dict; a concurrent `disconnect` at the await → `RuntimeError: dict changed size during iteration`. The messaging manager copies first (`messaging.py:40`); these don't. **Fix:** `list(room.items())`.

**T3-04 · Auto-end-room read-modify-write races across sessions/pods — LOW.** `calls.py:208-215` ends a room when local `participant_count == 0`; per-pod count + non-atomic check→update → premature end when peers are on another pod. **Fix:** DB-authoritative conditional `UPDATE ... WHERE status != 'ended'`.

### Config / Secrets / Deploy
**T3-05 · No deploy sets `ENVIRONMENT=production`; the prod fail-closed guard is inert — HIGH.** `assert_safe_for_environment()` only fires when `is_production and DEBUG`, but `ENVIRONMENT` defaults to `development` and no manifest overrides it. → an operator who sets `DEBUG=true` in prod boots the unauthenticated Owner backdoor instead of being refused. **Fix:** set `ENVIRONMENT=production` in compose + Helm `backend.env`; consider defaulting unknown env to prod-strict. *Gap:* no manifest-render test asserts the env is present.

**T3-06 · No liveness/readiness/startup probes on Helm Deployments — MEDIUM.** `/health` exists but k8s never uses it → traffic routed to pods before DB/migrations ready (500s); a wedged event loop is never restarted. **Fix:** add probes hitting `/api/v1/health` (backend) and `/` (frontend).

**T3-07 · docker-compose has no Redis service — MEDIUM.** Reinforces T3-01/02; the compose topology can't satisfy shared state. **Fix:** add `redis:7-alpine`, wire `REDIS_URL`.

### Frontend
**T3-08 · Frontend sends NO auth token — WS uses `?user_id=`, REST sends no `Authorization`; only works in DEBUG — HIGH.** `lib/useMessaging.ts:27`, `lib/api.ts:366,484` append `?user_id=`; no `Bearer`/`access_token`/IdP integration anywhere (**verified by grep**). Backend ignores client `user_id` and requires a verified token. → with `DEBUG=false` (prod default) **every WS closes 1008 and every REST returns 401** — the app is non-functional unless DEBUG (the Owner backdoor) is on. **Fix:** integrate Logto on the frontend; send `Authorization: Bearer` (REST) and `?token=`/cookie (WS); drop the `user_id` params. *This is the keystone of the four interacting risks.*

**T3-09 · No user-content XSS sink — informational.** Only `dangerouslySetInnerHTML` is the static theme bootstrap (`app/layout.tsx:42`); message content rendered as React text; `localStorage` holds only prefs, no tokens. No action (but note T1-01 is a *backend*-served XSS, independent of this).

### Supply-chain / Headers
**T3-10 · CSP keeps `'unsafe-inline'` + `'unsafe-eval'` — MEDIUM.** `deploy/nginx.conf` + `nginx.conf` `script-src 'self' 'unsafe-inline' 'unsafe-eval'` (for Next.js inline bootstrap) largely defeats CSP's XSS value; any future HTML sink is unprotected. **Fix:** nonce/hash the inline script, drop unsafe-*.

**T3-11 · Images default to mutable tags; digest empty — LOW.** Helm template prefers `@digest` when set but defaults `tag: v1.0.0`, `digest: ""`; compose pins tags only (`ollama:0.6.8`, `postgres:15-alpine`), not digests. **Fix:** set `digest` in prod values; pin compose by `@sha256`; confirm lockfiles used in image builds.

### Observability / Ops
**T3-12 · Broadcast failures swallowed; no metrics on dropped/zombie sockets or cross-pod gaps — LOW.** `calls.py:71-72`/`huddles.py:72-73` `except Exception: dead.add(uid)` silently; Sentry optional, no Prometheus. → multi-pod gaps (T3-01) and socket leaks degrade silently. **Fix:** counters + probes; require Sentry/metrics in prod.

---

## 4. State coverage, not code coverage (the antirez angle)

80% line coverage hides that the **highest-risk runtime states are entirely unexercised**. None of these would be caught by the current suite, and each is a candidate for an AI-QA agent that probes state rather than lines:

| Unverified state | Related finding | Suggested AI-QA probe |
|---|---|---|
| User A reads/deletes user B's conversation | T2-01/T2-02 | Two-identity integration test: create as A, access as B → expect 403 |
| Anonymous/non-member downloads a file | T1-02 | Hit `serve_file` with no token / wrong channel → expect 401/403 |
| Serve route returns executable content inline | T1-01 | Upload SVG, assert `Content-Disposition: attachment` + nosniff |
| DNS rebinds between SSRF check and connect | T1-03 | `getaddrinfo` stub that returns public IP then `169.254.169.254` |
| Valid token, non-member joins a room/channel WS | T2-07 | Connect with a non-participant token → expect 1008 |
| Forged body `user_id` overrides token identity | T2-04 | Execute command with spoofed `user_id` → assert server uses token |
| Message published on pod A reaches subscriber on pod B | T3-01 | Two manager instances over a real backplane |
| Rate limit holds across restart / second process | T3-02 | Two limiters sharing Redis → one shared counter |
| Disconnect during in-flight broadcast | T3-03 | Interleave `connect`/`disconnect`/`_broadcast` on one loop |
| Rendered Helm/compose actually sets `ENVIRONMENT=production` | T3-05 | Manifest-render assertion in CI |
| Real frontend against `DEBUG=false` backend | T3-08 | E2E authenticated flow, not DEBUG |

**Recommendation (per the article):** stand up an AI-QA agent that, per commit, (1) builds a real multi-user / multi-pod environment, (2) drives the *adversarial* states above rather than the happy path, and (3) reports anomalies — exactly the integration/state testing the unit suite can't reach.

---

## 5. Prioritized remediation plan

| Pri | Item | Findings |
|-----|------|----------|
| **P0** | Add `created_by` ownership to conversations (model+migration), filter list, 403 on foreign get/patch/delete; authorize `conversation_id` in chat | T2-01, T2-02 |
| **P0** | Frontend: real token on REST (`Bearer`) + WS (`?token=`/cookie); set `ENVIRONMENT=production` in compose+Helm so the DEBUG guard engages | T3-08, T3-05 |
| **P1** | `serve_file`: require auth + channel/meeting access; force attachment + nosniff; drop/sanitize SVG | T1-01, T1-02/T2-03 |
| **P1** | SSRF: pin resolved IP across check→connect; validate redirect targets | T1-03 |
| **P1** | WS room/channel membership authorization after auth | T2-07 |
| **P1** | bots/commands/execute: derive identity from token; validate channel | T2-04 |
| **P1** | Redis backplane for WS managers + Redis-backed rate limiter; add Redis service; probes | T3-01, T3-02, T3-06, T3-07 |
| **P2** | Bot ownership / Owner-gate mutations; channel membership model; per-route LLM/unfurl limits; unfurl body cap; copy-before-broadcast; NULL-owner deny | T2-05, T2-06, T2-08, T1-04, T3-03, T2-09 |
| **P3** | Schema bounds; nonce-based CSP (drop unsafe-*); digest-pin images; meeting-service path guard + streaming; magic-byte upload sniff; structured error logging; metrics | T1-05..09, T3-10, T3-11, T3-12 |
| **P-test** | State-coverage regression tests for every item in §4 | §4 |

---

*Generated by manual tiered gap analysis (no TestForge). Every CRITICAL/HIGH was verified by reading the cited source lines directly. Read through the lens of antirez, "A new era for software testing."*
