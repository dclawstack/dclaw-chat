"use client";

import { useState, useRef, KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { VoiceButton } from "./VoiceButton";
import { Send, Paperclip } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
  disabled?: boolean;
}

export function ChatInput({ onSend, isLoading, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (!input.trim() || isLoading || disabled) return;
    onSend(input.trim());
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        200
      )}px`;
    }
  };

  return (
    <div className="border-t bg-background p-4">
      <div className="max-w-3xl mx-auto">
        <div className="relative flex items-end gap-2 bg-muted rounded-xl p-2">
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0 h-8 w-8 rounded-lg"
            title="Attach file"
          >
            <Paperclip className="h-4 w-4" />
          </Button>

          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            placeholder="Message DClaw Chat..."
            aria-label="Message DClaw Chat"
            disabled={isLoading || disabled}
            rows={1}
            className="flex-1 bg-transparent resize-none py-2 px-1 text-sm outline-none placeholder:text-muted-foreground min-h-[36px] max-h-[200px]"
          />

          <VoiceButton
            onTranscript={(text) => {
              setInput((prev) => prev + text);
              textareaRef.current?.focus();
            }}
            disabled={isLoading || disabled}
          />

          <Button
            onClick={handleSend}
            disabled={!input.trim() || isLoading || disabled}
            size="icon"
            className="shrink-0 h-8 w-8 rounded-lg bg-dclaw-500 hover:bg-dclaw-600"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>

        <p className="text-xs text-muted-foreground text-center mt-2">
          DClaw Chat can make mistakes. Consider checking important information.
          PII is anonymized before cloud inference.
        </p>
      </div>
    </div>
  );
}
