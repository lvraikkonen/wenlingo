import argparse

from sqlmodel import Session

from app.db.session import engine
from app.services.parent_sessions import cleanup_parent_sessions


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean up old parent account sessions.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_false",
        dest="execute",
        help="Preview eligible rows without deleting them. This is the default.",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        dest="execute",
        help="Delete eligible rows.",
    )
    parser.set_defaults(execute=False)
    parser.add_argument("--revoked-retention-days", type=int, default=30)
    parser.add_argument("--expired-retention-days", type=int, default=30)
    args = parser.parse_args(argv)
    if args.revoked_retention_days < 0 or args.expired_retention_days < 0:
        raise SystemExit("retention days must be zero or positive")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    with Session(engine) as session:
        result = cleanup_parent_sessions(
            db=session,
            revoked_retention_days=args.revoked_retention_days,
            expired_retention_days=args.expired_retention_days,
            execute=args.execute,
        )

    mode = "execute" if args.execute else "dry-run"
    print(
        "mode={mode} scanned_count={scanned_count} eligible_count={eligible_count} "
        "deleted_count={deleted_count} reason_counts={reason_counts} "
        "revoked_cutoff={revoked_cutoff} expired_cutoff={expired_cutoff}".format(
            mode=mode,
            scanned_count=result.scanned_count,
            eligible_count=result.eligible_count,
            deleted_count=result.deleted_count,
            reason_counts=result.reason_counts,
            revoked_cutoff=result.revoked_cutoff.isoformat(),
            expired_cutoff=result.expired_cutoff.isoformat(),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
