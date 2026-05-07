import { AgentContext, AgentResult, OrchestratorPlan, SwarmAgent } from "./types";
import { swarmRegistry } from "./registry";

const INTENT_PATTERNS: Record<string, string[]> = {
  code: [
    "write", "code", "function", "script", "program", "debug", "error",
    "python", "javascript", "rust", "go", "typescript", "sql", "regex",
    "implement", "refactor", "class", "api", "endpoint", "build",
  ],
  research: [
    "search", "find", "look up", "what is", "who is", "how to", "explain",
    "documentation", "docs", "wikipedia", "article", "paper", "study",
    "compare", "difference between", "pros and cons",
  ],
  memory: [
    "remember", "recall", "previous", "last time", "we discussed", "earlier",
    "summary", "summarize", "what did i say", "conversation history",
  ],
  shield: [
    "anonymize", "pii", "redact", "privacy", "sensitive", "personal data",
    "gdpr", "hipaa", "compliance", "audit",
  ],
  creative: [
    "write", "story", "poem", "email", "letter", "draft", "copy",
    "blog", "social media", "tweet", "linkedin", "marketing",
  ],
  data: [
    "csv", "json", "xml", "analyze", "chart", "graph", "statistics",
    "dataset", "pandas", "dataframe", "visualization", "plot",
  ],
};

export class SwarmOrchestrator {
  private registry = swarmRegistry;
  private conversationState = new Map<string, OrchestratorPlan>();

  async classifyIntent(message: string): Promise<OrchestratorPlan> {
    const lower = message.toLowerCase();
    const scores: Record<string, number> = {};

    // Score each intent by keyword matches
    for (const [intent, keywords] of Object.entries(INTENT_PATTERNS)) {
      scores[intent] = keywords.reduce((sum, kw) => {
        return lower.includes(kw) ? sum + 1 : sum;
      }, 0);
    }

    // Boost memory intent if conversation references exist
    if (/\b(previous|earlier|last time|you said|we talked)\b/i.test(message)) {
      scores.memory = (scores.memory || 0) + 3;
    }

    // Find best match
    const entries = Object.entries(scores);
    const best = entries.reduce(
      (max, curr) => (curr[1] > max[1] ? curr : max),
      ["general", 0] as [string, number]
    );

    const intent = best[1] > 0 ? best[0] : "general";
    const confidence = Math.min(best[1] / 3, 1);

    // Map intent to primary agent
    const agentMap: Record<string, string> = {
      code: "code-agent",
      research: "research-agent",
      memory: "memory-agent",
      shield: "shield-agent",
      creative: "creative-agent",
      data: "data-agent",
      general: "general-agent",
    };

    const primaryId = agentMap[intent] || "general-agent";
    const primary = this.registry.get(primaryId);

    // Determine supporting agents
    const supporting: string[] = [];
    if (intent !== "shield" && /\b(email|name|phone|address|ssn|credit card)\b/i.test(message)) {
      supporting.push("shield-agent");
    }
    if (intent !== "memory" && scores.memory && scores.memory > 1) {
      supporting.push("memory-agent");
    }

    return {
      intent,
      confidence,
      primaryAgent: primary?.name || "General Assistant",
      supportingAgents: supporting.map((id) => this.registry.get(id)?.name || id),
      reasoning: `Detected ${intent} intent (${best[1]} keyword matches)`,
      requiresMultiTurn: /\b(step|then|next|after|first|finally)\b/i.test(message),
    };
  }

  async execute(ctx: AgentContext): Promise<AgentResult> {
    const plan = await this.classifyIntent(ctx.userMessage);
    this.conversationState.set(ctx.conversationId, plan);

    const primary = this.registry.findByName(plan.primaryAgent);
    if (!primary) {
      return {
        content: "I'm not sure how to handle that. Could you rephrase?",
        confidence: 0,
      };
    }

    // Run supporting agents first (e.g., shield, memory)
    let enrichedCtx = { ...ctx };
    for (const supporterName of plan.supportingAgents) {
      const supporter = this.registry.findByName(supporterName);
      if (supporter && supporter.id !== primary.id) {
        const result = await supporter.handler(enrichedCtx);
        if (result.metadata) {
          enrichedCtx = { ...enrichedCtx, ...result.metadata };
        }
      }
    }

    // Run primary agent
    const result = await primary.handler(enrichedCtx);

    return {
      ...result,
      metadata: {
        ...result.metadata,
        orchestratorPlan: plan,
      },
    };
  }

  getState(conversationId: string): OrchestratorPlan | undefined {
    return this.conversationState.get(conversationId);
  }

  clearState(conversationId: string): void {
    this.conversationState.delete(conversationId);
  }
}

export const swarmOrchestrator = new SwarmOrchestrator();
