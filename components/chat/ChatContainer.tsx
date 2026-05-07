"use client";

import { useState, useCallback, useEffect } from "react";
import { Message, Conversation, AIModel, MODELS } from "@/types/chat";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { Sidebar } from "./Sidebar";
import { ModelSelector } from "./ModelSelector";
import { SwarmStatus } from "@/components/swarm/SwarmStatus";
import { chatComplete, listModels } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Menu, Shield } from "lucide-react";

// Demo data
const demoConversations: Conversation[] = [
  {
    id: "1",
    title: "Python script for data processing",
    messages: [
      {
        id: "m1",
        role: "user",
        content: "Write a Python script to process CSV files and output summary statistics.",
        timestamp: new Date(Date.now() - 3600000),
      },
      {
        id: "m2",
        role: "assistant",
        content: "Here's a Python script using pandas:\n\n```python\nimport pandas as pd\nimport sys\n\ndef process_csv(filepath):\n    df = pd.read_csv(filepath)\n    summary = df.describe()\n    print(summary)\n    return summary\n\nif __name__ == '__main__':\n    process_csv(sys.argv[1])\n```",
        timestamp: new Date(Date.now() - 3500000),
        model: "Gemma 4B",
      },
    ],
    createdAt: new Date(Date.now() - 3600000),
    updatedAt: new Date(Date.now() - 3500000),
    folder: "Development",
  },
  {
    id: "2",
    title: "Kubernetes best practices",
    messages: [
      {
        id: "m3",
        role: "user",
        content: "What are Kubernetes best practices for production?",
        timestamp: new Date(Date.now() - 86400000),
      },
      {
        id: "m4",
        role: "assistant",
        content: "Key Kubernetes best practices:\n\n1. Use resource limits and requests\n2. Implement health checks (liveness/readiness probes)\n3. Use namespaces for isolation\n4. Enable RBAC\n5. Use ConfigMaps and Secrets\n6. Implement network policies\n7. Use Helm for package management",
        timestamp: new Date(Date.now() - 86300000),
        model: "Kimi K2.5",
      },
    ],
    createdAt: new Date(Date.now() - 86400000),
    updatedAt: new Date(Date.now() - 86300000),
    folder: "DevOps",
  },
];

