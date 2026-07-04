from datetime import timedelta
from hashlib import sha256
import json
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.models import DailyTaskLimitCounter, EssayFeedbackSubmission, utcnow
from app.services.llm_usage import (
    consume_daily_task_reservation,
    release_daily_task_reservation,
)


class IdempotencyPayloadMismatch(Exception):
    """Raised when the same client_submission_id is reused with different content."""


class SubmissionAlreadyTerminal(ValueError):
    """Raised when an official result save races with terminal submission cleanup."""


TRANSPORT_FIELDS = {"client_submission_id", "timestamp", "auth", "session"}
ACTIVE_STATUSES = {
    "created",
    "reserved",
    "streaming_started",
    "first_visible_content_sent",
    "backend_continuing_after_disconnect",
    "saving_result",
}
TERMINAL_STATUSES = {
    "completed",
    "failed_released",
    "expired_released",
}
RELEASED_TERMINAL_STATUSES = {
    "failed_released",
    "expired_released",
}


def _canonicalize_value(value: Any) -> Any:
    if value == "":
        return None
    if isinstance(value, dict):
        return {
            key: _canonicalize_value(value[key])
            for key in sorted(value)
            if key not in TRANSPORT_FIELDS
        }
    if isinstance(value, list):
        return [_canonicalize_value(item) for item in value]
    return value


