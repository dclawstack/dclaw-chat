"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createHuddle, listHuddles, HuddleRoom } from "@/lib/api";
import { HuddleRoomView } from "./HuddleRoomView";
import { Mic, Plus, Users } from "lucide-react";

interface HuddleListProps {
  userId?: string;
  displayName?: string;
}

export function HuddleList({
  userId = "local-user",
  displayName = "Anonymous",
}: HuddleListProps) {
  const [rooms, setRooms] = useState<HuddleRoom[]>([]);
  const [activeRoom, setActiveRoom] = useState<HuddleRoom | null>(null);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRooms = useCallback(async () => {
    try {
      const data = await listHuddles();
      setRooms(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load huddles");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRooms();
    const interval = setInterval(fetchRooms, 5000);
    return () => clearInterval(interval);
  }, [fetchRooms]);

  const handleCreate = async () => {
    setCreating(true);
    try {
      const room = await createHuddle(newName.trim() || "Huddle");
      setNewName("");
      setActiveRoom(room);
      await fetchRooms();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create huddle");
    } finally {
      setCreating(false);
    }
  };

  const handleJoin = (room: HuddleRoom) => {
    setActiveRoom(room);
  };

  const handleLeave = async () => {
    setActiveRoom(null);
    await fetchRooms();
  };

  if (activeRoom) {
    return (
      <div className="h-full">
        <HuddleRoomView
          room={activeRoom}
          userId={userId}
          displayName={displayName}
          isCreator={activeRoom.created_by === userId}
          onLeave={handleLeave}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-gray-950 text-white p-5 gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold">Huddles</h2>
          <p className="text-xs text-gray-400">Quick audio rooms — no scheduling needed</p>
        </div>
      </div>

      {/* Create new huddle */}
      <div className="flex gap-2">
        <Input
          placeholder="Room name (optional)"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          className="bg-gray-900 border-gray-700 text-white placeholder:text-gray-500 text-sm"
        />
        <Button
          onClick={handleCreate}
          disabled={creating}
          size="sm"
          className="gap-1.5 whitespace-nowrap"
        >
          <Plus className="w-4 h-4" />
          {creating ? "Starting…" : "Start huddle"}
        </Button>
      </div>

      {error && (
        <p className="text-xs text-red-400">{error}</p>
      )}

      {/* Room list */}
      {loading ? (
        <p className="text-xs text-gray-500">Loading huddles…</p>
      ) : rooms.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 text-gray-500">
          <Mic className="w-10 h-10 opacity-30" />
          <p className="text-sm">No active huddles</p>
          <p className="text-xs">Start one to collaborate instantly</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2 overflow-y-auto">
          {rooms.map((room) => (
            <HuddleRoomCard
              key={room.id}
              room={room}
              onJoin={() => handleJoin(room)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function HuddleRoomCard({
  room,
  onJoin,
}: {
  room: HuddleRoom;
  onJoin: () => void;
}) {
  const speakers = room.participants.filter((p) => p.is_speaking && !p.is_muted);

  return (
    <div className="flex items-center justify-between rounded-lg bg-gray-900 border border-gray-800 px-4 py-3 hover:border-gray-600 transition-colors">
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="text-sm font-medium truncate">{room.name}</span>
        <div className="flex items-center gap-3 text-xs text-gray-400">
          <span className="flex items-center gap-1">
            <Users className="w-3 h-3" />
            {room.participants.length}
          </span>
          {speakers.length > 0 && (
            <span className="flex items-center gap-1 text-green-400">
              <Mic className="w-3 h-3" />
              {speakers.length} speaking
            </span>
          )}
        </div>
        {room.participants.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {room.participants.slice(0, 5).map((p) => (
              <span
                key={p.user_id}
                className={`text-xs px-1.5 py-0.5 rounded-full ${
                  p.is_speaking && !p.is_muted
                    ? "bg-green-900/50 text-green-300 ring-1 ring-green-500"
                    : "bg-gray-800 text-gray-400"
                }`}
              >
                {p.display_name}
              </span>
            ))}
            {room.participants.length > 5 && (
              <span className="text-xs text-gray-500">
                +{room.participants.length - 5} more
              </span>
            )}
          </div>
        )}
      </div>
      <Button onClick={onJoin} size="sm" variant="outline" className="ml-3 shrink-0 gap-1.5">
        <Mic className="w-3.5 h-3.5" />
        Join
      </Button>
    </div>
  );
}
