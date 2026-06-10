"use client";

/**
 * Minimal auth surface: Clerk's avatar/account menu when signed in, a modal
 * sign-in button when signed out. Renders nothing when Clerk isn't configured
 * (no NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY), so dev mode stays clean.
 */

import {
  SignedIn,
  SignedOut,
  SignInButton,
  UserButton as ClerkUserButton,
} from "@clerk/clerk-react";
import { LogIn } from "lucide-react";

const PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export function AuthUserButton() {
  if (!PUBLISHABLE_KEY) return null;

  return (
    <div className="flex items-center">
      <SignedIn>
        <ClerkUserButton
          appearance={{
            elements: { avatarBox: "h-7 w-7" },
          }}
        />
      </SignedIn>
      <SignedOut>
        <SignInButton mode="modal">
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <LogIn className="h-4 w-4" />
            Sign in
          </button>
        </SignInButton>
      </SignedOut>
    </div>
  );
}
