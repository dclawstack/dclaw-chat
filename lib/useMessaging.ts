"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { ChannelMessage, MessageAttachment } from "@/types/chat";
import { wsAuthQuery } from "@/lib/auth";

const _apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const WS_BASE = _apiBase.replace(/^http/, "ws").replace(/\/api\/v1\/?$/, "/api/v1/messaging/ws");

interface UseMessagingOptions {
  channelId: string | null;
  /** Unused: identity now comes from the verified auth token (see lib/auth.ts). */
  userId?: string;
  /** Unused: identity now comes from the verified auth token (see lib/auth.ts). */
  userName?: string;
}

export function useMessaging({ channelId }: UseMessagingOptions) {
  const [messages, setMessages] = useState<ChannelMessage[]>([]);
  const [typingUsers, setTypingUsers] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const typingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isTypingRef = useRef(false);

  const connect = useCallback((chId: string) => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    const q = wsAuthQuery();
    const url = `${WS_BASE}/${chId}${q ? `?${q}` : ""}`;
    const ws = new WebSocket(url);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);

    ws.onmessage = (evt) => {
      const data = JSON.parse(evt.data);
      if (data.type === "history") {
        setMessages(data.messages);
      } else if (data.type === "message") {
        setMessages((prev) => {
          if (prev.some((m) => m.id === data.id)) return prev;
          if (data.thread_parent_id) {
            // Add the reply AND bump the parent's reply_count
            return prev
              .map((m) =>
                m.id === data.thread_parent_id
                  ? { ...m, reply_count: m.reply_count + 1 }
                  : m
              )
              .concat([data as ChannelMessage]);
          }
          return [...prev, data as ChannelMessage];
        });
      } else if (data.type === "typing") {
        setTypingUsers(data.typing_users || []);
      }
    };

    wsRef.current = ws;
  }, []);

  useEffect(() => {
    if (!channelId) return;
    setMessages([]);
    setTypingUsers([]);
    connect(channelId);
    return () => {
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [channelId, connect]);

  const sendMessage = useCallback(
    (content: string, threadParentId?: string, attachments?: MessageAttachment[]) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      wsRef.current.send(
        JSON.stringify({
          type: "message",
          content,
          thread_parent_id: threadParentId ?? null,
          attachments: attachments ?? [],
        })
      );
      stopTyping();
    },
    []
  );

  const startTyping = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    if (!isTypingRef.current) {
      isTypingRef.current = true;
      wsRef.current.send(JSON.stringify({ type: "typing_start" }));
    }
    if (typingTimerRef.current) clearTimeout(typingTimerRef.current);
    typingTimerRef.current = setTimeout(stopTyping, 3000);
  }, []);

  const stopTyping = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    if (isTypingRef.current) {
      isTypingRef.current = false;
      wsRef.current.send(JSON.stringify({ type: "typing_stop" }));
    }
    if (typingTimerRef.current) clearTimeout(typingTimerRef.current);
  }, []);

  return { messages, typingUsers, connected, sendMessage, startTyping, stopTyping };
}
