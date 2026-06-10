"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { buildSignalingUrl, endCallRoom } from "@/lib/api";
import {
  Mic, MicOff, Video, VideoOff, Monitor, MonitorOff,
  PhoneOff, Users, X, Phone,
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

function formatDuration(secs: number) {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60).toString().padStart(2, "0");
  const s = (secs % 60).toString().padStart(2, "0");
  return h > 0 ? `${h}:${m}:${s}` : `${m}:${s}`;
}

function initials(id: string) {
  return id.slice(0, 2).toUpperCase();
}

// ── Pre-join lobby ────────────────────────────────────────────────────────────

function Lobby({
  title,
  onJoin,
  onCancel,
}: {
  title: string;
  onJoin: (audio: boolean, video: boolean) => void;
  onCancel: () => void;
}) {
  const previewRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [audioOn, setAudioOn] = useState(true);
  const [videoOn, setVideoOn] = useState(true);
  const [cameraReady, setCameraReady] = useState(false);

  useEffect(() => {
    let active = true;
    navigator.mediaDevices
      .getUserMedia({ video: true, audio: true })
      .then((s) => {
        if (!active) { s.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = s;
        if (previewRef.current) previewRef.current.srcObject = s;
        setCameraReady(true);
      })
      .catch(() => setCameraReady(false));
    return () => {
      active = false;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const toggleAudio = () => {
    streamRef.current?.getAudioTracks().forEach((t) => { t.enabled = !audioOn; });
    setAudioOn((v) => !v);
  };

  const toggleVideo = () => {
    streamRef.current?.getVideoTracks().forEach((t) => { t.enabled = !videoOn; });
    setVideoOn((v) => !v);
  };

  const handleJoin = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    onJoin(audioOn, videoOn);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-950/95">
      <div className="w-full max-w-md mx-4 flex flex-col gap-6">
        {/* Title */}
        <div className="text-center">
          <p className="text-xs text-gray-500 uppercase tracking-widest mb-1">Joining</p>
          <h2 className="text-xl font-semibold text-white">{title}</h2>
        </div>

        {/* Camera preview */}
        <div className="relative aspect-video rounded-2xl overflow-hidden bg-gray-900 shadow-2xl">
          {cameraReady && videoOn ? (
            <video
              ref={previewRef}
              autoPlay
              muted
              playsInline
              className="w-full h-full object-cover"
              style={{ transform: "scaleX(-1)" }}
            />
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
              <div className="w-16 h-16 rounded-full bg-gray-700 flex items-center justify-center text-xl font-bold text-white">
                {initials("You")}
              </div>
              {cameraReady && !videoOn && (
                <p className="text-xs text-gray-500">Camera is off</p>
              )}
              {!cameraReady && (
                <p className="text-xs text-gray-500">Camera unavailable</p>
              )}
            </div>
          )}

          {/* Mic/cam toggles overlaid on bottom of preview */}
          <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-2">
            <LobbyToggle active={audioOn} onClick={toggleAudio}
              activeIcon={<Mic className="w-4 h-4" />}
              inactiveIcon={<MicOff className="w-4 h-4" />}
              label={audioOn ? "Mute" : "Unmute"}
            />
            <LobbyToggle active={videoOn} onClick={toggleVideo}
              activeIcon={<Video className="w-4 h-4" />}
              inactiveIcon={<VideoOff className="w-4 h-4" />}
              label={videoOn ? "Stop video" : "Start video"}
            />
          </div>
        </div>

        {/* Join / Cancel */}
        <div className="flex flex-col gap-2">
          <button
            onClick={handleJoin}
            className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition-colors flex items-center justify-center gap-2"
          >
            <Phone className="w-4 h-4" />
            Join now
          </button>
          <button
            onClick={onCancel}
            className="w-full py-2.5 rounded-xl text-gray-600 hover:text-white hover:bg-gray-800 text-sm transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

function LobbyToggle({
  active, onClick, activeIcon, inactiveIcon, label,
}: {
  active: boolean;
  onClick: () => void;
  activeIcon: React.ReactNode;
  inactiveIcon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
        active
          ? "bg-black/60 text-white hover:bg-black/80"
          : "bg-red-700/80 text-white hover:bg-red-700"
      }`}
    >
      {active ? activeIcon : inactiveIcon}
      <span>{label}</span>
    </button>
  );
}

// ── Main call room ────────────────────────────────────────────────────────────

export function CallRoom({ roomId, userId, isHost, onLeave }: CallRoomProps) {
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const localStream = useRef<MediaStream | null>(null);
  const screenStream = useRef<MediaStream | null>(null);
  const ws = useRef<WebSocket | null>(null);
  const peers = useRef<Map<string, RTCPeerConnection>>(new Map());
  const remoteStreams = useRef<Map<string, MediaStream>>(new Map());

  const [preJoinDone, setPreJoinDone] = useState(false);
  const [initialAudio, setInitialAudio] = useState(true);
  const [initialVideo, setInitialVideo] = useState(true);

  const [audioEnabled, setAudioEnabled] = useState(true);
  const [videoEnabled, setVideoEnabled] = useState(true);
  const [screenSharing, setScreenSharing] = useState(false);
  const [peerStates, setPeerStates] = useState<PeerState[]>([]);
  const [participantCount, setParticipantCount] = useState(1);
  const [showParticipants, setShowParticipants] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  // Duration timer
  useEffect(() => {
    if (!preJoinDone) return;
    const t = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(t);
  }, [preJoinDone]);

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
        if (candidate) sendSignal({ type: "ice", candidate, target: peerId });
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
              prev.find((p) => p.userId === peerId) ? prev : [...prev, { userId: peerId, stream: null }]
            );
            const pc = createPeerConnection(peerId);
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);
            sendSignal({ type: "offer", sdp: offer, target: peerId });
          }
          break;
        }
        case "peer-joined":
          setPeerStates((prev) =>
            prev.find((p) => p.userId === from) ? prev : [...prev, { userId: from, stream: null }]
          );
          setParticipantCount((c) => c + 1);
          break;
        case "peer-left":
          peers.current.get(from)?.close();
          peers.current.delete(from);
          remoteStreams.current.delete(from);
          setPeerStates((prev) => prev.filter((p) => p.userId !== from));
          setParticipantCount((c) => Math.max(1, c - 1));
          break;
        case "offer": {
          if (!peers.current.has(from)) {
            setPeerStates((prev) =>
              prev.find((p) => p.userId === from) ? prev : [...prev, { userId: from, stream: null }]
            );
          }
          const pc = peers.current.get(from) ?? createPeerConnection(from);
          await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp as RTCSessionDescriptionInit));
          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);
          sendSignal({ type: "answer", sdp: answer, target: from });
          break;
        }
        case "answer": {
          const pc = peers.current.get(from);
          if (pc) await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp as RTCSessionDescriptionInit));
          break;
        }
        case "ice": {
          const pc = peers.current.get(from);
          if (pc && msg.candidate) await pc.addIceCandidate(new RTCIceCandidate(msg.candidate as RTCIceCandidateInit));
          break;
        }
        case "call-ended":
          onLeave();
          break;
      }
    },
    [createPeerConnection, sendSignal, onLeave]
  );

  // Initialize media + WebSocket after pre-join
  useEffect(() => {
    if (!preJoinDone) return;
    let mounted = true;

    const init = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: initialVideo, audio: initialAudio });
        if (!mounted) { stream.getTracks().forEach((t) => t.stop()); return; }
        // Apply initial toggle preferences
        stream.getAudioTracks().forEach((t) => { t.enabled = initialAudio; });
        stream.getVideoTracks().forEach((t) => { t.enabled = initialVideo; });
        localStream.current = stream;
        if (localVideoRef.current) localVideoRef.current.srcObject = stream;
      } catch {
        if (mounted) localStream.current = new MediaStream();
      }

      const socket = new WebSocket(buildSignalingUrl(roomId, userId));
      ws.current = socket;
      socket.onmessage = (ev) => {
        try { handleSignalingMessage(JSON.parse(ev.data as string)); } catch { /* ignore */ }
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
  }, [preJoinDone, roomId, userId, initialAudio, initialVideo, handleSignalingMessage]);

  const toggleAudio = () => {
    localStream.current?.getAudioTracks().forEach((t) => { t.enabled = !t.enabled; });
    setAudioEnabled((v) => !v);
  };

  const toggleVideo = () => {
    localStream.current?.getVideoTracks().forEach((t) => { t.enabled = !t.enabled; });
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
      if (localVideoRef.current && localStream.current) localVideoRef.current.srcObject = localStream.current;
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
        screenTrack.onended = () => {
          screenStream.current = null;
          if (localVideoRef.current && localStream.current) localVideoRef.current.srcObject = localStream.current;
          setScreenSharing(false);
        };
        if (localVideoRef.current) localVideoRef.current.srcObject = screen;
        setScreenSharing(true);
      } catch { /* cancelled */ }
    }
  };

  const handleLeave = async () => {
    if (isHost) await endCallRoom(roomId).catch(() => {});
    onLeave();
  };

  // ── Pre-join lobby
  if (!preJoinDone) {
    return (
      <Lobby
        title="Call Room"
        onJoin={(audio, video) => {
          setInitialAudio(audio);
          setInitialVideo(video);
          setAudioEnabled(audio);
          setVideoEnabled(video);
          setPreJoinDone(true);
        }}
        onCancel={onLeave}
      />
    );
  }

  const totalParticipants = peerStates.length + 1;
  const alone = peerStates.length === 0;

  // Grid columns: 1 col solo, 2 for 2-4, 3 for 5+
  const cols = alone ? 1 : totalParticipants <= 2 ? 2 : totalParticipants <= 4 ? 2 : 3;

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#141414] text-white select-none">

      {/* ── Header ── */}
      <div className="flex items-center justify-between px-5 py-3 bg-[#1c1c1c] border-b border-white/5 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-green-500" />
          <span className="text-sm font-semibold text-white">Call Room</span>
          {screenSharing && (
            <span className="flex items-center gap-1.5 text-xs bg-blue-600/20 text-blue-400 border border-blue-500/30 px-2.5 py-0.5 rounded-full">
              <Monitor className="w-3 h-3" />
              Presenting
            </span>
          )}
        </div>
        <div className="flex items-center gap-5">
          <span className="text-sm font-mono text-gray-600 tabular-nums">{formatDuration(elapsed)}</span>
          <div className="flex items-center gap-1.5 text-gray-600 text-sm">
            <Users className="w-4 h-4" />
            <span>{participantCount}</span>
          </div>
        </div>
      </div>

      {/* ── Video area ── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <div className="flex-1 relative p-4 overflow-auto">
          {alone ? (
            /* Solo view — centered local video with waiting message */
            <div className="flex flex-col items-center justify-center h-full gap-4">
              <div className="relative w-full max-w-xl aspect-video rounded-2xl overflow-hidden bg-[#2a2a2a] shadow-xl">
                <video
                  ref={localVideoRef}
                  autoPlay muted playsInline
                  className="w-full h-full object-cover"
                  style={!screenSharing ? { transform: "scaleX(-1)" } : undefined}
                />
                {!videoEnabled && !screenSharing && (
                  <div className="absolute inset-0 flex items-center justify-center bg-[#2a2a2a]">
                    <div className="flex flex-col items-center gap-2">
                      <div className="w-16 h-16 rounded-full bg-gray-700 flex items-center justify-center text-xl font-bold">
                        {initials(userId)}
                      </div>
                    </div>
                  </div>
                )}
                <span className="absolute bottom-3 left-3 text-xs bg-black/60 backdrop-blur-sm px-2 py-0.5 rounded-full text-gray-200">
                  You
                </span>
                {!audioEnabled && (
                  <span className="absolute bottom-3 right-3 text-xs bg-black/60 backdrop-blur-sm p-1 rounded-full">
                    <MicOff className="w-3 h-3 text-red-400" />
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500">Waiting for others to join…</p>
            </div>
          ) : (
            /* Gallery grid with local PiP */
            <div className="relative h-full">
              <div
                className="grid gap-3 h-full"
                style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
              >
                {peerStates.map(({ userId: peerId, stream }) => (
                  <RemoteTile key={peerId} userId={peerId} stream={stream} />
                ))}
              </div>

              {/* Local video — PiP corner */}
              <div className="absolute bottom-3 right-3 w-44 aspect-video rounded-xl overflow-hidden bg-[#2a2a2a] shadow-2xl border border-white/10 z-10">
                <video
                  ref={localVideoRef}
                  autoPlay muted playsInline
                  className="w-full h-full object-cover"
                  style={!screenSharing ? { transform: "scaleX(-1)" } : undefined}
                />
                {!videoEnabled && !screenSharing && (
                  <div className="absolute inset-0 flex items-center justify-center bg-[#2a2a2a]">
                    <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-xs font-bold">
                      {initials(userId)}
                    </div>
                  </div>
                )}
                <span className="absolute bottom-1.5 left-2 text-[10px] text-gray-600 bg-black/60 px-1.5 py-0.5 rounded-full">
                  You
                </span>
              </div>
            </div>
          )}
        </div>

        {/* ── Participants panel ── */}
        {showParticipants && (
          <div className="w-64 bg-[#1c1c1c] border-l border-white/5 flex flex-col shrink-0">
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
              <span className="text-sm font-semibold">Participants ({participantCount})</span>
              <button onClick={() => setShowParticipants(false)} aria-label="Close participants panel" className="text-gray-500 hover:text-white transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-1">
              {/* Local user */}
              <div className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-white/5">
                <div className="w-8 h-8 rounded-full bg-blue-700 flex items-center justify-center text-xs font-bold shrink-0">
                  {initials(userId)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white truncate">You</p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {!audioEnabled && <MicOff className="w-3 h-3 text-red-400" />}
                  {!videoEnabled && <VideoOff className="w-3 h-3 text-gray-500" />}
                </div>
              </div>
              {/* Remote peers */}
              {peerStates.map(({ userId: peerId }) => (
                <div key={peerId} className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-white/5">
                  <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-xs font-bold shrink-0">
                    {initials(peerId)}
                  </div>
                  <p className="text-sm text-white truncate flex-1">{peerId}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Control bar ── */}
      <div className="shrink-0 bg-[#1c1c1c] border-t border-white/5 px-6 py-4">
        <div className="flex items-center justify-between max-w-2xl mx-auto">
          {/* Center controls */}
          <div className="flex items-center gap-2 mx-auto">
            <CallControl
              active={audioEnabled}
              onClick={toggleAudio}
              activeIcon={<Mic className="w-5 h-5" />}
              inactiveIcon={<MicOff className="w-5 h-5" />}
              label={audioEnabled ? "Mute" : "Unmute"}
            />
            <CallControl
              active={videoEnabled}
              onClick={toggleVideo}
              activeIcon={<Video className="w-5 h-5" />}
              inactiveIcon={<VideoOff className="w-5 h-5" />}
              label={videoEnabled ? "Stop video" : "Start video"}
            />
            <CallControl
              active={!screenSharing}
              onClick={toggleScreenShare}
              activeIcon={<Monitor className="w-5 h-5" />}
              inactiveIcon={<MonitorOff className="w-5 h-5" />}
              label={screenSharing ? "Stop sharing" : "Share screen"}
              highlightWhenInactive
            />
            <CallControl
              active={!showParticipants}
              onClick={() => setShowParticipants((v) => !v)}
              activeIcon={<Users className="w-5 h-5" />}
              inactiveIcon={<Users className="w-5 h-5" />}
              label="People"
              badge={participantCount}
            />
          </div>

          {/* Leave button — right-aligned */}
          <button
            onClick={handleLeave}
            className="flex flex-col items-center gap-1 group"
            aria-label="Leave call"
          >
            <div className="w-12 h-12 rounded-xl bg-red-600 hover:bg-red-500 flex items-center justify-center transition-colors">
              <PhoneOff className="w-5 h-5" />
            </div>
            <span className="text-[10px] text-gray-500 group-hover:text-gray-600 transition-colors">Leave</span>
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Remote video tile ─────────────────────────────────────────────────────────

function RemoteTile({ userId, stream }: { userId: string; stream: MediaStream | null }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    if (videoRef.current && stream) videoRef.current.srcObject = stream;
  }, [stream]);

  return (
    <div className="relative rounded-2xl overflow-hidden bg-[#2a2a2a] min-h-0">
      {stream ? (
        <video ref={videoRef} autoPlay playsInline className="w-full h-full object-cover" />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-16 h-16 rounded-full bg-gray-700 flex items-center justify-center text-2xl font-bold">
            {initials(userId)}
          </div>
        </div>
      )}
      <span className="absolute bottom-3 left-3 text-xs bg-black/60 backdrop-blur-sm px-2 py-0.5 rounded-full text-gray-200">
        {userId}
      </span>
    </div>
  );
}

// ── Control button ────────────────────────────────────────────────────────────

function CallControl({
  active,
  onClick,
  activeIcon,
  inactiveIcon,
  label,
  badge,
  highlightWhenInactive,
}: {
  active: boolean;
  onClick: () => void;
  activeIcon: React.ReactNode;
  inactiveIcon: React.ReactNode;
  label: string;
  badge?: number;
  highlightWhenInactive?: boolean;
}) {
  const isOff = !active && !highlightWhenInactive;
  const isHighlighted = !active && highlightWhenInactive;

  return (
    <button onClick={onClick} className="flex flex-col items-center gap-1 group" title={label}>
      <div className={`relative w-12 h-12 rounded-xl flex items-center justify-center transition-colors ${
        isOff
          ? "bg-red-700/80 hover:bg-red-700"
          : isHighlighted
          ? "bg-blue-600/80 hover:bg-blue-600"
          : "bg-[#2e2e2e] hover:bg-[#3a3a3a]"
      }`}>
        {active ? activeIcon : inactiveIcon}
        {badge !== undefined && (
          <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-blue-600 text-[9px] font-bold flex items-center justify-center">
            {badge}
          </span>
        )}
      </div>
      <span className="text-[10px] text-gray-500 group-hover:text-gray-600 transition-colors whitespace-nowrap">
        {label}
      </span>
    </button>
  );
}
