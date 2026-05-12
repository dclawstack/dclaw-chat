"""Slash-command parser and dispatcher."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ParsedCommand:
    raw: str
    name: str
    args: list[str] = field(default_factory=list)

    @property
    def args_str(self) -> str:
        return " ".join(self.args)


def parse_command(text: str) -> Optional[ParsedCommand]:
    """Return a ParsedCommand if *text* starts with '/', else None."""
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    parts = stripped[1:].split()
    if not parts:
        return None
    name = parts[0].lower()
    args = parts[1:]
    return ParsedCommand(raw=stripped, name=name, args=args)


async def dispatch_webhook(
    webhook_url: str,
    command: ParsedCommand,
    channel_id: str,
    user_id: str,
    user_name: str,
) -> Optional[str]:
    """POST command payload to a bot webhook and return its text reply, or None."""
    payload = {
        "command": command.name,
        "args": command.args,
        "text": command.args_str,
        "channel_id": channel_id,
        "user_id": user_id,
        "user_name": user_name,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("text") or data.get("message") or str(data)
    except Exception as exc:
        logger.warning("Webhook dispatch failed for %s: %s", webhook_url, exc)
        return None


def _builtin_help(commands_json: Optional[str]) -> str:
    if not commands_json:
        return "No commands configured for this bot."
    try:
        cmds = json.loads(commands_json)
    except Exception:
        return "Could not load command list."
    if not cmds:
        return "No commands configured for this bot."
    lines = ["**Available commands:**"]
    for cmd in cmds:
        usage = cmd.get("usage") or f"/{cmd.get('name', '?')}"
        desc = cmd.get("description", "")
        lines.append(f"• `{usage}` — {desc}")
    return "\n".join(lines)


async def execute_command(
    command: ParsedCommand,
    bot_commands_json: Optional[str],
    webhook_url: Optional[str],
    channel_id: str,
    user_id: str,
    user_name: str,
) -> str:
    """Dispatch a parsed command and return the reply text to post."""
    if command.name == "help":
        return _builtin_help(bot_commands_json)

    if webhook_url:
        reply = await dispatch_webhook(
            webhook_url, command, channel_id, user_id, user_name
        )
        if reply:
            return reply

    return f"✅ Command `/{command.name}` received."
