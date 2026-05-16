"use client";

import { useEffect, useState } from "react";
import { Video, Phone } from "lucide-react";
import { createCallRoom, listCallRooms } from "@/lib/api";
import { CallRoom } from "./CallRoom";

interface StartCallButtonProps {
  userId?: string;
  channelId?: string;
  title?: string;
}

export function StartCallButton({
  userId = "local-user",
  channelId,
  title = "New Call",
}: StartCallButtonProps) {
  const [roomId, setRoomId] = useState<string | null>(null);
  const [activeRoomId, setActiveRoomId] = useState<string | null>(null);
  const [isHost, setIsHost] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!channelId || roomId) return;
    let cancelled = false;

    const poll = async () => {
      try {
        const rooms = await listCallRooms(channelId);
        if (!cancelled) setActiveRoomId(rooms.length > 0 ? rooms[0].id : null);
      } catch {
        // ignore
      }
    };

    poll();
    const interval = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [channelId, roomId]);

  const handleStart = async () => {
    setLoading(true);
    try {
      const room = await createCallRoom({ title, channel_id: channelId });
      setIsHost(true);
      setRoomId(room.id);
      setActiveRoomId(null);
    } catch (err) {
      console.error("Failed to create call room:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleJoin = () => {
    if (activeRoomId) {
      setIsHost(false);
      setRoomId(activeRoomId);
      setActiveRoomId(null);
    }
  };

  const handleLeave = () => {
    setRoomId(null);
    setIsHost(false);
  };

  if (roomId) {
    return (
      <CallRoom
        roomId={roomId}
        userId={userId}
        isHost={isHost}
        onLeave={handleLeave}
      />
    );
  }

  if (activeRoomId) {
    return (
      <div className="flex items-center gap-2 bg-green-950/60 border border-green-800/50 rounded-lg px-3 py-1.5">
        <span className="flex items-center gap-1.5">
          <span className="relative flex h-2 w-2 shrink-0">
            <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
          </span>
          <span className="text-xs text-green-400 font-medium">Active call</span>
        </span>
        <div className="w-px h-3.5 bg-green-800/60" />
        <button
          onClick={handleJoin}
          className="flex items-center gap-1 text-xs font-semibold text-white bg-green-600 hover:bg-green-500 px-2.5 py-0.5 rounded-md transition-colors"
        >
          <Phone className="w-3 h-3" />
          Join
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={handleStart}
      disabled={loading}
      className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-accent px-2.5 py-1.5 rounded-md transition-colors disabled:opacity-50"
    >
      <Video className="w-3.5 h-3.5" />
      {loading ? "Starting…" : "Start call"}
    </button>
  );
}
