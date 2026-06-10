#!/usr/bin/env python3
"""v2.0 release gate — one command to verify the entire success path.

Usage (from repo root):  backend/.venv/bin/python scripts/v2-gate.py

Stages:
  1. preflight  — required env values present and well-formed
  2. suite      — full backend pytest + frontend tsc
  3. boot       — API starts against the configured (Neon) DB, health 200,
                  anonymous request 401 (DEBUG=false fail-closed)
  4. auth       — Clerk JWKS endpoint reachable and serving RS256 keys
  5. billing    — Stripe key valid (account retrievable), Pro price exists
  6. report     — pass/fail per v2.0 criterion

Read-only against external services (no charges, no writes to Stripe/Clerk).
The interactive criteria (real signup in a browser, checkout payment with a
test card) remain a human demo run — this script verifies everything machine
-checkable up to that point and prints the demo checklist.
"""
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PASS, FAIL, SKIP = "✅", "❌", "⏭️ "
results: list[tuple[str, str, str]] = []


def record(stage: str, ok: bool | None, note: str = "") -> None:
    results.append((stage, PASS if ok else (SKIP if ok is None else FAIL), note))


def load_env() -> dict:
    env = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def preflight(env: dict) -> bool:
    checks = {
        "DATABASE_URL": r"^postgresql\+asyncpg://.+neon\.tech",
        "DEBUG": r"^false$",
        "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": r"^pk_(test|live)_",
        "AUTH_JWKS_URL": r"^https://.+/\.well-known/jwks\.json$",
        "AUTH_ISSUER": r"^https://.+[^/]$",
        "STRIPE_SECRET_KEY": r"^sk_(test|live)_",
        "STRIPE_PRICE_PRO": r"^price_",
        "STRIPE_WEBHOOK_SECRET": r"^whsec_",
    }
    all_ok = True
    for key, pattern in checks.items():
        val = env.get(key, "")
        ok = bool(re.match(pattern, val))
        if not ok:
            all_ok = False
        record(f"preflight:{key}", ok, "" if ok else ("missing" if not val else "malformed"))
    return all_ok


def run_suite() -> bool:
    r1 = subprocess.run(
        [str(ROOT / "backend/.venv/bin/python"), "-m", "pytest", "tests", "-q"],
        cwd=ROOT / "backend", capture_output=True, text=True,
    )
    line = (r1.stdout.strip().splitlines() or ["?"])[-1]
    record("suite:pytest", r1.returncode == 0, line)
    r2 = subprocess.run(["npx", "tsc", "--noEmit"], cwd=ROOT, capture_output=True, text=True)
    record("suite:tsc", r2.returncode == 0)
    return r1.returncode == 0 and r2.returncode == 0


def boot_check() -> bool:
    sys.path.insert(0, str(ROOT / "backend"))
    os.chdir(ROOT)  # load root .env
    try:
        import httpx
        import uvicorn
        from app.main import app  # noqa

        t = threading.Thread(
            target=lambda: uvicorn.run(app, host="127.0.0.1", port=8056, log_level="error"),
            daemon=True,
        )
        t.start()
        for _ in range(20):
            time.sleep(2)
            try:
                r = httpx.get("http://127.0.0.1:8056/api/v1/health", timeout=3)
                break
            except Exception:
                continue
        else:
            record("boot:health", False, "server never came up")
            return False
        record("boot:health", r.status_code == 200)
        r2 = httpx.get("http://127.0.0.1:8056/api/v1/conversations", timeout=5)
        record("boot:anonymous-401", r2.status_code == 401, f"got {r2.status_code}")
        return r.status_code == 200 and r2.status_code == 401
    except Exception as e:
        record("boot", False, str(e)[:80])
        return False


def auth_check(env: dict) -> bool:
    try:
        import httpx
        r = httpx.get(env["AUTH_JWKS_URL"], timeout=10)
        keys = r.json().get("keys", [])
        ok = r.status_code == 200 and any(k.get("kty") == "RSA" for k in keys)
        record("auth:jwks", ok, f"{len(keys)} key(s)")
        return ok
    except Exception as e:
        record("auth:jwks", False, str(e)[:80])
        return False


def billing_check(env: dict) -> bool:
    try:
        import stripe
        stripe.api_key = env["STRIPE_SECRET_KEY"]
        stripe.Account.retrieve()
        record("billing:key", True)
        price = stripe.Price.retrieve(env["STRIPE_PRICE_PRO"])
        ok = bool(price.get("recurring"))
        record("billing:price", ok, "recurring per-seat" if ok else "price is not recurring")
        return ok
    except Exception as e:
        record("billing", False, str(e)[:80])
        return False


def main() -> int:
    env = load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    pf = preflight(env)
    suite_ok = run_suite()
    boot_ok = boot_check() if suite_ok else (record("boot", None, "skipped: suite red") or False)
    auth_ok = auth_check(env) if env.get("AUTH_JWKS_URL") else (record("auth:jwks", None, "no AUTH_JWKS_URL") or False)
    bill_ok = billing_check(env) if env.get("STRIPE_SECRET_KEY") else (record("billing", None, "no STRIPE_SECRET_KEY") or False)

    print("\n" + "=" * 72)
    print("V2.0 RELEASE GATE")
    print("=" * 72)
    for stage, mark, note in results:
        print(f"  {mark} {stage:42s} {note}")
    print("=" * 72)

    machine_ok = pf and suite_ok and boot_ok and auth_ok and bill_ok
    if machine_ok:
        print("""
ALL MACHINE-CHECKABLE GATES PASS. Final human demo checklist:
  1. Terminal A: cd backend && .venv/bin/uvicorn app.main:app --port 8000
  2. Terminal B: npm run dev   (sign-in button appears — Clerk key detected)
  3. Sign up with a fresh email → create workspace → invite teammate
  4. Second browser/incognito: accept invite → exchange messages in channel
  5. Ask the copilot about the discussion → answer shows graph citations
  6. Sidebar → Upgrade → complete Stripe test checkout (card 4242 4242 4242 4242)
  7. Plan badge flips to Pro after the webhook fires (use `stripe listen
     --forward-to localhost:8000/api/v1/billing/webhook` for local webhooks)
When step 7 completes, v2.0 ships.""")
        return 0
    print("\nGate incomplete — fix the ❌/⏭️  items above and re-run.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
