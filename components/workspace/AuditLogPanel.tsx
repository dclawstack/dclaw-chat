"use client";

import { useEffect, useState } from "react";
import { AuditEvent, listAuditEvents } from "@/lib/api";

interface AuditLogPanelProps {
  workspaceId: string;
}

/** Read-only audit trail for workspace Owners/Admins (#26). Members get a
 * 403 from the API; render that as a quiet "admins only" note. */
export function AuditLogPanel({ workspaceId }: AuditLogPanelProps) {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setEvents(null);
    setError(null);
    listAuditEvents(workspaceId, { limit: 50 })
      .then((evts) => {
        if (!cancelled) setEvents(evts);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  if (error) {
    return (
      <p className="px-2 text-[10px] text-muted-foreground leading-snug">
        Audit log is visible to workspace admins only.
      </p>
    );
  }
  if (events === null) {
    return <p className="px-2 text-[10px] text-muted-foreground">Loading audit log…</p>;
  }
  if (events.length === 0) {
    return <p className="px-2 text-[10px] text-muted-foreground">No audit events yet.</p>;
  }
  return (
    <ul className="px-2 space-y-1 max-h-40 overflow-y-auto">
      {events.map((e) => (
        <li key={e.id} className="text-[10px] leading-snug">
          <span className="font-mono text-dclaw-500">{e.action}</span>{" "}
          <span className="text-muted-foreground">
            by {e.actor_id} · {new Date(e.created_at).toLocaleString()}
          </span>
        </li>
      ))}
    </ul>
  );
}
