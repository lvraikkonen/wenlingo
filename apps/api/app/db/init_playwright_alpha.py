from app.db.seed_playwright_alpha import (
    _assert_playwright_alpha_seed_is_safe,
    seed_playwright_alpha,
)
from app.db.session import create_db_and_tables


def init_playwright_alpha() -> None:
    _assert_playwright_alpha_seed_is_safe()
    create_db_and_tables()
    seed_playwright_alpha()


if __name__ == "__main__":
    init_playwright_alpha()
