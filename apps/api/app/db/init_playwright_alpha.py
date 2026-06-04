from pathlib import Path

from sqlalchemy.engine import make_url

from app.db.seed_playwright_alpha import (
    ALLOWED_SQLITE_DATABASE_BASENAME,
    _assert_playwright_alpha_seed_is_safe,
    seed_playwright_alpha,
)
from app.core.config import get_settings
from app.db.session import create_db_and_tables


def _reset_sqlite_playwright_database(database_url: str) -> None:
    parsed_url = make_url(database_url)
    if parsed_url.get_backend_name() != "sqlite" or not parsed_url.database:
        return

    db_path = Path(parsed_url.database)
    if db_path.name != ALLOWED_SQLITE_DATABASE_BASENAME:
        return

    if db_path.exists():
        db_path.unlink()


def init_playwright_alpha() -> None:
    _assert_playwright_alpha_seed_is_safe()
    _reset_sqlite_playwright_database(get_settings().database_url)
    create_db_and_tables()
    seed_playwright_alpha()


if __name__ == "__main__":
    init_playwright_alpha()
