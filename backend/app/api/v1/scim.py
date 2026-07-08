"""SCIM 2.0 user provisioning, workspace-scoped (#31).

The enterprise IdP (Okta, Entra, …) calls these endpoints with a bearer token
that a workspace Owner/Admin issued (`POST /api/v1/workspaces/{id}/scim/token`).
Tokens are stored hashed; possession of the token *is* the authorization —
these routes are called by machines, not signed-in users.

Deactivating a user removes their membership (workspace APIs 403 immediately)
and force-closes their live WebSocket connections on every replica.
"""
from __future__ import annotations

import hashlib
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.workspace import WorkspaceMemberORM, WorkspaceORM
from app.repositories.workspace_repo import WorkspaceRepository
from app.services import audit
from app.services.messaging import manager as ws_manager

router = APIRouter()

SCIM_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_LIST_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
SCIM_ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(32)


async def _authorize(
    workspace_id: str,
    db: AsyncSession,
    authorization: Optional[str],
) -> WorkspaceORM:
    ws = await db.get(WorkspaceORM, workspace_id)
    if ws is None or not ws.scim_token_hash:
        raise HTTPException(404, "Unknown SCIM tenant")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer token required")
    token = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(hash_token(token), ws.scim_token_hash):
        raise HTTPException(401, "Invalid SCIM token")
    return ws


def _user_resource(member: WorkspaceMemberORM) -> dict:
    return {
        "schemas": [SCIM_USER_SCHEMA],
        "id": member.user_id,
        "userName": member.user_id,
        "active": True,
        "meta": {"resourceType": "User"},
    }


@router.get("/{workspace_id}/Users")
async def list_users(
    workspace_id: str,
    filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    await _authorize(workspace_id, db, authorization)
    stmt = select(WorkspaceMemberORM).where(
        WorkspaceMemberORM.workspace_id == workspace_id
    )
    # Minimal filter support: the `userName eq "value"` probe IdPs send
    # before provisioning.
    if filter:
        parts = filter.split()
        if len(parts) == 3 and parts[0] == "userName" and parts[1] == "eq":
            stmt = stmt.where(WorkspaceMemberORM.user_id == parts[2].strip('"'))
        else:
            raise HTTPException(400, "Unsupported SCIM filter")
    members = (await db.execute(stmt)).scalars().all()
    resources = [_user_resource(m) for m in members]
    return {
        "schemas": [SCIM_LIST_SCHEMA],
        "totalResults": len(resources),
        "startIndex": 1,
        "itemsPerPage": len(resources),
        "Resources": resources,
    }


@router.get("/{workspace_id}/Users/{user_id}")
async def get_user(
    workspace_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    await _authorize(workspace_id, db, authorization)
    repo = WorkspaceRepository(db)
    member = await repo.get_member(workspace_id, user_id)
    if member is None:
        raise HTTPException(404, "User not found")
    return _user_resource(member)


@router.post("/{workspace_id}/Users", status_code=201)
async def provision_user(
    workspace_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    await _authorize(workspace_id, db, authorization)
    user_name = payload.get("userName")
    if not user_name:
        raise HTTPException(400, "userName is required")
    repo = WorkspaceRepository(db)
    member = await repo.get_member(workspace_id, user_name)
    if member is None:
        member = await repo.add_member(workspace_id, user_name, role="Member")
        await audit.record(
            db, actor_id="scim", action="scim.provisioned",
            workspace_id=workspace_id, target_type="member", target_id=user_name,
        )
    return _user_resource(member)


async def _deprovision(
    db: AsyncSession, workspace_id: str, member: WorkspaceMemberORM
) -> None:
    user_id = member.user_id
    await db.delete(member)
    await db.commit()
    await audit.record(
        db, actor_id="scim", action="scim.deprovisioned",
        workspace_id=workspace_id, target_type="member", target_id=user_id,
    )
    # Revoke live access on every replica, not just this one.
    await ws_manager.force_disconnect(user_id)


@router.put("/{workspace_id}/Users/{user_id}")
@router.patch("/{workspace_id}/Users/{user_id}")
async def update_user(
    workspace_id: str,
    user_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    await _authorize(workspace_id, db, authorization)
    repo = WorkspaceRepository(db)
    member = await repo.get_member(workspace_id, user_id)

    # PATCH bodies carry Operations; PUT carries the resource. Either way the
    # only lifecycle bit we honour is `active`.
    active = payload.get("active")
    for op in payload.get("Operations", []):
        value = op.get("value")
        if isinstance(value, dict) and "active" in value:
            active = value["active"]
        elif op.get("path") == "active":
            active = value

    if active is False:
        if member is not None:
            await _deprovision(db, workspace_id, member)
        return {
            "schemas": [SCIM_USER_SCHEMA],
            "id": user_id,
            "userName": user_id,
            "active": False,
            "meta": {"resourceType": "User"},
        }
    if member is None:
        raise HTTPException(404, "User not found")
    return _user_resource(member)


@router.delete("/{workspace_id}/Users/{user_id}", status_code=204)
async def delete_user(
    workspace_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    await _authorize(workspace_id, db, authorization)
    repo = WorkspaceRepository(db)
    member = await repo.get_member(workspace_id, user_id)
    if member is not None:
        await _deprovision(db, workspace_id, member)
