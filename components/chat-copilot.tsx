"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Bot, X, Send, Loader2, FileText, CheckSquare, ChevronDown, ChevronUp, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CopilotMessage, ConversationSummary, ExtractedAction, Message } from "@/types/chat";
import { copilotChat, summarizeConversation, extractActions, ApiMessage } from "@/lib/api";
import { getStoredWorkspaceId } from "@/lib/useWorkspaces";
import { CitationBadge } from "@/components/graph/CatchMeUp";

interface ThreadSummaryCardProps {
  summary: ConversationSummary;
  onClose: () => void;
}

function ThreadSummaryCard({ summary, onClose }: ThreadSummaryCardProps) {
  const [expanded, setExpanded] = useState(true);
  const lines = summary.summary.split("\n").filter(Boolean);

  return (
    <div className="border border-border rounded-lg bg-muted/30 mb-3">
      <div
        role="button"
        tabIndex={0}
        className="flex items-center justify-between px-3 py-2 cursor-pointer"
        onClick={() => setExpanded((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setExpanded((v) => !v);
          }
        }}
      >
        <div className="flex items-center gap-2 text-xs font-medium text-foreground">
          <FileText className="h-3.5 w-3.5 text-dclaw-500" />
          Thread Summary
          <span className="text-muted-foreground font-normal">
            ({summary.messageCount} messages)
          </span>
        </div>
        <div className="flex items-center gap-1">
          {expanded ? (
            <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          )}
          <button
            onClick={(e) => { e.stopPropagation(); onClose(); }}
            aria-label="Close"
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      {expanded && (
        <div className="px-3 pb-3 space-y-1">
          {lines.map((line, i) => (
            <p key={i} className="text-xs text-muted-foreground leading-relaxed">
              {line}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

interface ActionsPanelProps {
  actions: ExtractedAction[];
  onClose: () => void;
}

function ActionsPanel({ actions, onClose }: ActionsPanelProps) {
  const [items, setItems] = useState(actions);
  const priorityColor: Record<string, string> = {
    high: "text-red-400",
    medium: "text-yellow-400",
    low: "text-green-400",
  };

  const toggle = (i: number) =>
    setItems((prev) =>
      prev.map((a, idx) =>
        idx === i ? { ...a, status: a.status === "done" ? "open" : "done" } : a
      )
    );

  return (
    <div className="border border-border rounded-lg bg-muted/30 mb-3">
      <div className="flex items-center justify-between px-3 py-2">
        <div className="flex items-center gap-2 text-xs font-medium text-foreground">
          <CheckSquare className="h-3.5 w-3.5 text-dclaw-500" />
          Extracted Actions
          <span className="text-muted-foreground font-normal">({items.length})</span>
        </div>
        <button onClick={onClose} aria-label="Close" className="text-muted-foreground hover:text-foreground">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="px-3 pb-3 space-y-2">
        {items.map((action, i) => (
          <div
            key={i}
            role="button"
            tabIndex={0}
            className="flex items-start gap-2 cursor-pointer"
            onClick={() => toggle(i)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                toggle(i);
              }
            }}
          >
            <div
              className={`mt-0.5 h-3.5 w-3.5 shrink-0 rounded border flex items-center justify-center ${
                action.status === "done"
                  ? "bg-dclaw-500 border-dclaw-500"
                  : "border-muted-foreground"
              }`}
            >
              {action.status === "done" && (
                <svg viewBox="0 0 10 8" className="h-2 w-2 fill-white">
                  <path d="M1 4l3 3 5-6" stroke="white" strokeWidth="1.5" fill="none" />
                </svg>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p
                className={`text-xs leading-relaxed ${
                  action.status === "done"
                    ? "line-through text-muted-foreground"
                    : "text-foreground"
                }`}
              >
                {action.text}
              </p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className={`text-[10px] font-medium ${priorityColor[action.priority]}`}>
                  {action.priority}
                </span>
                {action.assignee && (
                  <span className="text-[10px] text-muted-foreground">
                    → {action.assignee}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
        {items.length === 0 && (
          <p className="text-xs text-muted-foreground">No actions found in this thread.</p>
        )}
      </div>
    </div>
  );
}

interface ChatCopilotProps {
  conversationId: string | null;
  selectedModel: string;
  conversationMessages?: Message[];
}

export function ChatCopilot({ conversationId, selectedModel, conversationMessages = [] }: ChatCopilotProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [summary, setSummary] = useState<ConversationSummary | null>(null);
  const [actions, setActions] = useState<ExtractedAction[] | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Reset panels when conversation changes
  useEffect(() => {
    setSummary(null);
    setActions(null);
  }, [conversationId]);

  const handleSend = useCallback(async () => {
    const q = query.trim();
    if (!q || isLoading) return;
    setQuery("");

    const userMsg: CopilotMessage = {
      id: Date.now().toString(),
      role: "user",
      content: q,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const res = await copilotChat({
        query: q,
        conversation_id: conversationId ?? undefined,
        workspace_id: getStoredWorkspaceId() ?? undefined,
        model: selectedModel,
      });
      const assistantMsg: CopilotMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: res.answer,
        timestamp: new Date(),
        ragChunksUsed: res.rag_chunks_used,
        citations: res.citations,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg: CopilotMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `⚠️ ${err instanceof Error ? err.message : "Copilot error"}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  }, [query, isLoading, conversationId, selectedModel]);

  const handleSummarize = useCallback(async () => {
    if (!conversationId || isSummarizing) return;
    setIsSummarizing(true);
    const apiMessages: ApiMessage[] = conversationMessages.map((m) => ({
      role: m.role as "user" | "assistant" | "system",
      content: m.content,
    }));
    try {
      const res = await summarizeConversation(conversationId, apiMessages, selectedModel);
      setSummary({
        conversationId: res.conversation_id,
        summary: res.summary,
        messageCount: res.message_count,
      });
    } catch {
      setSummary({
        conversationId: conversationId,
        summary: "⚠️ Failed to generate summary. Try again.",
        messageCount: 0,
      });
    } finally {
      setIsSummarizing(false);
    }
  }, [conversationId, selectedModel, isSummarizing]);

  const handleExtractActions = useCallback(async () => {
    if (!conversationId || isExtracting) return;
    setIsExtracting(true);
    const apiMessages: ApiMessage[] = conversationMessages.map((m) => ({
      role: m.role as "user" | "assistant" | "system",
      content: m.content,
    }));
    try {
      const res = await extractActions(conversationId, apiMessages, selectedModel);
      setActions(
        res.actions.map((a) => ({
          text: a.text,
          priority: a.priority,
          assignee: a.assignee,
          status: a.status,
        }))
      );
    } catch {
      setActions([]);
    } finally {
      setIsExtracting(false);
    }
  }, [conversationId, selectedModel, isExtracting]);

  return (
    <>
      {/* Toggle button */}
      <Button
        variant="ghost"
        size="icon"
        className="relative"
        onClick={() => setOpen((v) => !v)}
        title="AI Copilot"
      >
        <Sparkles className="h-4 w-4" />
        {messages.length > 0 && (
          <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-dclaw-500" />
        )}
      </Button>

      {/* Sidebar panel */}
      {open && (
        <div className="fixed right-0 top-0 h-full w-80 bg-background border-l border-border flex flex-col z-40 shadow-xl">
          {/* Header */}
          <div className="h-14 border-b flex items-center justify-between px-4 shrink-0">
            <div className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-dclaw-500" />
              <span className="text-sm font-semibold">AI Copilot</span>
            </div>
            <Button variant="ghost" size="icon" onClick={() => setOpen(false)}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Action buttons */}
          <div className="flex gap-2 px-3 py-2 border-b shrink-0">
            <Button
              variant="outline"
              size="sm"
              className="flex-1 text-xs h-7"
              disabled={!conversationId || isSummarizing}
              onClick={handleSummarize}
            >
              {isSummarizing ? (
                <Loader2 className="h-3 w-3 animate-spin mr-1" />
              ) : (
                <FileText className="h-3 w-3 mr-1" />
              )}
              Summarize
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="flex-1 text-xs h-7"
              disabled={!conversationId || isExtracting}
              onClick={handleExtractActions}
            >
              {isExtracting ? (
                <Loader2 className="h-3 w-3 animate-spin mr-1" />
              ) : (
                <CheckSquare className="h-3 w-3 mr-1" />
              )}
              Actions
            </Button>
          </div>

          {/* Cards + messages */}
          <ScrollArea className="flex-1 px-3 py-3">
            {summary && (
              <ThreadSummaryCard
                summary={summary}
                onClose={() => setSummary(null)}
              />
            )}
            {actions && (
              <ActionsPanel
                actions={actions}
                onClose={() => setActions(null)}
              />
            )}

            {messages.length === 0 && !summary && !actions && (
              <div className="flex flex-col items-center justify-center h-40 text-center">
                <Bot className="h-8 w-8 text-muted-foreground mb-2" />
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Ask me anything about this conversation.
                  <br />
                  I use RAG to search your thread history.
                </p>
              </div>
            )}

            <div className="space-y-3">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[90%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
                      msg.role === "user"
                        ? "bg-dclaw-500 text-white"
                        : "bg-muted text-foreground"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                    {msg.ragChunksUsed !== undefined && msg.ragChunksUsed > 0 && (
                      <p className="mt-1 text-[10px] opacity-60">
                        {msg.ragChunksUsed} context chunks used
                      </p>
                    )}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-border/50">
                        <p className="text-[10px] text-muted-foreground mb-1">
                          Sources from your workspace graph
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {msg.citations.map((c, i) => (
                            <CitationBadge key={`${c.kind}-${c.name}-${i}`} citation={c} />
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="bg-muted rounded-lg px-3 py-2">
                    <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </ScrollArea>

          {/* Input */}
          <div className="border-t px-3 py-3 shrink-0">
            <div className="flex gap-2">
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
                placeholder={
                  conversationId
                    ? "Ask about this conversation…"
                    : "Select a conversation first"
                }
                disabled={!conversationId || isLoading}
                className="text-xs h-8"
              />
              <Button
                size="icon"
                className="h-8 w-8 shrink-0"
                disabled={!query.trim() || isLoading || !conversationId}
                onClick={handleSend}
              >
                <Send className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
