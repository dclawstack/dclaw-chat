"use client";

import { useState, useEffect, useCallback } from "react";
import { Channel } from "@/types/chat";
import { useMessaging } from "@/lib/useMessaging";
import { MessageThread } from "./MessageThread";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Hash, Plus, Send, Wifi, WifiOff, Loader2 } from "lucide-react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090/api/v1";

const USER_ID = "dev-user";
const USER_NAME = "You";

interface ChannelListProps {
  channels: Channel[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onAdd: (name: string) => void;
}

function ChannelList({ channels, activeId, onSelect, onAdd }: ChannelListProps) {
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
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Channels
        </span>
        <button
          onClick={() => setAdding((v) => !v)}
          className="text-muted-foreground hover:text-foreground"
          title="Add channel"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>

      {adding && (
        <div className="px-3 pb-2 flex gap-1">
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder="channel-name"
            className="h-7 text-xs"
            autoFocus
          />
          <Button size="sm" className="h-7 px-2 text-xs" onClick={handleAdd}>
            Add
          </Button>
        </div>
      )}

      {channels.map((ch) => (
        <button
          key={ch.id}
          onClick={() => onSelect(ch.id)}
          className={`w-full flex items-center gap-2 px-3 py-1.5 text-sm rounded-md transition-colors ${
            ch.id === activeId
              ? "bg-dclaw-100 text-dclaw-900 font-medium"
              : "text-muted-foreground hover:bg-accent hover:text-foreground"
          }`}
        >
          <Hash className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{ch.name}</span>
        </button>
      ))}
    </div>
  );
}

export function MessagingView() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [activeChannelId, setActiveChannelId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [loadingChannels, setLoadingChannels] = useState(true);

  const activeChannel = channels.find((c) => c.id === activeChannelId);

  const { messages, typingUsers, connected, sendMessage, startTyping, stopTyping } =
    useMessaging({ channelId: activeChannelId, userId: USER_ID, userName: USER_NAME });

  // Load channels from backend
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
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (res.ok) {
      const ch: Channel = await res.json();
      setChannels((prev) => [...prev, ch]);
      setActiveChannelId(ch.id);
    }
  }, []);

  const handleSend = useCallback(() => {
    const content = input.trim();
    if (!content || !activeChannelId) return;
    setInput("");
    sendMessage(content);
  }, [input, activeChannelId, sendMessage]);

  const handleSendReply = useCallback(
    (content: string, parentId: string) => {
      sendMessage(content, parentId);
    },
    [sendMessage]
  );

  const handleInputChange = (val: string) => {
    setInput(val);
    if (val.length > 0) startTyping();
    else stopTyping();
  };

  return (
    <div className="flex h-full">
      {/* Channel sidebar */}
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
            <ChannelList
              channels={channels}
              activeId={activeChannelId}
              onSelect={setActiveChannelId}
              onAdd={handleAddChannel}
            />
          )}
        </ScrollArea>
      </aside>

      {/* Main channel area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Channel header */}
        <header className="h-14 border-b flex items-center justify-between px-4 shrink-0">
          <div className="flex items-center gap-2">
            {activeChannel && (
              <>
                <Hash className="h-4 w-4 text-muted-foreground" />
                <span className="font-semibold text-sm">{activeChannel.name}</span>
              </>
            )}
            {!activeChannel && (
              <span className="text-sm text-muted-foreground">Select a channel</span>
            )}
          </div>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            {connected ? (
              <Wifi className="h-3.5 w-3.5 text-green-500" />
            ) : (
              <WifiOff className="h-3.5 w-3.5 text-destructive" />
            )}
            <span>{connected ? "Live" : "Offline"}</span>
          </div>
        </header>

        {/* Messages + threads */}
        {activeChannelId ? (
          <>
            <MessageThread
              messages={messages}
              typingUsers={typingUsers}
              userId={USER_ID}
              channelId={activeChannelId}
              onSendReply={handleSendReply}
            />

            {/* Input bar */}
            <div className="border-t px-4 py-3 shrink-0">
              <div className="flex gap-2">
                <Input
                  value={input}
                  onChange={(e) => handleInputChange(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
                  onBlur={stopTyping}
                  placeholder={`Message #${activeChannel?.name ?? "..."}`}
                  className="text-sm"
                />
                <Button
                  size="icon"
                  disabled={!input.trim() || !connected}
                  onClick={handleSend}
                >
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <p className="text-sm">Pick a channel to start messaging</p>
          </div>
        )}
      </div>
    </div>
  );
}
