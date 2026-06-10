# TestForge Consensus — dclaw-chat

**Models:** anthropic/claude-opus-4.8 (A) vs anthropic/claude-sonnet-4.6 (B)
**Path:** `/Users/rp/Documents/Tharuni WN/dclaw-chat`

A bug is CONFIRMED only when BOTH models' generated tests FAIL (both reproduce it).

| Finding | File:line | Severity | Opus-4.8 | Sonnet-4.6 | Verdict |
|---------|-----------|----------|----------|------------|---------|
| Missing Rate Limiting | `package.json:1` | medium | PASS (2✓) | PASS (4✓) | 🟢 NOT REPRODUCED |

## Generated tests

### Missing Rate Limiting — verdict: 🟢 NOT REPRODUCED

**Opus-4.8** (`security-package-l1.test.ts`, PASS (2✓)):

```ts
import { describe, it, expect } from "vitest";

// Synthetic auth handler with and without rate limiting.
type Result = { status: number; body: string };

function makeUnlimitedHandler() {
  // No rate limiting: every attempt is processed.
  let attempts = 0;
  return function handle(_user: string, _pass: string): Result {
    attempts++;
    return { status: 401, body: "invalid credentials" };
  };
}

// A simple fixed-window in-memory limiter, like express-rate-limit would provide.
function makeLimitedHandler(max: number) {
  const counts = new Map<string, number>();
  return function handle(ip: string, _user: string, _pass: string): Result {
    const used = counts.get(ip) ?? 0;
    if (used >= max) {
      return { status: 429, body: "Too Many Requests" };
    }
    counts.set(ip, used + 1);
    return { status: 401, body: "invalid credentials" };
  };
}

describe("missing rate limiting on auth endpoint", () => {
  it("foot-gun: unlimited handler allows unbounded brute-force attempts", () => {
    const handle = makeUnlimitedHandler();
    const responses: Result[] = [];
    for (let i = 0; i < 1000; i++) {
      responses.push(handle("admin", `guess-${i}`));
    }
    // Every single brute-force attempt was accepted and processed — never throttled.
    expect(responses.length).toBe(1000);
    expect(responses.every((r) => r.status === 401)).toBe(true);
    expect(responses.some((r) => r.status === 429)).toBe(false);
  });

  it("safe fix: rate-limited handler returns 429 after the limit", () => {
    const max = 5;
    const handle = makeLimitedHandler(max);
    const responses: Result[] = [];
    for (let i = 0; i < 20; i++) {
      responses.push(handle("1.2.3.4", "admin", `guess-${i}`));
    }
    const allowed = responses.filter((r) => r.status === 401);
    const blocked = responses.filter((r) => r.status === 429);
    expect(allowed.length).toBe(max);
    expect(blocked.length).toBe(20 - max);
    expect(responses[max].status).toBe(429);
  });
});
```

**Sonnet-4.6** (`security-package-l1.test.ts`, PASS (4✓)):

