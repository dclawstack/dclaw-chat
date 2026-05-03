import { SwarmAgent, AgentContext, AgentResult } from "../types";

export const researchAgent: SwarmAgent = {
  id: "research-agent",
  name: "Research Assistant",
  description: "Searches knowledge bases and explains complex topics",
  icon: "🔬",
  model: "cloud",
  priority: 2,
  capabilities: [
    {
      name: "knowledge-lookup",
      description: "Explain concepts and find facts",
      keywords: ["what is", "how to", "explain", "difference"],
      examples: ["What is Kubernetes?", "Explain quantum computing"],
    },
    {
      name: "comparison",
      description: "Compare technologies, approaches, or products",
      keywords: ["compare", "vs", "versus", "difference", "pros and cons"],
      examples: ["React vs Vue", "AWS vs GCP"],
    },
    {
      name: "documentation",
      description: "Find and summarize documentation",
      keywords: ["docs", "documentation", "api", "reference"],
      examples: ["FastAPI docs for WebSocket", "Kubernetes RBAC reference"],
    },
  ],
  handler: async (ctx: AgentContext): Promise<AgentResult> => {
    return {
      content: `[Research Assistant activated]\n\nQuerying knowledge sources...\n\nIn production, this would:\n• Search internal knowledge graph (Obsidian vault)\n• Query web via OpenRouter (Kimi K2.5)\n• Retrieve from DClaw's shared document corpus\n• Cite sources with confidence scores`,
      confidence: 0.85,
    };
  },
};
