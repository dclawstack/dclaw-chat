"use client";

import { Meeting } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const STATUS_LABEL: Record<Meeting["status"], string> = {
  pending: "Pending",
  transcribing: "Transcribing…",
  summarizing: "Summarizing…",
  done: "Done",
  failed: "Failed",
};

const STATUS_COLOR: Record<Meeting["status"], string> = {
  pending: "text-zinc-400",
  transcribing: "text-blue-400",
  summarizing: "text-yellow-400",
  done: "text-green-400",
  failed: "text-red-400",
};

interface MeetingCardProps {
  meeting: Meeting;
  selected?: boolean;
  onSelect: (meeting: Meeting) => void;
  onDelete: (meetingId: string) => void;
}

export function MeetingCard({ meeting, selected, onSelect, onDelete }: MeetingCardProps) {
  const date = new Date(meeting.created_at).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  const actions = meeting.action_items?.filter((a) => a.status === "open").length ?? 0;

  return (
    <div
      onClick={() => onSelect(meeting)}
      className={cn(
        "cursor-pointer rounded-lg border p-4 transition-colors hover:bg-zinc-800",
        selected ? "border-blue-500 bg-zinc-800" : "border-zinc-700 bg-zinc-900"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-zinc-100">{meeting.title}</p>
          <p className="mt-0.5 text-xs text-zinc-500">{date}</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 w-7 shrink-0 p-0 text-zinc-500 hover:text-red-400"
          onClick={(e) => {
            e.stopPropagation();
            onDelete(meeting.id);
          }}
        >
          ✕
        </Button>
      </div>
      <div className="mt-2 flex items-center gap-3 text-xs">
        <span className={cn("font-medium", STATUS_COLOR[meeting.status])}>
          {STATUS_LABEL[meeting.status]}
        </span>
        {meeting.status === "done" && actions > 0 && (
          <span className="text-zinc-500">{actions} open action{actions !== 1 ? "s" : ""}</span>
        )}
        {meeting.duration_seconds != null && (
          <span className="text-zinc-600">
            {Math.floor(meeting.duration_seconds / 60)}m {meeting.duration_seconds % 60}s
          </span>
        )}
      </div>
    </div>
  );
}
