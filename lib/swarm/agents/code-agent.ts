import { SwarmAgent, AgentContext, AgentResult } from "../types";

export const codeAgent: SwarmAgent = {
  id: "code-agent",
  name: "Code Assistant",
  description: "Writes, debugs, and explains code in any language",
  icon: "💻",
  model: "hybrid",
  priority: 1,
  capabilities: [
    {
      name: "code-generation",
      description: "Generate code from natural language descriptions",
      keywords: ["write", "code", "function", "script", "implement"],
      examples: ["Write a Python function to parse JSON", "Create a React component"],
    },
    {
      name: "debugging",
      description: "Find and fix bugs in code",
      keywords: ["debug", "error", "fix", "bug", "not working"],
      examples: ["Why is this throwing null pointer?", "Fix this TypeScript error"],
    },
    {
      name: "refactoring",
      description: "Improve code quality and structure",
      keywords: ["refactor", "clean", "optimize", "improve"],
      examples: ["Refactor this into smaller functions", "Make this more efficient"],
    },
  ],
  handler: async (ctx: AgentContext): Promise<AgentResult> => {
    // In production, this would call the LLM with a system prompt
    // For now, return a structured placeholder
    const lang = detectLanguage(ctx.userMessage);
    return {
      content: `[Code Assistant activated — ${lang || "auto-detected"} mode]\n\nAnalyzing your request...\n\nIn production, this routes to:\n• Local LLM (Gemma/Qwen) for fast autocomplete\n• Cloud fallback (Kimi) for complex architecture\n• PII Shield pre-processing for sensitive codebases`,
      confidence: 0.9,
      metadata: { detectedLanguage: lang },
    };
  },
};

function detectLanguage(message: string): string | null {
  const patterns: Record<string, RegExp> = {
    python: /\b(python|pandas|numpy|django|flask|py)\b/i,
    typescript: /\b(typescript|ts|react|next\.js|angular)\b/i,
    javascript: /\b(javascript|js|node|express)\b/i,
    rust: /\b(rust|cargo|crates)\b/i,
    go: /\b(golang|go\s+module)\b/i,
    sql: /\b(sql|postgres|mysql|query|database)\b/i,
  };
  for (const [lang, regex] of Object.entries(patterns)) {
    if (regex.test(message)) return lang;
  }
  return null;
}
