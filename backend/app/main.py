from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.database import engine, Base
from app.core.config import get_settings
from app.api.v1 import api_router
import app.models  # noqa: F401 — ensures all ORM tables are registered before create_all

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Safe schema migrations for existing tables
        await conn.execute(text(
            "ALTER TABLE channel_messages ADD COLUMN IF NOT EXISTS topic VARCHAR(50)"
        ))
        await conn.execute(text(
            "ALTER TABLE channel_messages ADD COLUMN IF NOT EXISTS attachments TEXT"
        ))
        # bots table columns added in v1.3
        try:
            await conn.execute(text(
                "ALTER TABLE bots ADD COLUMN IF NOT EXISTS avatar_emoji VARCHAR(10)"
            ))
        except Exception:
            pass
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="DClaw Chat API",
    description="AI conversations that remember",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
