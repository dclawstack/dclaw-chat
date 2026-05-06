# Use Cases

## 1. Customer Support Agent

**Scenario:** Your support team uses DClaw Chat to draft responses to customer tickets.

**Workflow:**
1. Paste the customer ticket into a new conversation
2. Ask the AI: "Draft a polite, helpful response to this customer"
3. Review and edit the draft
4. Copy the final response to your ticketing system

**Tips:**
- Use **Claude 3.5 Sonnet** for nuanced, empathetic language
- Save successful prompts as templates
- Organize conversations by customer tier (VIP, Enterprise, etc.)

## 2. Code Review Assistant

**Scenario:** Developers use DClaw Chat to review code snippets and suggest improvements.

**Workflow:**
1. Paste a code snippet into the chat
2. Ask: "Review this Python function for performance issues"
3. The AI suggests optimizations, catches edge cases, and recommends type hints

**Tips:**
- Use **GPT-4o** for broad language support
- Enable syntax highlighting in responses
- Export conversations as Markdown for documentation

## 3. Research Synthesis

**Scenario:** Researchers paste multiple paper abstracts and ask the AI to synthesize findings.

**Workflow:**
1. Create a conversation titled "Literature Review: LLM Safety"
2. Paste abstracts one by one
3. Ask: "What are the common themes across these papers?"
4. Follow up with: "Identify gaps in the current research"

**Tips:**
- Use folders to organize by research topic
- Long conversations maintain context across messages
- Export as PDF for sharing with collaborators

## 4. Creative Writing Partner

**Scenario:** Writers brainstorm ideas, outline plots, and refine drafts.

**Workflow:**
1. "Help me brainstorm 10 sci-fi story premises involving time travel"
2. Pick one and ask for a 3-act outline
3. Iterate chapter by chapter

**Tips:**
- Use temperature > 0.8 for more creative outputs
- Save different versions as separate conversations
- Use the voice input feature for hands-free brainstorming

## 5. On-Call Troubleshooting

**Scenario:** SREs paste error logs and ask the AI to diagnose issues.

**Workflow:**
1. Paste a stack trace into the chat
2. Ask: "What could cause this PostgreSQL connection error?"
3. Follow up with: "Suggest 3 fixes ordered by likelihood"

**Tips:**
- Use **local models** (Gemma 4B) for sensitive production logs
- The PII shield scrubs sensitive data before sending to cloud models
- Save common error patterns as reusable prompts
