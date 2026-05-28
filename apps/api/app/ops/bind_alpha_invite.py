import argparse
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.api.routes.alpha import hash_invite_code, record_product_event
from app.db.session import engine
from app.domain.models import AlphaInviteCode, ParentUser


def main() -> None:
    parser = argparse.ArgumentParser(description="Bind a legacy parent to an alpha invite.")
    parser.add_argument("--parent-id", required=True)
    parser.add_argument("--code", required=True)
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    with Session(engine) as session:
        parent = session.get(ParentUser, args.parent_id)
        if not parent:
            raise SystemExit("parent not found")

        invite = session.exec(
            select(AlphaInviteCode).where(
                AlphaInviteCode.code_hash == hash_invite_code(args.code)
            )
        ).first()
        if not invite:
            raise SystemExit("invite code not found")
        if invite.consumed_by_parent_id and invite.consumed_by_parent_id != parent.id:
            raise SystemExit("invite code is consumed by a different parent")

        invite.status = "consumed"
        invite.consumed_by_parent_id = parent.id
        invite.consumed_at = invite.consumed_at or datetime.now(timezone.utc)
        if args.note:
            invite.issued_to_note = args.note
        session.add(invite)
        record_product_event(
            session,
            "legacy_parent_invite_bound",
            parent_id=parent.id,
            invite_code_id=invite.id,
        )
        session.commit()
        print(f"bound invite {invite.id} to parent {parent.id}")


if __name__ == "__main__":
    main()
