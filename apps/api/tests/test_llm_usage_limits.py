from datetime import datetime, timezone

from sqlmodel import select

from app.domain.enums import TaskType
from app.domain.models import DailyTaskLimitCounter, LLMCallLog
from app.services.llm_usage import (
    consume_daily_task_reservation,
    fail_daily_task_reservation,
    local_product_day,
    llm_daily_limit_reached,
    local_day_start_utc,
    release_daily_task_reservation,
    reserve_daily_task_limit_slot,
)


def add_llm_log(
    session,
    *,
    student_id: str = "s1",
    task_name: str = "sentence_upgrade_feedback",
    provider: str = "http",
    final_status: str = "primary_success",
    created_at: datetime,
):
    session.add(
        LLMCallLog(
            student_id=student_id,
            task_type=TaskType.sentence,
            task_name=task_name,
            provider=provider,
            model="test-model",
            final_status=final_status,
            prompt_version="test-v1",
            input_summary="usage limit test",
            raw_response="{}",
            output_json={},
            validation_ok=final_status
            in {
                "primary_success",
                "fallback_success",
                "deterministic_fallback_used",
            },
            error_message="",
            retry_count=0,
            created_at=created_at,
        )
    )
    session.flush()


def test_local_day_start_utc_uses_asia_shanghai_boundary():
    now = datetime(2026, 6, 10, 1, 30, tzinfo=timezone.utc)

    assert local_day_start_utc(now, "Asia/Shanghai") == datetime(
        2026, 6, 9, 16, 0, tzinfo=timezone.utc
    )


def test_local_product_day_uses_configured_timezone():
    now = datetime(2026, 6, 7, 18, 30, tzinfo=timezone.utc)

    assert local_product_day(now, "Asia/Shanghai") == "2026-06-08"


def test_llm_daily_limit_reached_counts_task_outputs_not_provider(session):
    now = datetime(2026, 6, 10, 3, 0, tzinfo=timezone.utc)
    add_llm_log(
        session,
        task_name="sentence_upgrade_feedback",
        provider="http",
        final_status="primary_success",
        created_at=datetime(2026, 6, 9, 16, 5, tzinfo=timezone.utc),
    )
    add_llm_log(
        session,
        task_name="sentence_upgrade_feedback",
        provider="fallback-http",
        final_status="fallback_success",
        created_at=datetime(2026, 6, 9, 16, 10, tzinfo=timezone.utc),
    )
    add_llm_log(
        session,
        task_name="sentence_upgrade_feedback",
        provider="http",
        final_status="failed",
        created_at=datetime(2026, 6, 9, 16, 15, tzinfo=timezone.utc),
    )
    add_llm_log(
        session,
        task_name="essay_feedback",
        provider="http",
        final_status="primary_success",
        created_at=datetime(2026, 6, 9, 16, 20, tzinfo=timezone.utc),
    )

    assert llm_daily_limit_reached(
        session=session,
        student_id="s1",
        task_name="sentence_upgrade_feedback",
        limit=2,
        timezone_name="Asia/Shanghai",
        now=now,
    )
    assert not llm_daily_limit_reached(
        session=session,
        student_id="s1",
        task_name="sentence_upgrade_feedback",
        limit=3,
        timezone_name="Asia/Shanghai",
        now=now,
    )


def test_reserve_daily_task_limit_slot_allows_one_slot_and_blocks_next(session):
    first = reserve_daily_task_limit_slot(
        session=session,
        student_id="s1",
        task_name="sentence_challenge_generation",
        limit=1,
        timezone_name="Asia/Shanghai",
        now=datetime(2026, 6, 8, 1, 0, tzinfo=timezone.utc),
    )
    second = reserve_daily_task_limit_slot(
        session=session,
        student_id="s1",
        task_name="sentence_challenge_generation",
        limit=1,
        timezone_name="Asia/Shanghai",
        now=datetime(2026, 6, 8, 1, 1, tzinfo=timezone.utc),
    )

    assert first.reserved is True
    assert first.reservation_token is not None
    assert second.reserved is False
    counter = session.exec(select(DailyTaskLimitCounter)).one()
    assert counter.reserved_count == 1
    assert counter.consumed_count == 0
    assert first.reservation_token in counter.active_reservations


