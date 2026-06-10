"""Bot marketplace and slash-command execution API."""
from __future__ import annotations

import json
import uuid
import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db, async_session
from app.core.deps import get_current_user, CurrentUser
from app.core.exceptions import ForbiddenException
from app.models.bot import BotORM
from app.models.channel import ChannelMessageORM
from app.services.command_parser import parse_command, execute_command

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class CommandDef(BaseModel):
    name: str
    description: str = ""
    usage: str = ""
    params: List[dict] = []


class BotCreate(BaseModel):
    name: str
    slug: str
    description: str = ""
    avatar_emoji: Optional[str] = None
    webhook_url: Optional[str] = None
    commands: List[CommandDef] = []
    category: str = "general"


class BotUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    avatar_emoji: Optional[str] = None
    webhook_url: Optional[str] = None
    commands: Optional[List[CommandDef]] = None
    category: Optional[str] = None
    enabled: Optional[bool] = None


class BotOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    avatar_emoji: Optional[str]
    webhook_url: Optional[str]
    commands: List[CommandDef]
    category: str
    installed: bool
    enabled: bool
    created_at: str
    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_obj(cls, bot: BotORM) -> "BotOut":
        cmds: List[CommandDef] = []
        if bot.commands:
            try:
                raw = json.loads(bot.commands)
                cmds = [CommandDef(**c) for c in raw]
            except Exception:
                pass
        return cls(
            id=bot.id,
            name=bot.name,
            slug=bot.slug,
            description=bot.description or "",
            avatar_emoji=bot.avatar_emoji,
            webhook_url=bot.webhook_url,
            commands=cmds,
            category=bot.category or "general",
            installed=bot.installed,
            enabled=bot.enabled,
            created_at=bot.created_at.isoformat(),
        )


class CommandExecuteRequest(BaseModel):
    content: str
    channel_id: str


# ── Seed data ─────────────────────────────────────────────────────────────────

_SEED_BOTS = [
    {
        "name": "GitHub Bot",
        "slug": "github",
        "description": "Get pull request info, create issues, and trigger workflows from chat.",
        "avatar_emoji": "🐙",
        "webhook_url": None,
        "commands": [
            {"name": "pr", "description": "Show open pull requests", "usage": "/pr [repo]", "params": [{"name": "repo", "description": "Repository name", "required": False}]},
            {"name": "issue", "description": "Create a GitHub issue", "usage": "/issue <title>", "params": [{"name": "title", "description": "Issue title", "required": True}]},
            {"name": "deploy", "description": "Trigger a deployment workflow", "usage": "/deploy [env]", "params": [{"name": "env", "description": "Target environment (default: staging)", "required": False}]},
        ],
        "category": "developer",
    },
    {
        "name": "Remind Me",
        "slug": "remind",
        "description": "Set reminders and scheduled messages for your team.",
        "avatar_emoji": "⏰",
        "webhook_url": None,
        "commands": [
            {"name": "remind", "description": "Set a reminder", "usage": "/remind <message> in <time>", "params": [{"name": "message", "description": "What to remind", "required": True}, {"name": "time", "description": "When (e.g. 10m, 2h)", "required": True}]},
            {"name": "reminders", "description": "List your active reminders", "usage": "/reminders", "params": []},
        ],
        "category": "productivity",
    },
    {
        "name": "Standup Bot",
        "slug": "standup",
        "description": "Automate daily standups and collect team updates.",
        "avatar_emoji": "📋",
        "webhook_url": None,
        "commands": [
            {"name": "standup", "description": "Submit your standup update", "usage": "/standup <update>", "params": [{"name": "update", "description": "Your standup text", "required": True}]},
            {"name": "summary", "description": "Show today's standup summary", "usage": "/summary", "params": []},
        ],
        "category": "productivity",
    },
    {
        "name": "Poll Bot",
        "slug": "poll",
        "description": "Create quick polls and votes in any channel.",
        "avatar_emoji": "📊",
        "webhook_url": None,
        "commands": [
            {"name": "poll", "description": "Create a poll", "usage": '/poll "Question" "Option1" "Option2"', "params": [{"name": "question", "description": "Poll question", "required": True}, {"name": "options", "description": "Poll options (space-separated quoted strings)", "required": True}]},
            {"name": "vote", "description": "Vote on a poll", "usage": "/vote <poll_id> <option>", "params": [{"name": "poll_id", "description": "Poll ID", "required": True}, {"name": "option", "description": "Option to vote for", "required": True}]},
        ],
        "category": "fun",
    },
    {
        "name": "Jira Bot",
        "slug": "jira",
        "description": "Manage Jira tickets, sprints, and boards from chat.",
        "avatar_emoji": "🎯",
        "webhook_url": None,
        "commands": [
            {"name": "ticket", "description": "Create a Jira ticket", "usage": "/ticket <summary>", "params": [{"name": "summary", "description": "Ticket summary", "required": True}]},
            {"name": "sprint", "description": "Show current sprint status", "usage": "/sprint", "params": []},
            {"name": "assign", "description": "Assign a ticket", "usage": "/assign <ticket_id> <user>", "params": [{"name": "ticket_id", "description": "Ticket ID", "required": True}, {"name": "user", "description": "Assignee", "required": True}]},
        ],
        "category": "developer",
    },
    {
        "name": "Weather Bot",
        "slug": "weather",
        "description": "Get real-time weather forecasts for any location.",
        "avatar_emoji": "🌤️",
        "webhook_url": None,
        "commands": [
            {"name": "weather", "description": "Get weather for a location", "usage": "/weather <city>", "params": [{"name": "city", "description": "City name", "required": True}]},
            {"name": "forecast", "description": "Get 5-day forecast", "usage": "/forecast <city>", "params": [{"name": "city", "description": "City name", "required": True}]},
        ],
        "category": "fun",
    },
]


