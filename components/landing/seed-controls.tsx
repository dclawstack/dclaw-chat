"use client";

/**
 * Demo seed/clear controls for the landing page.
 *
 * This whole subtree is isolated so it can be removed in one step.
 * To remove: delete this file, the `components/landing/` directory if empty,
 * and the `<SeedControls />` usage in `app/landing/page.tsx`.
 */
import { useState } from "react";
import { Database, Eraser, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { apiFetch } from "@/lib/api";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type Status =
  | { kind: "idle" }
  | { kind: "loading"; action: "seed" | "clear" }
  | { kind: "success"; action: "seed" | "clear"; message: string }
  | { kind: "error"; action: "seed" | "clear"; message: string };

export default function SeedControls() {
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  async function call(action: "seed" | "clear") {
    setStatus({ kind: "loading", action });
    try {
      const res = await apiFetch(`${API_BASE}/admin/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      const total = Object.values(data.counts as Record<string, number>).reduce(
        (a, b) => a + b,
        0
      );
      const message =
        action === "seed"
          ? `Seeded ${total} demo records across all features.`
          : `Cleared ${total} records from the database.`;
      setStatus({ kind: "success", action, message });
    } catch (e) {
      setStatus({
        kind: "error",
        action,
        message: e instanceof Error ? e.message : String(e),
      });
    }
  }

  const loading = status.kind === "loading";

  return (
    <section className="py-16">
      <div className="mx-auto max-w-3xl px-6">
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-6 sm:p-8">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-amber-400">
                Demo controls
              </p>
              <h3 className="mt-1 font-display text-lg font-semibold text-white">
                Try the app with sample data
              </h3>
              <p className="mt-1 text-sm text-dk-muted">
                Seed populates conversations, channels, meetings, huddles, bots
                and calls. Clear wipes everything for a fresh state.
              </p>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => call("seed")}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {status.kind === "loading" && status.action === "seed" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Database className="h-4 w-4" />
              )}
              Seed demo data
            </button>
            <button
              type="button"
              onClick={() => call("clear")}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {status.kind === "loading" && status.action === "clear" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Eraser className="h-4 w-4" />
              )}
              Clear all data
            </button>
          </div>

          {status.kind === "success" && (
            <div className="mt-4 flex items-start gap-2 rounded-lg border border-green-500/20 bg-green-500/10 px-3 py-2 text-xs text-green-300">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{status.message}</span>
            </div>
          )}
          {status.kind === "error" && (
            <div className="mt-4 flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-300">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{status.message}</span>
            </div>
          )}

          <p className="mt-3 text-[11px] text-dk-muted">
            Backend must be running at{" "}
            <code className="rounded bg-white/5 px-1 py-0.5">{API_BASE}</code>.
          </p>
        </div>
      </div>
    </section>
  );
}
