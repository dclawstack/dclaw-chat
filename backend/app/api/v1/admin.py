"""
Demo seed/clear endpoints for the landing page.

This module is intentionally self-contained so it can be removed cleanly
later. To remove: delete this file and the `admin_router` line in
`app/api/v1/__init__.py`, then remove `<SeedControls />` from the landing page.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.bot import BotORM
from app.models.call import CallRoomORM
from app.models.channel import ChannelMessageORM, ChannelORM
from app.models.conversation import ConversationORM
from app.models.huddle import HuddleParticipantORM, HuddleRoomORM
from app.models.meeting import MeetingORM
from app.models.message import MessageORM

router = APIRouter()

SEED_MARKER = "demo-seed"


def _require_admin_enabled() -> None:
    """Fail-closed guard for destructive admin endpoints.

    Returns 404 (rather than 403) unless ADMIN_ENABLED is explicitly set, so the
    seed/clear endpoints are effectively invisible in any environment that hasn't
    opted in. They wipe all data, so they must never be open by default.
    """
    if not get_settings().admin_enabled:
        raise HTTPException(status_code=404)


def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/seed")
async def seed_demo_data(db: AsyncSession = Depends(get_db)) -> dict:
    """Populate the database with realistic demo data across every feature."""
    _require_admin_enabled()
    # Clear first so seeding is idempotent
    await _wipe_all(db)

    counts = {
        "conversations": 0,
        "messages": 0,
        "channels": 0,
        "channel_messages": 0,
        "meetings": 0,
        "huddles": 0,
        "huddle_participants": 0,
        "bots": 0,
        "call_rooms": 0,
    }

    now = _now()

    # ── AI Conversations ────────────────────────────────────────────────
    conversations_data = [
        {
            "title": "Q2 architecture review",
            "folder": "Work",
            "model": "gemma3:4b",
            "messages": [
                ("user", "Summarize our Q2 architecture decisions so far."),
                (
                    "assistant",
                    "Here are the key Q2 decisions:\n\n"
                    "1. Migrated the backend to async FastAPI with PostgreSQL.\n"
                    "2. Adopted WebRTC for browser-native peer-to-peer calls.\n"
                    "3. Integrated Whisper STT for live meeting transcription.\n"
                    "4. Deployed ClawShield PII guard in front of every LLM call.",
                ),
                ("user", "Which of these has the most risk?"),
                (
                    "assistant",
                    "The WebRTC rollout carries the highest risk because of NAT traversal "
                    "edge cases on enterprise networks. I'd recommend a staged rollout with "
                    "a TURN fallback before exposing it to all customers.",
                ),
            ],
        },
        {
            "title": "Brainstorm: onboarding flow",
            "folder": "Product",
            "model": "kimi-k2-thinking",
            "messages": [
                ("user", "Give me five onboarding ideas for a privacy-first chat app."),
                (
                    "assistant",
                    "1. A short interactive tour that ends with the user sending their first message to a local model.\n"
                    "2. A privacy checklist that shows exactly which data stays on-device.\n"
                    "3. Pre-installed sample bots so new users see automation immediately.\n"
                    "4. A 'bring your own model' wizard that pulls Ollama models with one click.\n"
                    "5. A scripted demo conversation new users can replay at any time.",
                ),
            ],
        },
        {
            "title": "Rust vs. Go for the relay service",
            "folder": "Engineering",
            "model": "gemma3:4b",
            "messages": [
                ("user", "Compare Rust and Go for our WebRTC SFU relay."),
                (
                    "assistant",
                    "Both work, but they optimize for different things:\n\n"
                    "**Rust** — best raw throughput, zero-cost abstractions, no GC pauses. "
                    "Steeper learning curve, slower iteration.\n\n"
                    "**Go** — simpler concurrency model, faster to ship, mature `pion/webrtc` "
                    "library already covers SFU primitives.\n\n"
                    "For a v1 relay where time-to-ship matters, I'd start with Go and revisit "
                    "if profiling shows GC stalls on hot media paths.",
                ),
            ],
        },
        {
            "title": "Draft release notes — v1.4",
            "folder": "Product",
            "model": "kimi-k2-thinking",
            "messages": [
                ("user", "Draft user-facing release notes for v1.4."),
                (
                    "assistant",
                    "## DClaw Chat v1.4\n\n"
                    "- 🎥 **WebRTC voice & video calls** with pre-join lobby and screen sharing.\n"
                    "- 🧠 **Swarm AI** automatically routes your prompts to specialist agents.\n"
                    "- 🛡️ **ClawShield PII guard** redacts sensitive data before it reaches any LLM.\n"
                    "- 🎙️ **AI meeting summaries** powered by Whisper STT.\n"
                    "- 🌓 **Light, Dark, and System themes** — switches instantly.",
                ),
            ],
        },
        {
            "title": "Personal — book recommendations",
            "folder": "Personal",
            "model": "gemma3:4b",
            "messages": [
                ("user", "Recommend three books on systems thinking."),
                (
                    "assistant",
                    "1. *Thinking in Systems* by Donella Meadows — the classic primer.\n"
                    "2. *The Fifth Discipline* by Peter Senge — systems thinking in organizations.\n"
                    "3. *Designing Data-Intensive Applications* by Martin Kleppmann — systems thinking applied to software.",
                ),
            ],
        },
    ]

    for idx, conv in enumerate(conversations_data):
        conv_id = _uid()
        created = now - timedelta(days=idx, hours=2)
        db.add(
            ConversationORM(
                id=conv_id,
                title=f"[{SEED_MARKER}] {conv['title']}",
                folder=conv["folder"],
                model=conv["model"],
                created_at=created,
                updated_at=created,
            )
        )
        counts["conversations"] += 1
        for m_idx, (role, content) in enumerate(conv["messages"]):
            db.add(
                MessageORM(
                    id=_uid(),
                    conversation_id=conv_id,
                    role=role,
                    content=content,
                    model=conv["model"] if role == "assistant" else None,
                    created_at=created + timedelta(minutes=m_idx * 2),
                )
            )
            counts["messages"] += 1

    # ── Team Channels ───────────────────────────────────────────────────
    channels_data = [
        {
            "name": "general",
            "type": "public",
            "messages": [
                ("u-alex", "Alex Chen", "Morning everyone 👋", "general", None),
                ("u-sam", "Sam Patel", "Sprint planning at 10? Same room as last week.", "general", None),
                ("u-jordan", "Jordan Lee", "Can't make 10, conflict with the design review. Notes after?", "general", None),
                ("u-ai", "DClaw Copilot", "I'll capture the notes and post a summary here when the meeting ends.", "general", None),
            ],
        },
        {
            "name": "engineering",
            "type": "public",
            "messages": [
                ("u-sam", "Sam Patel", "Pushed the WebRTC NAT fix to staging. Mind giving it a smoke test?", "backend", None),
                ("u-alex", "Alex Chen", "On it. Will report back in ~20 min.", "backend", None),
                ("u-alex", "Alex Chen", "Smoke test passed across Chrome / Safari / Firefox. Merging.", "backend", None),
                ("u-jordan", "Jordan Lee", "Frontend build is green too. Bundle size down 12kb after the lazy-load change.", "frontend", None),
                ("u-sam", "Sam Patel", "Nice. That's the third week in a row it's shrunk.", "frontend", None),
            ],
        },
        {
            "name": "design",
            "type": "public",
            "messages": [
                ("u-jordan", "Jordan Lee", "Posted new mockups for the call lobby. Feedback welcome.", "design", None),
                ("u-alex", "Alex Chen", "Love the camera preview placement. Much clearer than v3.", "design", None),
            ],
        },
        {
            "name": "random",
            "type": "public",
            "messages": [
                ("u-sam", "Sam Patel", "Coffee delivery downstairs ☕", None, None),
                ("u-jordan", "Jordan Lee", "On my way 🏃", None, None),
            ],
        },
    ]

    for idx, ch in enumerate(channels_data):
        ch_id = _uid()
        db.add(
            ChannelORM(
                id=ch_id,
                name=f"{SEED_MARKER}-{ch['name']}",
                type=ch["type"],
                created_at=now - timedelta(days=7 - idx),
            )
        )
        counts["channels"] += 1
        for m_idx, (uid, name, body, topic, attachments) in enumerate(ch["messages"]):
            db.add(
                ChannelMessageORM(
                    id=_uid(),
                    channel_id=ch_id,
                    user_id=uid,
                    user_name=name,
                    content=body,
                    topic=topic,
                    attachments=attachments,
                    created_at=now - timedelta(days=7 - idx, hours=2, minutes=-m_idx * 5),
                )
            )
            counts["channel_messages"] += 1

    # ── AI Meetings ─────────────────────────────────────────────────────
    meetings_data = [
        {
            "title": "Q2 Planning",
            "duration": 47 * 60,
            "transcript": (
                "Alex: Let's lock in the v1.4 scope.\n"
                "Sam: I think we ship WebRTC and meetings by end of May.\n"
                "Jordan: Design review for the lobby is on Thursday.\n"
                "Alex: Privacy audit needs to land before any cloud deployment.\n"
            ),
            "summary": (
                "- Agreed to ship WebRTC calls in v1.4 by end of May.\n"
                "- Sam owns the Whisper STT integration.\n"
                "- Design review for the call lobby is scheduled for Thursday.\n"
                "- Privacy audit must complete before any cloud deployment.\n"
            ),
            "action_items": json.dumps([
                {"text": "Finish Whisper STT integration by 2026-05-30", "priority": "high", "assignee": "Sam", "status": "open"},
                {"text": "Host call-lobby design review on 2026-05-28", "priority": "medium", "assignee": "Jordan", "status": "open"},
                {"text": "Schedule privacy audit before 2026-06-05", "priority": "high", "assignee": "Alex", "status": "open"},
            ]),
        },
        {
            "title": "Customer feedback — Acme",
            "duration": 32 * 60,
            "transcript": (
                "Acme PM: We'd love a way to install bots from the marketplace per-channel.\n"
                "Alex: Noted — that's already on the roadmap for v1.5.\n"
                "Acme PM: Also: SSO via Okta is a hard requirement for the rollout.\n"
            ),
            "summary": (
                "- Acme wants per-channel bot installs (already roadmapped for v1.5).\n"
                "- Okta SSO is a blocker for their company-wide rollout.\n"
                "- Follow-up demo scheduled for next week.\n"
            ),
            "action_items": json.dumps([
                {"text": "Confirm Okta SSO ETA with Acme by 2026-06-02", "priority": "high", "assignee": "Alex", "status": "open"},
            ]),
        },
        {
            "title": "Weekly engineering sync",
            "duration": 28 * 60,
            "transcript": (
                "Sam: Backend tests are green on main.\n"
                "Jordan: Frontend bundle shrank 12kb this week.\n"
                "Alex: We have one open P1 — the iOS Safari mic permission bug.\n"
            ),
            "summary": (
                "- All backend tests green on main.\n"
                "- Frontend bundle reduced by 12kb after lazy-loading work.\n"
                "- One open P1: iOS Safari mic permission flow needs a fix.\n"
            ),
            "action_items": json.dumps([
                {"text": "Fix iOS Safari mic permission flow by 2026-05-29", "priority": "high", "assignee": "Jordan", "status": "open"},
            ]),
        },
    ]

    for idx, mt in enumerate(meetings_data):
        db.add(
            MeetingORM(
                id=_uid(),
                title=f"[{SEED_MARKER}] {mt['title']}",
                duration_seconds=mt["duration"],
                status="done",
                transcript=mt["transcript"],
                summary=mt["summary"],
                action_items=mt["action_items"],
                created_by="dev-user",
                created_at=now - timedelta(days=idx * 3),
            )
        )
        counts["meetings"] += 1

    # ── Huddles ─────────────────────────────────────────────────────────
    huddles_data = [
        {
            "name": "Quick frontend sync",
            "status": "active",
            "participants": [
                ("u-alex", "Alex Chen", False, False),
                ("u-jordan", "Jordan Lee", True, False),
            ],
        },
        {
            "name": "Bug triage",
            "status": "active",
            "participants": [
                ("u-sam", "Sam Patel", True, False),
                ("u-alex", "Alex Chen", False, True),
                ("u-jordan", "Jordan Lee", False, False),
            ],
        },
        {
            "name": "Friday wind-down",
            "status": "closed",
            "participants": [
                ("u-sam", "Sam Patel", False, False),
                ("u-jordan", "Jordan Lee", False, False),
            ],
        },
    ]

    for idx, hd in enumerate(huddles_data):
        room_id = _uid()
        closed = now - timedelta(days=2) if hd["status"] == "closed" else None
        db.add(
            HuddleRoomORM(
                id=room_id,
                name=f"[{SEED_MARKER}] {hd['name']}",
                created_by="dev-user",
                status=hd["status"],
                created_at=now - timedelta(hours=idx + 1),
                closed_at=closed,
            )
        )
        counts["huddles"] += 1
        for uid, name, speaking, muted in hd["participants"]:
            db.add(
                HuddleParticipantORM(
                    id=_uid(),
                    room_id=room_id,
                    user_id=uid,
                    display_name=name,
                    is_speaking=speaking,
                    is_muted=muted,
                )
            )
            counts["huddle_participants"] += 1

    # ── Bot Marketplace ─────────────────────────────────────────────────
    bots_data = [
        ("Standup Bot", "standup", "Collects daily standup updates and posts a digest.", "📋", "productivity", True),
        ("Deploy Bot", "deploy", "Triggers deployments and reports build status.", "🚀", "devops", True),
        ("Polls", "polls", "Run quick polls right inside any channel.", "📊", "productivity", False),
        ("PR Buddy", "pr-buddy", "Summarizes incoming pull requests with AI.", "🔍", "devops", True),
        ("Coffee Roulette", "coffee", "Randomly pairs teammates for coffee chats.", "☕", "social", False),
        ("Status Page", "status", "Posts incidents from your status page into a channel.", "⚠️", "monitoring", False),
    ]

    for idx, (name, slug, desc, emoji, category, installed) in enumerate(bots_data):
        db.add(
            BotORM(
                id=_uid(),
                name=name,
                slug=f"{SEED_MARKER}-{slug}",
                description=desc,
                avatar_emoji=emoji,
                category=category,
                installed=installed,
                enabled=True,
                commands=json.dumps([{"name": f"/{slug}", "description": desc}]),
                created_at=now - timedelta(days=idx),
            )
        )
        counts["bots"] += 1

    # ── Call Rooms ──────────────────────────────────────────────────────
    calls_data = [
        ("Daily standup", "active", False),
        ("Customer demo — Acme", "waiting", True),
        ("All-hands rehearsal", "ended", True),
    ]

    for idx, (title, status, recording) in enumerate(calls_data):
        ended = now - timedelta(hours=4) if status == "ended" else None
        db.add(
            CallRoomORM(
                id=_uid(),
                title=f"[{SEED_MARKER}] {title}",
                host_id="dev-user",
                status=status,
                max_participants=50,
                recording_enabled=recording,
                created_at=now - timedelta(hours=idx + 1),
                ended_at=ended,
            )
        )
        counts["call_rooms"] += 1

    await db.commit()
    return {"status": "seeded", "counts": counts}


@router.post("/clear")
async def clear_all_data(db: AsyncSession = Depends(get_db)) -> dict:
    """Wipe all data from every table — both demo and user-created."""
    _require_admin_enabled()
    counts = await _wipe_all(db)
    await db.commit()
    return {"status": "cleared", "counts": counts}


async def _wipe_all(db: AsyncSession) -> dict:
    """Delete every row from every table. Caller is responsible for commit."""
    counts: dict[str, int] = {}
    # Order matters: child tables first to respect FKs even when CASCADE is set.
    for model, key in [
        (MessageORM, "messages"),
        (ConversationORM, "conversations"),
        (ChannelMessageORM, "channel_messages"),
        (ChannelORM, "channels"),
        (HuddleParticipantORM, "huddle_participants"),
        (HuddleRoomORM, "huddles"),
        (MeetingORM, "meetings"),
        (BotORM, "bots"),
        (CallRoomORM, "call_rooms"),
    ]:
        result = await db.execute(delete(model))
        counts[key] = result.rowcount or 0
    return counts
