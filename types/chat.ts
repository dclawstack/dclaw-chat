export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  model?: string;
  status?: "sending" | "sent" | "error";
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
  folder?: string;
}

export interface AIModel {
  id: string;
  name: string;
  provider: "local" | "cloud";
  description: string;
  icon: string;
}

export interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  isLoading: boolean;
  error: string | null;
  selectedModel: string;
  isSidebarOpen: boolean;
  isVoiceMode: boolean;
}

export const MODELS: AIModel[] = [
  {
    id: "gemma-4b",
    name: "Gemma 4B",
    provider: "local",
    description: "Fast local inference via Ollama",
    icon: "🖥️",
  },
  {
    id: "gemma-27b",
    name: "Gemma 27B",
    provider: "local",
    description: "High-quality local inference",
    icon: "🖥️",
  },
  {
    id: "qwen-32b",
    name: "Qwen 32B",
    provider: "local",
    description: "Best local model (M4 96GB)",
    icon: "🖥️",
  },
  {
    id: "kimi-k2.5",
    name: "Kimi K2.5",
    provider: "cloud",
    description: "OpenRouter cloud fallback",
    icon: "☁️",
  },
];