def test_consume_and_release_daily_task_reservation(session):
    reservation = reserve_daily_task_limit_slot(
        session=session,
        student_id="s1",
        task_name="sentence_challenge_feedback",
        limit=2,
        timezone_name="Asia/Shanghai",
        now=datetime(2026, 6, 8, 1, 0, tzinfo=timezone.utc),
    )

    consume_daily_task_reservation(
        session=session,
        counter_id=reservation.counter_id,
        reservation_token=reservation.reservation_token,
    )

    counter = session.get(DailyTaskLimitCounter, reservation.counter_id)
    assert counter.reserved_count == 0
    assert counter.consumed_count == 1
    assert reservation.reservation_token not in counter.active_reservations

    second = reserve_daily_task_limit_slot(
        session=session,
        student_id="s1",
        task_name="sentence_challenge_feedback",
        limit=2,
        timezone_name="Asia/Shanghai",
        now=datetime(2026, 6, 8, 1, 2, tzinfo=timezone.utc),
    )
    release_daily_task_reservation(
        session=session,
        counter_id=second.counter_id,
        reservation_token=second.reservation_token,
    )

    session.refresh(counter)
    assert counter.reserved_count == 0
    assert counter.consumed_count == 1
    assert counter.released_count == 1
    assert second.reservation_token not in counter.active_reservations


def test_fail_daily_task_reservation_releases_slot_and_records_failure(session):
    reservation = reserve_daily_task_limit_slot(
        session=session,
        student_id="s1",
        task_name="sentence_challenge_feedback",
        limit=1,
        timezone_name="Asia/Shanghai",
        now=datetime(2026, 6, 8, 1, 0, tzinfo=timezone.utc),
    )

    fail_daily_task_reservation(
        session=session,
        counter_id=reservation.counter_id,
        reservation_token=reservation.reservation_token,
    )

    counter = session.get(DailyTaskLimitCounter, reservation.counter_id)
    assert counter.reserved_count == 0
    assert counter.failed_count == 1
    assert counter.reservation_expires_at is None
    assert reservation.reservation_token not in counter.active_reservations


def test_stale_old_reservation_finalizer_does_not_release_newer_reservation(session):
    first = reserve_daily_task_limit_slot(
        session=session,
        student_id="s1",
        task_name="sentence_challenge_generation",
        limit=1,
        timezone_name="Asia/Shanghai",
        now=datetime(2026, 6, 8, 1, 0, tzinfo=timezone.utc),
        reservation_ttl_seconds=30,
    )
    second = reserve_daily_task_limit_slot(
        session=session,
        student_id="s1",
        task_name="sentence_challenge_generation",
        limit=1,
        timezone_name="Asia/Shanghai",
        now=datetime(2026, 6, 8, 1, 1, tzinfo=timezone.utc),
        reservation_ttl_seconds=120,
    )

    release_daily_task_reservation(
        session=session,
        counter_id=first.counter_id,
        reservation_token=first.reservation_token,
    )

    counter = session.get(DailyTaskLimitCounter, first.counter_id)
    assert first.reserved is True
    assert second.reserved is True
    assert counter.reserved_count == 1
    assert counter.released_count == 1
    assert second.reservation_token in counter.active_reservations
    assert first.reservation_token not in counter.active_reservations


def test_tokenless_finalizer_does_not_mutate_tokenized_reservation(session):
    reservation = reserve_daily_task_limit_slot(
        session=session,
        student_id="s1",
        task_name="sentence_challenge_generation",
        limit=1,
        timezone_name="Asia/Shanghai",
        now=datetime(2026, 6, 8, 1, 0, tzinfo=timezone.utc),
    )

    release_daily_task_reservation(session=session, counter_id=reservation.counter_id)

    counter = session.get(DailyTaskLimitCounter, reservation.counter_id)
    assert counter.reserved_count == 1
    assert counter.released_count == 0
    assert reservation.reservation_token in counter.active_reservations


def test_stale_reservation_is_released_before_limit_check(session):
    first = reserve_daily_task_limit_slot(
        session=session,
        student_id="s1",
        task_name="sentence_challenge_generation",
        limit=1,
        timezone_name="Asia/Shanghai",
        now=datetime(2026, 6, 8, 1, 0, tzinfo=timezone.utc),
        reservation_ttl_seconds=30,
    )
    second = reserve_daily_task_limit_slot(
        session=session,
        student_id="s1",
        task_name="sentence_challenge_generation",
        limit=1,
        timezone_name="Asia/Shanghai",
        now=datetime(2026, 6, 8, 1, 1, tzinfo=timezone.utc),
        reservation_ttl_seconds=30,
    )

    assert first.reserved is True
    assert second.reserved is True
    counter = session.get(DailyTaskLimitCounter, first.counter_id)
    assert counter.reserved_count == 1
    assert counter.released_count == 1
    assert second.reservation_token in counter.active_reservations
