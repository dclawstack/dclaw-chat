import Link from "next/link";
import {
  Bot, MessageSquare, Video, Users, Shield, Zap,
  Radio, Package, Mic, Brain, Lock, ArrowRight,
  CheckCircle, Star, ChevronRight, Globe, Cpu, Monitor,
  Palette, Sun, Moon, Settings as SettingsIcon, Sparkles,
} from "lucide-react";
// Demo seed/clear controls — isolated under components/landing/ for easy removal.
import SeedControls from "@/components/landing/seed-controls";

// ── Reusable primitives ───────────────────────────────────────────────────────

function GradientText({ children }: { children: React.ReactNode }) {
  return (
    <span className="bg-gradient-to-r from-blue-400 via-violet-400 to-purple-400 bg-clip-text text-transparent">
      {children}
    </span>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs font-medium text-blue-400">
      {children}
    </span>
  );
}

function FeatureCard({
  icon: Icon,
  title,
  description,
  accent = "blue",
}: {
  icon: React.ElementType;
  title: string;
  description: string;
  accent?: "blue" | "violet" | "green" | "orange" | "pink";
}) {
  const accents = {
    blue: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    violet: "bg-violet-500/10 text-violet-400 border-violet-500/20",
    green: "bg-green-500/10 text-green-400 border-green-500/20",
    orange: "bg-orange-500/10 text-orange-400 border-orange-500/20",
    pink: "bg-pink-500/10 text-pink-400 border-pink-500/20",
  };
  return (
    <div className="group relative rounded-2xl border border-white/8 bg-dk-surface-raised p-6 hover:border-white/15 transition-all duration-300 hover:-translate-y-0.5">
      <div className={`mb-4 inline-flex rounded-xl border p-2.5 ${accents[accent]}`}>
        <Icon className="h-5 w-5" />
      </div>
      <h3 className="mb-2 font-display text-base font-semibold text-white">{title}</h3>
      <p className="text-sm leading-relaxed text-dk-muted">{description}</p>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-blue-400">{children}</p>
  );
}

function Check({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2.5 text-sm text-dk-muted">
      <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-green-400" />
      {children}
    </li>
  );
}

// ── Navbar ────────────────────────────────────────────────────────────────────

function Navbar() {
  return (
    <nav className="fixed inset-x-0 top-0 z-50 border-b border-white/5 bg-dk-surface/80 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-sm">
            💬
          </div>
          <span className="font-display text-sm font-bold text-white">DClaw Chat</span>
        </div>
        <div className="hidden items-center gap-6 md:flex">
          {["Features", "Calls", "AI", "Security", "Personalize"].map((item) => (
            <a
              key={item}
              href={`#${item.toLowerCase()}`}
              className="text-xs font-medium text-dk-muted transition-colors hover:text-white"
            >
              {item}
            </a>
          ))}
        </div>
        <Link
          href="/app"
          className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-blue-500"
        >
          Open App
          <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    </nav>
  );
}

// ── Hero ──────────────────────────────────────────────────────────────────────

