import pytest
from sqlmodel import select

from app.domain.models import DailyTaskLimitCounter
from app.services.essay_feedback_submission import (
    IdempotencyPayloadMismatch,
    build_submission_payload_hash,
    cleanup_stale_submissions,
    create_or_get_submission,
    finalize_submission_once,
    finalize_submission_with_reservation,
)
from app.services.llm_usage import reserve_daily_task_limit_slot


def test_payload_hash_ignores_transport_fields():
    first = build_submission_payload_hash(
        task_name="essay_feedback",
        route_scope="direct_draft",
        payload_schema_version="v0.6e.1",
        payload={
            "title": "我的一天",
            "draft": "今天我去了公园。",
            "client_submission_id": "a",
            "timestamp": "2026-07-03T00:00:00Z",
        },
    )
    second = build_submission_payload_hash(
        task_name="essay_feedback",
        route_scope="direct_draft",
        payload_schema_version="v0.6e.1",
        payload={
            "draft": "今天我去了公园。",
            "title": "我的一天",
            "client_submission_id": "b",
        },
    )

    assert first == second


def test_same_key_different_payload_raises_conflict(session):
    create_or_get_submission(
        session=session,
        student_id="student-1",
        essay_id=None,
        task_name="essay_feedback",
        route_scope="direct_draft",
        client_submission_id="submission-1",
        payload={"title": "A", "draft": "draft A"},
    )

    with pytest.raises(IdempotencyPayloadMismatch):
        create_or_get_submission(
            session=session,
            student_id="student-1",
            essay_id=None,
            task_name="essay_feedback",
            route_scope="direct_draft",
            client_submission_id="submission-1",
            payload={"title": "B", "draft": "draft B"},
        )


def test_payload_mismatch_does_not_mutate_existing_submission(session):
    existing = create_or_get_submission(
        session=session,
        student_id="student-1",
        essay_id=None,
        task_name="essay_feedback",
        route_scope="direct_draft",
        client_submission_id="submission-1",
        payload={"title": "A", "draft": "draft A"},
    )

    with pytest.raises(IdempotencyPayloadMismatch):
        create_or_get_submission(
            session=session,
            student_id="student-1",
            essay_id=None,
            task_name="essay_feedback",
            route_scope="direct_draft",
            client_submission_id="submission-1",
            payload={"title": "B", "draft": "draft B"},
        )

    session.refresh(existing)
    assert existing.status == "created"


def test_finalize_submission_once_is_idempotent(session):
    submission = create_or_get_submission(
        session=session,
        student_id="student-1",
        essay_id="essay-1",
        task_name="essay_feedback",
        route_scope="prewriting_first_draft",
        client_submission_id="submission-1",
        payload={"draft": "孩子自己的初稿"},
    )

    first = finalize_submission_once(
        session=session,
        submission_id=submission.id,
        status="completed",
        essay_version_id="version-1",
        result_fetch_url="/api/essays/essay-1",
    )
    second = finalize_submission_once(
        session=session,
        submission_id=submission.id,
        status="completed",
        essay_version_id="version-1",
        result_fetch_url="/api/essays/essay-1",
    )

    assert first.completed_at is not None
    assert second.completed_at == first.completed_at


def test_completed_submission_consumes_reservation_once(session):
    reservation = reserve_daily_task_limit_slot(
        session=session,
        student_id="student-1",
        task_name="essay_feedback",
        limit=1,
        timezone_name="UTC",
    )
    submission = create_or_get_submission(
        session=session,
        student_id="student-1",
        essay_id=None,
        task_name="essay_feedback",
        route_scope="direct_draft",
        client_submission_id="submission-1",
        payload={"title": "A", "draft": "draft A"},
    )
    submission.daily_limit_counter_id = reservation.counter_id
    submission.daily_limit_reservation_token = reservation.reservation_token
    session.add(submission)
    session.commit()

    finalize_submission_with_reservation(
        session=session,
        submission_id=submission.id,
        terminal_status="completed",
        saved_result=True,
        essay_version_id="version-1",
        result_fetch_url="/api/essays/essay-1",
    )
    finalize_submission_with_reservation(
        session=session,
        submission_id=submission.id,
        terminal_status="completed",
        saved_result=True,
        essay_version_id="version-1",
        result_fetch_url="/api/essays/essay-1",
    )

    counter = session.get(DailyTaskLimitCounter, reservation.counter_id)
    assert counter is not None
    assert counter.consumed_count == 1
    assert counter.released_count == 0
    assert counter.reserved_count == 0


def test_failed_without_saved_result_releases_reservation_once(session):
    reservation = reserve_daily_task_limit_slot(
        session=session,
        student_id="student-1",
        task_name="essay_feedback",
        limit=1,
        timezone_name="UTC",
    )
    submission = create_or_get_submission(
        session=session,
        student_id="student-1",
        essay_id=None,
        task_name="essay_feedback",
        route_scope="direct_draft",
        client_submission_id="submission-1",
        payload={"title": "A", "draft": "draft A"},
    )
    submission.daily_limit_counter_id = reservation.counter_id
    submission.daily_limit_reservation_token = reservation.reservation_token
    session.add(submission)
    session.commit()

    finalize_submission_with_reservation(
        session=session,
        submission_id=submission.id,
        terminal_status="failed_released",
        saved_result=False,
        essay_version_id=None,
        result_fetch_url="",
    )
    finalize_submission_with_reservation(
        session=session,
        submission_id=submission.id,
        terminal_status="failed_released",
        saved_result=False,
        essay_version_id=None,
        result_fetch_url="",
    )

    counter = session.get(DailyTaskLimitCounter, reservation.counter_id)
    assert counter is not None
    assert counter.consumed_count == 0
    assert counter.released_count == 1
    assert counter.reserved_count == 0


def test_stale_streaming_submission_cleanup_releases_once(session):
    reservation = reserve_daily_task_limit_slot(
        session=session,
        student_id="student-1",
        task_name="essay_feedback",
        limit=1,
        timezone_name="UTC",
    )
    submission = create_or_get_submission(
        session=session,
        student_id="student-1",
        essay_id=None,
        task_name="essay_feedback",
        route_scope="direct_draft",
        client_submission_id="submission-1",
        payload={"title": "A", "draft": "draft A"},
    )
    submission.status = "streaming_started"
    submission.daily_limit_counter_id = reservation.counter_id
    submission.daily_limit_reservation_token = reservation.reservation_token
    session.add(submission)
    session.commit()

    cleanup_stale_submissions(session=session, now_offset_seconds=3600)
    cleanup_stale_submissions(session=session, now_offset_seconds=3600)

    counter = session.exec(select(DailyTaskLimitCounter)).one()
    assert counter.released_count == 1
    assert counter.reserved_count == 0
