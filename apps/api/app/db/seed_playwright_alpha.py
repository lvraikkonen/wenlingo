from datetime import datetime, timezone

from sqlalchemy import delete
from sqlmodel import Session, select

from app.api.routes.alpha import hash_invite_code
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
