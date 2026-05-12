"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { buildSignalingUrl, endCallRoom } from "@/lib/api";
import {
  Mic,
  MicOff,
  Video,
  VideoOff,
  Monitor,
  MonitorOff,
  PhoneOff,
  Users,
} from "lucide-react";

interface PeerState {
  userId: string;
  stream: MediaStream | null;
}

interface CallRoomProps {
  roomId: string;
  userId: string;
  isHost: boolean;
  onLeave: () => void;
}

const ICE_SERVERS = [{ urls: "stun:stun.l.google.com:19302" }];

export function CallRoom({ roomId, userId, isHost, onLeave }: CallRoomProps) {
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const localStream = useRef<MediaStream | null>(null);
  const screenStream = useRef<MediaStream | null>(null);
  const ws = useRef<WebSocket | null>(null);
  const peers = useRef<Map<string, RTCPeerConnection>>(new Map());
  const remoteStreams = useRef<Map<string, MediaStream>>(new Map());

  const [audioEnabled, setAudioEnabled] = useState(true);
  const [videoEnabled, setVideoEnabled] = useState(true);
  const [screenSharing, setScreenSharing] = useState(false);
  const [peerStates, setPeerStates] = useState<PeerState[]>([]);
  const [participantCount, setParticipantCount] = useState(1);

  const sendSignal = useCallback((msg: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(msg));
    }
  }, []);

  const createPeerConnection = useCallback(
    (peerId: string): RTCPeerConnection => {
      const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });

      localStream.current?.getTracks().forEach((t) => pc.addTrack(t, localStream.current!));

      pc.onicecandidate = ({ candidate }) => {
        if (candidate) {
          sendSignal({ type: "ice", candidate, target: peerId });
        }
      };

      const remote = new MediaStream();
      remoteStreams.current.set(peerId, remote);
      pc.ontrack = ({ track }) => {
        remote.addTrack(track);
        setPeerStates((prev) =>
          prev.map((p) => (p.userId === peerId ? { ...p, stream: remote } : p))
        );
      };

      peers.current.set(peerId, pc);
      return pc;
    },
    [sendSignal]
  );

  const handleSignalingMessage = useCallback(
    async (msg: Record<string, unknown>) => {
      const { type, from } = msg as { type: string; from: string };

      switch (type) {
        case "peers": {
          const peerIds = (msg.peers as string[]) ?? [];
          setParticipantCount(peerIds.length + 1);
          for (const peerId of peerIds) {
            setPeerStates((prev) =>
              prev.find((p) => p.userId === peerId)
                ? prev
                : [...prev, { userId: peerId, stream: null }]
            );
            const pc = createPeerConnection(peerId);
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);
            sendSignal({ type: "offer", sdp: offer, target: peerId });
          }
          break;
        }
        case "peer-joined": {
          const peerId = from;
          setPeerStates((prev) =>
            prev.find((p) => p.userId === peerId)
              ? prev
              : [...prev, { userId: peerId, stream: null }]
          );
          setParticipantCount((c) => c + 1);
          break;
        }
        case "peer-left": {
          const peerId = from;
          peers.current.get(peerId)?.close();
          peers.current.delete(peerId);
          remoteStreams.current.delete(peerId);
          setPeerStates((prev) => prev.filter((p) => p.userId !== peerId));
          setParticipantCount((c) => Math.max(1, c - 1));
          break;
        }
        case "offer": {
          const peerId = from;
          if (!peers.current.has(peerId)) {
            setPeerStates((prev) =>
              prev.find((p) => p.userId === peerId)
                ? prev
                : [...prev, { userId: peerId, stream: null }]
            );
          }
          const pc = peers.current.get(peerId) ?? createPeerConnection(peerId);
          await pc.setRemoteDescription(
            new RTCSessionDescription(msg.sdp as RTCSessionDescriptionInit)
          );
          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);
          sendSignal({ type: "answer", sdp: answer, target: peerId });
          break;
        }
        case "answer": {
          const pc = peers.current.get(from);
          if (pc) {
            await pc.setRemoteDescription(
              new RTCSessionDescription(msg.sdp as RTCSessionDescriptionInit)
            );
          }
          break;
        }
        case "ice": {
          const pc = peers.current.get(from);
          if (pc && msg.candidate) {
            await pc.addIceCandidate(new RTCIceCandidate(msg.candidate as RTCIceCandidateInit));
          }
          break;
        }
        case "call-ended": {
          onLeave();
          break;
        }
      }
    },
    [createPeerConnection, sendSignal, onLeave]
  );

  useEffect(() => {
    let mounted = true;

    const init = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        if (!mounted) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        localStream.current = stream;
        if (localVideoRef.current) {
          localVideoRef.current.srcObject = stream;
        }
      } catch {
        if (mounted) {
          const silent = new MediaStream();
          localStream.current = silent;
        }
      }

      const wsUrl = buildSignalingUrl(roomId, userId);
      const socket = new WebSocket(wsUrl);
      ws.current = socket;

      socket.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data as string);
          handleSignalingMessage(msg);
        } catch {
          // ignore malformed frames
        }
      };
    };

    init();

    return () => {
      mounted = false;
      localStream.current?.getTracks().forEach((t) => t.stop());
      screenStream.current?.getTracks().forEach((t) => t.stop());
      peers.current.forEach((pc) => pc.close());
      ws.current?.close();
    };
  }, [roomId, userId, handleSignalingMessage]);

  const toggleAudio = () => {
    localStream.current?.getAudioTracks().forEach((t) => {
      t.enabled = !t.enabled;
    });
    setAudioEnabled((v) => !v);
  };

  const toggleVideo = () => {
    localStream.current?.getVideoTracks().forEach((t) => {
      t.enabled = !t.enabled;
    });
    setVideoEnabled((v) => !v);
  };

  const toggleScreenShare = async () => {
    if (screenSharing) {
      screenStream.current?.getTracks().forEach((t) => t.stop());
      screenStream.current = null;
      const camTrack = localStream.current?.getVideoTracks()[0];
      if (camTrack) {
        peers.current.forEach((pc) => {
          const sender = pc.getSenders().find((s) => s.track?.kind === "video");
          if (sender) sender.replaceTrack(camTrack);
        });
      }
      setScreenSharing(false);
    } else {
      try {
        const screen = await navigator.mediaDevices.getDisplayMedia({ video: true });
        screenStream.current = screen;
        const screenTrack = screen.getVideoTracks()[0];
        peers.current.forEach((pc) => {
          const sender = pc.getSenders().find((s) => s.track?.kind === "video");
          if (sender) sender.replaceTrack(screenTrack);
        });
        screenTrack.onended = () => setScreenSharing(false);
        setScreenSharing(true);
      } catch {
        // user cancelled or permission denied
      }
    }
  };

  const handleLeave = async () => {
    if (isHost) {
      await endCallRoom(roomId).catch(() => {});
    }
    onLeave();
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-gray-950 text-white">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-gray-800">
        <span className="font-semibold text-sm">Call Room</span>
        <div className="flex items-center gap-2 text-gray-400 text-sm">
          <Users className="w-4 h-4" />
          <span>{participantCount}</span>
        </div>
      </div>

      {/* Video grid */}
      <div className="flex-1 grid gap-2 p-4 overflow-auto"
        style={{
          gridTemplateColumns: `repeat(${Math.min(peerStates.length + 1, 3)}, 1fr)`,
        }}
      >
        {/* Local video */}
        <div className="relative rounded-lg overflow-hidden bg-gray-900 aspect-video">
          <video
            ref={localVideoRef}
            autoPlay
            muted
            playsInline
            className="w-full h-full object-cover"
          />
          <span className="absolute bottom-2 left-2 text-xs bg-black/60 px-1.5 py-0.5 rounded">
            You
          </span>
          {!videoEnabled && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-900">
              <VideoOff className="w-10 h-10 text-gray-500" />
            </div>
          )}
        </div>

        {/* Remote videos */}
        {peerStates.map(({ userId: peerId, stream }) => (
          <RemoteVideo key={peerId} userId={peerId} stream={stream} />
        ))}
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-4 py-5 border-t border-gray-800">
        <ControlButton
          active={audioEnabled}
          onClick={toggleAudio}
          icon={audioEnabled ? <Mic className="w-5 h-5" /> : <MicOff className="w-5 h-5" />}
          label={audioEnabled ? "Mute" : "Unmute"}
        />
        <ControlButton
          active={videoEnabled}
          onClick={toggleVideo}
          icon={videoEnabled ? <Video className="w-5 h-5" /> : <VideoOff className="w-5 h-5" />}
          label={videoEnabled ? "Stop video" : "Start video"}
        />
        <ControlButton
          active={screenSharing}
          onClick={toggleScreenShare}
          icon={screenSharing ? <MonitorOff className="w-5 h-5" /> : <Monitor className="w-5 h-5" />}
          label={screenSharing ? "Stop sharing" : "Share screen"}
        />
        <Button
          onClick={handleLeave}
          className="rounded-full w-14 h-14 bg-red-600 hover:bg-red-700 text-white"
          size="icon"
          aria-label="Leave call"
        >
          <PhoneOff className="w-5 h-5" />
        </Button>
      </div>
    </div>
  );
}

function RemoteVideo({ userId, stream }: { userId: string; stream: MediaStream | null }) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  return (
    <div className="relative rounded-lg overflow-hidden bg-gray-900 aspect-video">
      {stream ? (
        <video ref={videoRef} autoPlay playsInline className="w-full h-full object-cover" />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-16 h-16 rounded-full bg-gray-700 flex items-center justify-center text-2xl font-bold">
            {userId.charAt(0).toUpperCase()}
          </div>
        </div>
      )}
      <span className="absolute bottom-2 left-2 text-xs bg-black/60 px-1.5 py-0.5 rounded">
        {userId}
      </span>
    </div>
  );
}

function ControlButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className={`flex items-center justify-center rounded-full w-14 h-14 transition-colors ${
        active ? "bg-gray-700 hover:bg-gray-600" : "bg-red-900/60 hover:bg-red-900"
      }`}
    >
      {icon}
    </button>
  );
}
