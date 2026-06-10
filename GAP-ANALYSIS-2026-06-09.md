# Deep Gap Analysis — dclaw-chat

**Date:** 2026-06-09
**Branch:** `security/fix-3model-consensus-bugs`
**Method:** Manual tiered analysis (Tier 1 static/unit · Tier 2 integration/auth · Tier 3 system/architectural). **No TestForge / consensus-model tooling used.** All headline findings independently verified against source by reading the exact lines cited.
**Baseline:** 7 consensus bugs in `pathb-bug-report.md`.

---

## 0. Executive summary

The branch landed the **easy, self-contained fixes correctly** (path traversal, SSRF guard plumbing, upload size limit) but **left the harder auth fixes half-done or undone**, and — more importantly — the analysis surfaced a **systemic CRITICAL that was not in the original 7**: **JWT signatures are never verified**, which makes every "authenticated" endpoint and every ownership check in the codebase forgeable.

| Metric | Result |
|---|---|
| Test suite | **5 failed / 198 passed**, 76% coverage — branch ships red |
| Consensus bugs fully fixed | **3 of 7** (#3 SSRF webhook, #4 SSRF unfurl, #5 path traversal) |
| Consensus bugs partial | **2 of 7** (#1 admin, #2 WS identity) |
| Consensus bugs NOT fixed | **2 of 7** (#6 get_meeting IDOR, #7 reply_count race) |
| New gaps found beyond the 7 | **12** (1 CRITICAL, 5 HIGH, 4 MEDIUM, 2 LOW) |

**Fix these first, in order:**
1. **JWT signature verification** (`deps.py:39`, `messaging.py:484`) — CRITICAL, total auth bypass; nullifies everything below it.
2. **Rotate the live OpenAI key** sitting in on-disk `.env` — CRITICAL operational (not committed, but exposed on disk).
3. Finish the half-done consensus fixes: **get_meeting IDOR**, **calls/huddles WS auth**.
4. **Distributed rate limiting** + **atomic reply_count**.

---

## 1. Consensus-bug fix verification (the original 7)

| # | Bug | Location | Status | Evidence |
|---|-----|----------|--------|----------|
| 1 | Unauth admin seed/clear wipes data | `admin.py:53,446` | 🟡 **PARTIAL** | Now gated by `_require_admin_enabled()` (404 unless `admin_enabled=True`, default **False** → fail-closed ✔). But **no `get_current_user`/role check** — if the flag is ever turned on (e.g. for the landing "full-capacity preview"), `/admin/clear` is fully anonymous and `_wipe_all` deletes all 9 tables. `/seed` has no rate limit. |
| 2 | WS accepts identity from query params | `messaging.py`, `calls.py:161`, `huddles.py:221` | 🟡 **PARTIAL** | **Only messaging WS fixed** (`_authenticate_ws`, token-derived identity). **`calls.py:161` and `huddles.py:221` still declare `user_id: str = "anonymous"`** straight from the query string with no token. The fix was not propagated to the two other endpoints the report explicitly named. |
| 3 | SSRF via bot webhook_url | `command_parser.py:57` | 🟢 **FIXED** | `assert_url_safe(...)` before POST, `follow_redirects=False`, fail-closed (returns `None`). Residual: TOCTOU/DNS-rebinding + no write-time validation (see T1-01, T1-07). |
| 4 | SSRF in URL unfurl | `files.py:108` | 🟢 **FIXED** | Same guard, `follow_redirects=False`, fail-closed. Same residual TOCTOU. |
| 5 | Path traversal in file serving | `files.py:74-81` | 🟢 **FIXED ✔** | `(.../file_id/filename).resolve()` + `is_relative_to(base)`. Verified: `..`, absolute, nested traversal all rejected; legit paths pass. Cleanest fix on the branch. |
| 6 | IDOR on get_meeting | `meetings.py:121-131` | 🔴 **NOT FIXED** | `get_meeting` returns any meeting by id with **no `created_by` check**, while `list`/`patch`/`delete`/`process` in the same file all enforce ownership. The exact one-line fix from the report was never added. |
| 7 | reply_count race (lost updates) | `messaging.py:184,448,559` | 🔴 **NOT FIXED** | All three reply paths still do `parent.reply_count += 1` (read-modify-write). No atomic SQL update. |

---

## 2. Tier 1 — Static / unit-level findings

### T1-01 · SSRF guard has a DNS-rebinding / TOCTOU window — **HIGH**
`backend/app/core/ssrf.py:23-36`
The guard calls `socket.getaddrinfo(host)` once to validate; httpx then **resolves the same host again** at connect time. An attacker controlling DNS (low TTL) returns a public IP to the guard and `127.0.0.1` / `169.254.169.254` to httpx. `follow_redirects=False` narrows but does not close this.
**Fix:** resolve once, pin the validated IP, and connect to that exact IP via a custom httpx transport/resolver. Provide a single `safe_get()`/`safe_client()` factory so call sites can't accidentally reopen the hole.

### T1-02 · Parser-differential IP bypass (octal / leading-zero octets) — **MEDIUM**
`backend/app/core/ssrf.py:25-35`
`getaddrinfo("0177.0.0.1")` returns `177.0.0.1` (public → passes), but some HTTP/libc stacks read `0177` as octal `127`. Decimal (`2130706433`) and hex (`0x7f...`) literals *are* caught; non-canonical octal slips.
**Fix:** if `hostname` is an IP-literal in any form, normalize via `ipaddress.ip_address` and validate directly; only `getaddrinfo` genuine DNS names.

### T1-03 · Safety contract not enforced by the guard — **LOW**
Both call sites independently remembered `follow_redirects=False`; a third caller that forgets reintroduces redirect-rebind SSRF. Centralize in a `safe_client()` factory.

### T1-04 · SSRF fix left 5 tests failing — branch ships red — **MEDIUM (CI health)**
`tests/unit/test_command_parser_extra.py` (3), `tests/unit/test_files_extra.py` (2)
`assert_url_safe` runs a **real** `socket.getaddrinfo` that the test's `httpx.MockTransport` cannot intercept; `.test` hostnames fail DNS → `SSRFError` → webhook returns `None` / unfurl returns base dict, so the mocked response is never reached. Fail-closed-on-DNS-failure is correct for prod (note: it also silently drops all webhooks/unfurls during a DNS outage), but the tests were not updated.
**Fix:** make `assert_url_safe` injectable/monkeypatchable in tests, or stub `socket.getaddrinfo`. Do **not** relax fail-closed.

### T1-05 · `file_id`/`filename` not format-validated at the serve route — **LOW**
`files.py:74-81` is solid, but `messaging.py` passes URL params straight in. Add a UUID regex on `file_id` and a charset check on `filename` as defense-in-depth before touching the filesystem.

### T1-06 · `unfurl` swallows non-SSRF exceptions silently — **LOW**
`files.py` catches all and returns `base` with no log; blocked-internal-probe attempts are invisible. Log + emit a metric/security event when `SSRFError` is caught.

### T1-07 · No `webhook_url` validation at write time — **MEDIUM**
`bots.py:227,266` store `webhook_url` with no scheme/host check; only dispatch validates. `file://`/`gopher://`/internal URLs are persistable. Add `assert_url_safe` (scheme at minimum) on create/update; keep dispatch-time check too.

**Correct & verified:** path-traversal fix (#5); blocklist coverage (RFC1918, loopback, link-local incl. `169.254.169.254`, CGNAT, IPv6 ULA/link-local, IPv4-mapped); `follow_redirects=False` at both sites; fail-closed posture.

---

## 3. Tier 2 — Integration / endpoint-auth findings

### T2-01 · **JWT signature is never verified — full authentication bypass — CRITICAL**
`backend/app/core/deps.py:37-42` (duplicated at `messaging.py:484-489`)
```python
payload = jwt.decode(
    token,
    options={"verify_signature": False, "verify_exp": True},
    algorithms=["HS256", "RS256"],
    audience=settings.LOGTO_AUDIENCE or None,
)
```
`verify_signature: False` is **unconditional** (not gated on DEBUG). Anyone can mint a JWT with arbitrary `sub`/`email`/`role` — including `"role": "Owner"` — and be fully authenticated as any user/admin.
**Exploit:** `Authorization: Bearer <unsigned JWT {"sub":"victim","role":"Owner"}>` → impersonate anyone, pass every `created_by == user.user_id` ownership check, satisfy any role gate. **This nullifies every other auth control in the system.** The SSRF fixes that lean on "authenticated user" as mitigation become effectively unauthenticated.
**Fix:** verify RS256 against Logto JWKS (`LOGTO_JWKS_URL`) with `verify_signature: True`, validate `aud`/`iss`. Pin algorithms to RS256 in prod (avoid alg-confusion). Remove the bypass from **both** deps.py and messaging.py. Gate any unsigned/dev path strictly on `settings.DEBUG`.

### T2-02 · IDOR — `get_meeting` leaks any user's transcript (consensus #6) — **HIGH**
`meetings.py:121-131`. Add after the 404: `if meeting.created_by and meeting.created_by != user.user_id: raise HTTPException(403)`.

### T2-03 · calls WebSocket trusts client `user_id` (consensus #2, calls) — **HIGH**
`calls.py:157-163` — `user_id: str = "anonymous"` from query; used to relay WebRTC offers/answers/ICE. Spoof a peer's id → hijack/MITM signaling, or join any room. Apply the messaging `_authenticate_ws` pattern.

### T2-04 · huddles WebSocket trusts client `user_id` (consensus #2, huddles) — **HIGH**
`huddles.py:217-223` — same flaw, **worse**: handler calls `repo.update_speaking(...)` / `repo.leave_room(...)` with the spoofed id, mutating other users' participant state. Token-authenticate; never read identity from the query string.

### T2-05 · Bots have no ownership model → webhook repoint = SSRF exfil — **HIGH**
`bots.py` PUT/DELETE/install/uninstall check no ownership; `BotORM` has no owner column. Any authed user repoints any (shared) bot's `webhook_url` to an attacker host; the SSRF guard only blocks *internal* IPs, so external exfil of other users' command payloads (`channel_id`, `user_id`, `user_name`) succeeds. Add an owner column + enforce; restrict webhook changes to admins; consider an egress allowlist.

### T2-06 · Conversations / channels are a global namespace (IDOR by design) — **HIGH**
`conversations.py` `list` returns `list_all()` (no user filter); `get`/`update`/`delete` do no ownership check; no `created_by` column. Same for channel messages in `messaging.py` (no membership check on `channel_id`). Every user reads/edits/deletes everyone's conversations and history. Add ownership/membership model and scope all reads/writes.

### T2-07 · command-execute accepts attacker-controlled identity in body — **MEDIUM**
`bots.py:92-96` `user_id="dev-user"`/`user_name="You"` from the request body are used as message author + webhook payload; the authenticated `user` is ignored. Derive from `CurrentUser`, drop from schema.

### T2-08 · File-serving endpoint has no auth — **MEDIUM**
`messaging.py:218-223` `GET /messaging/files/{file_id}/{filename}` lacks `Depends(get_current_user)` (unlike all sibling routes). Traversal is fixed, but anyone who learns a file id downloads arbitrary uploads. Add auth + access check.

### T2-09 · Admin destructive endpoints have no auth behind the flag — **MEDIUM** (HIGH if flag on)
`admin.py:53,446` rely solely on `admin_enabled`. Layer `Depends(require_role("Owner"))` on top; rate-limit `/seed`.

### T2-10 · No per-route rate limit on LLM/unfurl endpoints (cost abuse) — **LOW**
Only a global 200/min (and see T3-02 — that's bypassable). Tight `@limiter.limit` on inference + unfurl routes.

### T2-11 · CORS `allow_credentials=True` with wildcard methods/headers — **LOW**
`main.py:79-85`. Origins are restricted today (default localhost). Keep an explicit prod allowlist; never combine `*` with credentials.

### Endpoint auth matrix (abridged — full detail in Tier 2 audit)
| Path | Auth? | Ownership? | Note |
|---|---|---|---|
| GET /meetings/{id} | yes | **NO** | T2-02 IDOR |
| WS /calls/{room}/ws | **NO** | no | T2-03 |
| WS /huddles/{room}/ws | **NO** | no | T2-04 |
| WS /messaging/ws/{ch} | yes (token) | no | fixed ✔ |
| GET/PATCH/DELETE /conversations/{id} | yes | **NO** | T2-06 |
| GET/POST /channels/{id}/messages | yes | **NO** | no membership |
| PUT/DELETE /bots/{id} | yes | **NO** | T2-05 |
| POST /bots/commands/execute | yes | spoofable id | T2-07 |
| GET /messaging/files/{id}/{name} | **NO** | no | T2-08 |
| POST /admin/seed,/clear | flag only | n/a | T2-09 |
| GET /meetings (list), PATCH/DELETE /meetings/{id} | yes | **yes ✔** | correct |
| POST /calls/{id}/end, /huddles/{id}/close | yes | **yes ✔** | correct (host_id/created_by) |

*All "yes ✔" ownership checks are only as strong as the forgeable identity from T2-01.*

---

## 4. Tier 3 — System / architectural findings

### Concurrency
- **T3-01 · reply_count read-modify-write (consensus #7) — HIGH** · `messaging.py:184,448,559`. Concurrent replies lose increments. Use `update(...).values(reply_count=ChannelMessageORM.reply_count + 1)`.
- **T3-02 · In-memory rate limiter is per-process — HIGH** · `ratelimit.py:12`, `main.py:71`. slowapi uses default `MemoryStorage` (no `storage_uri`). With multiple uvicorn workers / Helm `replicaCount: 2`, effective limit = `200 × N` and an attacker hitting different workers bypasses it; counters reset every deploy. `get_remote_address` behind nginx sees the proxy IP unless `X-Forwarded-For` is trusted. Redis is already a dep (`cache.py`) — wire `storage_uri=redis://...` and configure trusted-proxy parsing.
- **T3-03 · WS broadcast cleanup heuristic leaks zombies; single-process manager — LOW/MEDIUM** · `services/messaging.py:53-62`. A socket that errors while still `CONNECTED` is kept forever → `online_count` over-reports. Manager is in-process: a user on pod A is invisible to broadcasts from pod B (no Redis pub/sub backplane). Add a heartbeat reaper; route broadcasts through Redis pub/sub for multi-pod.
- **T3-04 · `require_role` is dead + broken — MEDIUM** · `deps.py:58-66`. It's an `async def` returning the `checker` factory and has **zero call sites** (`grep` confirms). RBAC is unenforced everywhere; `role` is read but never gates anything. Make it a sync factory and actually apply it to privileged routes.

### Config / Secrets / Deploy
- **T3-05 · JWT signatures never verified — CRITICAL** · (same as T2-01; also at `messaging.py:484-489`).
- **T3-06 · Live OpenAI key in on-disk `.env` — CRITICAL (operational)** · `.env:12` holds a full `sk-proj-...` key. **Verified: `.env` is gitignored, untracked, and never appears in git history** — so not a repo leak, but a live credential in plaintext on disk. **Rotate/revoke it now** and treat as compromised.
- **T3-07 · `DEBUG=true` → unauthenticated dev-user Owner backdoor — HIGH** · `config.py` default `False` (good), but `.env:5` sets `DEBUG=true`. When DEBUG is on and no creds are sent, `deps.py:26-27` returns `CurrentUser("dev-user", role="Owner")` and the WS grants `("dev-user","You")`. Deploy manifests don't set DEBUG (prod = False), but anyone running compose with this `.env` ships an open-Owner backdoor. Assert `DEBUG is False` at startup under a prod marker.
- **T3-08 · Swagger `/docs` + `/openapi.json` exposed in prod — MEDIUM** · `deploy/nginx.conf:36-41`, `main.py:120`. Disable docs when not DEBUG; drop the nginx proxy blocks.
- **T3-09 · CORS credentials + wildcard methods/headers; verify error responses carry CORS — MEDIUM** · `main.py:71-85`.
- **T3-10 · Bare nginx serves HTTP-only (`listen 80`, no TLS/HSTS) — MEDIUM** · `deploy/nginx.conf`. Helm ingress has TLS via cert-manager; the compose/bare path does not. Terminate TLS or front it; redirect 80→443.
- **T3-11 · Default Postgres password `dclawpass` / `postgres:postgres` — LOW/MEDIUM** · `docker-compose.yml:9,42`, `helm/values.yaml:32`. Require the var (no default).

### Frontend
- **T3-12 · WS client sends no token; relies on DEBUG dev-user — MEDIUM** · `lib/useMessaging.ts`, `components/calls/CallRoom.tsx`, `components/huddles/HuddleRoomView.tsx` build WS URLs with `?user_id=&user_name=` and no token. So either prod (DEBUG off) closes all sockets 1008 and chat breaks, or DEBUG on = everyone is "dev-user". Plumb the real token to the socket once T3-05 lands.
- **Clean (verified):** the only `dangerouslySetInnerHTML` (`app/layout.tsx:41`) is a static theme bootstrap, not user input; no raw-HTML/markdown chat rendering sink; auth tokens not in localStorage; the `sk-` hit in `lib/swarm/agents/shield-agent.ts:9` is a detection regex, not a secret.

### Supply-chain / Headers
- **T3-13 · No CSP, no HSTS, weak headers — MEDIUM** · `deploy/nginx.conf:8-11` sets X-Frame-Options / X-Content-Type-Options / deprecated X-XSS-Protection but no CSP/HSTS/Permissions-Policy; the static-serving `nginx.conf` sets none; `next.config.js` (`output: 'export'`) has no `headers()`.
- **T3-14 · Images pinned to `latest` / mutable tags — LOW** · `helm/values.yaml:7,17`, `docker-compose.yml`. Pin by digest. Python deps themselves are unremarkable.

---

## 5. Test & coverage gaps

- **Branch ships with 5 failing tests** (T1-04) — must be green before merge.
- Coverage 76%, but the **least-covered files are the highest-risk**: `messaging.py` 29% (all the WS auth + reply_count paths), `admin.py` 33%, `deps.py` 41% (the auth code with the CRITICAL bug), `calls.py` 49%, `files.py` 63%.
- **Missing security regression tests** for: JWT forgery rejection, IDOR on get_meeting, WS auth on calls/huddles, conversation/bot ownership, SSRF DNS-rebinding, rate-limit-across-workers. None of these would have been caught by the current suite.

---

## 6. Prioritized remediation plan

| Pri | Item | Findings |
|-----|------|----------|
| **P0** | Verify JWT signatures (JWKS/RS256) in deps.py **and** messaging.py | T2-01 / T3-05 |
| **P0** | Rotate/revoke the live OpenAI key; scrub `.env` | T3-06 |
| **P1** | Add ownership check to `get_meeting` | #6 / T2-02 |
| **P1** | Token-auth calls + huddles WebSockets | #2 / T2-03,04 |
| **P1** | Atomic `reply_count` SQL update | #7 / T3-01 |
| **P1** | Distributed rate limiting via Redis + trusted-proxy config | T3-02 |
| **P1** | Fix the 5 failing tests (injectable SSRF guard) | T1-04 |
| **P2** | Ownership model for conversations/channels/bots; auth on file-serve; derive identity server-side in command-execute | T2-05,06,07,08 |
| **P2** | Add auth (not just flag) to admin endpoints; fix + use `require_role` | T2-09 / T3-04 |
| **P2** | Pin-IP SSRF transport (close TOCTOU); write-time webhook validation | T1-01,07 |
| **P3** | Disable prod docs; CSP/HSTS; TLS in bare nginx; non-default DB password; pin image digests; DEBUG startup assert | T3-07..14 |
| **P3** | Security regression tests for every item above | §5 |

---

*Generated by manual tiered gap analysis. Every CRITICAL/HIGH was verified by reading the cited source lines directly.*
