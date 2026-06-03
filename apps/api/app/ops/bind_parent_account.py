import argparse
from contextlib import closing

from sqlmodel import select

from app.db.session import get_session
from app.domain.models import ParentAccount, ParentUser, utcnow


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized:
        raise SystemExit("email is required")
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description="Bind an alpha parent to a parent account.")
    parser.add_argument("--parent-id", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    email_normalized = _normalize_email(args.email)
    now = utcnow()

    session_gen = get_session()
    with closing(session_gen):
        session = next(session_gen)
        parent = session.get(ParentUser, args.parent_id)
        if not parent:
            raise SystemExit("parent not found")

        account = session.exec(
            select(ParentAccount).where(
                ParentAccount.email_normalized == email_normalized
            )
        ).first()
        if not account:
            account = ParentAccount(
                email_normalized=email_normalized,
                email_verified_at=now,
                updated_at=now,
            )
            session.add(account)
            session.flush()
        elif not account.email_verified_at:
            account.email_verified_at = now
            account.updated_at = now
            session.add(account)

        if parent.account_id and parent.account_id != account.id:
            raise SystemExit("parent is already linked to another account")

        existing_parent_for_account = session.exec(
            select(ParentUser).where(
                ParentUser.account_id == account.id,
                ParentUser.id != parent.id,
            )
        ).first()
        if existing_parent_for_account:
            raise SystemExit("account is already linked to another parent")

        parent.account_id = account.id
        parent.account_linked_at = parent.account_linked_at or now
        session.add(parent)
        session.commit()
        print(f"bound parent {parent.id} to account_id {account.id}")


if __name__ == "__main__":
    main()
