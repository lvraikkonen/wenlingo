import argparse
import secrets

from sqlmodel import Session

from app.api.routes.alpha import hash_invite_code
from app.db.session import engine
from app.domain.models import AlphaInviteCode


def _generate_code() -> str:
    return f"ALPHA-{secrets.token_urlsafe(9).upper().replace('-', '').replace('_', '')}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create alpha invite codes.")
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--label-prefix", default="Alpha family")
    parser.add_argument("--issued-to-note", default="")
    args = parser.parse_args()

    if args.count < 1:
        raise SystemExit("--count must be at least 1")

    raw_codes: list[str] = []
    with Session(engine) as session:
        for index in range(1, args.count + 1):
            code = _generate_code()
            while hash_invite_code(code) in {
                row.code_hash for row in session.query(AlphaInviteCode).all()
            }:
                code = _generate_code()
            invite = AlphaInviteCode(
                code_hash=hash_invite_code(code),
                label=f"{args.label_prefix} {index:02d}",
                status="issued",
                issued_to_note=args.issued_to_note,
            )
            session.add(invite)
            raw_codes.append(code)
        session.commit()

    for code in raw_codes:
        print(code)


if __name__ == "__main__":
    main()
