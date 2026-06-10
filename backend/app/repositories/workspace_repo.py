from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.workspace import (
    WorkspaceORM,
    WorkspaceMemberORM,
    WorkspaceInviteORM,
)


async def is_workspace_member(
    db: AsyncSession, workspace_id: str, user_id: str
) -> bool:
    """Module-level membership probe shared by routers (channels/calls/huddles)."""
    result = await db.execute(
        select(WorkspaceMemberORM.id).where(
            WorkspaceMemberORM.workspace_id == workspace_id,
            WorkspaceMemberORM.user_id == user_id,
        )
    )
    return result.scalar_one_or_none() is not None


class WorkspaceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, name: str, created_by: str) -> WorkspaceORM:
        workspace = WorkspaceORM(name=name, created_by=created_by)
        self.db.add(workspace)
        await self.db.flush()
        self.db.add(
            WorkspaceMemberORM(
                workspace_id=workspace.id, user_id=created_by, role="Owner"
            )
        )
        await self.db.commit()
        await self.db.refresh(workspace)
        return workspace

    async def get_by_id(self, workspace_id: str) -> Optional[WorkspaceORM]:
        result = await self.db.execute(
            select(WorkspaceORM)
            .options(selectinload(WorkspaceORM.members))
            .where(WorkspaceORM.id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: str) -> List[WorkspaceORM]:
        result = await self.db.execute(
            select(WorkspaceORM)
            .join(
                WorkspaceMemberORM,
                WorkspaceMemberORM.workspace_id == WorkspaceORM.id,
            )
            .options(selectinload(WorkspaceORM.members))
            .where(WorkspaceMemberORM.user_id == user_id)
            .order_by(WorkspaceORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_member(
        self, workspace_id: str, user_id: str
    ) -> Optional[WorkspaceMemberORM]:
        result = await self.db.execute(
            select(WorkspaceMemberORM).where(
                WorkspaceMemberORM.workspace_id == workspace_id,
                WorkspaceMemberORM.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def add_member(
        self, workspace_id: str, user_id: str, role: str = "Member"
    ) -> WorkspaceMemberORM:
        member = WorkspaceMemberORM(
            workspace_id=workspace_id, user_id=user_id, role=role
        )
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def list_members(self, workspace_id: str) -> List[WorkspaceMemberORM]:
        result = await self.db.execute(
            select(WorkspaceMemberORM)
            .where(WorkspaceMemberORM.workspace_id == workspace_id)
            .order_by(WorkspaceMemberORM.created_at.asc())
        )
        return list(result.scalars().all())

    async def create_invite(
        self, workspace_id: str, email: str, invited_by: str
    ) -> WorkspaceInviteORM:
        invite = WorkspaceInviteORM(
            workspace_id=workspace_id, email=email, invited_by=invited_by
        )
        self.db.add(invite)
        await self.db.commit()
        await self.db.refresh(invite)
        return invite

    async def get_invite(self, token: str) -> Optional[WorkspaceInviteORM]:
        result = await self.db.execute(
            select(WorkspaceInviteORM).where(WorkspaceInviteORM.id == token)
        )
        return result.scalar_one_or_none()

    async def accept_invite(
        self, invite: WorkspaceInviteORM, user_id: str
    ) -> WorkspaceMemberORM:
        """Mark the invite accepted and ensure the caller is a member.

        Idempotent: if the caller already belongs to the workspace, the
        existing member row is returned and only ``accepted_by`` is updated.
        """
        existing = await self.get_member(invite.workspace_id, user_id)
        invite.accepted_by = user_id
        if existing:
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        member = WorkspaceMemberORM(
            workspace_id=invite.workspace_id, user_id=user_id, role="Member"
        )
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)
        return member
