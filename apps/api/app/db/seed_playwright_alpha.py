import os
from pathlib import PurePosixPath
from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlmodel import Session, select

from app.api.routes.alpha import hash_invite_code
from app.core.config import get_settings
from app.db.session import engine
from app.domain.models import (
    AlphaInviteCode,
    AuthMagicCode,
    ParentAccount,
    ParentSession,
    ParentUser,
)

NEW_ALPHA_EMAIL = "parent@example.com"
NEW_ALPHA_INVITE_CODE = "ALPHA-E2E"
LEGACY_PARENT_ID = "legacy-e2e-parent"
LEGACY_PARENT_EMAIL = "legacy-e2e-parent@example.com"
LEGACY_INVITE_CODE = "LEGACY-E2E"
PLAYWRIGHT_ALPHA_SEED_FLAG = "PLAYWRIGHT_ALPHA_SEED"
DEFAULT_PLAYWRIGHT_DATABASE_URL = "sqlite:///./playwright-e2e.db"
ALLOWED_SQLITE_DATABASE_BASENAME = "playwright-e2e.db"
ALLOWED_POSTGRES_DATABASE_NAMES = {"wenlingo_test", "playwright_e2e"}
LOCAL_DATABASE_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


def _is_disposable_e2e_database_url(database_url: str) -> bool:
    normalized = database_url.strip().lower()
    if normalized == DEFAULT_PLAYWRIGHT_DATABASE_URL:
        return True

    try:
        parsed_url = make_url(database_url)
    except Exception:
        return False

    backend_name = parsed_url.get_backend_name()
    database_name = (parsed_url.database or "").lower()
    if backend_name == "sqlite":
        return PurePosixPath(database_name).name == ALLOWED_SQLITE_DATABASE_BASENAME
    if backend_name == "postgresql":
        return (
            (parsed_url.host or "").lower() in LOCAL_DATABASE_HOSTS
            and database_name in ALLOWED_POSTGRES_DATABASE_NAMES
        )
    return False


def _safe_database_target(database_url: str) -> str:
    try:
        parsed_url = make_url(database_url)
    except Exception:
        return "unparseable database URL"

    backend_name = parsed_url.get_backend_name()
    database_name = parsed_url.database or ""
    if backend_name == "sqlite":
        database_name = PurePosixPath(database_name).name
    return f"{backend_name}:{database_name or '<none>'}"


def _assert_playwright_alpha_seed_is_safe(database_url: str | None = None) -> None:
    if os.environ.get(PLAYWRIGHT_ALPHA_SEED_FLAG) != "1":
        raise SystemExit(
            f"{PLAYWRIGHT_ALPHA_SEED_FLAG}=1 is required to run Playwright alpha seed."
        )

    target_database_url = database_url or get_settings().database_url
    if not _is_disposable_e2e_database_url(target_database_url):
        raise SystemExit(
            "Refusing to seed non-disposable database target: "
            f"{_safe_database_target(target_database_url)}"
        )


def _ensure_invite(
    session: Session,
    *,
    code: str,
    label: str,
    status: str,
    consumed_by_parent_id: str | None = None,
) -> AlphaInviteCode:
    code_hash = hash_invite_code(code)
    invite = session.exec(
        select(AlphaInviteCode).where(AlphaInviteCode.code_hash == code_hash)
    ).first()
    if invite is None:
        invite = AlphaInviteCode(code_hash=code_hash, label=label)

    invite.label = label
    invite.status = status
    invite.consumed_by_parent_id = consumed_by_parent_id
    invite.consumed_at = (
        datetime.now(timezone.utc) if consumed_by_parent_id is not None else None
    )
    session.add(invite)
    return invite


def seed_playwright_alpha() -> None:
    _assert_playwright_alpha_seed_is_safe()

    with Session(engine) as session:
        accounts = session.exec(
            select(ParentAccount).where(
                ParentAccount.email_normalized == NEW_ALPHA_EMAIL
            )
        ).all()
        account_ids = [account.id for account in accounts]
        if account_ids:
            linked_parents = session.exec(
                select(ParentUser).where(ParentUser.account_id.in_(account_ids))
            ).all()
            for parent in linked_parents:
                parent.account_id = None
                parent.account_linked_at = None
                session.add(parent)

            session.execute(
                delete(ParentSession).where(
                    ParentSession.account_id.in_(account_ids)
                )
            )

        session.execute(
            delete(AuthMagicCode).where(
                AuthMagicCode.email_normalized == NEW_ALPHA_EMAIL
            )
        )
        for account in accounts:
            session.delete(account)

        legacy_parent = session.get(ParentUser, LEGACY_PARENT_ID)
        if legacy_parent is None:
            legacy_parent = ParentUser(
                id=LEGACY_PARENT_ID,
                email=LEGACY_PARENT_EMAIL,
                display_name="Legacy E2E Parent",
            )
        legacy_parent.account_id = None
        legacy_parent.account_linked_at = None
        session.add(legacy_parent)

        _ensure_invite(
            session,
            code=NEW_ALPHA_INVITE_CODE,
            label="E2E alpha invite",
            status="issued",
        )
        _ensure_invite(
            session,
            code=LEGACY_INVITE_CODE,
            label="E2E legacy invite",
            status="consumed",
            consumed_by_parent_id=LEGACY_PARENT_ID,
        )
        session.commit()


if __name__ == "__main__":
    seed_playwright_alpha()
