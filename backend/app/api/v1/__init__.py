from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.models import router as models_router
from app.api.v1.health import router as health_router
from app.api.v1.ai import router as ai_router
from app.api.v1.messaging import router as messaging_router
from app.api.v1.meetings import router as meetings_router
from app.api.v1.bots import router as bots_router

api_router = APIRouter()
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(conversations_router, prefix="/conversations", tags=["conversations"])
api_router.include_router(models_router, prefix="/models", tags=["models"])
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(ai_router, prefix="/ai", tags=["ai-copilot"])
api_router.include_router(messaging_router, prefix="/messaging", tags=["messaging"])
api_router.include_router(meetings_router, prefix="/meetings", tags=["meetings"])
api_router.include_router(bots_router, prefix="/bots", tags=["bots"])
