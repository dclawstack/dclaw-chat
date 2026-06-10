import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session
from app.core.deps import get_current_user, CurrentUser
from app.repositories.meeting_repo import MeetingRepository
from app.schemas.meeting import (
    MeetingOut,
    MeetingCreate,
    MeetingUpdateTitle,
    ProcessMeetingRequest,
)
from app.services.files import FileService
from app.services.meeting_service import MeetingService, AUDIO_MIMES

router = APIRouter()
logger = logging.getLogger(__name__)

_file_service = FileService()


async def _run_processing(meeting_id: str, model_id: Optional[str]) -> None:
    """Background coroutine that opens its own DB session for the processing pipeline."""
    try:
        async with async_session() as db:
            repo = MeetingRepository(db)
            meeting = await repo.get_by_id(meeting_id)
            if not meeting:
                logger.error(f"Background processing: meeting {meeting_id} not found")
                return
            service = MeetingService(db)
            await service.process_meeting(meeting, model_id=model_id)
    except Exception as e:
        logger.error(f"Background processing failed for meeting {meeting_id}: {e}")

ALLOWED_MIMES = AUDIO_MIMES | {
    "application/octet-stream",  # fallback for unknown types
}


@router.post("", response_model=MeetingOut, status_code=201)
async def create_meeting(
    req: MeetingCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = MeetingRepository(db)
    meeting = await repo.create(title=req.title, created_by=user.user_id)
    return meeting


@router.post("/upload", response_model=MeetingOut, status_code=201)
async def upload_and_create_meeting(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Upload an audio/video file and create a meeting record ready for processing."""
    mime = file.content_type or "application/octet-stream"
    if not any(mime.startswith(prefix) for prefix in ("audio/", "video/", "application/octet-stream")):
        raise HTTPException(400, f"Unsupported file type: {mime}. Upload audio or video files.")

    upload_info = await _file_service.save_upload(file)
    meeting_title = title or (file.filename or "Untitled Meeting").rsplit(".", 1)[0]

    repo = MeetingRepository(db)
    meeting = await repo.create(title=meeting_title, created_by=user.user_id)
    meeting = await repo.update_file(
        meeting,
        file_id=upload_info["id"],
        filename=upload_info["name"],
        mime_type=upload_info["mime_type"],
        status="pending",
    )
    return meeting


@router.post("/{meeting_id}/process", response_model=MeetingOut)
async def process_meeting(
    meeting_id: str,
    req: ProcessMeetingRequest = ProcessMeetingRequest(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Trigger async transcription → summarization → action extraction for a meeting."""
    repo = MeetingRepository(db)
    meeting = await repo.get_by_id(meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    if meeting.created_by and meeting.created_by != user.user_id:
        raise HTTPException(403, "Not your meeting")
    if meeting.status in ("transcribing", "summarizing"):
        raise HTTPException(409, "Meeting is already being processed")
    if not meeting.file_id:
        raise HTTPException(400, "No audio file attached to this meeting. Upload a file first.")

    # Mark as transcribing immediately so the response reflects the new state
    meeting = await repo.update_status(meeting, "transcribing")

    # Background task uses its own DB session (request session closes after response)
    asyncio.create_task(_run_processing(meeting_id, req.model))
    return meeting


@router.get("", response_model=List[MeetingOut])
async def list_meetings(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = MeetingRepository(db)
    return await repo.list_all(created_by=user.user_id, limit=limit, offset=offset)


@router.get("/{meeting_id}", response_model=MeetingOut)
async def get_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = MeetingRepository(db)
    meeting = await repo.get_by_id(meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    if meeting.created_by and meeting.created_by != user.user_id:
        raise HTTPException(403, "Not authorized to access this meeting")
    return meeting


@router.patch("/{meeting_id}", response_model=MeetingOut)
async def update_meeting_title(
    meeting_id: str,
    req: MeetingUpdateTitle,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = MeetingRepository(db)
    meeting = await repo.get_by_id(meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    if meeting.created_by and meeting.created_by != user.user_id:
        raise HTTPException(403, "Not your meeting")
    return await repo.update_title(meeting, req.title)


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = MeetingRepository(db)
    meeting = await repo.get_by_id(meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    if meeting.created_by and meeting.created_by != user.user_id:
        raise HTTPException(403, "Not your meeting")
    await repo.delete(meeting)
