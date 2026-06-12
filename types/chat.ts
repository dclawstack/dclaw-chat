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
  icon?: string;
  available?: boolean;
}

export interface ConversationSummary {
  conversationId: string;
  summary: string;
  messageCount: number;
}

export interface ExtractedAction {
  text: string;
  priority: "low" | "medium" | "high";
  assignee?: string;
  status: "open" | "done";
}

export interface Channel {
  id: string;
  name: string;
  type: "public" | "dm" | "group";
  workspace_id?: string | null;
  created_at: string;
}

export interface FileAttachment {
  type: "file" | "image" | "video";
  id: string;
  name: string;
  mime_type: string;
  size: number;
  url: string;
}

export interface LinkPreview {
  type: "link";
  url: string;
  title?: string;
  description?: string;
  image?: string;
  favicon?: string;
}

export type MessageAttachment = FileAttachment | LinkPreview;

export interface ChannelMessage {
  id: string;
  channel_id: string;
  user_id: string;
  user_name: string;
  content: string;
  thread_parent_id: string | null;
  reply_count: number;
  topic?: string | null;
  attachments?: MessageAttachment[] | null;
  created_at: string;
}

export interface ChannelTopic {
  topic: string;
  count: number;
}

export interface CopilotMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  ragChunksUsed?: number;
  citations?: import("@/lib/api").GraphCitation[];
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

export interface CommandParam {
  name: string;
  description: string;
  required: boolean;
}

export interface BotCommand {
  name: string;
  description: string;
  usage: string;
  params: CommandParam[];
}

export interface Bot {
  id: string;
  name: string;
  slug: string;
  description: string;
  avatar_emoji: string | null;
  webhook_url: string | null;
  commands: BotCommand[];
  category: string;
  installed: boolean;
  enabled: boolean;
  created_at: string;
}

// Fallback models used when backend is unreachable
export const MODELS: AIModel[] = [
  {
    id: "gemma-4b",
    name: "Gemma 4B",
    provider: "local",
    description: "Fast local inference via Ollama",
    icon: "🖥️",
  },
  {
    id: "qwen-32b",
    name: "Qwen 3.5 35B",
    provider: "local",
    description: "Best local model (M4 96GB)",
    icon: "🖥️",
  },
  {
    id: "nemotron-cascade-2",
    name: "Nemotron Cascade 2",
    provider: "local",
    description: "NVIDIA Nemotron local inference",
    icon: "🖥️",
  },
  {
    id: "glm-4.7-flash",
    name: "GLM 4.7 Flash",
    provider: "local",
    description: "Zhipu GLM local inference",
    icon: "🖥️",
  },
  {
    id: "kimi-k2.5",
    name: "Kimi K2.5",
    provider: "cloud",
    description: "OpenRouter cloud fallback",
    icon: "☁️",
  },
  {
    id: "claude-3.5-sonnet",
    name: "Claude 3.5 Sonnet",
    provider: "cloud",
    description: "Anthropic Claude via OpenRouter",
    icon: "☁️",
  },
  {
    id: "claude-3-opus",
    name: "Claude 3 Opus",
    provider: "cloud",
    description: "Anthropic Claude Max via OpenRouter",
    icon: "☁️",
  },
  {
    id: "gpt-4o",
    name: "GPT-4o",
    provider: "cloud",
    description: "OpenAI GPT-4o via OpenRouter",
    icon: "☁️",
  },
  {
    id: "deepseek-v4",
    name: "DeepSeek V4",
    provider: "cloud",
    description: "DeepSeek V4 Pro via NVIDIA NIMs (free tier)",
    icon: "☁️",
  },
];
