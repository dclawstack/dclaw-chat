import json
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.audit import AuditEventOut
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceOut,
    MemberOut,
    MemberRoleUpdate,
    ModelPolicyOut,
    ModelPolicyUpdate,
    InviteCreate,
    InviteOut,
    InviteAccepted,
)
from app.models.audit import AuditEventORM
from app.repositories.workspace_repo import WorkspaceRepository
from app.core.database import get_db
from app.core.deps import get_current_user, CurrentUser
from app.core.exceptions import NotFoundException, ForbiddenException
from app.services import audit
from app.services import model_policy

router = APIRouter()


async def require_member(
    repo: WorkspaceRepository,
    workspace_id: str,
    user: CurrentUser,
    *,
    roles: Optional[tuple[str, ...]] = None,
):
    """404 on unknown workspace, 403 unless the caller is a member.

    When ``roles`` is given, the caller's member role must also be one of
    them (e.g. ``("Owner", "Admin")`` for invite creation).
    Returns ``(workspace, member)``.
    """
    workspace = await repo.get_by_id(workspace_id)
    if not workspace:
        raise NotFoundException("Workspace not found")
    member = await repo.get_member(workspace_id, user.user_id)
    if not member:
        raise ForbiddenException("Not a member of this workspace")
    if roles is not None and member.role not in roles:
        raise ForbiddenException(f"Required workspace role: {', '.join(roles)}")
    return workspace, member


def _to_out(workspace, user_id: Optional[str] = None) -> WorkspaceOut:
    my_role = None
    if user_id is not None:
        my_role = next(
            (m.role for m in workspace.members if m.user_id == user_id), None
        )
    return WorkspaceOut(
        id=workspace.id,
        name=workspace.name,
        created_by=workspace.created_by,
        created_at=workspace.created_at,
        member_count=len(workspace.members),
        my_role=my_role,
    )


