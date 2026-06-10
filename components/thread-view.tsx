"use client";

import { useState, useRef, useEffect } from "react";
import { ChannelMessage } from "@/types/chat";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { X, Send, Sparkles, ChevronDown, ChevronUp, MessageSquare } from "lucide-react";
import { TopicBadge } from "@/components/messaging/TopicBadge";
import { apiFetch } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface ThreadViewProps {
  parent: ChannelMessage;
  replies: ChannelMessage[];
  channelId: string;
  onClose: () => void;
  onSendReply: (content: string) => void;
  userId: string;
}

export function ThreadView({
  parent,
  replies,
  channelId,
  onClose,
  onSendReply,
  userId,
}: ThreadViewProps) {
  const [input, setInput] = useState("");
  const [summary, setSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [replies]);

  const handleSend = () => {
    if (!input.trim()) return;
    onSendReply(input.trim());
    setInput("");
  };

  const handleSummarize = async () => {
    if (summary) {
      setSummaryOpen((v) => !v);
      return;
    }
    setSummaryOpen(true);
    setSummaryLoading(true);
    try {
      const topic = parent.topic || "general";
      const res = await apiFetch(
        `${API_BASE}/messaging/channels/${channelId}/topics/${encodeURIComponent(topic)}/summary`
      );
      const data = await res.json();
      setSummary(data.summary ?? "No summary available.");
    } catch {
      setSummary("Could not load summary.");
    } finally {
      setSummaryLoading(false);
    }
  };

  const fmt = (ts: string) =>
    new Date(ts).toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });

  return (
    <div className="w-80 border-l flex flex-col bg-background shrink-0">
      {/* Header */}
      <div className="h-14 border-b flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-dclaw-500" />
          <span className="text-sm font-semibold">Thread</span>
          {parent.topic && <TopicBadge topic={parent.topic} />}
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs gap-1 text-muted-foreground hover:text-foreground"
            onClick={handleSummarize}
            title="Auto-summarize this topic"
          >
            <Sparkles className="h-3 w-3" />
            Summary
            {summaryOpen ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
          </Button>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Auto-summary panel */}
      {summaryOpen && (
        <div className="border-b bg-muted/30 px-4 py-3 text-xs space-y-1">
          <p className="font-semibold text-muted-foreground flex items-center gap-1">
            <Sparkles className="h-3 w-3 text-dclaw-500" />
            Topic summary · {parent.topic ?? "general"}
          </p>
          {summaryLoading ? (
            <p className="text-muted-foreground animate-pulse">Summarizing…</p>
          ) : (
            <p className="whitespace-pre-wrap leading-relaxed text-foreground">{summary}</p>
          )}
        </div>
      )}

      <ScrollArea className="flex-1">
        {/* Parent message */}
        <div className="px-4 py-3 border-b bg-muted/20">
          <div className="flex items-center gap-2 mb-1">
            <Avatar className="h-6 w-6 bg-muted shrink-0">
              <AvatarFallback className="text-xs">
                {parent.user_name.slice(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <span className="text-xs font-semibold">{parent.user_name}</span>
            <span className="text-xs text-muted-foreground">{fmt(parent.created_at)}</span>
          </div>
          <p className="text-sm whitespace-pre-wrap break-words">{parent.content}</p>
        </div>

        <p className="text-xs text-muted-foreground px-4 py-2">
          {replies.length} {replies.length === 1 ? "reply" : "replies"}
        </p>

        {replies.map((r) => (
          <div key={r.id} className="flex gap-3 px-4 py-2 hover:bg-muted/30 transition-colors">
            <Avatar
              className={`h-7 w-7 shrink-0 ${
                r.user_id === userId ? "bg-dclaw-500" : "bg-muted"
              }`}
            >
              <AvatarFallback
                className={`text-xs ${r.user_id === userId ? "text-white" : ""}`}
              >
                {r.user_name.slice(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                <span className="text-xs font-semibold">{r.user_name}</span>
                <span className="text-xs text-muted-foreground">{fmt(r.created_at)}</span>
                {r.topic && r.topic !== parent.topic && (
                  <TopicBadge topic={r.topic} small />
                )}
              </div>
              <p className="text-sm whitespace-pre-wrap break-words">{r.content}</p>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </ScrollArea>

      {/* Reply input */}
      <div className="border-t px-3 py-3 shrink-0">
        <div className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            placeholder="Reply in thread…"
            className="text-sm h-9"
          />
          <Button
            size="icon"
            className="h-9 w-9 shrink-0"
            disabled={!input.trim()}
            onClick={handleSend}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
