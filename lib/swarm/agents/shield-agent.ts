import { SwarmAgent, AgentContext, AgentResult } from "../types";

// Simple PII patterns for demonstration
const PII_PATTERNS: Record<string, RegExp> = {
  email: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g,
  phone: /\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g,
  ssn: /\b\d{3}-\d{2}-\d{4}\b/g,
  creditCard: /\b(?:\d{4}[-\s]?){3}\d{4}\b/g,
  apiKey: /\b(sk-[a-zA-Z0-9]{20,})\b/g,
  ipAddress: /\b(?:\d{1,3}\.){3}\d{1,3}\b/g,
};

export const shieldAgent: SwarmAgent = {
  id: "shield-agent",
  name: "ClawShield",
  description: "Anonymizes PII before cloud inference",
  icon: "🛡️",
  model: "local", // Always local — never send PII to cloud
  priority: 0,    // Highest priority — runs before other agents
  capabilities: [
    {
      name: "pii-detection",
      description: "Detect personally identifiable information",
      keywords: ["pii", "anonymize", "privacy", "redact", "sensitive"],
      examples: ["Redact emails from this text", "Is there PII here?"],
    },
    {
      name: "compliance-check",
      description: "Check content against compliance policies",
      keywords: ["gdpr", "hipaa", "compliance", "audit"],
      examples: ["Is this HIPAA compliant?", "GDPR check"],
    },
  ],
  handler: async (ctx: AgentContext): Promise<AgentResult> => {
    let text = ctx.userMessage;
    const redactions: string[] = [];
    let piiFound = false;

    for (const [type, pattern] of Object.entries(PII_PATTERNS)) {
      text = text.replace(pattern, (match) => {
        piiFound = true;
        redactions.push(`${type}: ${match.substring(0, 3)}***`);
        return `[${type.toUpperCase()}_REDACTED]`;
      });
    }

    return {
      content: piiFound
        ? `🛡️ ClawShield: ${redactions.length} PII items redacted before processing.`
        : "🛡️ ClawShield: No PII detected.",
      confidence: 1,
      metadata: {
        piiFound,
        redactions,
        strippedMessage: text,
        piiStripped: true,
      },
    };
  },
};
