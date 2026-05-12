"use client";

import { useState, useRef, useEffect, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090/api/v1";
import { ChannelMessage } from "@/types/chat";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { MessageSquare, X, Send } from "lucide-react";
import { TypingIndicator } from "./TypingIndicator";

interface MessageItemProps {
  message: ChannelMessage;
  isOwn: boolean;
  onReply: (msg: ChannelMessage) => void;
}

function MessageItem({ message, isOwn, onReply }: MessageItemProps) {
  const time = new Date(message.created_at).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "numeric",
    hour12: true,
  });

  return (
    <div className="group flex gap-3 px-4 py-3 hover:bg-muted/30 transition-colors">
      <Avatar className={`h-8 w-8 shrink-0 ${isOwn ? "bg-dclaw-500" : "bg-muted"}`}>
        <AvatarFallback className={`text-xs ${isOwn ? "text-white" : "text-foreground"}`}>
          {message.user_name.slice(0, 2).toUpperCase()}
        </AvatarFallback>
      </Avatar>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-semibold">{message.user_name}</span>
          <span className="text-xs text-muted-foreground">{time}</span>
        </div>
        <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
          {message.content}
        </p>
        {message.reply_count > 0 && (
          <button
            onClick={() => onReply(message)}
            className="mt-1 flex items-center gap-1 text-xs text-dclaw-500 hover:underline"
          >
            <MessageSquare className="h-3 w-3" />
            {message.reply_count} {message.reply_count === 1 ? "reply" : "replies"}
          </button>
        )}
      </div>

      {/* Reply button on hover */}
      <button
        onClick={() => onReply(message)}
        className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-foreground transition-opacity shrink-0 self-start mt-1"
        title="Reply in thread"
      >
        <MessageSquare className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

interface ThreadPanelProps {
  parent: ChannelMessage;
  replies: ChannelMessage[];
  onClose: () => void;
  onSendReply: (content: string) => void;
  userId: string;
}

function ThreadPanel({ parent, replies, onClose, onSendReply, userId }: ThreadPanelProps) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [replies]);

  const handleSend = () => {
    if (!input.trim()) return;
    onSendReply(input.trim());
    setInput("");
  };

  return (
    <div className="w-80 border-l flex flex-col bg-background shrink-0">
      <div className="h-14 border-b flex items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-dclaw-500" />
          <span className="text-sm font-semibold">Thread</span>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        {/* Parent message */}
        <div className="px-4 py-3 border-b bg-muted/20">
          <p className="text-xs text-muted-foreground mb-1">{parent.user_name}</p>
          <p className="text-sm whitespace-pre-wrap">{parent.content}</p>
        </div>
        <p className="text-xs text-muted-foreground px-4 py-2">
          {replies.length} {replies.length === 1 ? "reply" : "replies"}
        </p>
        {replies.map((r) => (
          <MessageItem key={r.id} message={r} isOwn={r.user_id === userId} onReply={() => {}} />
        ))}
        <div ref={bottomRef} />
      </ScrollArea>

      <div className="border-t px-3 py-3">
        <div className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            placeholder="Reply in thread…"
            className="text-sm h-9"
          />
          <Button size="icon" className="h-9 w-9 shrink-0" disabled={!input.trim()} onClick={handleSend}>
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

interface MessageThreadProps {
  messages: ChannelMessage[];
  typingUsers: string[];
  userId: string;
  channelId: string;
  onSendReply: (content: string, parentId: string) => void;
  isLoading?: boolean;
}

export function MessageThread({
  messages,
  typingUsers,
  userId,
  channelId,
  onSendReply,
  isLoading,
}: MessageThreadProps) {
  const [threadParent, setThreadParent] = useState<ChannelMessage | null>(null);
  const [fetchedReplies, setFetchedReplies] = useState<ChannelMessage[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Fetch historical replies when thread panel opens
  useEffect(() => {
    if (!threadParent || !channelId) {
      setFetchedReplies([]);
      return;
    }
    fetch(`${API_BASE}/messaging/channels/${channelId}/messages/${threadParent.id}/thread`)
      .then((r) => r.json())
      .then((data: ChannelMessage[]) => setFetchedReplies(data))
      .catch(() => setFetchedReplies([]));
  }, [threadParent?.id, channelId]);

  // Merge fetched historical replies with live WS replies, deduplicated
  const liveReplies = threadParent
    ? messages.filter((m) => m.thread_parent_id === threadParent.id)
    : [];
  const seenIds = new Set(liveReplies.map((m) => m.id));
  const threadReplies = [
    ...fetchedReplies.filter((m) => !seenIds.has(m.id)),
    ...liveReplies,
  ].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-8">
        <MessageSquare className="h-10 w-10 mb-3 opacity-30" />
        <p className="text-sm font-medium text-foreground">No messages yet</p>
        <p className="text-xs mt-1">Be the first to say something!</p>
      </div>
    );
  }

  const rootMessages = messages.filter((m) => !m.thread_parent_id);

  return (
    <div className="flex flex-1 min-h-0">
      <div className="flex-1 flex flex-col min-w-0">
        <ScrollArea className="flex-1">
          <div>
            {rootMessages.map((msg) => (
              <MessageItem
                key={msg.id}
                message={msg}
                isOwn={msg.user_id === userId}
                onReply={setThreadParent}
              />
            ))}
            <div ref={bottomRef} />
          </div>
        </ScrollArea>
        <TypingIndicator typingUsers={typingUsers} />
      </div>

      {threadParent && (
        <ThreadPanel
          parent={threadParent}
          replies={threadReplies}
          onClose={() => setThreadParent(null)}
          onSendReply={(content) => onSendReply(content, threadParent.id)}
          userId={userId}
        />
      )}
    </div>
  );
}
