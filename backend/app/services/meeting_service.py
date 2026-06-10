import json
import logging
from pathlib import Path
from typing import List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.meeting import MeetingORM
from app.repositories.meeting_repo import MeetingRepository
from app.schemas.meeting import MeetingActionItem
from app.schemas.chat import Message
from app.services.ollama_service import OllamaService, OLLAMA_MODELS
from app.services.model_router import router as model_router
from app.services.files import FileService, UPLOAD_DIR

settings = get_settings()
logger = logging.getLogger(__name__)

DEFAULT_MODEL = next(iter(OLLAMA_MODELS.keys()), "gemma-4b")
AUDIO_MIMES = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/wave", "audio/x-wav",
    "audio/ogg", "audio/webm", "audio/mp4", "audio/m4a", "audio/aac",
    "video/mp4", "video/webm", "video/ogg", "video/quicktime",
}


class WhisperService:
    """Calls OpenAI-compatible Whisper API for audio transcription."""

    def __init__(self):
        self.api_url = getattr(settings, "WHISPER_API_URL", "") or "https://api.openai.com/v1"
        self.api_key = getattr(settings, "OPENAI_API_KEY", "")

    async def transcribe(self, file_path: Path, mime_type: str) -> str:
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not set — returning placeholder transcript")
            return (
                "[Transcription unavailable: OPENAI_API_KEY is not configured. "
                "Set OPENAI_API_KEY or WHISPER_API_URL in your environment to enable "
                "Whisper speech-to-text transcription.]"
            )

        audio_bytes = file_path.read_bytes()
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.api_url}/audio/transcriptions",
                headers=headers,
                files={"file": (file_path.name, audio_bytes, mime_type)},
                data={"model": "whisper-1", "response_format": "verbose_json"},
            )
            response.raise_for_status()
            data = response.json()

        transcript = data.get("text", "").strip()
        logger.info(f"Whisper transcription: {len(transcript)} chars")
        return transcript


class MeetingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = MeetingRepository(db)
        self.ollama = OllamaService()
        self.whisper = WhisperService()
        self.files = FileService()

    def _pick_model(self, model_id: Optional[str]) -> str:
        if model_id and model_id in OLLAMA_MODELS:
            return model_id
        return DEFAULT_MODEL

    async def process_meeting(self, meeting: MeetingORM, model_id: Optional[str] = None) -> MeetingORM:
        """Full pipeline: transcribe → summarize → extract actions."""
        model = self._pick_model(model_id)
        try:
            # Step 1: Transcribe
            await self.repo.update_status(meeting, "transcribing")
            transcript = await self._transcribe(meeting)
            meeting = await self.repo.update_transcript(meeting, transcript)

            # Step 2: Summarize + extract actions
            summary, actions = await self._summarize_and_extract(transcript, model)
            actions_json = json.dumps([a.model_dump() for a in actions])
            meeting = await self.repo.update_summary(meeting, summary, actions_json)

        except Exception as e:
            logger.error(f"Meeting processing failed for {meeting.id}: {e}")
            await self.repo.update_status(meeting, "failed")
            raise

        return meeting

    async def _transcribe(self, meeting: MeetingORM) -> str:
        if not meeting.file_id or not meeting.filename:
            raise ValueError("Meeting has no uploaded file")

        file_path = UPLOAD_DIR / meeting.file_id / meeting.filename
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        mime = meeting.mime_type or "audio/mpeg"
        return await self.whisper.transcribe(file_path, mime)

    async def _summarize_and_extract(
        self, transcript: str, model: str
    ) -> tuple[str, List[MeetingActionItem]]:
        truncated = transcript[:8_000]

        summary_prompt = (
            "You are an AI meeting assistant. Summarize the following meeting transcript "
            "in 4-6 concise bullet points. Highlight key topics, decisions, and outcomes. "
            "Start each bullet with '•'.\n\n"
            f"--- TRANSCRIPT ---\n{truncated}\n---\n\nSummary:"
        )
        summary_messages = [Message(role="user", content=summary_prompt)]
        try:
            # Route through the consensus/model-routing layer (T1: local with
            # cloud fallback). model_override keeps honoring the caller's pick.
            result = await model_router.run(
                "summarize", summary_messages, temperature=0.3, model_override=model
            )
            summary_text = result.content
        except Exception as e:
            # Preserve the pre-router behavior: fall back to a direct local
            # call; if that also fails the exception propagates as before.
            logger.warning(f"Model router summarize failed, using direct Ollama: {e}")
            summary_text = await self.ollama.chat(model, summary_messages, temperature=0.3)

        actions_prompt = (
            "Extract all actionable items from this meeting transcript. "
            "For each action, output exactly one line in this format:\n"
            "ACTION: <action text> | PRIORITY: <low|medium|high> | ASSIGNEE: <name or 'unassigned'>\n\n"
            f"--- TRANSCRIPT ---\n{truncated}\n---\n\nActions:"
        )
        actions_messages = [Message(role="user", content=actions_prompt)]
        raw_actions = await self.ollama.chat(model, actions_messages, temperature=0.2)

        actions = _parse_action_lines(raw_actions)
        return summary_text.strip(), actions


def _parse_action_lines(raw: str) -> List[MeetingActionItem]:
    items: List[MeetingActionItem] = []
    for line in raw.splitlines():
        if "ACTION:" not in line:
            continue
        try:
            parts = {
                p.split(":")[0].strip(): p.split(":", 1)[1].strip()
                for p in line.split("|")
                if ":" in p
            }
            text = parts.get("ACTION", line.strip())
            priority = parts.get("PRIORITY", "medium").lower()
            if priority not in ("low", "medium", "high"):
                priority = "medium"
            assignee = parts.get("ASSIGNEE", "unassigned")
            items.append(MeetingActionItem(
                text=text,
                priority=priority,  # type: ignore[arg-type]
                assignee=assignee if assignee.lower() != "unassigned" else None,
            ))
        except Exception:
            continue
    return items
