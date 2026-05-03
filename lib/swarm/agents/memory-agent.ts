import { SwarmAgent, AgentContext, AgentResult } from "../types";

export const memoryAgent: SwarmAgent = {
  id: "memory-agent",
  name: "Memory Assistant",
  description: "Summarizes and retrieves conversation context",
  icon: "🧠",
  model: "local",
  priority: 3,
  capabilities: [
    {
      name: "context-retrieval",
      description: "Recall previous conversation points",
      keywords: ["remember", "recall", "previous", "earlier", "last time"],
      examples: ["What did I ask earlier?", "Summarize our conversation"],
    },
    {
      name: "conversation-summary",
      description: "Generate summaries of long conversations",
      keywords: ["summarize", "summary", "tl;dr", "key points"],
      examples: ["TL;DR this conversation", "What are the action items?"],
    },
  ],
  handler: async (ctx: AgentContext): Promise<AgentResult> => {
    const recentMessages = ctx.history.slice(-10);
    const summary = recentMessages.length > 0
      ? `Recent context: ${recentMessages.length} messages in this thread.`
      : "No previous context for this conversation.";

    return {
      content: `[Memory Assistant]\n\n${summary}\n\nIn production, this would:\n• Vector-search conversation embeddings\n• Retrieve relevant past sessions\n• Maintain user preference profiles\n• Generate rolling summaries for long contexts`,
      confidence: 0.8,
      metadata: {
        memory: summary,
        messageCount: recentMessages.length,
      },
    };
  },
};
