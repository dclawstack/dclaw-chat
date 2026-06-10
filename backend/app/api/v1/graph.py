"""Workspace knowledge-graph routes (V2 plan §4.2).

All routes are workspace-scoped: any caller who is not a member of the
workspace gets 403, mirroring the channel/call/huddle scoping rules.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, CurrentUser
from app.core.exceptions import NotFoundException, ForbiddenException
from app.models.graph import GraphEntityORM
from app.repositories.graph_repo import GraphRepository
from app.repositories.workspace_repo import is_workspace_member
from app.schemas.graph import (
    GraphEntityOut,
    GraphNeighborsOut,
    CatchMeUpOut,
)
from app.services.graph_service import GraphService

router = APIRouter()


async def _require_member(
    db: AsyncSession, workspace_id: str, user: CurrentUser
) -> None:
    if not await is_workspace_member(db, workspace_id, user.user_id):
        raise ForbiddenException("Not a member of this workspace")


@router.get(
    "/workspaces/{workspace_id}/entities", response_model=List[GraphEntityOut]
)
async def search_workspace_entities(
    workspace_id: str,
    q: str = "",
    kind: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    await _require_member(db, workspace_id, user)
    kinds = [k.strip() for k in kind.split(",") if k.strip()] if kind else None
    repo = GraphRepository(db)
    return await repo.search_entities(
        workspace_id, q, kinds=kinds, limit=max(1, min(limit, 100))
    )


@router.get(
    "/workspaces/{workspace_id}/entities/{entity_id}/neighbors",
    response_model=GraphNeighborsOut,
)
async def get_entity_neighbors(
    workspace_id: str,
    entity_id: str,
    depth: int = 1,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    await _require_member(db, workspace_id, user)
    entity = await db.get(GraphEntityORM, entity_id)
    if entity is None or entity.workspace_id != workspace_id:
        raise NotFoundException("Entity not found")
    repo = GraphRepository(db)
    result = await repo.neighbors(entity_id, depth=max(1, min(depth, 3)))
    return {
        "entity": entity,
        "entities": result["entities"],
        "edges": result["edges"],
    }


@router.get(
    "/workspaces/{workspace_id}/catch-me-up", response_model=CatchMeUpOut
)
async def catch_me_up(
    workspace_id: str,
    since: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    await _require_member(db, workspace_id, user)
    return await GraphService.catch_me_up(db, workspace_id, since=since)
