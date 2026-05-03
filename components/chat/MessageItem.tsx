"use client";

import { Message } from "@/types/chat";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Loader2, AlertCircle } from "lucide-react";

interface MessageItemProps {
  message: Message;
}

export function MessageItem({ message }: MessageItemProps) {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";

  const formatTime = (date: Date) => {
    return new Intl.DateTimeFormat("en-US", {
      hour: "numeric",
      minute: "numeric",
      hour12: true,
    }).format(date);
  };

  const renderContent = (content: string) => {
    // Simple markdown-like rendering
    const lines = content.split("\n");
    return lines.map((line, i) => {
      if (line.startsWith("```")) {
        return null; // Handle code blocks separately
      }
      if (line.startsWith("# ")) {
        return (
          <h1 key={i} className="text-lg font-bold mb-2">
            {line.replace("# ", "")}
          </h1>
        );
      }
      if (line.startsWith("## ")) {
        return (
          <h2 key={i} className="text-base font-semibold mb-2">
            {line.replace("## ", "")}
          </h2>
        );
      }
      if (line.startsWith("- ")) {
        return (
          <li key={i} className="ml-4 list-disc">
            {line.replace("- ", "")}
          </li>
        );
      }
      if (line.match(/^\d+\.\s/)) {
        return (
          <li key={i} className="ml-4 list-decimal">
            {line.replace(/^\d+\.\s/, "")}
          </li>
        );
      }
      if (line.trim() === "") {
        return <div key={i} className="h-2" />;
      }
      return (
        <p key={i} className="mb-1 leading-relaxed">
          {line}
        </p>
      );
    });
  };

  return (
    <div
      className={`flex gap-3 px-4 py-4 ${
        isUser ? "bg-dclaw-50/50" : "bg-background"
      }`}
    >
      <Avatar className={`shrink-0 ${isUser ? "bg-dclaw-100" : "bg-dclaw-500"}`}>
        <AvatarFallback
          className={`text-sm ${isUser ? "text-dclaw-700" : "text-white"}`}
        >
          {isUser ? "You" : "🤖"}
        </AvatarFallback>
      </Avatar>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-semibold">
            {isUser ? "You" : "DClaw Assistant"}
          </span>
          {message.model && (
            <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
              {message.model}
            </span>
          )}
          <span className="text-xs text-muted-foreground">
            {formatTime(message.timestamp)}
          </span>
          {message.status === "sending" && (
            <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
          )}
          {message.status === "error" && (
            <AlertCircle className="h-3 w-3 text-destructive" />
          )}
        </div>

        <div className="text-sm prose max-w-none">
          {renderContent(message.content)}
        </div>
      </div>
    </div>
  );
}
