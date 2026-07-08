import { authHeaders, wsAuthQuery } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/** fetch wrapper that injects the Authorization header when a token is set. */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  return fetch(input, { ...init, headers: { ...authHeaders(), ...(init.headers || {}) } });
}

export interface ApiMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatCompletionRequest {
  conversation_id: string;
  messages: ApiMessage[];
  model: string;
  temperature?: number;
  /** Workspace context — the workspace's AI model policy applies (#30). */
  workspace_id?: string | null;
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
  const res = await apiFetch(`${API_BASE}/chat/completions`, {
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
  const res = await apiFetch(`${API_BASE}/chat/stream`, {
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

export async function listModels(workspaceId?: string | null): Promise<ModelInfo[]> {
  const qs = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
  const res = await apiFetch(`${API_BASE}/models${qs}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch models: ${res.statusText}`);
  }
  return res.json();
}

export interface CopilotChatRequest {
  query: string;
  conversation_id?: string;
  workspace_id?: string;
  model?: string;
  include_context?: boolean;
}

/** Knowledge-graph citation: an entity + a pointer back to its source. */
export interface GraphCitation {
  name: string;
  kind: string;
  summary?: string | null;
  source_type?: string | null;
  source_id?: string | null;
  updated_at?: string | null;
}

export interface CopilotChatResponse {
  answer: string;
  model: string;
  rag_chunks_used: number;
  context_snippets: string[];
  citations?: GraphCitation[];
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
  const res = await apiFetch(`${API_BASE}/ai/chat`, {
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
  const res = await apiFetch(`${API_BASE}/ai/summarize`, {
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
  const res = await apiFetch(`${API_BASE}/ai/actions`, {
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
  const res = await apiFetch(`${API_BASE}/meetings`, {
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
  const res = await apiFetch(`${API_BASE}/meetings/upload`, {
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
  const res = await apiFetch(`${API_BASE}/meetings/${meetingId}/process`, {
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
  const res = await apiFetch(`${API_BASE}/meetings`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getMeeting(meetingId: string): Promise<Meeting> {
  const res = await apiFetch(`${API_BASE}/meetings/${meetingId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function deleteMeeting(meetingId: string): Promise<void> {
  const res = await apiFetch(`${API_BASE}/meetings/${meetingId}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
}

// ── Voice & Video Calls ────────────────────────────────────────────────────────

export interface CallRoom {
  id: string;
  title: string;
  host_id?: string;
  channel_id?: string;
  status: "waiting" | "active" | "ended";
  max_participants: number;
  recording_enabled: boolean;
  created_at: string;
  ended_at?: string;
}

export interface CallRoomCreate {
  title?: string;
  channel_id?: string;
  max_participants?: number;
  recording_enabled?: boolean;
}

export async function createCallRoom(req: CallRoomCreate = {}): Promise<CallRoom> {
  const res = await apiFetch(`${API_BASE}/calls`, {
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

export async function listCallRooms(channelId?: string): Promise<CallRoom[]> {
  const url = new URL(`${API_BASE}/calls`);
  if (channelId) url.searchParams.set("channel_id", channelId);
  const res = await apiFetch(url.toString());
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getCallRoom(roomId: string): Promise<CallRoom> {
  const res = await apiFetch(`${API_BASE}/calls/${roomId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function endCallRoom(roomId: string): Promise<CallRoom> {
  const res = await apiFetch(`${API_BASE}/calls/${roomId}/end`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function deleteCallRoom(roomId: string): Promise<void> {
  const res = await apiFetch(`${API_BASE}/calls/${roomId}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
}

export function buildSignalingUrl(roomId: string, _userId: string): string {
  const wsBase = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1")
    .replace(/^http/, "ws");
  // Identity comes from the verified token; the backend ignores user_id params.
  const q = wsAuthQuery();
  return `${wsBase}/calls/${roomId}/ws${q ? `?${q}` : ""}`;
}

// ── Huddles ───────────────────────────────────────────────────────────────────

export interface HuddleParticipant {
  id: string;
  room_id: string;
  user_id: string;
  display_name: string;
  is_speaking: boolean;
  is_muted: boolean;
  joined_at: string;
  last_seen_at: string;
}

export interface HuddleRoom {
  id: string;
  name: string;
  created_by?: string;
  status: "active" | "closed";
  created_at: string;
  closed_at?: string;
  participants: HuddleParticipant[];
}

export async function createHuddle(name: string = "Huddle"): Promise<HuddleRoom> {
  const res = await apiFetch(`${API_BASE}/huddles`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function listHuddles(): Promise<HuddleRoom[]> {
  const res = await apiFetch(`${API_BASE}/huddles`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getHuddle(roomId: string): Promise<HuddleRoom> {
  const res = await apiFetch(`${API_BASE}/huddles/${roomId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function joinHuddle(
  roomId: string,
  displayName: string = "Anonymous"
): Promise<HuddleParticipant> {
  const res = await apiFetch(`${API_BASE}/huddles/${roomId}/join`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_name: displayName }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function leaveHuddle(roomId: string): Promise<void> {
  const res = await apiFetch(`${API_BASE}/huddles/${roomId}/leave`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
}

export async function updateHuddleSpeaking(
  roomId: string,
  isSpeaking: boolean,
  isMuted?: boolean
): Promise<HuddleParticipant> {
  const res = await apiFetch(`${API_BASE}/huddles/${roomId}/speaking`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_speaking: isSpeaking, is_muted: isMuted }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function closeHuddle(roomId: string): Promise<HuddleRoom> {
  const res = await apiFetch(`${API_BASE}/huddles/${roomId}/close`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function deleteHuddle(roomId: string): Promise<void> {
  const res = await apiFetch(`${API_BASE}/huddles/${roomId}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
}

export function buildHuddleWsUrl(roomId: string, _userId: string): string {
  const wsBase = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1")
    .replace(/^http/, "ws");
  // Identity comes from the verified token; the backend ignores user_id params.
  const q = wsAuthQuery();
  return `${wsBase}/huddles/${roomId}/ws${q ? `?${q}` : ""}`;
}

// ── Workspaces ────────────────────────────────────────────────────────────────

export interface Workspace {
  id: string;
  name: string;
  created_by: string;
  created_at: string;
  member_count: number;
  /** Caller's role in this workspace: Owner | Admin | Member | Guest */
  my_role?: string | null;
}

export async function listWorkspaces(): Promise<Workspace[]> {
  const res = await apiFetch(`${API_BASE}/workspaces`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function createWorkspace(name: string): Promise<Workspace> {
  const res = await apiFetch(`${API_BASE}/workspaces`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export interface WorkspaceInvite {
  token: string;
  workspace_id: string;
  email: string;
}

export async function createWorkspaceInvite(
  workspaceId: string,
  email: string
): Promise<WorkspaceInvite> {
  const res = await apiFetch(`${API_BASE}/workspaces/${workspaceId}/invites`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function acceptWorkspaceInvite(
  token: string
): Promise<{ workspace_id: string; role: string }> {
  const res = await apiFetch(`${API_BASE}/workspaces/invites/${token}/accept`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function exportWorkspaceMessages(workspaceId: string): Promise<unknown> {
  const res = await apiFetch(`${API_BASE}/workspaces/${workspaceId}/export`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export interface ModelPolicy {
  allowed_models: string[] | null;
  local_only: boolean;
}

export async function getModelPolicy(workspaceId: string): Promise<ModelPolicy> {
  const res = await apiFetch(`${API_BASE}/workspaces/${workspaceId}/settings/models`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function setModelPolicy(
  workspaceId: string,
  policy: ModelPolicy
): Promise<ModelPolicy> {
  const res = await apiFetch(`${API_BASE}/workspaces/${workspaceId}/settings/models`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(policy),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export interface AuditEvent {
  id: string;
  workspace_id: string | null;
  actor_id: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  detail: string | null;
  created_at: string;
}

export async function listAuditEvents(
  workspaceId: string,
  opts: { action?: string; limit?: number; offset?: number } = {}
): Promise<AuditEvent[]> {
  const params = new URLSearchParams();
  if (opts.action) params.set("action", opts.action);
  if (opts.limit) params.set("limit", String(opts.limit));
  if (opts.offset) params.set("offset", String(opts.offset));
  const qs = params.toString();
  const res = await apiFetch(
    `${API_BASE}/workspaces/${workspaceId}/audit${qs ? `?${qs}` : ""}`
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Workspace Knowledge Graph ─────────────────────────────────────────────────

export interface GraphEntity {
  id: string;
  workspace_id?: string | null;
  kind: string;
  name: string;
  summary?: string | null;
  source_type?: string | null;
  source_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface GraphEdge {
  id: string;
  workspace_id?: string | null;
  src_id: string;
  dst_id: string;
  relation: string;
  weight: number;
  source_id?: string | null;
  created_at: string;
}

export interface GraphNeighbors {
  entity: GraphEntity;
  entities: GraphEntity[];
  edges: GraphEdge[];
}

export interface CatchMeUpResult {
  workspace_id: string;
  since?: string | null;
  entities: GraphCitation[];
  decisions: GraphCitation[];
  action_items: GraphCitation[];
  edges: GraphEdge[];
}

export async function searchGraphEntities(
  workspaceId: string,
  q?: string,
  kind?: string
): Promise<GraphEntity[]> {
  const url = new URL(`${API_BASE}/graph/workspaces/${workspaceId}/entities`);
  if (q) url.searchParams.set("q", q);
  if (kind) url.searchParams.set("kind", kind);
  const res = await apiFetch(url.toString());
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getEntityNeighbors(
  workspaceId: string,
  entityId: string
): Promise<GraphNeighbors> {
  const res = await apiFetch(
    `${API_BASE}/graph/workspaces/${workspaceId}/entities/${entityId}/neighbors`
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getCatchMeUp(
  workspaceId: string,
  since?: string
): Promise<CatchMeUpResult> {
  const url = new URL(`${API_BASE}/graph/workspaces/${workspaceId}/catch-me-up`);
  if (since) url.searchParams.set("since", since);
  const res = await apiFetch(url.toString());
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Billing (Stripe per-seat subscriptions — Phase 5)
// ---------------------------------------------------------------------------

export interface WorkspaceBilling {
  workspace_id: string;
  plan: "free" | "pro";
  status: "inactive" | "active" | "past_due" | "canceled";
  seats: number;
}

export async function getBilling(workspaceId: string): Promise<WorkspaceBilling> {
  const res = await apiFetch(`${API_BASE}/billing/workspaces/${workspaceId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Start a Stripe Checkout for the Pro plan. Returns `null` when the backend
 * has no Stripe keys configured (HTTP 503) so callers can hide billing UI.
 */
export async function startCheckout(
  workspaceId: string,
  returnUrl: string
): Promise<{ checkout_url: string } | null> {
  const res = await apiFetch(`${API_BASE}/billing/workspaces/${workspaceId}/checkout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ return_url: returnUrl }),
  });
  if (res.status === 503) return null; // billing not configured
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
