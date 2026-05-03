"use client";

import { useState, useRef, useEffect } from "react";
import { AIModel, MODELS } from "@/types/chat";
import { Button } from "@/components/ui/button";
import { ChevronDown, Check } from "lucide-react";

interface ModelSelectorProps {
  selectedModel: string;
  onSelect: (modelId: string) => void;
}

export function ModelSelector({ selectedModel, onSelect }: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selected = MODELS.find((m) => m.id === selectedModel) || MODELS[0];

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-xs"
      >
        <span>{selected.icon}</span>
        <span className="hidden sm:inline">{selected.name}</span>
        <ChevronDown className="h-3 w-3" />
      </Button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-64 bg-popover border rounded-lg shadow-lg z-50 p-1">
          <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
            Local Models
          </div>
          {MODELS.filter((m) => m.provider === "local").map((model) => (
            <ModelOption
              key={model.id}
              model={model}
              isSelected={model.id === selectedModel}
              onSelect={() => {
                onSelect(model.id);
                setIsOpen(false);
              }}
            />
          ))}

          <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground mt-1">
            Cloud Models
          </div>
          {MODELS.filter((m) => m.provider === "cloud").map((model) => (
            <ModelOption
              key={model.id}
              model={model}
              isSelected={model.id === selectedModel}
              onSelect={() => {
                onSelect(model.id);
                setIsOpen(false);
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ModelOption({
  model,
  isSelected,
  onSelect,
}: {
  model: AIModel;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={`w-full flex items-center gap-2 px-2 py-2 rounded-md text-sm hover:bg-accent transition-colors ${
        isSelected ? "bg-accent" : ""
      }`}
    >
      <span className="text-base">{model.icon}</span>
      <div className="flex-1 text-left">
        <div className="font-medium">{model.name}</div>
        <div className="text-xs text-muted-foreground">{model.description}</div>
      </div>
      {isSelected && <Check className="h-4 w-4 text-dclaw-500" />}
    </button>
  );
}
