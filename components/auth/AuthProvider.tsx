"use client";

/**
 * Client-side Clerk integration (static-export compatible — no server
 * middleware, no @clerk/nextjs).
 *
 * When NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is absent the app renders without
 * Clerk so local dev against a DEBUG backend keeps working (and `next build`
 * never requires the key).
 *
 * TokenSync keeps lib/auth.ts's token seam fresh: Clerk session tokens live
 * 60s, so we refresh every 50s and on sign-in state changes. REST calls pick
 * the token up via authHeaders(), WebSockets via wsAuthQuery().
 */

import { useEffect } from "react";
import { ClerkProvider, useAuth } from "@clerk/clerk-react";
import { setAuthToken } from "@/lib/auth";

const PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

const TOKEN_REFRESH_MS = 50_000; // Clerk tokens expire after 60s

function TokenSync() {
  const { getToken, isSignedIn } = useAuth();

  useEffect(() => {
    let cancelled = false;

    const sync = async () => {
      if (!isSignedIn) {
        setAuthToken(null);
        return;
      }
      try {
        const token = await getToken();
        if (!cancelled) setAuthToken(token);
      } catch {
        if (!cancelled) setAuthToken(null);
      }
    };

    void sync();
    const interval = setInterval(() => void sync(), TOKEN_REFRESH_MS);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [getToken, isSignedIn]);

  return null;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  if (!PUBLISHABLE_KEY) {
    // Clerk not configured — run without auth (dev mode / DEBUG backend).
    return <>{children}</>;
  }

  return (
    <ClerkProvider publishableKey={PUBLISHABLE_KEY}>
      <TokenSync />
      {children}
    </ClerkProvider>
  );
}
