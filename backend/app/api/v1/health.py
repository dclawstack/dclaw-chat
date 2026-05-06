from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("")
async def health_check(db: AsyncSession = Depends(get_db)):
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "service": "dclaw-chat-backend",
        "version": settings.APP_VERSION,
        "database": db_status,
    }


@router.get("/detailed")
async def health_detailed(db: AsyncSession = Depends(get_db)):
    checks = {}

    # Database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok", "latency_ms": 0}
    except Exception as e:
        checks["database"] = {"status": "error", "detail": str(e)}

    return {
        "status": "ok" if all(c["status"] == "ok" for c in checks.values()) else "degraded",
        "version": settings.APP_VERSION,
        "checks": checks,
    }
