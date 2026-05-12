const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface ApiMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatCompletionRequest {
  conversation_id: string;
  messages: ApiMessage[];
  model: string;
  temperature?: number;
}

export interface ChatCompletionResponse {
  id: string;
  message: ApiMessage;
  model: string;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
  };
}

export async function chatComplete(
  req: ChatCompletionRequest
): Promise<ChatCompletionResponse> {
  const res = await fetch(`${API_BASE}/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

export interface ChatStreamCallbacks {
  onToken: (token: string) => void;
  onDone: () => void;
  onError: (err: Error) => void;
}

export async function chatStream(
  req: ChatCompletionRequest,
  callbacks: ChatStreamCallbacks
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    callbacks.onError(new Error(err.detail || `HTTP ${res.status}`));
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    callbacks.onError(new Error("No response body"));
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6).trim();
        if (data === "[DONE]") {
          callbacks.onDone();
          return;
        }
        try {
          const parsed = JSON.parse(data);
          if (parsed.error) {
            callbacks.onError(new Error(parsed.error));
            return;
          }
          if (parsed.delta) callbacks.onToken(parsed.delta);
        } catch {
          // ignore malformed SSE lines
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
  callbacks.onDone();
}

export interface ModelInfo {
  id: string;
  name: string;
  provider: "local" | "cloud";
  description: string;
  available: boolean;
}

export async function listModels(): Promise<ModelInfo[]> {
  const res = await fetch(`${API_BASE}/models`);
  if (!res.ok) {
    throw new Error(`Failed to fetch models: ${res.statusText}`);
  }
  return res.json();
}

export interface CopilotChatRequest {
  query: string;
  conversation_id?: string;
  model?: string;
  include_context?: boolean;
}

export interface CopilotChatResponse {
  answer: string;
  model: string;
  rag_chunks_used: number;
  context_snippets: string[];
}

export interface SummarizeResponse {
  conversation_id: string;
  summary: string;
  message_count: number;
}

export interface ActionsResponse {
  conversation_id: string;
  actions: Array<{
    text: string;
    priority: "low" | "medium" | "high";
    assignee?: string;
    status: "open" | "done";
  }>;
}

export async function copilotChat(req: CopilotChatRequest): Promise<CopilotChatResponse> {
  const res = await fetch(`${API_BASE}/ai/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function summarizeConversation(
  conversationId: string,
  messages: ApiMessage[],
  model?: string
): Promise<SummarizeResponse> {
  const res = await fetch(`${API_BASE}/ai/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId, messages, model }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function extractActions(
  conversationId: string,
  messages: ApiMessage[],
  model?: string
): Promise<ActionsResponse> {
  const res = await fetch(`${API_BASE}/ai/actions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId, messages, model }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Meeting Summaries ─────────────────────────────────────────────────────────

export interface MeetingActionItem {
  text: string;
  priority: "low" | "medium" | "high";
  assignee?: string;
  status: "open" | "done";
}

export interface Meeting {
  id: string;
  title: string;
  file_id?: string;
  filename?: string;
  mime_type?: string;
  duration_seconds?: number;
  status: "pending" | "transcribing" | "summarizing" | "done" | "failed";
  transcript?: string;
  summary?: string;
  action_items?: MeetingActionItem[];
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export async function createMeeting(title: string): Promise<Meeting> {
  const res = await fetch(`${API_BASE}/meetings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function uploadMeeting(file: File, title?: string): Promise<Meeting> {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);
  const res = await fetch(`${API_BASE}/meetings/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function processMeeting(meetingId: string, model?: string): Promise<Meeting> {
  const res = await fetch(`${API_BASE}/meetings/${meetingId}/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: model ?? "gemma-4b" }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function listMeetings(): Promise<Meeting[]> {
  const res = await fetch(`${API_BASE}/meetings`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getMeeting(meetingId: string): Promise<Meeting> {
  const res = await fetch(`${API_BASE}/meetings/${meetingId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function deleteMeeting(meetingId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/meetings/${meetingId}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
}
