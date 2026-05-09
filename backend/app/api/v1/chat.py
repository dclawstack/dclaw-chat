import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse
from app.services.chat_service import ChatService
from app.core.database import get_db
from app.core.deps import get_current_user, CurrentUser

router = APIRouter()


@router.post("/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    req: ChatCompletionRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    service = ChatService(db)
    return await service.complete(req)


@router.post("/stream")
async def chat_stream(
    req: ChatCompletionRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    service = ChatService(db)

    async def event_generator():
        try:
            async for token in service.stream_complete(req):
                yield f"data: {json.dumps({'delta': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
