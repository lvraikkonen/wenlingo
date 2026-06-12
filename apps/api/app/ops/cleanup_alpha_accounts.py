import argparse
from contextlib import closing

from fastapi import HTTPException
from sqlmodel import select

from app.core.config import get_settings
from app.db.session import get_session
from app.domain.models import ParentAccount
from app.services.admin_test_account_cleanup import (
    DELETE_ALPHA_ACCOUNT_CONFIRMATION,
    delete_alpha_accounts,
    preview_alpha_account_deletion,
)
from app.services.auth_security import mask_email


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized:
        raise SystemExit("email is required")
    return normalized


def _print_result(prefix: str, result) -> None:
    print(f"{prefix}: {result.deleted_count} account(s)")
    for row in result.deleted_accounts:
        print(
            "account_id={account_id} email={email} parents={parents} "
            "children={children} sessions={sessions} invites={invites}".format(
                account_id=row.account_id,
                email=row.email_masked,
                parents=len(row.parent_ids),
                children=row.child_count,
                sessions=row.deleted_session_count,
                invites=row.deleted_invite_count,
            )
        )


def _resolve_account_ids(session, *, emails: list[str], account_ids: list[str]) -> list[str]:
    resolved = list(account_ids)
    for raw_email in emails:
        email_normalized = _normalize_email(raw_email)
        account = session.exec(
            select(ParentAccount).where(
                ParentAccount.email_normalized == email_normalized
            )
        ).first()
        if not account:
            raise SystemExit(f"account not found for {mask_email(email_normalized)}")
        resolved.append(account.id)
    deduped = list(dict.fromkeys(resolved))
    if not deduped:
        raise SystemExit("at least one --email or --account-id is required")
    return deduped


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up Alpha accounts by id or email.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--email", action="append", default=[])
    target.add_argument("--account-id", action="append", default=[])
    parser.add_argument(
        "--allow-real-email",
        action="store_true",
        help="Allow deleting non-test email domains such as qq.com or hotmail.com.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview rows that would be deleted. This is the default.",
    )
    parser.add_argument(
        "--execute",
        action="store_false",
        dest="dry_run",
        help="Actually delete rows after confirmation.",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help='Required with --execute. Use exactly "DELETE ALPHA ACCOUNT".',
    )
    args = parser.parse_args()

    settings = get_settings()
    if settings.environment == "production":
        raise SystemExit("refusing to clean up Alpha accounts in production")

    session_gen = get_session()
    with closing(session_gen):
        session = next(session_gen)
        account_ids = _resolve_account_ids(
            session,
            emails=args.email,
            account_ids=args.account_id,
        )
        try:
            if args.dry_run:
                preview = preview_alpha_account_deletion(
                    session,
                    account_ids=account_ids,
                    allow_real_email=args.allow_real_email,
                )
                _print_result("dry-run", preview)
                return
            result = delete_alpha_accounts(
                session,
                account_ids=account_ids,
                confirm=args.confirm,
                allow_real_email=args.allow_real_email,
            )
            _print_result("deleted", result)
        except HTTPException as exc:
            raise SystemExit(str(exc.detail)) from exc


if __name__ == "__main__":
    main()
