"use client";

import { useState } from "react";
import { BotCommand, CommandParam } from "@/types/chat";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Trash2, ChevronDown, ChevronUp } from "lucide-react";

interface CommandBuilderProps {
  commands: BotCommand[];
  onChange: (commands: BotCommand[]) => void;
}

const emptyCommand = (): BotCommand => ({
  name: "",
  description: "",
  usage: "",
  params: [],
});

const emptyParam = (): CommandParam => ({
  name: "",
  description: "",
  required: false,
});

export function CommandBuilder({ commands, onChange }: CommandBuilderProps) {
  const [expanded, setExpanded] = useState<number | null>(null);

  const addCommand = () => {
    const next = [...commands, emptyCommand()];
    onChange(next);
    setExpanded(next.length - 1);
  };

  const removeCommand = (idx: number) => {
    onChange(commands.filter((_, i) => i !== idx));
    if (expanded === idx) setExpanded(null);
  };

  const updateCommand = (idx: number, patch: Partial<BotCommand>) => {
    onChange(commands.map((c, i) => (i === idx ? { ...c, ...patch } : c)));
  };

  const addParam = (cmdIdx: number) => {
    const cmd = commands[cmdIdx];
    updateCommand(cmdIdx, { params: [...cmd.params, emptyParam()] });
  };

  const removeParam = (cmdIdx: number, pIdx: number) => {
    const cmd = commands[cmdIdx];
    updateCommand(cmdIdx, { params: cmd.params.filter((_, i) => i !== pIdx) });
  };

  const updateParam = (cmdIdx: number, pIdx: number, patch: Partial<CommandParam>) => {
    const cmd = commands[cmdIdx];
    updateCommand(cmdIdx, {
      params: cmd.params.map((p, i) => (i === pIdx ? { ...p, ...patch } : p)),
    });
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Commands
        </span>
        <Button variant="outline" size="sm" className="h-7 px-2 text-xs gap-1" onClick={addCommand}>
          <Plus className="h-3.5 w-3.5" />
          Add command
        </Button>
      </div>

      {commands.length === 0 && (
        <p className="text-xs text-muted-foreground py-2 text-center">
          No commands yet. Add a command to let users interact with this bot.
        </p>
      )}

      {commands.map((cmd, idx) => (
        <div key={idx} className="border rounded-md overflow-hidden">
          {/* Command header row */}
          <div
            className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-accent/50 bg-muted/40"
            onClick={() => setExpanded(expanded === idx ? null : idx)}
          >
            <span className="font-mono text-xs font-semibold text-dclaw-600 min-w-[60px]">
              /{cmd.name || "…"}
            </span>
            <span className="text-xs text-muted-foreground flex-1 truncate">
              {cmd.description || "No description"}
            </span>
            <button
              className="text-muted-foreground hover:text-destructive shrink-0"
              onClick={(e) => { e.stopPropagation(); removeCommand(idx); }}
              title="Remove command"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
            {expanded === idx
              ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            }
          </div>

          {/* Expanded form */}
          {expanded === idx && (
            <div className="px-3 pb-3 pt-2 space-y-2 bg-background">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs text-muted-foreground mb-0.5 block">Name</label>
                  <Input
                    value={cmd.name}
                    onChange={(e) => updateCommand(idx, { name: e.target.value.toLowerCase().replace(/\s+/g, "-") })}
                    placeholder="deploy"
                    className="h-7 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-0.5 block">Usage</label>
                  <Input
                    value={cmd.usage}
                    onChange={(e) => updateCommand(idx, { usage: e.target.value })}
                    placeholder="/deploy [env]"
                    className="h-7 text-xs font-mono"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-0.5 block">Description</label>
                <Input
                  value={cmd.description}
                  onChange={(e) => updateCommand(idx, { description: e.target.value })}
                  placeholder="Trigger a deployment"
                  className="h-7 text-xs"
                />
              </div>

              {/* Parameters */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Parameters</span>
                  <button
                    className="text-xs text-dclaw-600 hover:underline flex items-center gap-0.5"
                    onClick={() => addParam(idx)}
                  >
                    <Plus className="h-3 w-3" />
                    Add param
                  </button>
                </div>
                {cmd.params.map((param, pIdx) => (
                  <div key={pIdx} className="flex items-center gap-1.5 bg-muted/30 rounded px-2 py-1">
                    <Input
                      value={param.name}
                      onChange={(e) => updateParam(idx, pIdx, { name: e.target.value })}
                      placeholder="param-name"
                      className="h-6 text-xs font-mono w-24 shrink-0"
                    />
                    <Input
                      value={param.description}
                      onChange={(e) => updateParam(idx, pIdx, { description: e.target.value })}
                      placeholder="Description"
                      className="h-6 text-xs flex-1"
                    />
                    <label className="flex items-center gap-1 text-xs text-muted-foreground shrink-0 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={param.required}
                        onChange={(e) => updateParam(idx, pIdx, { required: e.target.checked })}
                        className="h-3 w-3"
                      />
                      req
                    </label>
                    <button
                      className="text-muted-foreground hover:text-destructive shrink-0"
                      onClick={() => removeParam(idx, pIdx)}
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
