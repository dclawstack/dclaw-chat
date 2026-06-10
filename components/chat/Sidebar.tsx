"use client";

import { useState } from "react";
import { Conversation } from "@/types/chat";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CatchMeUp } from "@/components/graph/CatchMeUp";
import { UpgradeButton } from "@/components/billing/UpgradeButton";
import { AuthUserButton } from "@/components/auth/UserButton";
import { useWorkspaces } from "@/lib/useWorkspaces";
import {
  Plus,
  MessageSquare,
  Trash2,
  FolderOpen,
  Settings,
  X,
  ChevronDown,
  ChevronRight,
  Sparkles,
} from "lucide-react";

interface SidebarProps {
  conversations: Conversation[];
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: string) => void;
  onOpenSettings: () => void;
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onOpenSettings,
  isOpen,
  onClose,
}: SidebarProps) {
  // Group conversations by folder
  const grouped = conversations.reduce((acc, conv) => {
    const folder = conv.folder || "Uncategorized";
    if (!acc[folder]) acc[folder] = [];
    acc[folder].push(conv);
    return acc;
  }, {} as Record<string, Conversation[]>);

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          role="button"
          tabIndex={0}
          aria-label="Close sidebar"
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onClose();
            }
          }}
        />
      )}

      <aside
        className={`fixed lg:static inset-y-0 left-0 z-50 w-72 bg-card border-r flex flex-col transition-transform duration-200 ease-in-out ${
          isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        {/* Header */}
        <div className="p-4 border-b flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-dclaw-500 flex items-center justify-center text-white text-lg">
              💬
            </div>
            <div>
              <h1 className="font-bold text-sm">DClaw Chat</h1>
              <p className="text-xs text-muted-foreground">
                AI conversations
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden h-8 w-8"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* New Chat Button */}
        <div className="p-3">
          <Button
            onClick={onNewConversation}
            className="w-full justify-start gap-2 bg-dclaw-500 hover:bg-dclaw-600"
          >
            <Plus className="h-4 w-4" />
            New Chat
          </Button>
        </div>

        {/* Conversations */}
        <ScrollArea className="flex-1 px-3">
          {Object.entries(grouped).map(([folder, items]) => (
            <div key={folder} className="mb-4">
              <div className="flex items-center gap-1 px-2 py-1 text-xs font-semibold text-muted-foreground">
                <FolderOpen className="h-3 w-3" />
                {folder}
              </div>
              {items.map((conversation) => (
                <ConversationItem
                  key={conversation.id}
                  conversation={conversation}
                  isActive={conversation.id === activeConversationId}
                  onClick={() => onSelectConversation(conversation.id)}
                  onDelete={() => onDeleteConversation(conversation.id)}
                />
              ))}
            </div>
          ))}

          {conversations.length === 0 && (
            <div className="text-center text-muted-foreground text-sm py-8">
              No conversations yet.
              <br />
              Start a new chat!
            </div>
          )}
        </ScrollArea>

        {/* Workspace memory */}
        <CatchMeUpSection />

        {/* Footer */}
        <div className="p-3 border-t flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onOpenSettings}
            className="flex-1 justify-start gap-2 text-muted-foreground hover:text-foreground"
          >
            <Settings className="h-4 w-4" />
            Settings
          </Button>
          <AuthUserButton />
        </div>
      </aside>
    </>
  );
}

function CatchMeUpSection() {
  const [expanded, setExpanded] = useState(false);
  const { workspaces, currentId, setCurrent, isLoading } = useWorkspaces();

  return (
    <div className="border-t px-3 py-2">
      <button
        className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5" />
        )}
        <Sparkles className="h-3.5 w-3.5 text-dclaw-500" />
        Catch me up
      </button>

      {expanded && (
        <div className="mt-2 space-y-2">
          {workspaces.length > 0 && (
            <select
              value={currentId ?? ""}
              onChange={(e) => setCurrent(e.target.value || null)}
              aria-label="Workspace"
              className="w-full h-7 rounded-md border border-border bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-dclaw-500"
            >
              {workspaces.map((ws) => (
                <option key={ws.id} value={ws.id}>
                  {ws.name}
                </option>
              ))}
            </select>
          )}

          {currentId && <UpgradeButton workspaceId={currentId} />}

          {currentId ? (
            <CatchMeUp workspaceId={currentId} />
          ) : (
            <p className="px-2 text-xs text-muted-foreground leading-relaxed">
              {isLoading
                ? "Loading workspaces…"
                : "Join a workspace to build your team's memory."}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function ConversationItem({
  conversation,
  isActive,
  onClick,
  onDelete,
}: {
  conversation: Conversation;
  isActive: boolean;
  onClick: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      className={`group flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer text-sm transition-colors ${
        isActive
          ? "bg-dclaw-100 text-dclaw-900"
          : "hover:bg-accent text-foreground"
      }`}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
    >
      <MessageSquare className="h-4 w-4 shrink-0" />
      <span className="flex-1 truncate">{conversation.title}</span>
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 opacity-0 group-hover:opacity-100 shrink-0"
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
      >
        <Trash2 className="h-3 w-3" />
      </Button>
    </div>
  );
}
