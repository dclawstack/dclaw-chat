import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.gzip import GZipMiddleware

import structlog
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded

from app.core.database import engine, Base
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.migrations import check_database_revision
from app.core.ratelimit import limiter
from app.api.v1 import api_router
import app.models  # noqa: F401 — ensures all ORM tables are registered before create_all

# Structured logging
configure_logging()
log = get_logger(__name__)

settings = get_settings()

# Fail closed before anything else binds: prod must never run the DEBUG
# unauthenticated-Owner backdoor (T3-07).
settings.assert_safe_for_environment()

# Observability — only initialise Sentry when a DSN is provided.
if os.environ.get("SENTRY_DSN"):
    import sentry_sdk

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup. Production never creates or mutates schema — Alembic owns it
    # (#22): verify the DB is at the migration head and fail loudly if not.
    if settings.is_production:
        async with engine.connect() as conn:
            await conn.run_sync(check_database_revision)
        yield
        await engine.dispose()
        return

    # Dev/test bootstrap: create tables directly from the ORM metadata.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    if engine.dialect.name != "sqlite":
        # Safe schema migrations for pre-existing dev databases. Postgres-only
        # DDL (sqlite lacks ADD COLUMN IF NOT EXISTS; sqlite dev DBs are fully
        # created by create_all above anyway).
        async with engine.begin() as conn:
            await conn.execute(text(
                "ALTER TABLE channel_messages ADD COLUMN IF NOT EXISTS topic VARCHAR(50)"
            ))
            await conn.execute(text(
                "ALTER TABLE channel_messages ADD COLUMN IF NOT EXISTS attachments TEXT"
            ))
            # conversations ownership (v2.0 P0): NULL = legacy-shared row
            await conn.execute(text(
                "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS created_by VARCHAR(64)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_conversations_created_by"
                " ON conversations (created_by)"
            ))
            # bots ownership (v2.0 P2, T2-05): NULL = legacy-shared bot
            await conn.execute(text(
                "ALTER TABLE bots ADD COLUMN IF NOT EXISTS created_by VARCHAR(64)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_bots_created_by ON bots (created_by)"
            ))
            # channel workspace scoping (v2.0 P2, T2-06): NULL = legacy/global channel
            await conn.execute(text(
                "ALTER TABLE channels ADD COLUMN IF NOT EXISTS workspace_id VARCHAR(36)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_channels_workspace_id"
                " ON channels (workspace_id)"
            ))
            # call/huddle room workspace scoping (v2.0 P2, T2-07)
            await conn.execute(text(
                "ALTER TABLE call_rooms ADD COLUMN IF NOT EXISTS workspace_id VARCHAR(36)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_call_rooms_workspace_id"
                " ON call_rooms (workspace_id)"
            ))
            await conn.execute(text(
                "ALTER TABLE huddle_rooms ADD COLUMN IF NOT EXISTS workspace_id VARCHAR(36)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_huddle_rooms_workspace_id"
                " ON huddle_rooms (workspace_id)"
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


# Interactive API docs and the OpenAPI schema leak the full endpoint surface;
# expose them only in DEBUG, never in prod (T3-08).
_docs_enabled = settings.DEBUG
app = FastAPI(
    title="DClaw Chat API",
    description="AI conversations that remember",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# Rate limiting (slowapi) — shared limiter from app.core.ratelimit
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Response compression
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request-id middleware — binds a request_id into structlog contextvars and
# echoes it back on the response as X-Request-ID.
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    try:
        response = await call_next(request)
    finally:
        structlog.contextvars.clear_contextvars()
    response.headers["X-Request-ID"] = request_id
    return response


# API Routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_root():
    return JSONResponse(
        content={"status": "ok"},
        headers={"Cache-Control": "public, max-age=30"},
    )


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs" if _docs_enabled else None,
    }