def build_submission_payload_hash(
    *,
    task_name: str,
    route_scope: str,
    payload_schema_version: str,
    payload: dict[str, Any],
) -> str:
    canonical = {
        "payload_schema_version": payload_schema_version,
        "route_scope": route_scope,
        "task_name": task_name,
        "payload": _canonicalize_value(payload),
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def idempotency_scope_for(student_id: str, essay_id: str | None) -> str:
    return essay_id if essay_id else f"direct:{student_id}"


def _submission_by_idempotency_key(
    *,
    session: Session,
    idempotency_scope: str,
    task_name: str,
    client_submission_id: str,
) -> EssayFeedbackSubmission | None:
    return session.exec(
        select(EssayFeedbackSubmission).where(
            EssayFeedbackSubmission.idempotency_scope == idempotency_scope,
            EssayFeedbackSubmission.task_name == task_name,
            EssayFeedbackSubmission.client_submission_id == client_submission_id,
        )
    ).first()


def create_or_get_submission(
    *,
    session: Session,
    student_id: str,
    essay_id: str | None,
    task_name: str,
    route_scope: str,
    client_submission_id: str,
    payload: dict[str, Any],
) -> EssayFeedbackSubmission:
    payload_hash = build_submission_payload_hash(
        task_name=task_name,
        route_scope=route_scope,
        payload_schema_version="v0.6e.1",
        payload=payload,
    )
    scope = idempotency_scope_for(student_id, essay_id)
    existing = _submission_by_idempotency_key(
        session=session,
        idempotency_scope=scope,
        task_name=task_name,
        client_submission_id=client_submission_id,
    )
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise IdempotencyPayloadMismatch
        return existing

    submission = EssayFeedbackSubmission(
        student_id=student_id,
        essay_id=essay_id,
        idempotency_scope=scope,
        route_scope=route_scope,
        payload_schema_version="v0.6e.1",
        task_name=task_name,
        client_submission_id=client_submission_id,
        payload_hash=payload_hash,
        status="created",
    )
    try:
        with session.begin_nested():
            session.add(submission)
            session.flush()
        return submission
    except IntegrityError as exc:
        with session.no_autoflush:
            existing = _submission_by_idempotency_key(
                session=session,
                idempotency_scope=scope,
                task_name=task_name,
                client_submission_id=client_submission_id,
            )
        if existing is None:
            raise
        if existing.payload_hash != payload_hash:
            raise IdempotencyPayloadMismatch from exc
        return existing


def _get_submission_for_update(
    *,
    session: Session,
    submission_id: str,
) -> EssayFeedbackSubmission:
    submission = session.exec(
        select(EssayFeedbackSubmission)
        .where(EssayFeedbackSubmission.id == submission_id)
        .with_for_update()
    ).first()
    if submission is None:
        raise ValueError("essay feedback submission not found")
    return submission


def _is_terminal(submission: EssayFeedbackSubmission) -> bool:
    return submission.completed_at is not None or submission.status in TERMINAL_STATUSES


def _reservation_token_is_active(
    *,
    session: Session,
    counter_id: str | None,
    reservation_token: str | None,
) -> bool:
    if counter_id is None:
        return True
    if reservation_token is None:
        return False
    counter = session.exec(
        select(DailyTaskLimitCounter)
        .where(DailyTaskLimitCounter.id == counter_id)
        .with_for_update()
    ).first()
    if counter is None:
        return False
    return reservation_token in dict(counter.active_reservations or {})


def mark_submission_status(
    *,
    session: Session,
    submission_id: str,
    status: str,
    llm_call_log_id: str | None = None,
    error_code: str = "",
    error_message: str = "",
) -> EssayFeedbackSubmission:
    if status in TERMINAL_STATUSES:
        raise ValueError("terminal submission statuses must use finalizers")
    submission = _get_submission_for_update(session=session, submission_id=submission_id)
    if _is_terminal(submission):
        return submission
    submission.status = status
    submission.updated_at = utcnow()
    if llm_call_log_id is not None:
        submission.llm_call_log_id = llm_call_log_id
    if error_code:
        submission.error_code = error_code
    if error_message:
        submission.error_message = error_message
    session.add(submission)
    session.flush()
    return submission


def begin_submission_result_save(
    *,
    session: Session,
    submission_id: str,
) -> EssayFeedbackSubmission:
    submission = _get_submission_for_update(session=session, submission_id=submission_id)
    if _is_terminal(submission):
        raise SubmissionAlreadyTerminal("essay feedback submission is already terminal")
    submission.status = "saving_result"
    submission.updated_at = utcnow()
    session.add(submission)
    session.flush()
    return submission


def finalize_submission_once(
    *,
    session: Session,
    submission_id: str,
    status: str,
    essay_version_id: str | None,
    result_fetch_url: str,
    llm_call_log_id: str | None = None,
    error_code: str = "",
    error_message: str = "",
) -> EssayFeedbackSubmission:
    submission = _get_submission_for_update(session=session, submission_id=submission_id)
    if _is_terminal(submission):
        return submission

    now = utcnow()
    submission.status = status
    submission.essay_version_id = essay_version_id
    submission.result_fetch_url = result_fetch_url
    submission.updated_at = now
    submission.completed_at = now
    if llm_call_log_id is not None:
        submission.llm_call_log_id = llm_call_log_id
    if error_code:
        submission.error_code = error_code
    if error_message:
        submission.error_message = error_message
    session.add(submission)
    session.flush()
    return submission


def finalize_submission_with_reservation(
    *,
    session: Session,
    submission_id: str,
    terminal_status: str,
    saved_result: bool,
    essay_version_id: str | None,
    result_fetch_url: str,
    llm_call_log_id: str | None = None,
    error_code: str = "",
    error_message: str = "",
) -> EssayFeedbackSubmission:
    submission = _get_submission_for_update(session=session, submission_id=submission_id)
    if _is_terminal(submission):
        return submission

    if terminal_status == "completed" and saved_result:
        if not _reservation_token_is_active(
            session=session,
            counter_id=submission.daily_limit_counter_id,
            reservation_token=submission.daily_limit_reservation_token,
        ):
            raise ValueError("essay feedback submission reservation is no longer active")
        consume_daily_task_reservation(
            session=session,
            counter_id=submission.daily_limit_counter_id,
            reservation_token=submission.daily_limit_reservation_token,
        )
    elif terminal_status in RELEASED_TERMINAL_STATUSES and not saved_result:
        release_daily_task_reservation(
            session=session,
            counter_id=submission.daily_limit_counter_id,
            reservation_token=submission.daily_limit_reservation_token,
        )
    else:
        raise ValueError("invalid essay feedback submission finalization")

    return finalize_submission_once(
        session=session,
        submission_id=submission_id,
        status=terminal_status,
        essay_version_id=essay_version_id,
        result_fetch_url=result_fetch_url,
        llm_call_log_id=llm_call_log_id,
        error_code=error_code,
        error_message=error_message,
    )


def cleanup_stale_submissions(
    *,
    session: Session,
    now_offset_seconds: int = 0,
    stale_after_seconds: int = 120,
) -> int:
    now = utcnow() + timedelta(seconds=now_offset_seconds)
    cutoff = now - timedelta(seconds=stale_after_seconds)
    stale_submissions = session.exec(
        select(EssayFeedbackSubmission).where(
            EssayFeedbackSubmission.status.in_(ACTIVE_STATUSES),
            EssayFeedbackSubmission.updated_at <= cutoff,
        )
    ).all()

    finalized_count = 0
    for submission in stale_submissions:
        if _is_terminal(submission):
            continue
        finalize_submission_with_reservation(
            session=session,
            submission_id=submission.id,
            terminal_status="expired_released",
            saved_result=False,
            essay_version_id=None,
            result_fetch_url="",
            error_code="submission_timeout",
        )
        finalized_count += 1
    session.flush()
    return finalized_count
