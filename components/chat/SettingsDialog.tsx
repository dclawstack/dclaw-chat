"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  X,
  Settings as SettingsIcon,
  Trash2,
  Server,
  Cpu,
  Sparkles,
  Sun,
  Moon,
  Monitor,
  Palette,
} from "lucide-react";
import { AIModel } from "@/types/chat";

const TEMP_KEY = "dclaw.chat.temperature";
const DEFAULT_MODEL_KEY = "dclaw.chat.defaultModel";
const THEME_KEY = "dclaw.chat.theme";

export type ThemeMode = "light" | "dark" | "system";

export function getStoredTemperature(): number {
  if (typeof window === "undefined") return 0.7;
  const raw = window.localStorage.getItem(TEMP_KEY);
  const parsed = raw ? parseFloat(raw) : NaN;
  return Number.isFinite(parsed) ? parsed : 0.7;
}

export function getStoredDefaultModel(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(DEFAULT_MODEL_KEY);
}

export function getStoredTheme(): ThemeMode {
  if (typeof window === "undefined") return "system";
  const raw = window.localStorage.getItem(THEME_KEY);
  return raw === "light" || raw === "dark" || raw === "system" ? raw : "system";
}

function applyTheme(mode: ThemeMode) {
  if (typeof document === "undefined") return;
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const isDark = mode === "dark" || (mode === "system" && prefersDark);
  document.documentElement.classList.toggle("dark", isDark);
}

export function setStoredTheme(mode: ThemeMode) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(THEME_KEY, mode);
  applyTheme(mode);
}

/** Wire up the OS-preference listener so "system" mode reacts live. Call once at app mount. */
export function useThemeSync() {
  useEffect(() => {
    applyTheme(getStoredTheme());
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if (getStoredTheme() === "system") applyTheme("system");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
}

interface SettingsDialogProps {
  open: boolean;
  onClose: () => void;
  models: AIModel[];
  selectedModel: string;
  onSelectModel: (id: string) => void;
  onClearAllConversations: () => void;
}

export function SettingsDialog({
  open,
  onClose,
  models,
  selectedModel,
  onSelectModel,
  onClearAllConversations,
}: SettingsDialogProps) {
  const [temperature, setTemperature] = useState<number>(0.7);
  const [theme, setTheme] = useState<ThemeMode>("system");
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => {
    if (open) {
      setTemperature(getStoredTemperature());
      setTheme(getStoredTheme());
      setConfirmClear(false);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  function handleTempChange(value: number) {
    setTemperature(value);
    window.localStorage.setItem(TEMP_KEY, value.toString());
  }

  function handleDefaultModel(id: string) {
    onSelectModel(id);
    window.localStorage.setItem(DEFAULT_MODEL_KEY, id);
  }

  function handleThemeChange(mode: ThemeMode) {
    setTheme(mode);
    setStoredTheme(mode);
  }

  function handleClear() {
    if (!confirmClear) {
      setConfirmClear(true);
      return;
    }
    onClearAllConversations();
    setConfirmClear(false);
    onClose();
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/60"
        role="button"
        tabIndex={0}
        aria-label="Close settings"
        onClick={onClose}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onClose();
          }
        }}
      />
      <div className="relative z-10 w-full max-w-md rounded-lg border bg-card text-card-foreground shadow-2xl">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div className="flex items-center gap-2">
            <SettingsIcon className="h-4 w-4 text-dclaw-500" />
            <h2 className="text-sm font-semibold">Settings</h2>
          </div>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-5 px-4 py-4 text-sm">
          {/* Theme */}
          <section>
            <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <Palette className="h-3.5 w-3.5" />
              APPEARANCE
            </div>
            <div className="grid grid-cols-3 gap-2">
              {(
                [
                  { mode: "light" as const, label: "Light", Icon: Sun },
                  { mode: "dark" as const, label: "Dark", Icon: Moon },
                  { mode: "system" as const, label: "System", Icon: Monitor },
                ]
              ).map(({ mode, label, Icon }) => {
                const active = theme === mode;
                return (
                  <button
                    key={mode}
                    onClick={() => handleThemeChange(mode)}
                    className={`flex flex-col items-center gap-1 rounded-md border px-2 py-2 text-xs transition-colors ${
                      active
                        ? "border-dclaw-500 bg-dclaw-500/10 text-foreground"
                        : "border-border text-muted-foreground hover:bg-accent hover:text-foreground"
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                  </button>
                );
              })}
            </div>
          </section>

          {/* Default Model */}
          <section>
            <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <Cpu className="h-3.5 w-3.5" />
              DEFAULT MODEL
            </div>
            <select
              value={selectedModel}
              onChange={(e) => handleDefaultModel(e.target.value)}
              aria-label="Default model"
              className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dclaw-500"
            >
              {models.map((m) => (
                <option key={m.id} value={m.id} disabled={!m.available}>
                  {m.name}
                  {!m.available && " (unavailable)"}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-muted-foreground">
              Persisted across sessions.
            </p>
          </section>

          {/* Temperature */}
          <section>
            <div className="mb-2 flex items-center justify-between text-xs font-medium text-muted-foreground">
              <span className="flex items-center gap-2">
                <Sparkles className="h-3.5 w-3.5" />
                TEMPERATURE
              </span>
              <span className="font-mono text-foreground">{temperature.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={temperature}
              onChange={(e) => handleTempChange(parseFloat(e.target.value))}
              aria-label="Temperature"
              className="w-full accent-dclaw-500"
            />
            <div className="mt-1 flex justify-between text-xs text-muted-foreground">
              <span>Focused</span>
              <span>Creative</span>
            </div>
          </section>

          {/* API Endpoint */}
          <section>
            <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <Server className="h-3.5 w-3.5" />
              API ENDPOINT
            </div>
            <code className="block break-all rounded-md border bg-muted px-3 py-2 text-xs">
              {apiUrl}
            </code>
          </section>

          {/* Clear conversations */}
          <section className="border-t pt-4">
            <div className="mb-2 text-xs font-medium text-muted-foreground">
              DANGER ZONE
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClear}
              className={`w-full justify-start gap-2 ${
                confirmClear
                  ? "bg-destructive/10 text-destructive hover:bg-destructive/20"
                  : "text-muted-foreground hover:text-destructive"
              }`}
            >
              <Trash2 className="h-4 w-4" />
              {confirmClear ? "Click again to confirm" : "Clear all conversations"}
            </Button>
          </section>
        </div>

        <div className="border-t px-4 py-3 text-xs text-muted-foreground">
          DClaw Chat · v1.0.0
        </div>
      </div>
    </div>
  );
}