@router.post("", response_model=WorkspaceOut, status_code=201)
async def create_workspace(
    req: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = WorkspaceRepository(db)
    workspace = await repo.create(name=req.name, created_by=user.user_id)
    return _to_out(workspace, user.user_id)


@router.get("", response_model=List[WorkspaceOut])
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = WorkspaceRepository(db)
    workspaces = await repo.list_for_user(user.user_id)
    return [_to_out(w, user.user_id) for w in workspaces]


@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = WorkspaceRepository(db)
    workspace, _ = await require_member(repo, workspace_id, user)
    return _to_out(workspace, user.user_id)


@router.get("/{workspace_id}/members", response_model=List[MemberOut])
async def list_workspace_members(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = WorkspaceRepository(db)
    await require_member(repo, workspace_id, user)
    members = await repo.list_members(workspace_id)
    return [MemberOut.model_validate(m) for m in members]


@router.post("/{workspace_id}/invites", response_model=InviteOut, status_code=201)
async def create_workspace_invite(
    workspace_id: str,
    req: InviteCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = WorkspaceRepository(db)
    await require_member(repo, workspace_id, user, roles=("Owner", "Admin"))
    invite = await repo.create_invite(
        workspace_id=workspace_id, email=req.email, invited_by=user.user_id
    )
    await audit.record(
        db, actor_id=user.user_id, action="invite.created",
        workspace_id=workspace_id, target_type="invite", target_id=invite.id,
        detail={"email": req.email},
    )
    return InviteOut(
        token=invite.id, workspace_id=invite.workspace_id, email=invite.email
    )


@router.post("/invites/{token}/accept", response_model=InviteAccepted)
async def accept_workspace_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = WorkspaceRepository(db)
    invite = await repo.get_invite(token)
    if not invite:
        raise NotFoundException("Invite not found")
    member = await repo.accept_invite(invite, user.user_id)
    await audit.record(
        db, actor_id=user.user_id, action="invite.accepted",
        workspace_id=member.workspace_id, target_type="invite", target_id=token,
    )
    return InviteAccepted(workspace_id=member.workspace_id, role=member.role)


@router.get("/{workspace_id}/settings/models", response_model=ModelPolicyOut)
async def get_model_policy(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    repo = WorkspaceRepository(db)
    workspace, _ = await require_member(repo, workspace_id, user)
    allowed, local_only = await model_policy.get_policy(db, workspace_id)
    return ModelPolicyOut(allowed_models=allowed, local_only=local_only)


@router.put("/{workspace_id}/settings/models", response_model=ModelPolicyOut)
async def set_model_policy(
    workspace_id: str,
    req: ModelPolicyUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """AI model policy is Owner/Admin-only (#30)."""
    repo = WorkspaceRepository(db)
    workspace, _ = await require_member(repo, workspace_id, user, roles=("Owner", "Admin"))
    workspace.allowed_models = (
        json.dumps(req.allowed_models) if req.allowed_models is not None else None
    )
    workspace.local_only = req.local_only
    await db.commit()
    await audit.record(
        db, actor_id=user.user_id, action="workspace.model_policy_changed",
        workspace_id=workspace_id, target_type="workspace", target_id=workspace_id,
        detail={"allowed_models": req.allowed_models, "local_only": req.local_only},
    )
    return ModelPolicyOut(allowed_models=req.allowed_models, local_only=req.local_only)


async def _count_owners(repo: WorkspaceRepository, workspace_id: str) -> int:
    members = await repo.list_members(workspace_id)
    return sum(1 for m in members if m.role == "Owner")


@router.patch("/{workspace_id}/members/{member_user_id}", response_model=MemberOut)
async def change_member_role(
    workspace_id: str,
    member_user_id: str,
    req: MemberRoleUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Role changes are Owner/Admin-only; only an Owner may grant or revoke
    the Owner role, and the last Owner can never be demoted (#27)."""
    repo = WorkspaceRepository(db)
    _, actor = await require_member(repo, workspace_id, user, roles=("Owner", "Admin"))
    target = await repo.get_member(workspace_id, member_user_id)
    if not target:
        raise NotFoundException("Member not found")
    if (target.role == "Owner" or req.role == "Owner") and actor.role != "Owner":
        raise ForbiddenException("Only an Owner can grant or revoke the Owner role")
    if target.role == "Owner" and req.role != "Owner":
        if await _count_owners(repo, workspace_id) <= 1:
            raise ForbiddenException("Cannot demote the last Owner")
    old_role = target.role
    target.role = req.role
    await db.commit()
    await db.refresh(target)
    await audit.record(
        db, actor_id=user.user_id, action="member.role_changed",
        workspace_id=workspace_id, target_type="member", target_id=member_user_id,
        detail={"from": old_role, "to": req.role},
    )
    return MemberOut.model_validate(target)


@router.delete("/{workspace_id}/members/{member_user_id}", status_code=204)
async def remove_member(
    workspace_id: str,
    member_user_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Member removal is Owner/Admin-only; Owners can only be removed by an
    Owner, and never the last one (#27)."""
    repo = WorkspaceRepository(db)
    _, actor = await require_member(repo, workspace_id, user, roles=("Owner", "Admin"))
    target = await repo.get_member(workspace_id, member_user_id)
    if not target:
        raise NotFoundException("Member not found")
    if target.role == "Owner":
        if actor.role != "Owner":
            raise ForbiddenException("Only an Owner can remove an Owner")
        if await _count_owners(repo, workspace_id) <= 1:
            raise ForbiddenException("Cannot remove the last Owner")
    await db.delete(target)
    await db.commit()
    await audit.record(
        db, actor_id=user.user_id, action="member.removed",
        workspace_id=workspace_id, target_type="member", target_id=member_user_id,
    )


@router.get("/{workspace_id}/audit", response_model=List[AuditEventOut])
async def list_audit_events(
    workspace_id: str,
    action: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Append-only audit trail (#26). Workspace Owner/Admin only; there is
    deliberately no route that mutates audit rows."""
    repo = WorkspaceRepository(db)
    await require_member(repo, workspace_id, user, roles=("Owner", "Admin"))
    stmt = select(AuditEventORM).where(AuditEventORM.workspace_id == workspace_id)
    if action:
        stmt = stmt.where(AuditEventORM.action == action)
    stmt = (
        stmt.order_by(AuditEventORM.created_at.desc(), AuditEventORM.id)
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [AuditEventOut.model_validate(r) for r in rows]
