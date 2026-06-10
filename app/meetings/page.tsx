"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Meeting,
  deleteMeeting,
  listMeetings,
  uploadMeeting,
} from "@/lib/api";
import { MeetingCard } from "@/components/meetings/MeetingCard";
import { MeetingView } from "@/components/meetings/MeetingView";
import { Button } from "@/components/ui/button";

const POLL_INTERVAL_MS = 5000;

export default function MeetingsPage() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [selected, setSelected] = useState<Meeting | null>(null);
  const [uploading, setUploading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await listMeetings();
      setMeetings(data);
      setSelected((prev) => (prev ? data.find((m) => m.id === prev.id) ?? prev : null));
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Failed to load meetings");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while any meeting is in-progress
  useEffect(() => {
    const hasInProgress = meetings.some(
      (m) => m.status === "transcribing" || m.status === "summarizing"
    );
    if (hasInProgress) {
      pollRef.current = setInterval(load, POLL_INTERVAL_MS);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [meetings, load]);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const meeting = await uploadMeeting(file);
      setMeetings((prev) => [meeting, ...prev]);
      setSelected(meeting);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function handleDelete(meetingId: string) {
    if (!confirm("Delete this meeting?")) return;
    try {
      await deleteMeeting(meetingId);
      setMeetings((prev) => prev.filter((m) => m.id !== meetingId));
      if (selected?.id === meetingId) setSelected(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  }

  function handleUpdated(updated: Meeting) {
    setMeetings((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
    setSelected(updated);
  }

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100">
      {/* Sidebar */}
      <aside className="flex w-72 shrink-0 flex-col border-r border-zinc-800">
        <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
          <h1 className="font-semibold text-zinc-100">Meeting Summaries</h1>
          <Button
            size="sm"
            disabled={uploading}
            onClick={() => fileInputRef.current?.click()}
            className="text-xs"
          >
            {uploading ? "Uploading…" : "+ Upload"}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*,video/*"
            className="hidden"
            onChange={handleFileChange}
            aria-label="Upload meeting recording"
          />
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {loadError && (
            <p className="px-2 py-3 text-xs text-red-400">{loadError}</p>
          )}
          {!loadError && meetings.length === 0 && (
            <p className="px-2 py-4 text-center text-xs text-zinc-600">
              No meetings yet.
              <br />
              Upload an audio or video recording to get started.
            </p>
          )}
          <div className="flex flex-col gap-2">
            {meetings.map((m) => (
              <MeetingCard
                key={m.id}
                meeting={m}
                selected={selected?.id === m.id}
                onSelect={setSelected}
                onDelete={handleDelete}
              />
            ))}
          </div>
        </div>
      </aside>

      {/* Detail panel */}
      <main className="flex min-w-0 flex-1 flex-col">
        {selected ? (
          <MeetingView meeting={selected} onUpdated={handleUpdated} />
        ) : (
          <div className="flex h-full items-center justify-center text-zinc-600">
            Select a meeting or upload a recording
          </div>
        )}
      </main>
    </div>
  );
}