export function ChatContainer() {
  const [conversations, setConversations] = useState<Conversation[]>(demoConversations);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState("gemma-4b");
  const [availableModels, setAvailableModels] = useState<AIModel[]>(MODELS);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [activeAgents, setActiveAgents] = useState<string[]>([]);
  const [currentPlan, setCurrentPlan] = useState<{
    intent: string;
    primaryAgent: string;
    supportingAgents: string[];
    reasoning: string;
  } | undefined>();

  const activeConversation = conversations.find(
    (c) => c.id === activeConversationId
  );

  // Fetch available models from backend on mount
  useEffect(() => {
    listModels()
      .then((models) => {
        setAvailableModels(models);
        // If current selection isn't available, pick first available
        const currentAvailable = models.find((m) => m.id === selectedModel)?.available;
        if (!currentAvailable) {
          const firstAvailable = models.find((m) => m.available);
          if (firstAvailable) setSelectedModel(firstAvailable.id);
        }
      })
      .catch(() => {
        // Fallback to hardcoded models if backend unreachable
      });
  }, []);

  const handleNewConversation = useCallback(() => {
    const newConversation: Conversation = {
      id: Date.now().toString(),
      title: "New Conversation",
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    setConversations((prev) => [newConversation, ...prev]);
    setActiveConversationId(newConversation.id);
    setIsSidebarOpen(false);
    setCurrentPlan(undefined);
    setActiveAgents([]);
  }, []);

  const handleSelectConversation = useCallback((id: string) => {
    setActiveConversationId(id);
    setIsSidebarOpen(false);
    setCurrentPlan(undefined);
    setActiveAgents([]);
  }, []);

  const handleDeleteConversation = useCallback((id: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeConversationId === id) {
      setActiveConversationId(null);
      setCurrentPlan(undefined);
      setActiveAgents([]);
    }
  }, [activeConversationId]);

  const handleSendMessage = useCallback(
    async (content: string) => {
      if (!activeConversationId) {
        handleNewConversation();
        return;
      }

      const userMessage: Message = {
        id: Date.now().toString(),
        role: "user",
        content,
        timestamp: new Date(),
      };

      setConversations((prev) =>
        prev.map((c) =>
          c.id === activeConversationId
            ? { ...c, messages: [...c.messages, userMessage], updatedAt: new Date() }
            : c
        )
      );

      setIsLoading(true);
      setError(null);

      try {
        const conversation = conversations.find((c) => c.id === activeConversationId);

        // Build messages for backend API
        const apiMessages = conversation?.messages.map((m) => ({
          role: m.role,
          content: m.content,
        })) || [];
        apiMessages.push({ role: "user" as const, content });

        // Generate swarm plan for UI visualization
        const lower = content.toLowerCase();
        let intent = "general";
        if (/\b(write|code|function|script|debug|python|javascript|rust|go|typescript|sql)\b/i.test(lower)) intent = "code";
        else if (/\b(search|find|what is|who is|how to|explain|compare|difference)\b/i.test(lower)) intent = "research";
        else if (/\b(remember|recall|previous|last time|summary|summarize)\b/i.test(lower)) intent = "memory";
        else if (/\b(anonymize|pii|privacy|gdpr|hipaa)\b/i.test(lower)) intent = "shield";

        const agentNames: Record<string, string> = {
          code: "Code Assistant",
          research: "Research Assistant",
          memory: "Memory Assistant",
          shield: "ClawShield",
          general: "General Assistant",
        };

        setCurrentPlan({
          intent,
          primaryAgent: agentNames[intent],
          supportingAgents: intent !== "shield" ? ["ClawShield"] : [],
          reasoning: `Detected ${intent} intent from message`,
        });
        setActiveAgents([agentNames[intent], "ClawShield"]);

        // Call backend API for real LLM response
        const result = await chatComplete({
          conversation_id: activeConversationId,
          messages: apiMessages,
          model: selectedModel,
          temperature: 0.7,
        });

        const model = availableModels.find((m) => m.id === selectedModel);

        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: result.message.content,
          timestamp: new Date(),
          model: model?.name,
        };

        setConversations((prev) =>
          prev.map((c) =>
            c.id === activeConversationId
              ? {
                  ...c,
                  messages: [...c.messages, assistantMessage],
                  updatedAt: new Date(),
                  title:
                    c.messages.length === 0
                      ? content.substring(0, 40) + "..."
                      : c.title,
                }
              : c
          )
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred");
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: "Sorry, I encountered an error processing your request.",
          timestamp: new Date(),
          status: "error",
        };
        setConversations((prev) =>
          prev.map((c) =>
            c.id === activeConversationId
              ? { ...c, messages: [...c.messages, errorMessage] }
              : c
          )
        );
      } finally {
        setIsLoading(false);
      }
    },
    [activeConversationId, selectedModel, handleNewConversation, conversations]
  );

  return (
    <div className="flex h-screen bg-background">
      <Sidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="h-14 border-b flex items-center justify-between px-4 shrink-0">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setIsSidebarOpen(true)}
            >
              <Menu className="h-5 w-5" />
            </Button>

            {activeConversation ? (
              <div>
                <h2 className="text-sm font-semibold truncate max-w-[200px] sm:max-w-md">
                  {activeConversation.title}
                </h2>
                <p className="text-xs text-muted-foreground">
                  {activeConversation.messages.length} messages
                </p>
              </div>
            ) : (
              <span className="text-sm text-muted-foreground">
                Select a conversation or start a new chat
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <div className="hidden sm:flex items-center gap-1 text-xs text-muted-foreground bg-muted px-2 py-1 rounded-full">
              <Shield className="h-3 w-3 text-dclaw-500" />
              PII Shield active
            </div>
            <ModelSelector
              selectedModel={selectedModel}
              onSelect={setSelectedModel}
              models={availableModels}
            />
          </div>
        </header>

        {/* Error Banner */}
        {error && (
          <div className="bg-destructive/10 text-destructive text-sm px-4 py-2 text-center">
            {error}
            <button
              className="ml-2 underline"
              onClick={() => setError(null)}
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Messages */}
        <MessageList
          messages={activeConversation?.messages || []}
          isLoading={isLoading}
        />

        {/* Swarm Status */}
        <SwarmStatus activeAgents={activeAgents} currentPlan={currentPlan} />

        {/* Input */}
        <ChatInput
          onSend={handleSendMessage}
          isLoading={isLoading}
          disabled={!activeConversationId}
        />
      </div>
    </div>
  );
}
