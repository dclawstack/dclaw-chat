"use client";

import { useState } from "react";
import { SwarmAgent } from "@/lib/swarm/types";
import { swarmRegistry } from "@/lib/swarm/registry";
import { Bot, ChevronDown, ChevronUp, Shield, Sparkles } from "lucide-react";

interface SwarmStatusProps {
  activeAgents: string[];
  currentPlan?: {
    intent: string;
    primaryAgent: string;
    supportingAgents: string[];
    reasoning: string;
  };
}

export function SwarmStatus({ activeAgents, currentPlan }: SwarmStatusProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const allAgents = swarmRegistry.list();

  const getAgentIcon = (name: string) => {
    const agent = swarmRegistry.findByName(name);
    return agent?.icon || "🤖";
  };

  return (
    <div className="border-t bg-muted/50">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <div className="flex items-center gap-2">
          <Sparkles className="h-3 w-3 text-dclaw-500" />
          <span>
            {activeAgents.length > 0
              ? `${activeAgents.length} agent${activeAgents.length > 1 ? "s" : ""} active`
              : "Swarm ready"}
          </span>
          {currentPlan && (
            <span className="hidden sm:inline">
              · Intent: <span className="font-medium">{currentPlan.intent}</span>
              · Primary: {getAgentIcon(currentPlan.primaryAgent)} {currentPlan.primaryAgent}
            </span>
          )}
        </div>
        {isExpanded ? (
          <ChevronUp className="h-3 w-3" />
        ) : (
          <ChevronDown className="h-3 w-3" />
        )}
      </button>

      {isExpanded && (
        <div className="px-4 pb-3 space-y-3">
          {/* Current Plan */}
          {currentPlan && (
            <div className="bg-background rounded-lg p-3 text-xs space-y-2">
              <div className="font-semibold text-foreground flex items-center gap-1">
                <Bot className="h-3 w-3" />
                Current Plan
              </div>
              <div className="grid grid-cols-2 gap-2 text-muted-foreground">
                <div>
                  <span className="font-medium">Intent:</span> {currentPlan.intent}
                </div>
                <div>
                  <span className="font-medium">Primary:</span>{" "}
                  {getAgentIcon(currentPlan.primaryAgent)} {currentPlan.primaryAgent}
                </div>
                {currentPlan.supportingAgents.length > 0 && (
                  <div className="col-span-2">
                    <span className="font-medium">Supporting:</span>{" "}
                    {currentPlan.supportingAgents.map((a) => (
                      <span key={a} className="mr-2">
                        {getAgentIcon(a)} {a}
                      </span>
                    ))}
                  </div>
                )}
                <div className="col-span-2 italic">{currentPlan.reasoning}</div>
              </div>
            </div>
          )}

          {/* Agent Registry */}
          <div className="space-y-1">
            <div className="text-xs font-semibold text-muted-foreground">
              Available Agents ({allAgents.length})
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {allAgents.map((agent) => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  isActive={activeAgents.includes(agent.name)}
                />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AgentCard({
  agent,
  isActive,
}: {
  agent: SwarmAgent;
  isActive: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-2 px-2 py-1.5 rounded-md text-xs transition-colors ${
        isActive
          ? "bg-dclaw-100 text-dclaw-900 border border-dclaw-200"
          : "bg-background text-muted-foreground border border-transparent"
      }`}
    >
      <span className="text-base">{agent.icon}</span>
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate">{agent.name}</div>
        <div className="text-[10px] truncate opacity-70">{agent.description}</div>
      </div>
      {agent.id === "shield-agent" && (
        <Shield className="h-3 w-3 text-dclaw-500 shrink-0" />
      )}
    </div>
  );
}
