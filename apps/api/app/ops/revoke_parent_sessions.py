import argparse
from contextlib import closing

from sqlmodel import select

from app.db.session import get_session
from app.domain.models import ParentAccount, ParentSession, utcnow


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized:
        raise SystemExit("email is required")
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description="Revoke active parent account sessions.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--email")
    target.add_argument("--account-id")
    args = parser.parse_args()

    session_gen = get_session()
    with closing(session_gen):
        session = next(session_gen)
        account_id = args.account_id
        if args.email:
            account = session.exec(
                select(ParentAccount).where(
                    ParentAccount.email_normalized == _normalize_email(args.email)
                )
            ).first()
            if not account:
                raise SystemExit("account not found")
            account_id = account.id

        now = utcnow()
        sessions = session.exec(
            select(ParentSession).where(
                ParentSession.account_id == account_id,
                ParentSession.revoked_at.is_(None),
                ParentSession.expires_at > now,
            )
        ).all()
        for parent_session in sessions:
            parent_session.revoked_at = now
            session.add(parent_session)
        session.commit()
        print(f"revoked {len(sessions)} active sessions for account_id {account_id}")


if __name__ == "__main__":
    main()
