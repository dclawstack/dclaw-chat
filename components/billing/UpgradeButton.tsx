"use client";

import { useEffect, useState } from "react";
import { getBilling, startCheckout, WorkspaceBilling } from "@/lib/api";

/**
 * Plan badge + "Upgrade" button for a workspace.
 *
 * Renders nothing while billing state is unknown, when the billing API is
 * unreachable, or when the backend reports billing is not configured (503
 * from checkout) — the feature stays invisible until Stripe keys exist.
 */
export function UpgradeButton({ workspaceId }: { workspaceId: string }) {
  const [billing, setBilling] = useState<WorkspaceBilling | null>(null);
  const [hidden, setHidden] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setBilling(null);
    setHidden(false);
    getBilling(workspaceId)
      .then((b) => {
        if (!cancelled) setBilling(b);
      })
      .catch(() => {
        if (!cancelled) setHidden(true);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  if (hidden || !billing) return null;

  const isPro = billing.plan === "pro" && billing.status === "active";

  const onUpgrade = async () => {
    setBusy(true);
    try {
      const res = await startCheckout(workspaceId, window.location.origin);
      if (!res) {
        // Billing not configured on the backend — hide the whole control.
        setHidden(true);
        return;
      }
      window.location.href = res.checkout_url;
    } catch {
      // Forbidden / transient error: keep the badge, drop the spinner.
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center justify-between px-2">
      <span
        className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
          isPro
            ? "bg-dclaw-100 text-dclaw-900"
            : "bg-muted text-muted-foreground"
        }`}
      >
        {isPro ? "Pro" : "Free"}
      </span>
      {!isPro && (
        <button
          onClick={onUpgrade}
          disabled={busy}
          className="text-xs font-medium text-dclaw-500 hover:text-dclaw-600 disabled:opacity-50 transition-colors"
        >
          {busy ? "Redirecting…" : "Upgrade"}
        </button>
      )}
    </div>
  );
}
