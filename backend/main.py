import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from models import Base
from routers import chat, conversations, models

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/dclaw_chat")
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="DClaw Chat API",
    description="AI conversations that remember",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3002", "http://localhost:1420"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
async def get_db():
    async with async_session() as session:
        yield session

app.state.get_db = get_db

# Routers
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(conversations.router, prefix="/api/v1", tags=["conversations"])
app.include_router(models.router, prefix="/api/v1", tags=["models"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "dclaw-chat-backend"}


@app.get("/")
async def root():
    return {
        "name": "DClaw Chat API",
        "version": "0.1.0",
        "docs": "/docs",
    }
