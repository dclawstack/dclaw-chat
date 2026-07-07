"""Startup guard: production runs only on an Alembic-managed schema (#22).

The app never creates or alters tables in production. Instead it verifies at
startup that the database is stamped at the migration head and refuses to boot
otherwise, so a missed ``alembic upgrade head`` fails loudly at deploy time
instead of surfacing as runtime errors on missing columns.
"""
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection

# backend/ — alembic.ini and alembic/ live next to the app package.
_BACKEND_DIR = Path(__file__).resolve().parents[2]


def get_script_directory() -> ScriptDirectory:
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    return ScriptDirectory.from_config(cfg)


def check_database_revision(connection: Connection) -> None:
    """Raise RuntimeError unless *connection*'s DB is at the migration head."""
    heads = set(get_script_directory().get_heads())
    current = set(MigrationContext.configure(connection).get_current_heads())
    if current != heads:
        raise RuntimeError(
            "Refusing to start: database schema revision "
            f"{sorted(current) if current else '(unstamped)'} does not match the "
            f"expected migration head {sorted(heads)}. "
            "Run 'alembic upgrade head' before starting the app. "
            "For an existing install created before Alembic was introduced "
            "(schema already current), run 'alembic stamp head' once instead."
        )
