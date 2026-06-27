import argparse

from sqlmodel import Session

from app.db.session import engine
from app.services.qa_child_profile_cleanup import (
    DELETE_QA_CHILD_PROFILES_CONFIRMATION,
    QAChildProfileCleanupError,
    cleanup_qa_child_profiles,
    preview_qa_child_profile_cleanup,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean up V0.6b Dev QA child profiles.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_false",
        dest="execute",
        help="Preview matching QA child profiles without deleting them. This is the default.",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        dest="execute",
        help="Delete matching QA child profiles after confirmation.",
    )
    parser.set_defaults(execute=False)
    parser.add_argument(
        "--confirm",
        default="",
        help=f'Required with --execute. Use exactly "{DELETE_QA_CHILD_PROFILES_CONFIRMATION}".',
    )
    return parser.parse_args(argv)


def _print_result(result) -> None:
    env = result.detected_environment
    print(
        "mode={mode} environment={environment} railway_environment={railway} "
        "execute_allowed={execute_allowed} matched_count={matched_count} deleted_count={deleted_count}".format(
            mode=result.mode,
            environment=env.environment,
            railway=env.railway_environment_name or "-",
            execute_allowed=env.execute_allowed,
            matched_count=result.matched_count,
            deleted_count=result.deleted_count,
        )
    )
    for child in result.children:
        print(
            "student_id={student_id} child_name={child_name} parent_id={parent_id} "
            "essay_ids={essay_ids} record_counts={record_counts}".format(
                student_id=child.student_id,
                child_name=child.child_name,
                parent_id=child.parent_id,
                essay_ids=",".join(child.essay_ids) if child.essay_ids else "-",
                record_counts=child.record_counts,
            )
        )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    with Session(engine) as session:
        try:
            if args.execute:
                result = cleanup_qa_child_profiles(session, confirm=args.confirm)
            else:
                result = preview_qa_child_profile_cleanup(session)
        except QAChildProfileCleanupError as exc:
            raise SystemExit(str(exc)) from exc

    _print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
