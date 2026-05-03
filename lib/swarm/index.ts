import { swarmRegistry } from "./registry";
import { swarmOrchestrator } from "./orchestrator";
import { codeAgent } from "./agents/code-agent";
import { researchAgent } from "./agents/research-agent";
import { shieldAgent } from "./agents/shield-agent";
import { memoryAgent } from "./agents/memory-agent";
import { generalAgent } from "./agents/general-agent";

// Register all agents on module load
swarmRegistry.register(shieldAgent);
swarmRegistry.register(codeAgent);
swarmRegistry.register(researchAgent);
swarmRegistry.register(memoryAgent);
swarmRegistry.register(generalAgent);

export { swarmRegistry, swarmOrchestrator };
export * from "./types";
