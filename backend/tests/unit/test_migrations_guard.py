"""Regression tests for the Alembic startup guard (#22).

Production must never create or mutate schema at startup: it verifies the DB
is stamped at the migration head and refuses to boot otherwise. Dev/test keeps
the create_all bootstrap.
"""
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.migrations import check_database_revision, get_script_directory


def test_single_migration_head_exists():
    heads = get_script_directory().get_heads()
    assert len(heads) == 1


def test_guard_raises_on_unstamped_db():
    eng = sa.create_engine("sqlite://")
    with eng.connect() as conn:
        with pytest.raises(RuntimeError, match="unstamped"):
            check_database_revision(conn)


def test_guard_passes_when_db_is_at_head():
    head = get_script_directory().get_heads()[0]
    eng = sa.create_engine("sqlite://")
    with eng.connect() as conn:
        conn.execute(sa.text(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        ))
        conn.execute(sa.text(f"INSERT INTO alembic_version VALUES ('{head}')"))
        check_database_revision(conn)  # must not raise


def test_guard_raises_on_stale_revision():
    eng = sa.create_engine("sqlite://")
    with eng.connect() as conn:
        conn.execute(sa.text(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        ))
        conn.execute(sa.text("INSERT INTO alembic_version VALUES ('deadbeef0000')"))
        with pytest.raises(RuntimeError, match="alembic upgrade head"):
            check_database_revision(conn)


@pytest.mark.asyncio
async def test_lifespan_production_fails_loudly_on_unstamped_db(monkeypatch):
    """In production the app refuses to start when the DB has no revision —
    and never falls back to create_all."""
    from app import main

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(main, "engine", test_engine)
    monkeypatch.setattr(main.settings, "ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        async with main.lifespan(main.app):
            pass

    # The guard path must not have created any tables.
    async with test_engine.connect() as conn:
        tables = (await conn.execute(sa.text(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ))).scalars().all()
    assert tables == []
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_lifespan_dev_bootstraps_schema(monkeypatch):
    """Outside production the create_all bootstrap still works."""
    from app import main

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(main, "engine", test_engine)
    monkeypatch.setattr(main.settings, "ENVIRONMENT", "development")

    async with main.lifespan(main.app):
        async with test_engine.connect() as conn:
            tables = (await conn.execute(sa.text(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ))).scalars().all()
        assert "conversations" in tables
