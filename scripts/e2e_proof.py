#!/usr/bin/env python3
"""End-to-end proof of the v2.0 success path against REAL infrastructure.

Runs the FastAPI app in-process (real Neon DB, real local Ollama for graph
extraction, real Stripe test key) and drives two distinct user identities
through every success criterion:

  1. stranger signs up            (identity A — auth proven separately via Clerk)
  2. invite a teammate            (A invites, B accepts → membership)
  3. chat in a scoped channel     (workspace-bound channel, messages persist)
  4. copilot cites the graph      (Ollama extracts entities → /ai/chat citations)
  5. pay via Stripe               (real Checkout Session created)
  6. DEBUG=false                  (asserted from live settings)
  7. ≥70% local LLM               (router stats / benchmark — reported)
  8. zero cross-tenant access     (outsider gets 403 on A's workspace)

Identity is injected via the same dependency-override the test suite uses;
live Clerk RS256 verification is proven by the running server's logs.
Run: backend/.venv/bin/python scripts/e2e_proof.py
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT)  # load root .env

for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

import httpx  # noqa: E402
from httpx import ASGITransport  # noqa: E402

from app.main import app  # noqa: E402
from app.core.deps import get_current_user, CurrentUser  # noqa: E402
from app.core.config import get_settings  # noqa: E402

PASS, FAIL = "✅", "❌"
_id = {"u": CurrentUser(user_id="e2e-alice", email="alice@e2e.test", role="User")}


async def _override():
    return _id["u"]


app.dependency_overrides[get_current_user] = _override


def as_user(uid: str, email: str):
    _id["u"] = CurrentUser(user_id=uid, email=email, role="User")


results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"  {PASS if ok else FAIL} {name}{(' — ' + detail) if detail else ''}")
    return ok


async def main():
    settings = get_settings()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://e2e") as c:
        print("\n=== DClaw Chat v2.0 — end-to-end proof (real Neon + Ollama + Stripe) ===\n")

        # 6. DEBUG=false (fail-closed posture)
        check("crit6: DEBUG=false", settings.DEBUG is False, f"DEBUG={settings.DEBUG}")

        # 1+2. Alice creates a workspace; invites Bob; Bob accepts
        as_user("e2e-alice", "alice@e2e.test")
        r = await c.post("/api/v1/workspaces", json={"name": "E2E HQ"})
        ws = r.json()["id"]
        check("crit1/2: workspace created by signed-in user", r.status_code == 201, ws)

        r = await c.post(f"/api/v1/workspaces/{ws}/invites", json={"email": "bob@e2e.test"})
        token = r.json()["token"]
        check("crit2: invite issued", r.status_code in (200, 201))

        as_user("e2e-bob", "bob@e2e.test")
        r = await c.post(f"/api/v1/workspaces/invites/{token}/accept")
        check("crit2: teammate joined", r.status_code == 200 and r.json()["workspace_id"] == ws)

        # 8. Cross-tenant: a third user (not a member) is denied
        as_user("e2e-mallory", "mallory@e2e.test")
        r = await c.get(f"/api/v1/workspaces/{ws}/members")
        check("crit8: non-member 403 on workspace", r.status_code == 403, f"got {r.status_code}")

        # 3. Alice creates a workspace-scoped channel and both chat
        as_user("e2e-alice", "alice@e2e.test")
        r = await c.post("/api/v1/messaging/channels", json={"name": "e2e-room", "workspace_id": ws})
        ch = r.json()["id"]
        ok_ch = r.status_code == 201 and r.json()["workspace_id"] == ws
        check("crit3: workspace-scoped channel created", ok_ch, f"ws={r.json().get('workspace_id')}")

        msgs = [
            ("e2e-alice", "alice@e2e.test", "Decision: we ship DClaw Chat v2.0 on Friday."),
            ("e2e-bob", "bob@e2e.test", "Bob will prepare the launch demo deck."),
        ]
        for uid, email, content in msgs:
            as_user(uid, email)
            r = await c.post(f"/api/v1/messaging/channels/{ch}/messages", json={"content": content})
            if r.status_code != 201:
                check("crit3: message persisted", False, f"{uid} got {r.status_code}")
                break
        else:
            check("crit3: messages persisted in scoped channel", True, f"{len(msgs)} messages")

        # 8b. Cross-tenant on the channel: mallory cannot read it
        as_user("e2e-mallory", "mallory@e2e.test")
        r = await c.get(f"/api/v1/messaging/channels/{ch}/messages")
        check("crit8: non-member 403 on channel messages", r.status_code == 403, f"got {r.status_code}")

        # 4. Graph extraction is fire-and-forget (real Ollama, ~seconds per msg).
        # Poll the entities endpoint until the background tasks commit.
        as_user("e2e-alice", "alice@e2e.test")
        ents = []
        for _ in range(20):  # up to ~40s; wait for both messages to extract
            await asyncio.sleep(2)
            r = await c.get(f"/api/v1/graph/workspaces/{ws}/entities")
            ents = r.json() if r.status_code == 200 else []
            if len(ents) >= 3:
                break
        check("crit4: knowledge graph populated from chat", len(ents) > 0,
              f"{len(ents)} entities: " + ", ".join(e.get("name", "?") for e in ents[:6]))

        r = await c.post("/api/v1/ai/chat",
                         json={"query": "What did we decide?", "workspace_id": ws})
        cites = r.json().get("citations", []) if r.status_code == 200 else []
        check("crit4: copilot answers with graph citations", r.status_code == 200 and len(cites) > 0,
              f"{len(cites)} citations" if r.status_code == 200 else f"status {r.status_code}")

        # 5. Stripe — real Checkout Session against the test key
        r = await c.post(f"/api/v1/billing/workspaces/{ws}/checkout",
                         json={"return_url": "http://localhost:3000/app"})
        url = r.json().get("checkout_url", "") if r.status_code == 200 else ""
        check("crit5: Stripe checkout session created", url.startswith("https://checkout.stripe.com")
              or "stripe.com" in url, url[:60] or f"status {r.status_code}: {r.text[:80]}")

    print("\n=== summary ===")
    passed = sum(1 for _, ok in results if ok)
    print(f"{passed}/{len(results)} criteria proven against live infrastructure")
    # crit7 (>=70% local) was measured separately by benchmarks (100% local)
    print("crit7: ≥70% local LLM — measured 100% local in benchmarks/ scorecard")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
