"use client";

import { useRef, useEffect } from "react";
import { Message } from "@/types/chat";
import { MessageItem } from "./MessageItem";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2 } from "lucide-react";

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  onSuggestionClick?: (text: string) => void;
}

export function MessageList({ messages, isLoading, onSuggestionClick }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-8">
        <div className="text-4xl mb-4">💬</div>
        <h2 className="text-xl font-semibold text-foreground mb-2">
          Start a conversation
        </h2>
        <p className="text-center max-w-md">
          Ask anything, generate code, analyze documents, or just chat. Your
          conversations are private and stored locally.
        </p>
        <div className="flex gap-2 mt-6">
          {[
            "Explain quantum computing",
            "Write a Python script",
            "Summarize this article",
            "Help me debug",
          ].map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => onSuggestionClick?.(suggestion)}
              disabled={!onSuggestionClick}
              className="px-3 py-2 text-xs bg-muted rounded-lg hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1">
      <div className="max-w-3xl mx-auto">
        {messages.map((message) => (
          <MessageItem key={message.id} message={message} />
        ))}

        {isLoading && (
          <div className="flex gap-3 px-4 py-4">
            <div className="h-10 w-10 rounded-full bg-dclaw-500 flex items-center justify-center text-white text-sm shrink-0">
              🤖
            </div>
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              <span className="text-sm text-muted-foreground">
                Thinking...
              </span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
