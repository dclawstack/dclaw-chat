"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { Channel, ChannelTopic, MessageAttachment } from "@/types/chat";
import { useMessaging } from "@/lib/useMessaging";
import { MessageThread } from "./MessageThread";
import { MediaGallery } from "./MediaGallery";
import { AttachmentList } from "./MessageAttachment";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TopicBadge } from "./TopicBadge";
import { Hash, Plus, Send, Wifi, WifiOff, Loader2, Tag, X, Paperclip, Images, Trash2 } from "lucide-react";
import { StartCallButton } from "@/components/calls/StartCallButton";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090/api/v1";
const USER_ID = "dev-user";
const USER_NAME = "You";
const URL_RE = /https?:\/\/[^\s]+/;

interface ChannelListProps {
  channels: Channel[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onAdd: (name: string) => void;
  onDelete: (id: string) => void;
}

function ChannelList({ channels, activeId, onSelect, onAdd, onDelete }: ChannelListProps) {
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const handleAdd = () => {
    const name = newName.trim().toLowerCase().replace(/\s+/g, "-");
    if (!name) return;
    onAdd(name);
    setNewName("");
    setAdding(false);
  };
  return (
    <div className="mb-4">
      <div className="flex items-center justify-between px-3 py-1">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Channels</span>
        <button onClick={() => setAdding((v) => !v)} className="text-muted-foreground hover:text-foreground" title="Add channel">
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>
      {adding && (
        <div className="px-3 pb-2 flex gap-1">
          <Input value={newName} onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder="channel-name" className="h-7 text-xs" autoFocus />
          <Button size="sm" className="h-7 px-2 text-xs" onClick={handleAdd}>Add</Button>
        </div>
      )}
      {channels.map((ch) => (
        <div key={ch.id} className="group relative">
          <button onClick={() => onSelect(ch.id)}
            className={`w-full flex items-center gap-2 px-3 py-1.5 text-sm rounded-md transition-colors ${
              ch.id === activeId ? "bg-dclaw-100 text-dclaw-900 font-medium" : "text-muted-foreground hover:bg-accent hover:text-foreground"
            }`}>
            <Hash className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate flex-1 text-left">{ch.name}</span>
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(ch.id); }}
            className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
            title="Delete channel"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}

interface TopicsPanelProps {
  topics: ChannelTopic[];
  activeTopic: string | null;
  onSelect: (topic: string | null) => void;
  onDelete: (topic: string) => void;
}

function TopicsPanel({ topics, activeTopic, onSelect, onDelete }: TopicsPanelProps) {
  const [confirmTopic, setConfirmTopic] = useState<string | null>(null);

  if (topics.length === 0) return null;
  return (
    <div className="mt-2">
      {/* Confirmation dialog */}
      {confirmTopic && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-card border rounded-lg shadow-lg p-5 w-72 flex flex-col gap-3">
            <p className="text-sm font-semibold">Delete topic &quot;{confirmTopic}&quot;?</p>
            <p className="text-xs text-muted-foreground">
              This will permanently remove the topic tag from all messages in this channel. Messages themselves are kept.
            </p>
            <div className="flex gap-2 justify-end">
              <Button variant="ghost" size="sm" onClick={() => setConfirmTopic(null)}>
                Cancel
              </Button>
              <Button
                size="sm"
                className="bg-destructive text-white hover:bg-destructive/90"
                onClick={() => { onDelete(confirmTopic); setConfirmTopic(null); }}
              >
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between px-3 py-1">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1">
          <Tag className="h-3 w-3" />Topics
        </span>
        {activeTopic && (
          <button onClick={() => onSelect(null)} className="text-muted-foreground hover:text-foreground">
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      <div className="px-3 py-1 flex flex-col gap-1">
        {topics.map(({ topic, count }) => (
          <div
            key={topic}
            className={`group flex items-center gap-1 rounded-md text-xs transition-colors ${
              activeTopic === topic ? "bg-accent" : "hover:bg-accent/50"
            }`}
          >
            <button
              onClick={() => onSelect(activeTopic === topic ? null : topic)}
              className="flex items-center gap-2 flex-1 min-w-0 px-2 py-1"
            >
              <TopicBadge topic={topic} small />
              <span className="ml-auto text-muted-foreground">{count}</span>
            </button>
            <button
              onClick={() => setConfirmTopic(topic)}
              className="pr-2 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive shrink-0"
              title="Delete topic"
            >
              <Trash2 className="h-3 w-3" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export function MessagingView() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [activeChannelId, setActiveChannelId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [loadingChannels, setLoadingChannels] = useState(true);
  const [activeTopic, setActiveTopic] = useState<string | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<MessageAttachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [showGallery, setShowGallery] = useState(false);
  const [hiddenTopics, setHiddenTopics] = useState<Set<string>>(new Set());
  const fileInputRef = useRef<HTMLInputElement>(null);
  const unfurlTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const activeChannel = channels.find((c) => c.id === activeChannelId);
  const { messages, typingUsers, connected, sendMessage, startTyping, stopTyping } =
    useMessaging({ channelId: activeChannelId, userId: USER_ID, userName: USER_NAME });

  const topics = useMemo<ChannelTopic[]>(() => {
    const counts: Record<string, number> = {};
    for (const m of messages) {
      if (m.topic && !m.thread_parent_id && !hiddenTopics.has(m.topic))
        counts[m.topic] = (counts[m.topic] ?? 0) + 1;
    }
    return Object.entries(counts).map(([topic, count]) => ({ topic, count }))
      .sort((a, b) => b.count - a.count);
  }, [messages, hiddenTopics]);

  useEffect(() => { setActiveTopic(null); setHiddenTopics(new Set()); }, [activeChannelId]);

  useEffect(() => {
    fetch(`${API_BASE}/messaging/channels`)
      .then((r) => r.json())
      .then((data: Channel[]) => {
        setChannels(data);
        if (data.length > 0) setActiveChannelId(data[0].id);
      })
      .catch(() => {})
      .finally(() => setLoadingChannels(false));
  }, []);

  const handleAddChannel = useCallback(async (name: string) => {
    const res = await fetch(`${API_BASE}/messaging/channels`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (res.ok) {
      const ch: Channel = await res.json();
      setChannels((prev) => [...prev, ch]);
      setActiveChannelId(ch.id);
    }
  }, []);

  const handleDeleteChannel = useCallback(async (id: string) => {
    await fetch(`${API_BASE}/messaging/channels/${id}`, { method: "DELETE" }).catch(() => {});
    setChannels((prev) => prev.filter((c) => c.id !== id));
    if (activeChannelId === id) {
      setActiveChannelId((prev) => {
        const remaining = channels.filter((c) => c.id !== id);
        return remaining.length > 0 ? remaining[0].id : null;
      });
    }
  }, [activeChannelId, channels]);

  const handleDeleteTopic = useCallback(async (topic: string) => {
    if (activeChannelId) {
      await fetch(`${API_BASE}/messaging/channels/${activeChannelId}/topics/${encodeURIComponent(topic)}`, {
        method: "DELETE",
      }).catch(() => {});
    }
    setHiddenTopics((prev) => { const next = new Set(prev); next.add(topic); return next; });
    if (activeTopic === topic) setActiveTopic(null);
  }, [activeChannelId, activeTopic]);

  // Link unfurling — debounced on input change
  const tryUnfurl = useCallback((text: string) => {
    const match = text.match(URL_RE);
    if (!match) return;
    const url = match[0];
    if (pendingAttachments.some((a) => a.type === "link" && (a as any).url === url)) return;
    if (unfurlTimerRef.current) clearTimeout(unfurlTimerRef.current);
    unfurlTimerRef.current = setTimeout(async () => {
      try {
        const res = await fetch(`${API_BASE}/messaging/unfurl`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url }),
        });
        if (res.ok) {
          const preview = await res.json();
          if (preview.title) {
            setPendingAttachments((prev) => {
              if (prev.some((a) => a.type === "link" && (a as any).url === url)) return prev;
              return [...prev.filter((a) => a.type !== "link"), preview];
            });
          }
        }
      } catch { /* silent */ }
    }, 600);
  }, [pendingAttachments]);

  const handleInputChange = (val: string) => {
    setInput(val);
    if (val.length > 0) startTyping(); else stopTyping();
    if (URL_RE.test(val)) tryUnfurl(val);
    else setPendingAttachments((prev) => prev.filter((a) => a.type !== "link"));
  };

  // File upload
  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!activeChannelId || !e.target.files?.length) return;
    setUploading(true);
    try {
      for (const file of Array.from(e.target.files)) {
        const form = new FormData();
        form.append("file", file);
        const res = await fetch(`${API_BASE}/messaging/channels/${activeChannelId}/upload`, {
          method: "POST", body: form,
        });
        if (res.ok) {
          const att = await res.json();
          setPendingAttachments((prev) => [...prev, att]);
        }
      }
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }, [activeChannelId]);

  const handleSend = useCallback(() => {
    const content = input.trim();
    if ((!content && !pendingAttachments.length) || !activeChannelId) return;
    sendMessage(content || "​", undefined, pendingAttachments.length ? pendingAttachments : undefined);
    setInput("");
    setPendingAttachments([]);
    stopTyping();
  }, [input, activeChannelId, pendingAttachments, sendMessage, stopTyping]);

  const handleSendReply = useCallback((content: string, parentId: string) => {
    sendMessage(content, parentId);
  }, [sendMessage]);

  const removeAttachment = (idx: number) =>
    setPendingAttachments((prev) => prev.filter((_, i) => i !== idx));

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="w-56 border-r flex flex-col bg-card shrink-0">
        <div className="p-3 border-b">
          <p className="text-xs font-semibold text-muted-foreground">WORKSPACE</p>
        </div>
        <ScrollArea className="flex-1 p-2">
          {loadingChannels ? (
            <div className="flex justify-center py-4">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              <ChannelList channels={channels} activeId={activeChannelId}
                onSelect={setActiveChannelId} onAdd={handleAddChannel} onDelete={handleDeleteChannel} />
              <TopicsPanel topics={topics} activeTopic={activeTopic} onSelect={setActiveTopic} onDelete={handleDeleteTopic} />
            </>
          )}
        </ScrollArea>
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="h-14 border-b flex items-center justify-between px-4 shrink-0">
          <div className="flex items-center gap-2">
            {activeChannel && (
              <>
                <Hash className="h-4 w-4 text-muted-foreground" />
                <span className="font-semibold text-sm">{activeChannel.name}</span>
                {activeTopic && (
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-muted-foreground">·</span>
                    <TopicBadge topic={activeTopic} />
                    <button onClick={() => setActiveTopic(null)} className="text-muted-foreground hover:text-foreground">
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                )}
              </>
            )}
            {!activeChannel && <span className="text-sm text-muted-foreground">Select a channel</span>}
          </div>
          <div className="flex items-center gap-2">
            {activeChannelId && (
              <StartCallButton
                userId={USER_ID}
                channelId={activeChannelId}
                title={`#${activeChannel?.name ?? "call"}`}
              />
            )}
            {activeChannelId && (
              <Button variant="ghost" size="sm" className="h-7 px-2 gap-1 text-xs text-muted-foreground"
                onClick={() => setShowGallery((v) => !v)} title="Media gallery">
                <Images className="h-3.5 w-3.5" />
                Gallery
              </Button>
            )}
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              {connected ? <Wifi className="h-3.5 w-3.5 text-green-500" /> : <WifiOff className="h-3.5 w-3.5 text-destructive" />}
              <span>{connected ? "Live" : "Offline"}</span>
            </div>
          </div>
        </header>

        {activeChannelId ? (
          <div className="flex flex-1 min-h-0">
            <div className="flex-1 flex flex-col min-w-0">
              <MessageThread
                messages={messages} typingUsers={typingUsers}
                userId={USER_ID} channelId={activeChannelId}
                onSendReply={handleSendReply}
                topicFilter={activeTopic} onTopicClick={setActiveTopic}
              />

              {/* Pending attachments preview */}
              {pendingAttachments.length > 0 && (
                <div className="border-t px-4 pt-3 flex flex-wrap gap-2">
                  {pendingAttachments.map((att, i) => (
                    <div key={i} className="relative group">
                      <AttachmentList attachments={[att]} />
                      <button onClick={() => removeAttachment(i)}
                        className="absolute -top-1.5 -right-1.5 h-4 w-4 rounded-full bg-destructive text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                        <X className="h-2.5 w-2.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Input bar */}
              <div className="border-t px-4 py-3 shrink-0">
                <div className="flex gap-2">
                  <input ref={fileInputRef} type="file" multiple className="hidden"
                    accept="image/*,video/*,.pdf,.doc,.docx,.txt,.zip"
                    onChange={handleFileSelect} />
                  <Button variant="ghost" size="icon" className="h-9 w-9 shrink-0 text-muted-foreground"
                    disabled={uploading || !connected} onClick={() => fileInputRef.current?.click()}
                    title="Attach file">
                    {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Paperclip className="h-4 w-4" />}
                  </Button>
                  <Input value={input}
                    onChange={(e) => handleInputChange(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
                    onBlur={stopTyping}
                    placeholder={activeTopic ? `Message #${activeChannel?.name} · ${activeTopic}` : `Message #${activeChannel?.name ?? "..."}`}
                    className="text-sm" />
                  <Button size="icon" disabled={(!input.trim() && !pendingAttachments.length) || !connected}
                    onClick={handleSend}>
                    <Send className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>

            {/* Media gallery panel */}
            {showGallery && (
              <div className="w-72 border-l flex flex-col shrink-0">
                <MediaGallery messages={messages} onClose={() => setShowGallery(false)} />
              </div>
            )}
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <p className="text-sm">Pick a channel to start messaging</p>
          </div>
        )}
      </div>
    </div>
  );
}
