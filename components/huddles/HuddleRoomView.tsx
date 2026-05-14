"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  buildHuddleWsUrl,
  joinHuddle,
  leaveHuddle,
  updateHuddleSpeaking,
  closeHuddle,
  HuddleParticipant,
  HuddleRoom,
} from "@/lib/api";
import { Mic, MicOff, PhoneOff, Users } from "lucide-react";

interface HuddleRoomViewProps {
  room: HuddleRoom;
  userId: string;
  displayName?: string;
  isCreator?: boolean;
  onLeave: () => void;
}

const SPEAKING_THRESHOLD = 0.01;
const SPEAKING_POLL_MS = 300;

export function HuddleRoomView({
  room,
  userId,
  displayName = "Anonymous",
  isCreator = false,
  onLeave,
}: HuddleRoomViewProps) {
  const [participants, setParticipants] = useState<HuddleParticipant[]>(
    room.participants
  );
  const [muted, setMuted] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const updateParticipant = useCallback(
    (userId: string, patch: Partial<HuddleParticipant>) => {
      setParticipants((prev) =>
        prev.map((p) => (p.user_id === userId ? { ...p, ...patch } : p))
      );
    },
    []
  );

  // Handle incoming WebSocket presence events
  const handleWsMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string);
        switch (msg.type) {
          case "participant-joined":
            setParticipants((prev) =>
              prev.find((p) => p.user_id === msg.user_id)
                ? prev
                : [
                    ...prev,
                    {
                      id: msg.user_id,
                      room_id: room.id,
                      user_id: msg.user_id,
                      display_name: msg.display_name ?? msg.user_id,
                      is_speaking: false,
                      is_muted: false,
                      joined_at: new Date().toISOString(),
                      last_seen_at: new Date().toISOString(),
                    },
                  ]
            );
            break;
          case "participant-left":
            setParticipants((prev) =>
              prev.filter((p) => p.user_id !== msg.user_id)
            );
            break;
          case "speaking-update":
            updateParticipant(msg.user_id, {
              is_speaking: msg.is_speaking,
              ...(msg.is_muted != null ? { is_muted: msg.is_muted } : {}),
            });
            break;
          case "huddle-closed":
            onLeave();
            break;
        }
      } catch {
        // ignore malformed frames
      }
    },
    [room.id, onLeave, updateParticipant]
  );

  useEffect(() => {
    let mounted = true;

    const init = async () => {
      // Join the huddle via REST
      try {
        const participant = await joinHuddle(room.id, displayName);
        if (mounted) {
          setParticipants((prev) =>
            prev.find((p) => p.user_id === userId)
              ? prev
              : [...prev, participant]
          );
        }
      } catch {
        // Already joined or error — continue
      }

      // Open WebSocket for real-time presence
      const ws = new WebSocket(buildHuddleWsUrl(room.id, userId));
      wsRef.current = ws;
      ws.onmessage = handleWsMessage;

      // Set up audio level detection
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        if (!mounted) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        const ctx = new AudioContext();
        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        analyserRef.current = analyser;

        const data = new Uint8Array(analyser.frequencyBinCount);
        pollRef.current = setInterval(() => {
          if (!analyserRef.current) return;
          analyserRef.current.getByteFrequencyData(data);
          const avg = data.reduce((s, v) => s + v, 0) / data.length / 255;
          const nowSpeaking = avg > SPEAKING_THRESHOLD;
          setSpeaking((prev) => {
            if (prev !== nowSpeaking) {
              updateHuddleSpeaking(room.id, nowSpeaking).catch(() => {});
              if (wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send(
                  JSON.stringify({ type: "speaking-update", is_speaking: nowSpeaking })
                );
              }
            }
            return nowSpeaking;
          });
        }, SPEAKING_POLL_MS);
      } catch {
        // Microphone permission denied — still join without audio detection
      }
    };

    init();

    return () => {
      mounted = false;
      if (pollRef.current) clearInterval(pollRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      wsRef.current?.close();
    };
  }, [room.id, userId, displayName, handleWsMessage]);

  const toggleMute = () => {
    const next = !muted;
    setMuted(next);
    streamRef.current?.getAudioTracks().forEach((t) => {
      t.enabled = !next;
    });
    updateHuddleSpeaking(room.id, false, next).catch(() => {});
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: "speaking-update", is_speaking: false, is_muted: next })
      );
    }
  };

  const handleLeave = async () => {
    if (pollRef.current) clearInterval(pollRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    wsRef.current?.close();
    if (isCreator) {
      await closeHuddle(room.id).catch(() => {});
    } else {
      await leaveHuddle(room.id).catch(() => {});
    }
    onLeave();
  };

  return (
    <div className="flex flex-col h-full bg-gray-950 text-white rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800">
        <div>
          <p className="font-semibold text-sm">{room.name}</p>
          <p className="text-xs text-gray-400">Audio huddle</p>
        </div>
        <div className="flex items-center gap-1.5 text-gray-400 text-xs">
          <Users className="w-3.5 h-3.5" />
          <span>{participants.length}</span>
        </div>
      </div>

      {/* Participants grid */}
      <div className="flex-1 p-4 overflow-y-auto">
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
          {participants.map((p) => (
            <ParticipantTile key={p.user_id} participant={p} isSelf={p.user_id === userId} />
          ))}
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-4 py-4 border-t border-gray-800">
        <button
          onClick={toggleMute}
          aria-label={muted ? "Unmute" : "Mute"}
          title={muted ? "Unmute" : "Mute"}
          className={`flex items-center justify-center rounded-full w-12 h-12 transition-colors ${
            muted ? "bg-red-900/60 hover:bg-red-900" : "bg-gray-700 hover:bg-gray-600"
          }`}
        >
          {muted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
        </button>
        <Button
          onClick={handleLeave}
          className="rounded-full w-12 h-12 bg-red-600 hover:bg-red-700 text-white"
          size="icon"
          aria-label={isCreator ? "End huddle" : "Leave huddle"}
        >
          <PhoneOff className="w-5 h-5" />
        </Button>
      </div>
    </div>
  );
}

function ParticipantTile({
  participant,
  isSelf,
}: {
  participant: HuddleParticipant;
  isSelf: boolean;
}) {
  const initials = participant.display_name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div
        className={`relative w-14 h-14 rounded-full flex items-center justify-center text-lg font-bold transition-all ${
          participant.is_speaking && !participant.is_muted
            ? "ring-2 ring-green-400 ring-offset-2 ring-offset-gray-950 bg-gray-700"
            : "bg-gray-700"
        }`}
      >
        {initials}
        {participant.is_muted && (
          <span className="absolute -bottom-0.5 -right-0.5 bg-gray-950 rounded-full p-0.5">
            <MicOff className="w-3 h-3 text-red-400" />
          </span>
        )}
        {participant.is_speaking && !participant.is_muted && (
          <span className="absolute inset-0 rounded-full animate-ping bg-green-400 opacity-20" />
        )}
      </div>
      <span className="text-xs text-gray-300 text-center truncate w-full px-1">
        {isSelf ? `${participant.display_name} (you)` : participant.display_name}
      </span>
    </div>
  );
}
