"use client";

import { useState } from "react";
import { Meeting, MeetingActionItem, processMeeting } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const PRIORITY_COLOR: Record<MeetingActionItem["priority"], string> = {
  high: "border-red-500 text-red-400",
  medium: "border-yellow-500 text-yellow-400",
  low: "border-zinc-600 text-zinc-400",
};

interface MeetingViewProps {
  meeting: Meeting;
  onUpdated: (meeting: Meeting) => void;
}

export function MeetingView({ meeting, onUpdated }: MeetingViewProps) {
  const [tab, setTab] = useState<"summary" | "transcript" | "actions">("summary");
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isProcessing = meeting.status === "transcribing" || meeting.status === "summarizing";

  async function handleProcess() {
    setProcessing(true);
    setError(null);
    try {
      const updated = await processMeeting(meeting.id);
      onUpdated(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Processing failed");
    } finally {
      setProcessing(false);
    }
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-hidden p-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">{meeting.title}</h2>
          <p className="text-xs text-zinc-500">
            {new Date(meeting.created_at).toLocaleString()}
            {meeting.duration_seconds != null && (
              <> · {Math.floor(meeting.duration_seconds / 60)}m {meeting.duration_seconds % 60}s</>
            )}
          </p>
        </div>
        {meeting.status === "pending" && meeting.file_id && (
          <Button
            size="sm"
            onClick={handleProcess}
            disabled={processing || isProcessing}
            className="shrink-0"
          >
            {processing || isProcessing ? "Processing…" : "Process Meeting"}
          </Button>
        )}
      </div>

      {error && (
        <p className="rounded border border-red-500/30 bg-red-900/20 px-3 py-2 text-sm text-red-400">
          {error}
        </p>
      )}

      {isProcessing && (
        <div className="rounded border border-blue-500/30 bg-blue-900/20 px-3 py-2 text-sm text-blue-400">
          {meeting.status === "transcribing" ? "Transcribing audio…" : "Generating summary…"}{" "}
          This may take a few minutes.
        </div>
      )}

      {meeting.status === "failed" && (
        <div className="rounded border border-red-500/30 bg-red-900/20 px-3 py-2 text-sm text-red-400">
          Processing failed.{" "}
          <button onClick={handleProcess} className="underline hover:no-underline">
            Retry
          </button>
        </div>
      )}

      {meeting.status === "done" && (
        <>
          {/* Tabs */}
          <div className="flex gap-1 border-b border-zinc-700 pb-1">
            {(["summary", "transcript", "actions"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={cn(
                  "rounded px-3 py-1 text-sm capitalize transition-colors",
                  tab === t
                    ? "bg-zinc-700 text-zinc-100"
                    : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
                )}
              >
                {t}
                {t === "actions" && meeting.action_items && (
                  <span className="ml-1.5 rounded-full bg-zinc-600 px-1.5 py-0.5 text-xs">
                    {meeting.action_items.filter((a) => a.status === "open").length}
                  </span>
                )}
              </button>
            ))}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">
            {tab === "summary" && (
              <div className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-300">
                {meeting.summary || "No summary available."}
              </div>
            )}

            {tab === "transcript" && (
              <div className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-zinc-400">
                {meeting.transcript || "No transcript available."}
              </div>
            )}

            {tab === "actions" && (
              <div className="flex flex-col gap-2">
                {!meeting.action_items?.length && (
                  <p className="text-sm text-zinc-500">No action items found.</p>
                )}
                {meeting.action_items?.map((item, i) => (
                  <ActionItemRow key={i} item={item} />
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {meeting.status === "pending" && !meeting.file_id && (
        <p className="text-sm text-zinc-500">
          No audio file attached. Upload a recording to get started.
        </p>
      )}
    </div>
  );
}

function ActionItemRow({ item }: { item: MeetingActionItem }) {
  return (
    <div
      className={cn(
        "rounded border-l-2 bg-zinc-800/60 px-3 py-2",
        PRIORITY_COLOR[item.priority]
      )}
    >
      <p className="text-sm text-zinc-200">{item.text}</p>
      <div className="mt-1 flex gap-3 text-xs">
        <span className={cn("capitalize font-medium", PRIORITY_COLOR[item.priority].split(" ")[1])}>
          {item.priority}
        </span>
        {item.assignee && <span className="text-zinc-500">→ {item.assignee}</span>}
        <span
          className={cn(
            "capitalize",
            item.status === "done" ? "text-green-500" : "text-zinc-500"
          )}
        >
          {item.status}
        </span>
      </div>
    </div>
  );
}
