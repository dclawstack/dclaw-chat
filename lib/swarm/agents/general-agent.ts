import { SwarmAgent, AgentContext, AgentResult } from "../types";

export const generalAgent: SwarmAgent = {
  id: "general-agent",
  name: "General Assistant",
  description: "General-purpose chat and fallback handler",
  icon: "🤖",
  model: "hybrid",
  priority: 10,
  capabilities: [
    {
      name: "general-chat",
      description: "Casual conversation and general questions",
      keywords: ["hello", "hi", "help", "thanks"],
      examples: ["Hello!", "How are you?", "What can you do?"],
    },
  ],
  handler: async (ctx: AgentContext): Promise<AgentResult> => {
    return {
      content: "I'm here to help. I can write code, research topics, manage your conversation memory, and protect your privacy with ClawShield. What would you like to work on?",
      confidence: 0.5,
    };
  },
};
