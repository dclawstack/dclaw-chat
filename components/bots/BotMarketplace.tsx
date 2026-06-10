"use client";

import { useState, useEffect, useCallback } from "react";
import { Bot, BotCommand } from "@/types/chat";
import { CommandBuilder } from "./CommandBuilder";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Bot as BotIcon,
  Plus,
  Search,
  CheckCircle,
  Settings,
  X,
  Loader2,
  Zap,
  Package,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const CATEGORIES = ["all", "developer", "productivity", "fun", "general"];

const CATEGORY_LABELS: Record<string, string> = {
  all: "All",
  developer: "Developer",
  productivity: "Productivity",
  fun: "Fun",
  general: "General",
};

// ── Bot card ──────────────────────────────────────────────────────────────────

interface BotCardProps {
  bot: Bot;
  onInstall: (id: string) => void;
  onUninstall: (id: string) => void;
  onEdit: (bot: Bot) => void;
  loading: boolean;
}

function BotCard({ bot, onInstall, onUninstall, onEdit, loading }: BotCardProps) {
  return (
    <div className={`border rounded-lg p-4 flex flex-col gap-3 bg-card transition-shadow hover:shadow-md ${bot.installed ? "border-dclaw-300" : ""}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-3">
          <div className="text-2xl w-10 h-10 flex items-center justify-center bg-muted rounded-lg shrink-0">
            {bot.avatar_emoji || "🤖"}
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-sm">{bot.name}</span>
              {bot.installed && (
                <CheckCircle className="h-3.5 w-3.5 text-dclaw-500 shrink-0" aria-label="Installed" />
              )}
            </div>
            <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground capitalize">
              {bot.category}
            </span>
          </div>
        </div>
        {bot.installed && (
          <button
            className="text-muted-foreground hover:text-foreground shrink-0"
            onClick={() => onEdit(bot)}
            title="Configure bot"
          >
            <Settings className="h-4 w-4" />
          </button>
        )}
      </div>

      <p className="text-xs text-muted-foreground leading-relaxed">{bot.description}</p>

      {bot.commands.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {bot.commands.slice(0, 3).map((cmd) => (
            <span key={cmd.name} className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
              /{cmd.name}
            </span>
          ))}
          {bot.commands.length > 3 && (
            <span className="text-xs text-muted-foreground">+{bot.commands.length - 3} more</span>
          )}
        </div>
      )}

      <div className="mt-auto">
        {bot.installed ? (
          <Button
            variant="outline"
            size="sm"
            className="w-full text-xs h-8"
            disabled={loading}
            onClick={() => onUninstall(bot.id)}
          >
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : null}
            Uninstall
          </Button>
        ) : (
          <Button
            size="sm"
            className="w-full text-xs h-8 bg-dclaw-500 hover:bg-dclaw-600 text-white"
            disabled={loading}
            onClick={() => onInstall(bot.id)}
          >
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : null}
            Install
          </Button>
        )}
      </div>
    </div>
  );
}

// ── Create / Edit bot modal ───────────────────────────────────────────────────

interface BotFormState {
  name: string;
  slug: string;
  description: string;
  avatar_emoji: string;
  webhook_url: string;
  category: string;
  commands: BotCommand[];
}

const defaultForm = (): BotFormState => ({
  name: "",
  slug: "",
  description: "",
  avatar_emoji: "🤖",
  webhook_url: "",
  category: "general",
  commands: [],
});

interface BotFormPanelProps {
  initial: BotFormState | null;
  botId: string | null;
  onSave: (form: BotFormState, botId: string | null) => Promise<void>;
  onClose: () => void;
  saving: boolean;
}

function BotFormPanel({ initial, botId, onSave, onClose, saving }: BotFormPanelProps) {
  const [form, setForm] = useState<BotFormState>(initial ?? defaultForm());

  const set = (patch: Partial<BotFormState>) => setForm((f) => ({ ...f, ...patch }));

  const handleNameChange = (name: string) => {
    set({
      name,
      slug: name.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, ""),
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-background border rounded-xl w-full max-w-lg max-h-[90vh] flex flex-col shadow-xl">
        <div className="flex items-center justify-between px-5 py-4 border-b shrink-0">
          <h3 className="font-semibold text-sm">{botId ? "Edit Bot" : "Create Custom Bot"}</h3>
          <button onClick={onClose} aria-label="Close" className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <ScrollArea className="flex-1 px-5 py-4">
          <div className="space-y-4">
            <div className="grid grid-cols-[48px_1fr] gap-3 items-end">
              <div>
                <label className="text-xs text-muted-foreground mb-0.5 block">Icon</label>
                <Input
                  value={form.avatar_emoji}
                  onChange={(e) => set({ avatar_emoji: e.target.value })}
                  className="h-9 text-center text-lg"
                  maxLength={2}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-0.5 block">Bot name</label>
                <Input
                  value={form.name}
                  onChange={(e) => handleNameChange(e.target.value)}
                  placeholder="My Awesome Bot"
                  className="h-9 text-sm"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted-foreground mb-0.5 block">Slug</label>
                <Input
                  value={form.slug}
                  onChange={(e) => set({ slug: e.target.value.toLowerCase().replace(/\s+/g, "-") })}
                  placeholder="my-bot"
                  className="h-8 text-xs font-mono"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-0.5 block">Category</label>
                <select
                  value={form.category}
                  onChange={(e) => set({ category: e.target.value })}
                  aria-label="Category"
                  className="w-full h-8 text-xs rounded-md border bg-background px-2"
                >
                  {CATEGORIES.filter((c) => c !== "all").map((c) => (
                    <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="text-xs text-muted-foreground mb-0.5 block">Description</label>
              <Input
                value={form.description}
                onChange={(e) => set({ description: e.target.value })}
                placeholder="What does this bot do?"
                className="h-8 text-xs"
              />
            </div>

            <div>
              <label className="text-xs text-muted-foreground mb-0.5 block">
                Webhook URL <span className="text-muted-foreground/60">(optional)</span>
              </label>
              <Input
                value={form.webhook_url}
                onChange={(e) => set({ webhook_url: e.target.value })}
                placeholder="https://your-service.com/webhook"
                className="h-8 text-xs font-mono"
                type="url"
              />
              <p className="text-xs text-muted-foreground mt-0.5">
                Commands will POST a JSON payload to this URL and display the response.
              </p>
            </div>

            <CommandBuilder
              commands={form.commands}
              onChange={(commands) => set({ commands })}
            />
          </div>
        </ScrollArea>

        <div className="flex gap-2 px-5 py-4 border-t shrink-0">
          <Button variant="outline" size="sm" className="flex-1 text-xs" onClick={onClose}>
            Cancel
          </Button>
          <Button
            size="sm"
            className="flex-1 text-xs bg-dclaw-500 hover:bg-dclaw-600 text-white"
            disabled={saving || !form.name || !form.slug}
            onClick={() => onSave(form, botId)}
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : null}
            {botId ? "Save changes" : "Create bot"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── Main marketplace view ─────────────────────────────────────────────────────

export function BotMarketplace() {
  const [bots, setBots] = useState<Bot[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [category, setCategory] = useState("all");
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editBot, setEditBot] = useState<Bot | null>(null);
  const [saving, setSaving] = useState(false);

  const fetchBots = useCallback(async () => {
    try {
      setLoading(true);
      const res = await apiFetch(`${API_BASE}/bots`);
      if (res.ok) setBots(await res.json());
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchBots(); }, [fetchBots]);

  const handleInstall = async (id: string) => {
    setActionLoading(id);
    try {
      const res = await apiFetch(`${API_BASE}/bots/${id}/install`, { method: "POST" });
      if (res.ok) {
        const updated: Bot = await res.json();
        setBots((prev) => prev.map((b) => (b.id === id ? updated : b)));
      }
    } finally { setActionLoading(null); }
  };

  const handleUninstall = async (id: string) => {
    setActionLoading(id);
    try {
      const res = await apiFetch(`${API_BASE}/bots/${id}/uninstall`, { method: "POST" });
      if (res.ok) {
        const updated: Bot = await res.json();
        setBots((prev) => prev.map((b) => (b.id === id ? updated : b)));
      }
    } finally { setActionLoading(null); }
  };

  const handleSave = async (form: BotFormState, botId: string | null) => {
    setSaving(true);
    try {
      const body = {
        ...form,
        webhook_url: form.webhook_url || null,
      };
      let res: Response;
      if (botId) {
        res = await apiFetch(`${API_BASE}/bots/${botId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } else {
        res = await apiFetch(`${API_BASE}/bots`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      }
      if (res.ok) {
        const saved: Bot = await res.json();
        if (botId) {
          setBots((prev) => prev.map((b) => (b.id === botId ? saved : b)));
        } else {
          setBots((prev) => [...prev, saved]);
        }
        setShowForm(false);
        setEditBot(null);
      }
    } finally { setSaving(false); }
  };

  const filtered = bots.filter((b) => {
    const matchCat = category === "all" || b.category === category;
    const matchSearch =
      !search ||
      b.name.toLowerCase().includes(search.toLowerCase()) ||
      b.description.toLowerCase().includes(search.toLowerCase());
    return matchCat && matchSearch;
  });

  const installedCount = bots.filter((b) => b.installed).length;

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Header */}
      <div className="border-b px-6 py-4 shrink-0">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="font-semibold text-base flex items-center gap-2">
              <Package className="h-5 w-5 text-dclaw-500" />
              Bot Marketplace
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {installedCount} bot{installedCount !== 1 ? "s" : ""} installed · Type <code className="bg-muted px-1 rounded">/command</code> in any channel
            </p>
          </div>
          <Button
            size="sm"
            className="text-xs bg-dclaw-500 hover:bg-dclaw-600 text-white gap-1"
            onClick={() => { setEditBot(null); setShowForm(true); }}
          >
            <Plus className="h-3.5 w-3.5" />
            Create bot
          </Button>
        </div>

        {/* Search + category filter */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search bots…"
              className="pl-8 h-8 text-xs"
            />
          </div>
          <div className="flex gap-1">
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setCategory(cat)}
                className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                  category === cat
                    ? "bg-dclaw-500 text-white font-medium"
                    : "text-muted-foreground hover:bg-accent"
                }`}
              >
                {CATEGORY_LABELS[cat]}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Bot grid */}
      <ScrollArea className="flex-1 p-6">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-2">
            <BotIcon className="h-8 w-8" />
            <p className="text-sm">No bots found</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((bot) => (
              <BotCard
                key={bot.id}
                bot={bot}
                onInstall={handleInstall}
                onUninstall={handleUninstall}
                onEdit={(b) => { setEditBot(b); setShowForm(true); }}
                loading={actionLoading === bot.id}
              />
            ))}
          </div>
        )}

        {/* Installed commands quick reference */}
        {!loading && installedCount > 0 && (
          <div className="mt-8 border rounded-lg p-4">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <Zap className="h-3.5 w-3.5" />
              Installed Commands
            </h3>
            <div className="flex flex-wrap gap-2">
              {bots
                .filter((b) => b.installed && b.enabled)
                .flatMap((b) =>
                  b.commands.map((cmd) => (
                    <div
                      key={`${b.id}-${cmd.name}`}
                      className="flex items-center gap-1.5 bg-muted rounded-md px-2 py-1"
                    >
                      <span className="text-base leading-none">{b.avatar_emoji || "🤖"}</span>
                      <div>
                        <p className="font-mono text-xs font-medium">/{cmd.name}</p>
                        <p className="text-xs text-muted-foreground">{cmd.description}</p>
                      </div>
                    </div>
                  ))
                )}
            </div>
          </div>
        )}
      </ScrollArea>

      {/* Create/Edit modal */}
      {showForm && (
        <BotFormPanel
          initial={
            editBot
              ? {
                  name: editBot.name,
                  slug: editBot.slug,
                  description: editBot.description,
                  avatar_emoji: editBot.avatar_emoji || "🤖",
                  webhook_url: editBot.webhook_url || "",
                  category: editBot.category,
                  commands: editBot.commands,
                }
              : null
          }
          botId={editBot?.id ?? null}
          onSave={handleSave}
          onClose={() => { setShowForm(false); setEditBot(null); }}
          saving={saving}
        />
      )}
    </div>
  );
}
