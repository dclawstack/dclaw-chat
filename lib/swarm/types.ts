export interface AgentCapability {
  name: string;
  description: string;
  keywords: string[];
  examples: string[];
}

export interface AgentMessage {
  id: string;
  from: string;        // agent name or "user"
  to: string;          // agent name or "user" or "orchestrator"
  content: string;
  type: "request" | "response" | "handoff" | "tool_call" | "observation";
  timestamp: Date;
  metadata?: Record<string, unknown>;
}

export interface AgentContext {
  conversationId: string;
  userMessage: string;
  history: AgentMessage[];
  memory?: string;           // summarized context from MemoryAgent
  piiStripped?: boolean;     // whether Shield has processed this
  model?: string;            // which LLM to use
}

export interface AgentResult {
  content: string;
  confidence: number;        // 0-1 how sure the agent is this is its domain
  handoffTo?: string;        // suggest another agent take over
  toolCalls?: ToolCall[];
  metadata?: Record<string, unknown>;
}

export interface ToolCall {
  tool: string;
  params: Record<string, unknown>;
}

export interface SwarmAgent {
  id: string;
  name: string;
  description: string;
  icon: string;
  capabilities: AgentCapability[];
  model: "local" | "cloud" | "hybrid";
  priority: number;          // lower = higher priority in routing
  handler: (ctx: AgentContext) => Promise<AgentResult>;
}

export interface OrchestratorPlan {
  intent: string;
  confidence: number;
  primaryAgent: string;
  supportingAgents: string[];
  reasoning: string;
  requiresMultiTurn: boolean;
}
