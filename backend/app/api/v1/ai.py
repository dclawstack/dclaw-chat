from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.ai import (
    AIChatRequest,
    AIChatResponse,
    SummarizeRequest,
    SummarizeResponse,
    ActionsRequest,
    ActionsResponse,
)
from app.services.chat_ai import ChatAIService
from app.core.database import get_db
from app.core.deps import get_current_user, CurrentUser
from app.core.exceptions import ForbiddenException
from app.repositories.workspace_repo import is_workspace_member

router = APIRouter()


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(
    req: AIChatRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Graph citations are workspace data: members only.
    if req.workspace_id and not await is_workspace_member(
        db, req.workspace_id, user.user_id
    ):
        raise ForbiddenException("Not a member of this workspace")
    service = ChatAIService(db)
    return await service.chat(req)


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_conversation(
    req: SummarizeRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    service = ChatAIService(db)
    return await service.summarize(req)


@router.post("/actions", response_model=ActionsResponse)
async def extract_actions(
    req: ActionsRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    service = ChatAIService(db)
    return await service.extract_actions(req)
