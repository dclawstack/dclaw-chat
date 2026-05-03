import { SwarmAgent, AgentCapability } from "./types";

export class AgentRegistry {
  private agents = new Map<string, SwarmAgent>();

  register(agent: SwarmAgent): void {
    this.agents.set(agent.id, agent);
  }

  unregister(agentId: string): boolean {
    return this.agents.delete(agentId);
  }

  get(id: string): SwarmAgent | undefined {
    return this.agents.get(id);
  }

  list(): SwarmAgent[] {
    return Array.from(this.agents.values()).sort(
      (a, b) => a.priority - b.priority
    );
  }

  findByCapability(keyword: string): SwarmAgent[] {
    return this.list().filter((agent) =>
      agent.capabilities.some((cap) =>
        cap.keywords.some((k) =>
          keyword.toLowerCase().includes(k.toLowerCase())
        )
      )
    );
  }

  findByName(name: string): SwarmAgent | undefined {
    return this.list().find(
      (a) => a.name.toLowerCase() === name.toLowerCase() || a.id === name
    );
  }

  getCapabilities(): { agent: string; capabilities: AgentCapability[] }[] {
    return this.list().map((a) => ({
      agent: a.name,
      capabilities: a.capabilities,
    }));
  }
}

// Singleton registry instance
export const swarmRegistry = new AgentRegistry();
