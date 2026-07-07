from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat_service import ChatService
from app.services.model_router import ModelRouter
from app.services import model_policy
from app.core.database import get_db
from app.core.deps import get_current_user, CurrentUser
from app.repositories.workspace_repo import is_workspace_member

router = APIRouter()


@router.get("")
async def list_models(
    workspace_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    service = ChatService(db)
    models = await service.list_models()
    if workspace_id:
        # Workspace policy filters what members may pick (#30).
        if not await is_workspace_member(db, workspace_id, user.user_id):
            raise HTTPException(403, "Not a member of this workspace")
        allowed, local_only = await model_policy.get_policy(db, workspace_id)
        models = model_policy.filter_models(models, allowed, local_only)
    return models


@router.get("/router-stats")
async def router_stats(
    user: CurrentUser = Depends(get_current_user),
):
    """Per-process model-router usage counters (local-first KPI tracking)."""
    return ModelRouter.stats()