```ts
import { describe, it, expect } from "vitest";

// ---------------------------------------------------------------------------
// Synthetic helpers – no real HTTP server, no network, no timers
// ---------------------------------------------------------------------------

/** Minimal in-memory rate limiter (the "safe fix" implementation). */
function createRateLimiter(options: { windowMs: number; max: number }) {
  const hits = new Map<string, { count: number; resetAt: number }>();

  return function limit(
    ip: string,
    nowMs: number
  ): { allowed: boolean; remaining: number; retryAfter?: number } {
    const entry = hits.get(ip);

    if (!entry || nowMs >= entry.resetAt) {
      // First request in this window (or window has expired)
      hits.set(ip, { count: 1, resetAt: nowMs + options.windowMs });
      return { allowed: true, remaining: options.max - 1 };
    }

    if (entry.count < options.max) {
      entry.count += 1;
      return { allowed: true, remaining: options.max - entry.count };
    }

    // Limit exceeded
    return {
      allowed: false,
      remaining: 0,
      retryAfter: entry.resetAt - nowMs,
    };
  };
}

/** Simulates an auth handler WITHOUT any rate limiting. */
function unprotectedAuthHandler(
  attempts: Array<{ ip: string; password: string }>
): Array<{ ip: string; status: number }> {
  return attempts.map(({ ip, password }) => ({
    ip,
    // Always processes every request – no throttling whatsoever
    status: password === "correct" ? 200 : 401,
  }));
}

/** Simulates an auth handler WITH rate limiting applied. */
function protectedAuthHandler(
  attempts: Array<{ ip: string; password: string; nowMs: number }>,
  limiter: ReturnType<typeof createRateLimiter>
): Array<{ ip: string; status: number }> {
  return attempts.map(({ ip, password, nowMs }) => {
    const result = limiter(ip, nowMs);
    if (!result.allowed) {
      return { ip, status: 429 };
    }
    return { ip, status: password === "correct" ? 200 : 401 };
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Auth endpoint rate limiting", () => {
  it("demonstrates the foot-gun: without rate limiting, brute-force succeeds unimpeded", () => {
    // Attacker fires 100 login attempts from the same IP
    const ATTEMPTS = 100;
    const attackerIp = "203.0.113.42";
    const bruteForceAttempts = Array.from({ length: ATTEMPTS }, (_, i) => ({
      ip: attackerIp,
      // Last attempt uses the correct password
      password: i === ATTEMPTS - 1 ? "correct" : `wrong-${i}`,
    }));

    const responses = unprotectedAuthHandler(bruteForceAttempts);

    // Every single request is processed – no 429 ever returned
    const blockedResponses = responses.filter((r) => r.status === 429);
    expect(blockedResponses).toHaveLength(0);

    // The attacker eventually gets a 200 after exhausting passwords
    const successfulLogin = responses.find((r) => r.status === 200);
    expect(successfulLogin).toBeDefined();

    // All 100 requests were served – demonstrating the vulnerability
    expect(responses).toHaveLength(ATTEMPTS);
  });

  it("safe fix: rate limiter blocks excessive requests with HTTP 429", () => {
    const MAX_REQUESTS = 5;
    const WINDOW_MS = 60_000; // 1 minute
    const limiter = createRateLimiter({ windowMs: WINDOW_MS, max: MAX_REQUESTS });

    const attackerIp = "203.0.113.42";
    const baseTime = 1_000_000; // arbitrary fixed epoch ms – no Date.now()

    // Attacker fires 20 attempts within the same window
    const bruteForceAttempts = Array.from({ length: 20 }, (_, i) => ({
      ip: attackerIp,
      password: i === 19 ? "correct" : `wrong-${i}`,
      nowMs: baseTime + i * 100, // 100 ms apart, all within the 60 s window
    }));

    const responses = protectedAuthHandler(bruteForceAttempts, limiter);

    // First MAX_REQUESTS attempts are allowed (401 for wrong passwords)
    const allowedResponses = responses.slice(0, MAX_REQUESTS);
    allowedResponses.forEach((r) => {
      expect(r.status).not.toBe(429);
    });

    // All subsequent attempts are rate-limited
    const throttledResponses = responses.slice(MAX_REQUESTS);
    throttledResponses.forEach((r) => {
      expect(r.status).toBe(429);
    });

    // The attacker never reaches the correct-password attempt
    const successfulLogin = responses.find((r) => r.status === 200);
    expect(successfulLogin).toBeUndefined();
  });

  it("safe fix: rate limit window resets after the configured period", () => {
    const MAX_REQUESTS = 3;
    const WINDOW_MS = 60_000;
    const limiter = createRateLimiter({ windowMs: WINDOW_MS, max: MAX_REQUESTS });

    const ip = "198.51.100.7";
    const baseTime = 2_000_000;

    // Exhaust the limit in window 1
    const window1 = Array.from({ length: MAX_REQUESTS }, (_, i) => ({
      ip,
      password: "wrong",
      nowMs: baseTime + i * 1_000,
    }));
    const window1Responses = protectedAuthHandler(window1, limiter);
    window1Responses.forEach((r) => expect(r.status).not.toBe(429));

    // One more request in window 1 should be blocked
    const overLimitResponse = protectedAuthHandler(
      [{ ip, password: "wrong", nowMs: baseTime + MAX_REQUESTS * 1_000 }],
      limiter
    );
    expect(overLimitResponse[0].status).toBe(429);

    // After the window expires, requests are allowed again
    const window2 = Array.from({ length: MAX_REQUESTS }, (_, i) => ({
      ip,
      password: "wrong",
      nowMs: baseTime + WINDOW_MS + i * 1_000, // new window
    }));
    const window2Responses = protectedAuthHandler(window2, limiter);
    window2Responses.forEach((r) => expect(r.status).not.toBe(429));
  });

  it("safe fix: different IPs are tracked independently", () => {
    const MAX_REQUESTS = 2;
    const limiter = createRateLimiter({ windowMs: 60_000, max: MAX_REQUESTS });

    const baseTime = 3_000_000;
    const ipA = "10.0.0.1";
    const ipB = "10.0.0.2";

    // Exhaust limit for ipA
    const ipAAttempts = Array.from({ length: MAX_REQUESTS + 1 }, (_, i) => ({
      ip: ipA,
      password: "wrong",
      nowMs: baseTime + i * 100,
    }));
    const ipAResponses = protectedAuthHandler(ipAAttempts, limiter);
    expect(ipAResponses[MAX_REQUESTS].status).toBe(429); // ipA is blocked

    // ipB should still be allowed (fresh counter)
    const ipBAttempts = [{ ip: ipB, password: "wrong", nowMs: baseTime + 500 }];
    const ipBResponses = protectedAuthHandler(ipBAttempts, limiter);
    expect(ipBResponses[0].status).not.toBe(429); // ipB is NOT blocked
  });
});
```