async def _seed_bots(db: AsyncSession) -> None:
    for seed in _SEED_BOTS:
        existing = await db.execute(select(BotORM).where(BotORM.slug == seed["slug"]))
        if existing.scalar_one_or_none():
            continue
        cmds = seed.pop("commands", [])
        bot = BotORM(
            id=str(uuid.uuid4()),
            commands=json.dumps(cmds),
            **seed,
        )
        seed["commands"] = cmds  # restore for idempotency
        db.add(bot)
    await db.commit()


def _assert_owner(bot: BotORM, user: CurrentUser) -> None:
    """403 on another user's bot. NULL owner = legacy-shared row
    (same fail-open policy as conversations)."""
    if bot.created_by and bot.created_by != user.user_id:
        raise ForbiddenException("Not your bot")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[BotOut])
async def list_bots(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    await _seed_bots(db)
    q = select(BotORM)
    if category:
        q = q.where(BotORM.category == category)
    result = await db.execute(q.order_by(BotORM.name))
    bots = list(result.scalars().all())
    return [BotOut.from_orm_obj(b) for b in bots]


@router.post("", response_model=BotOut, status_code=201)
async def create_bot(
    req: BotCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    existing = await db.execute(select(BotORM).where(BotORM.slug == req.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Bot with slug '{req.slug}' already exists")
    bot = BotORM(
        id=str(uuid.uuid4()),
        name=req.name,
        slug=req.slug,
        description=req.description,
        avatar_emoji=req.avatar_emoji,
        webhook_url=req.webhook_url,
        commands=json.dumps([c.model_dump() for c in req.commands]),
        category=req.category,
        installed=True,
        created_by=user.user_id,
    )
    db.add(bot)
    await db.commit()
    await db.refresh(bot)
    return BotOut.from_orm_obj(bot)


@router.get("/{bot_id}", response_model=BotOut)
async def get_bot(
    bot_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    bot = await db.get(BotORM, bot_id)
    if not bot:
        raise HTTPException(404, "Bot not found")
    return BotOut.from_orm_obj(bot)


@router.put("/{bot_id}", response_model=BotOut)
async def update_bot(
    bot_id: str,
    req: BotUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    bot = await db.get(BotORM, bot_id)
    if not bot:
        raise HTTPException(404, "Bot not found")
    _assert_owner(bot, user)
    if req.name is not None:
        bot.name = req.name
    if req.description is not None:
        bot.description = req.description
    if req.avatar_emoji is not None:
        bot.avatar_emoji = req.avatar_emoji
    if req.webhook_url is not None:
        bot.webhook_url = req.webhook_url
    if req.commands is not None:
        bot.commands = json.dumps([c.model_dump() for c in req.commands])
    if req.category is not None:
        bot.category = req.category
    if req.enabled is not None:
        bot.enabled = req.enabled
    await db.commit()
    await db.refresh(bot)
    return BotOut.from_orm_obj(bot)


@router.delete("/{bot_id}", status_code=204)
async def delete_bot(
    bot_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    bot = await db.get(BotORM, bot_id)
    if not bot:
        raise HTTPException(404, "Bot not found")
    _assert_owner(bot, user)
    await db.delete(bot)
    await db.commit()


@router.post("/{bot_id}/install", response_model=BotOut)
async def install_bot(
    bot_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    bot = await db.get(BotORM, bot_id)
    if not bot:
        raise HTTPException(404, "Bot not found")
    bot.installed = True
    await db.commit()
    await db.refresh(bot)
    return BotOut.from_orm_obj(bot)


@router.post("/{bot_id}/uninstall", response_model=BotOut)
async def uninstall_bot(
    bot_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    bot = await db.get(BotORM, bot_id)
    if not bot:
        raise HTTPException(404, "Bot not found")
    bot.installed = False
    await db.commit()
    await db.refresh(bot)
    return BotOut.from_orm_obj(bot)


@router.get("/commands/all")
async def list_commands(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Return all commands from installed & enabled bots."""
    result = await db.execute(
        select(BotORM).where(BotORM.installed == True, BotORM.enabled == True)  # noqa: E712
    )
    bots = list(result.scalars().all())
    out = []
    for bot in bots:
        cmds = []
        if bot.commands:
            try:
                cmds = json.loads(bot.commands)
            except Exception:
                pass
        for cmd in cmds:
            out.append({
                "bot_id": bot.id,
                "bot_name": bot.name,
                "bot_slug": bot.slug,
                "bot_avatar": bot.avatar_emoji,
                **cmd,
            })
    return out


@router.post("/commands/execute")
async def run_command(
    req: CommandExecuteRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Parse and execute a slash command, persisting the bot reply."""
    cmd = parse_command(req.content)
    if not cmd:
        raise HTTPException(400, "Not a slash command")

    # Find a matching installed bot
    result = await db.execute(
        select(BotORM).where(BotORM.installed == True, BotORM.enabled == True)  # noqa: E712
    )
    bots = list(result.scalars().all())

    matched_bot: Optional[BotORM] = None
    for bot in bots:
        if not bot.commands:
            continue
        try:
            cmds = json.loads(bot.commands)
        except Exception:
            continue
        if any(c.get("name") == cmd.name for c in cmds):
            matched_bot = bot
            break

    if not matched_bot:
        return {"reply": f"Unknown command `/{cmd.name}`. Type `/help` to see available commands."}

    reply_text = await execute_command(
        command=cmd,
        bot_commands_json=matched_bot.commands,
        webhook_url=matched_bot.webhook_url,
        channel_id=req.channel_id,
        user_id=user.user_id,
        user_name=user.email or user.user_id,
    )

    # Persist bot reply as a channel message
    async with async_session() as write_db:
        bot_msg = ChannelMessageORM(
            id=str(uuid.uuid4()),
            channel_id=req.channel_id,
            user_id=f"bot-{matched_bot.slug}",
            user_name=f"{matched_bot.avatar_emoji or '🤖'} {matched_bot.name}",
            content=reply_text,
        )
        write_db.add(bot_msg)
        await write_db.commit()
        await write_db.refresh(bot_msg)

    return {
        "reply": reply_text,
        "bot_name": matched_bot.name,
        "bot_slug": matched_bot.slug,
    }
