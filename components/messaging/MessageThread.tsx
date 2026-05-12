"use client";

import { useState, useRef, useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090/api/v1";
import { ChannelMessage } from "@/types/chat";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageSquare } from "lucide-react";
import { TypingIndicator } from "./TypingIndicator";
import { TopicBadge } from "./TopicBadge";
import { ThreadView } from "@/components/thread-view";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

interface MessageItemProps {
  message: ChannelMessage;
  isOwn: boolean;
  onReply: (msg: ChannelMessage) => void;
  onTopicClick?: (topic: string) => void;
}

function MessageItem({ message, isOwn, onReply, onTopicClick }: MessageItemProps) {
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
        <div className="flex items-center gap-2 mb-0.5 flex-wrap">
          <span className="text-sm font-semibold">{message.user_name}</span>
          <span className="text-xs text-muted-foreground">{time}</span>
          {message.topic && (
            <TopicBadge
              topic={message.topic}
              small
              onClick={onTopicClick ? () => onTopicClick(message.topic!) : undefined}
            />
          )}
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

interface MessageThreadProps {
  messages: ChannelMessage[];
  typingUsers: string[];
  userId: string;
  channelId: string;
  onSendReply: (content: string, parentId: string) => void;
  topicFilter?: string | null;
  onTopicClick?: (topic: string) => void;
  isLoading?: boolean;
}

export function MessageThread({
  messages,
  typingUsers,
  userId,
  channelId,
  onSendReply,
  topicFilter,
  onTopicClick,
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
    fetch(
      `${API_BASE}/messaging/channels/${channelId}/messages/${threadParent.id}/thread`
    )
      .then((r) => r.json())
      .then((data: ChannelMessage[]) => setFetchedReplies(data))
      .catch(() => setFetchedReplies([]));
  }, [threadParent?.id, channelId]);

  // Merge historical + live replies, deduped and sorted
  const liveReplies = threadParent
    ? messages.filter((m) => m.thread_parent_id === threadParent.id)
    : [];
  const seenIds = new Set(liveReplies.map((m) => m.id));
  const threadReplies = [
    ...fetchedReplies.filter((m) => !seenIds.has(m.id)),
    ...liveReplies,
  ].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  // Apply topic filter to root messages only
  const rootMessages = messages.filter(
    (m) =>
      !m.thread_parent_id &&
      (!topicFilter || m.topic === topicFilter)
  );

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-8">
        <MessageSquare className="h-10 w-10 mb-3 opacity-30" />
        <p className="text-sm font-medium text-foreground">No messages yet</p>
        <p className="text-xs mt-1">Be the first to say something!</p>
      </div>
    );
  }

  if (topicFilter && rootMessages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-8">
        <p className="text-sm">No messages tagged <strong>{topicFilter}</strong></p>
      </div>
    );
  }

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
                onTopicClick={onTopicClick}
              />
            ))}
            <div ref={bottomRef} />
          </div>
        </ScrollArea>
        <TypingIndicator typingUsers={typingUsers} />
      </div>

      {threadParent && (
        <ThreadView
          parent={threadParent}
          replies={threadReplies}
          channelId={channelId}
          onClose={() => setThreadParent(null)}
          onSendReply={(content) => onSendReply(content, threadParent.id)}
          userId={userId}
        />
      )}
    </div>
  );
}
