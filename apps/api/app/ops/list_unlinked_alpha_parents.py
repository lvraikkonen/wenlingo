from contextlib import closing

from sqlmodel import select

from app.db.session import get_session
from app.domain.models import AlphaInviteCode, ParentAccount, ParentUser, StudentProfile


def main() -> None:
    session_gen = get_session()
    with closing(session_gen):
        session = next(session_gen)
        parents = session.exec(
            select(ParentUser)
            .where(ParentUser.account_id.is_(None))
            .order_by(ParentUser.created_at)
        ).all()

        for parent in parents:
            invite = session.exec(
                select(AlphaInviteCode)
                .where(AlphaInviteCode.consumed_by_parent_id == parent.id)
                .order_by(AlphaInviteCode.consumed_at.desc())
            ).first()
            child_count = len(
                session.exec(
                    select(StudentProfile).where(StudentProfile.parent_id == parent.id)
                ).all()
            )
            invite_label = invite.label if invite else ""
            print(
                f"invite={invite_label}\tparent_id={parent.id}\t"
                f"display_name={parent.display_name}\tchild_count={child_count}"
            )


if __name__ == "__main__":
    main()
