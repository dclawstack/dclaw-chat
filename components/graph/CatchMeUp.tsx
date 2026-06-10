"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getCatchMeUp, CatchMeUpResult, GraphCitation } from "@/lib/api";

const KIND_ICONS: Record<string, string> = {
  person: "👤",
  topic: "🏷️",
  decision: "✅",
  action_item: "📌",
  meeting: "🎙️",
  file: "📄",
};

export function kindIcon(kind: string): string {
  return KIND_ICONS[kind] ?? "🔗";
}

/** Compact badge for a knowledge-graph citation: kind icon + name. */
export function CitationBadge({ citation }: { citation: GraphCitation }) {
  const tooltip = citation.source_type
    ? `${citation.source_type}${citation.source_id ? `: ${citation.source_id}` : ""}`
    : citation.kind;
  return (
    <span
      title={tooltip}
      className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/50 px-2 py-0.5 text-[10px] text-foreground max-w-full"
    >
      <span aria-hidden>{kindIcon(citation.kind)}</span>
      <span className="truncate">{citation.name}</span>
    </span>
  );
}

function CitationSection({ title, items }: { title: string; items: GraphCitation[] }) {
  if (items.length === 0) return null;
  return (
    <div className="space-y-1">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      <div className="flex flex-wrap gap-1">
        {items.map((c, i) => (
          <CitationBadge key={`${c.kind}-${c.name}-${i}`} citation={c} />
        ))}
      </div>
    </div>
  );
}

interface CatchMeUpProps {
  workspaceId: string;
  /** Optional ISO timestamp — only show graph activity after this point. */
  since?: string;
}

/** Workspace-memory digest: recent decisions, action items, and topics. */
export function CatchMeUp({ workspaceId, since }: CatchMeUpProps) {
  const [data, setData] = useState<CatchMeUpResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setData(await getCatchMeUp(workspaceId, since));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load catch-me-up");
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId, since]);

  useEffect(() => {
    void load();
  }, [load]);

  const isEmpty =
    !!data &&
    data.decisions.length === 0 &&
    data.action_items.length === 0 &&
    data.entities.length === 0;

  return (
    <div className="border border-border rounded-lg bg-muted/30">
      <div className="flex items-center justify-between px-3 py-2">
        <span className="text-xs font-medium text-foreground">Catch me up</span>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => void load()}
          disabled={isLoading}
          title="Refresh"
          aria-label="Refresh catch-me-up"
        >
          {isLoading ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <RefreshCw className="h-3 w-3" />
          )}
        </Button>
      </div>
      <div className="px-3 pb-3 space-y-3">
        {error && <p className="text-xs text-red-400">{error}</p>}
        {!error && isEmpty && (
          <p className="text-xs text-muted-foreground leading-relaxed">
            Your team&apos;s memory builds as you chat.
          </p>
        )}
        {!error && data && !isEmpty && (
          <>
            <CitationSection title="Decisions" items={data.decisions} />
            <CitationSection title="Action items" items={data.action_items} />
            <CitationSection title="Topics & more" items={data.entities} />
          </>
        )}
        {!error && !data && isLoading && (
          <p className="text-xs text-muted-foreground">Loading workspace memory…</p>
        )}
      </div>
    </div>
  );
}

export default CatchMeUp;
