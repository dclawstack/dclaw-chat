from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat_service import ChatService
from app.core.database import get_db
from app.core.deps import get_current_user, CurrentUser

router = APIRouter()


@router.get("")
async def list_models(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    service = ChatService(db)
    return await service.list_models()
