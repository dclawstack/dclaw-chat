"use client";

import { useEffect, useState } from "react";
import { getModelPolicy, setModelPolicy } from "@/lib/api";

interface ModelPolicyToggleProps {
  workspaceId: string;
}

/** Admin-only switch for the workspace's local-only AI policy (#30). The
 * backend enforces the policy server-side; this just exposes the knob. */
export function ModelPolicyToggle({ workspaceId }: ModelPolicyToggleProps) {
  const [localOnly, setLocalOnly] = useState<boolean | null>(null);
  const [allowed, setAllowed] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getModelPolicy(workspaceId)
      .then((p) => {
        if (!cancelled) {
          setLocalOnly(p.local_only);
          setAllowed(p.allowed_models);
        }
      })
      .catch(() => {
        if (!cancelled) setLocalOnly(null);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  if (localOnly === null) return null;

  const toggle = async () => {
    setBusy(true);
    try {
      const p = await setModelPolicy(workspaceId, {
        allowed_models: allowed,
        local_only: !localOnly,
      });
      setLocalOnly(p.local_only);
    } catch {
      // leave state unchanged; backend rejected (e.g. race on role change)
    } finally {
      setBusy(false);
    }
  };

  return (
    <label className="flex items-center gap-2 px-2 text-xs text-muted-foreground cursor-pointer">
      <input
        type="checkbox"
        checked={localOnly}
        onChange={toggle}
        disabled={busy}
        className="h-3 w-3 accent-dclaw-500"
      />
      Local-only AI (block cloud models)
    </label>
  );
}
