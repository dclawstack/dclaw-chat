"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Video } from "lucide-react";
import { createCallRoom } from "@/lib/api";
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
  const [loading, setLoading] = useState(false);

  const handleStart = async () => {
    setLoading(true);
    try {
      const room = await createCallRoom({ title, channel_id: channelId });
      setRoomId(room.id);
    } catch (err) {
      console.error("Failed to create call room:", err);
    } finally {
      setLoading(false);
    }
  };

  if (roomId) {
    return (
      <CallRoom
        roomId={roomId}
        userId={userId}
        isHost
        onLeave={() => setRoomId(null)}
      />
    );
  }

  return (
    <Button
      onClick={handleStart}
      disabled={loading}
      variant="outline"
      size="sm"
      className="gap-2"
    >
      <Video className="w-4 h-4" />
      {loading ? "Starting…" : "Start call"}
    </Button>
  );
}