function Hero() {
  return (
    <section className="relative overflow-hidden pt-32 pb-24">
      {/* Background glow */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-1/2 top-0 h-[600px] w-[900px] -translate-x-1/2 rounded-full bg-blue-600/10 blur-3xl" />
        <div className="absolute left-1/3 top-20 h-[300px] w-[400px] rounded-full bg-violet-600/8 blur-3xl" />
      </div>

      <div className="mx-auto max-w-4xl px-6 text-center">
        <Badge>
          <Star className="h-3 w-3" /> New: Light/Dark themes · WebRTC Calls · AI Meetings
        </Badge>

        <h1 className="mt-6 font-display text-5xl font-bold tracking-tight text-white sm:text-6xl lg:text-7xl">
          The AI-powered workspace
          <br />
          <GradientText>your team deserves</GradientText>
        </h1>

        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-dk-muted">
          DClaw Chat combines real-time team messaging, voice & video calls,
          AI conversations, and smart meeting summaries — all with enterprise-grade
          privacy and local LLM support.
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/app"
            className="flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-900/30 transition-all hover:bg-blue-500 hover:-translate-y-0.5"
          >
            Get started free
            <ArrowRight className="h-4 w-4" />
          </Link>
          <a
            href="#features"
            className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-6 py-3 text-sm font-semibold text-white transition-all hover:bg-white/10"
          >
            See all features
            <ChevronRight className="h-4 w-4" />
          </a>
        </div>

        {/* Stats row */}
        <div className="mt-16 grid grid-cols-3 gap-6 border-t border-white/8 pt-10">
          {[
            { value: "10+", label: "AI Models" },
            { value: "WebRTC", label: "Real-time Calls" },
            { value: "100%", label: "Privacy First" },
          ].map(({ value, label }) => (
            <div key={label} className="flex flex-col items-center gap-1">
              <span className="font-display text-3xl font-bold text-white">{value}</span>
              <span className="text-xs text-dk-muted">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Feature grid ──────────────────────────────────────────────────────────────

function FeaturesGrid() {
  return (
    <section id="features" className="py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-14 text-center">
          <SectionLabel>Everything you need</SectionLabel>
          <h2 className="font-display text-4xl font-bold text-white">
            One platform. <GradientText>All the tools.</GradientText>
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-dk-muted">
            From AI chat to live calls and bot automation — DClaw Chat brings your entire team workflow into a single, beautiful interface.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <FeatureCard icon={Bot} accent="blue" title="AI Conversations"
            description="Chat with powerful local LLMs like Gemma, Kimi K2.5, and more. Swarm agents handle research, code, and memory automatically." />
          <FeatureCard icon={MessageSquare} accent="violet" title="Team Channels"
            description="Organized messaging with threads, topics, file sharing, link unfurling, and real-time typing indicators." />
          <FeatureCard icon={Video} accent="green" title="Voice & Video Calls"
            description="Browser-native WebRTC calls with screen sharing, participant gallery, and a polished Teams-style interface." />
          <FeatureCard icon={Radio} accent="orange" title="Huddles"
            description="Spontaneous drop-in rooms for quick syncs. No scheduling needed — just jump in and collaborate instantly." />
          <FeatureCard icon={Mic} accent="pink" title="AI Meeting Summaries"
            description="Whisper STT transcribes your meetings automatically. An LLM then generates concise bullet-point summaries." />
          <FeatureCard icon={Package} accent="blue" title="Bot Marketplace"
            description="Install workflow bots with slash commands, webhooks, and automated triggers. Build your own with the open bot framework." />
          <FeatureCard icon={Shield} accent="violet" title="ClawShield PII Protection"
            description="Automatic detection and redaction of personally identifiable information before it ever reaches an AI model." />
          <FeatureCard icon={Brain} accent="green" title="Swarm Intelligence"
            description="Multiple specialized AI agents collaborate on complex tasks — code, research, memory, and privacy all handled in parallel." />
          <FeatureCard icon={Lock} accent="orange" title="Local-first Privacy"
            description="Run LLMs entirely on your own hardware. No data leaves your network. Full GDPR and HIPAA compatibility." />
          <FeatureCard icon={Palette} accent="pink" title="Light & Dark Themes"
            description="Pick Light, Dark, or System mode from Settings. The whole app — including the sidebar, chat, and dialogs — switches instantly and persists across sessions." />
          <FeatureCard icon={SettingsIcon} accent="violet" title="Customizable Settings"
            description="Set your default model, tune temperature with a live slider, see the active API endpoint, and clear conversations — all from a single Settings dialog." />
          <FeatureCard icon={Sparkles} accent="green" title="Quick-start Suggestions"
            description="One-click prompt suggestions get you chatting in seconds. Auto-creates a fresh conversation so you can jump straight from idle to insight." />
        </div>
      </div>
    </section>
  );
}

// ── Calls section ─────────────────────────────────────────────────────────────

function CallsSection() {
  return (
    <section id="calls" className="py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="overflow-hidden rounded-3xl border border-white/8 bg-gradient-to-br from-[#0f1729] to-[#0e0e10]">
          <div className="grid lg:grid-cols-2">
            {/* Text */}
            <div className="flex flex-col justify-center p-10 lg:p-14">
              <SectionLabel>Voice & Video</SectionLabel>
              <h2 className="font-display text-4xl font-bold text-white">
                Calls that feel <GradientText>professional</GradientText>
              </h2>
              <p className="mt-4 text-dk-muted leading-relaxed">
                Start a call directly from any channel. Pre-join lobby lets you
                check your mic and camera before entering. A Teams-style gallery
                view keeps everyone visible.
              </p>
              <ul className="mt-8 space-y-3">
                <Check>Pre-join lobby with camera preview and device toggles</Check>
                <Check>Gallery grid view with local picture-in-picture</Check>
                <Check>Screen sharing with live presenter badge</Check>
                <Check>Participants panel with mic/camera status</Check>
                <Check>Call duration timer and auto-cleanup on disconnect</Check>
              </ul>
            </div>
            {/* Mock call UI */}
            <div className="relative flex items-center justify-center bg-[#111111] p-8 lg:p-12">
              <div className="w-full max-w-sm rounded-2xl border border-white/8 bg-[#1a1a1a] overflow-hidden shadow-2xl">
                {/* Call header */}
                <div className="flex items-center justify-between px-4 py-3 bg-[#1c1c1c] border-b border-white/5">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-green-500" />
                    <span className="text-xs font-semibold text-white">Call Room</span>
                  </div>
                  <span className="font-mono text-xs text-gray-400">04:23</span>
                </div>
                {/* Video tiles */}
                <div className="grid grid-cols-2 gap-2 p-3">
                  {["You", "Alex", "Sam", "Jordan"].map((name, i) => (
                    <div key={name} className="aspect-video rounded-xl bg-[#2a2a2a] relative overflow-hidden flex items-center justify-center">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                        ["bg-blue-700","bg-violet-700","bg-green-700","bg-orange-700"][i]
                      }`}>
                        {name[0]}
                      </div>
                      <span className="absolute bottom-1.5 left-2 text-[9px] text-gray-300 bg-black/60 px-1 py-0.5 rounded-full">{name}</span>
                    </div>
                  ))}
                </div>
                {/* Controls */}
                <div className="flex items-center justify-center gap-3 px-4 pb-4 pt-2">
                  {[Mic, Video, Monitor].map((Icon, i) => (
                    <div key={i} className="w-9 h-9 rounded-xl bg-[#2e2e2e] flex items-center justify-center">
                      <Icon className="w-4 h-4 text-white" />
                    </div>
                  ))}
                  <div className="w-9 h-9 rounded-xl bg-red-600 flex items-center justify-center ml-2">
                    <Video className="w-4 h-4 text-white" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── AI section ────────────────────────────────────────────────────────────────

function AISection() {
  const models = ["Gemma 4B", "Kimi K2.5", "Llama 3.1", "Mistral 7B", "Phi-3"];
  return (
    <section id="ai" className="py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid items-center gap-12 lg:grid-cols-2">
          {/* Mock AI chat */}
          <div className="order-2 lg:order-1 rounded-2xl border border-white/8 bg-dk-surface-raised overflow-hidden shadow-dk-lg">
            {/* Model selector */}
            <div className="flex items-center gap-2 border-b border-white/5 px-4 py-3">
              <Cpu className="h-3.5 w-3.5 text-blue-400" />
              <span className="text-xs text-dk-muted">Model:</span>
              <span className="text-xs font-medium text-white">Gemma 4B</span>
              <div className="ml-auto flex items-center gap-1 text-xs text-green-400 bg-green-500/10 px-2 py-0.5 rounded-full">
                <Shield className="h-3 w-3" /> PII Shield active
              </div>
            </div>
            {/* Messages */}
            <div className="space-y-4 p-5">
              <div className="flex justify-end">
                <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-blue-600 px-4 py-2.5 text-sm text-white">
                  Summarize our Q2 architecture decisions
                </div>
              </div>
              <div className="flex gap-3">
                <div className="h-7 w-7 shrink-0 rounded-full bg-violet-700 flex items-center justify-center text-xs font-bold">AI</div>
                <div className="max-w-[80%] rounded-2xl rounded-tl-sm bg-dk-surface-elevated px-4 py-2.5 text-sm text-dk-body leading-relaxed">
                  Here are the key Q2 decisions:
                  <ul className="mt-2 space-y-1 text-dk-muted text-xs">
                    <li>• Migrated to async FastAPI with PostgreSQL</li>
                    <li>• Adopted WebRTC for peer-to-peer calls</li>
                    <li>• Integrated Whisper STT for meetings</li>
                  </ul>
                </div>
              </div>
              <div className="flex gap-3 opacity-60">
                <div className="h-7 w-7 shrink-0 rounded-full bg-violet-700 flex items-center justify-center text-xs">AI</div>
                <div className="flex gap-1 items-center px-4 py-3 rounded-2xl rounded-tl-sm bg-dk-surface-elevated">
                  <span className="w-1.5 h-1.5 rounded-full bg-dk-muted animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-dk-muted animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-dk-muted animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
            {/* Model pills */}
            <div className="border-t border-white/5 px-5 py-3 flex gap-2 flex-wrap">
              {models.map((m) => (
                <span key={m} className="rounded-full bg-white/5 px-2.5 py-0.5 text-[10px] text-dk-muted border border-white/8">{m}</span>
              ))}
            </div>
          </div>

          {/* Text */}
          <div className="order-1 lg:order-2">
            <SectionLabel>Swarm AI</SectionLabel>
            <h2 className="font-display text-4xl font-bold text-white">
              AI that <GradientText>thinks together</GradientText>
            </h2>
            <p className="mt-4 leading-relaxed text-dk-muted">
              DClaw Chat's swarm engine routes your message to the right specialist agent automatically — code, research, memory, or privacy. Multiple agents collaborate in parallel to give you the best answer.
            </p>
            <ul className="mt-8 space-y-3">
              <Check>10+ local LLMs — no API keys needed</Check>
              <Check>Swarm agents: Code, Research, Memory, ClawShield</Check>
              <Check>Streaming responses with real-time token display</Check>
              <Check>Automatic intent detection and agent routing</Check>
              <Check>Conversation history with folder organization</Check>
            </ul>
            <Link href="/app" className="mt-8 inline-flex items-center gap-2 text-sm font-semibold text-blue-400 hover:text-blue-300 transition-colors">
              Try AI chat now <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Channels section ──────────────────────────────────────────────────────────

function ChannelsSection() {
  return (
    <section className="py-24 bg-gradient-to-b from-transparent via-dk-surface-raised/30 to-transparent">
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid items-center gap-12 lg:grid-cols-2">
          {/* Text */}
          <div>
            <SectionLabel>Team Messaging</SectionLabel>
            <h2 className="font-display text-4xl font-bold text-white">
              Channels built for <GradientText>real teams</GradientText>
            </h2>
            <p className="mt-4 leading-relaxed text-dk-muted">
              Create channels, organize conversations by topic, reply in threads, and share files. DClaw Copilot — your AI assistant — lives right inside every channel.
            </p>
            <ul className="mt-8 space-y-3">
              <Check>Auto-classified topics (frontend, backend, devops, bug…)</Check>
              <Check>Threaded replies with reply count</Check>
              <Check>File & image uploads with media gallery</Check>
              <Check>Link unfurling with rich previews</Check>
              <Check>DClaw Copilot AI replies in every channel</Check>
              <Check>Real-time typing indicators over WebSocket</Check>
            </ul>
          </div>
          {/* Mock channel UI */}
          <div className="rounded-2xl border border-white/8 bg-dk-surface-raised overflow-hidden shadow-dk-lg">
            {/* Sidebar */}
            <div className="flex h-72">
              <div className="w-40 border-r border-white/5 bg-dk-surface p-3 space-y-1">
                <p className="text-[9px] font-semibold text-dk-muted uppercase tracking-widest px-2 mb-2">Channels</p>
                {[
                  { name: "general", active: true },
                  { name: "engineering", active: false },
                  { name: "design", active: false },
                  { name: "random", active: false },
                ].map(({ name, active }) => (
                  <div key={name} className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-xs ${
                    active ? "bg-blue-600/20 text-blue-300" : "text-dk-muted"
                  }`}>
                    <span className="text-[10px]">#</span>{name}
                  </div>
                ))}
                <div className="pt-3 border-t border-white/5 mt-2">
                  <p className="text-[9px] font-semibold text-dk-muted uppercase tracking-widest px-2 mb-1.5">Topics</p>
                  {["bug","feature","backend"].map((t) => (
                    <div key={t} className="px-2 py-0.5 text-[10px] text-dk-muted">{t} <span className="text-dk-muted-darker">·3</span></div>
                  ))}
                </div>
              </div>
              {/* Messages area */}
              <div className="flex-1 p-4 space-y-3 overflow-hidden">
                {[
                  { user: "Sam", color: "bg-violet-700", msg: "Just pushed the WebRTC fix 🎉", time: "2:14 PM" },
                  { user: "Alex", color: "bg-green-700", msg: "Nice! Merging now.", time: "2:15 PM" },
                  { user: "AI", color: "bg-blue-700", msg: "Merge complete. No conflicts detected.", time: "2:15 PM" },
                ].map(({ user, color, msg, time }) => (
                  <div key={user + time} className="flex items-start gap-2">
                    <div className={`h-6 w-6 shrink-0 rounded-full ${color} flex items-center justify-center text-[9px] font-bold text-white`}>
                      {user[0]}
                    </div>
                    <div>
                      <div className="flex items-baseline gap-2">
                        <span className="text-[11px] font-semibold text-white">{user}</span>
                        <span className="text-[9px] text-dk-muted">{time}</span>
                      </div>
                      <p className="text-[11px] text-dk-muted leading-snug">{msg}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Meetings section ──────────────────────────────────────────────────────────

function MeetingsSection() {
  return (
    <section className="py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="rounded-3xl border border-white/8 bg-gradient-to-br from-violet-950/40 to-dk-surface p-10 lg:p-16">
          <div className="grid items-center gap-10 lg:grid-cols-2">
            <div>
              <SectionLabel>AI Meetings</SectionLabel>
              <h2 className="font-display text-4xl font-bold text-white">
                Never miss what <GradientText>matters</GradientText>
              </h2>
              <p className="mt-4 leading-relaxed text-dk-muted">
                Record your meetings and let Whisper STT transcribe everything automatically. The AI then produces a clean bullet-point summary — decisions, action items, and next steps.
              </p>
              <ul className="mt-6 space-y-3">
                <Check>Whisper-powered speech-to-text transcription</Check>
                <Check>LLM-generated bullet summaries with action items</Check>
                <Check>Attendee tracking and meeting metadata</Check>
                <Check>Searchable meeting history</Check>
              </ul>
            </div>
            {/* Mock summary card */}
            <div className="rounded-2xl border border-white/8 bg-dk-surface p-6 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-white">Q2 Planning — May 15</span>
                <span className="text-xs text-dk-muted">47 min</span>
              </div>
              <div className="space-y-2">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-dk-muted">AI Summary</p>
                {[
                  "Agreed to ship WebRTC calls in v1.4 by end of May",
                  "Sam owns the Whisper STT integration",
                  "Design review scheduled for next Thursday",
                  "Privacy audit before any cloud deployment",
                ].map((point) => (
                  <div key={point} className="flex items-start gap-2 text-xs text-dk-muted">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-400" />
                    {point}
                  </div>
                ))}
              </div>
              <div className="border-t border-white/5 pt-3 flex items-center gap-2">
                <Globe className="h-3 w-3 text-dk-muted" />
                <span className="text-[10px] text-dk-muted">Attendees: Alex, Sam, Jordan, You</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Security section ──────────────────────────────────────────────────────────

function SecuritySection() {
  return (
    <section id="security" className="py-24">
      <div className="mx-auto max-w-6xl px-6 text-center">
        <SectionLabel>Privacy & Security</SectionLabel>
        <h2 className="font-display text-4xl font-bold text-white">
          Enterprise security, <GradientText>zero compromise</GradientText>
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-dk-muted">
          Built from the ground up for teams that can't afford data leaks. Every feature is designed with privacy as the default.
        </p>
        <div className="mt-12 grid gap-4 sm:grid-cols-3">
          {[
            {
              icon: Shield,
              title: "ClawShield PII Guard",
              body: "Automatically detects and redacts emails, phone numbers, SSNs, and other PII before any AI model sees your data.",
              color: "text-blue-400 bg-blue-500/10 border-blue-500/20",
            },
            {
              icon: Lock,
              title: "Local LLM Execution",
              body: "All AI inference runs on your own hardware via Ollama. Your conversations never leave your network.",
              color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
            },
            {
              icon: Zap,
              title: "Zero-Trust Architecture",
              body: "JWT authentication, role-based access, and encrypted channels. Built to meet GDPR, HIPAA, and SOC 2 requirements.",
              color: "text-green-400 bg-green-500/10 border-green-500/20",
            },
          ].map(({ icon: Icon, title, body, color }) => (
            <div key={title} className="rounded-2xl border border-white/8 bg-dk-surface-raised p-8 text-left">
              <div className={`mb-4 inline-flex rounded-xl border p-3 ${color}`}>
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="mb-2 font-display text-base font-semibold text-white">{title}</h3>
              <p className="text-sm leading-relaxed text-dk-muted">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Personalize section ───────────────────────────────────────────────────────

function PersonalizeSection() {
  return (
    <section id="personalize" className="py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid items-center gap-12 lg:grid-cols-2">
          {/* Mock Settings dialog */}
          <div className="rounded-2xl border border-white/8 bg-dk-surface-raised overflow-hidden shadow-dk-lg">
            <div className="flex items-center justify-between border-b border-white/5 px-4 py-3">
              <div className="flex items-center gap-2">
                <SettingsIcon className="h-4 w-4 text-blue-400" />
                <span className="text-sm font-semibold text-white">Settings</span>
              </div>
              <span className="text-[10px] text-dk-muted">esc to close</span>
            </div>
            <div className="space-y-5 p-5">
              {/* Theme */}
              <div>
                <p className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-dk-muted">
                  <Palette className="h-3 w-3" /> Appearance
                </p>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { Icon: Sun, label: "Light", active: false },
                    { Icon: Moon, label: "Dark", active: true },
                    { Icon: Monitor, label: "System", active: false },
                  ].map(({ Icon, label, active }) => (
                    <div
                      key={label}
                      className={`flex flex-col items-center gap-1 rounded-md border px-2 py-2 text-[11px] ${
                        active
                          ? "border-blue-500 bg-blue-500/10 text-white"
                          : "border-white/10 text-dk-muted"
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                      {label}
                    </div>
                  ))}
                </div>
              </div>
              {/* Model */}
              <div>
                <p className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-dk-muted">
                  <Cpu className="h-3 w-3" /> Default model
                </p>
                <div className="rounded-md border border-white/10 bg-dk-surface px-3 py-2 text-xs text-white">
                  Gemma 4B
                </div>
              </div>
              {/* Temperature */}
              <div>
                <div className="mb-2 flex items-center justify-between text-[10px] font-semibold uppercase tracking-widest text-dk-muted">
                  <span className="flex items-center gap-1.5">
                    <Sparkles className="h-3 w-3" /> Temperature
                  </span>
                  <span className="font-mono text-white">0.70</span>
                </div>
                <div className="relative h-1.5 rounded-full bg-white/10">
                  <div className="absolute inset-y-0 left-0 w-[70%] rounded-full bg-blue-500" />
                  <div className="absolute left-[70%] -top-1 h-3.5 w-3.5 -translate-x-1/2 rounded-full bg-blue-400 ring-2 ring-blue-500/40" />
                </div>
                <div className="mt-1 flex justify-between text-[9px] text-dk-muted">
                  <span>Focused</span>
                  <span>Creative</span>
                </div>
              </div>
            </div>
          </div>

          {/* Text */}
          <div>
            <SectionLabel>Personalize</SectionLabel>
            <h2 className="font-display text-4xl font-bold text-white">
              Make it <GradientText>yours</GradientText>
            </h2>
            <p className="mt-4 leading-relaxed text-dk-muted">
              Every setting respects your preferences and persists across sessions.
              Switch between Light, Dark, and System themes, pick your default model,
              and tune how creative the AI should be — without leaving the chat.
            </p>
            <ul className="mt-8 space-y-3">
              <Check>Light, Dark, and System theme modes — switches instantly</Check>
              <Check>Persistent default model that loads on every visit</Check>
              <Check>Temperature slider tunes AI focus vs. creativity</Check>
              <Check>One-click clear-all-conversations with confirm step</Check>
              <Check>API endpoint shown for self-host debugging</Check>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── CTA ───────────────────────────────────────────────────────────────────────

function CTA() {
  return (
    <section className="py-24">
      <div className="mx-auto max-w-3xl px-6 text-center">
        <div className="relative rounded-3xl border border-blue-500/20 bg-gradient-to-b from-blue-950/50 to-dk-surface p-14 overflow-hidden">
          <div className="pointer-events-none absolute inset-0 -z-10">
            <div className="absolute left-1/2 top-0 h-64 w-64 -translate-x-1/2 rounded-full bg-blue-600/15 blur-3xl" />
          </div>
          <h2 className="font-display text-4xl font-bold text-white">
            Ready to transform <br />
            <GradientText>how your team works?</GradientText>
          </h2>
          <p className="mt-4 text-dk-muted">
            DClaw Chat is open-source and self-hostable. Get started in minutes.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/app"
              className="flex items-center gap-2 rounded-xl bg-blue-600 px-8 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-900/40 transition-all hover:bg-blue-500 hover:-translate-y-0.5"
            >
              Open DClaw Chat
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Footer ────────────────────────────────────────────────────────────────────

function Footer() {
  return (
    <footer className="border-t border-white/5 py-10">
      <div className="mx-auto max-w-6xl px-6 flex flex-col items-center gap-3 sm:flex-row sm:justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-blue-600 text-xs">💬</div>
          <span className="text-sm font-semibold text-white">DClaw Chat</span>
        </div>
        <p className="text-xs text-dk-muted">© 2026 DClaw Stack. All rights reserved.</p>
        <div className="flex gap-4 text-xs text-dk-muted">
          <a href="#" className="hover:text-white transition-colors">Privacy</a>
          <a href="#" className="hover:text-white transition-colors">Terms</a>
          <a href="https://github.com/dclawstack/dclaw-chat" className="hover:text-white transition-colors">GitHub</a>
        </div>
      </div>
    </footer>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-dk-surface text-dk-body antialiased">
      <Navbar />
      <main>
        <Hero />
        <SeedControls />
        <FeaturesGrid />
        <CallsSection />
        <AISection />
        <ChannelsSection />
        <MeetingsSection />
        <SecuritySection />
        <PersonalizeSection />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
