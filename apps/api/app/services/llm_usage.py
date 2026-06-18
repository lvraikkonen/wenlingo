from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.models import DailyTaskLimitCounter, LLMCallLog, utcnow


PRODUCT_OUTPUT_FINAL_STATUSES = {
    "primary_success",
    "fallback_success",
    "deterministic_fallback_used",
}


@dataclass(frozen=True)
class DailyLimitReservation:
    reserved: bool
    counter_id: str | None
    product_day: str


def local_day_start_utc(now: datetime, timezone_name: str) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    local_tz = ZoneInfo(timezone_name)
    local_today = now.astimezone(local_tz).date()
    local_start = datetime.combine(local_today, time.min, tzinfo=local_tz)
    return local_start.astimezone(timezone.utc)


def local_product_day(now: datetime, timezone_name: str) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(ZoneInfo(timezone_name)).date().isoformat()


def llm_daily_limit_reached(
    *,
    session: Session,
    student_id: str,
    task_name: str,
    limit: int,
    timezone_name: str,
    now: datetime | None = None,
) -> bool:
    if limit <= 0:
        return False
    now = now or datetime.now(timezone.utc)
    count = session.exec(
        select(func.count(LLMCallLog.id)).where(
            LLMCallLog.student_id == student_id,
            LLMCallLog.task_name == task_name,
            LLMCallLog.final_status.in_(PRODUCT_OUTPUT_FINAL_STATUSES),
            LLMCallLog.created_at >= local_day_start_utc(now, timezone_name),
        )
    ).one()
    return int(count) >= limit


def _release_stale_reservation(counter: DailyTaskLimitCounter, now: datetime) -> None:
    reservation_expires_at = counter.reservation_expires_at
    if reservation_expires_at is not None and reservation_expires_at.tzinfo is None:
        reservation_expires_at = reservation_expires_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if (
        counter.reserved_count > 0
        and reservation_expires_at is not None
        and reservation_expires_at <= now
    ):
        counter.released_count += counter.reserved_count
        counter.reserved_count = 0
        counter.reservation_expires_at = None
        counter.updated_at = now


def _daily_task_counter_statement(
    *,
    student_id: str,
    task_name: str,
    product_day: str,
):
    return (
        select(DailyTaskLimitCounter)
        .where(
            DailyTaskLimitCounter.student_id == student_id,
            DailyTaskLimitCounter.task_name == task_name,
            DailyTaskLimitCounter.product_day == product_day,
        )
        .with_for_update()
    )


def _load_daily_task_counter_for_update(
    *,
    session: Session,
    student_id: str,
    task_name: str,
    product_day: str,
) -> DailyTaskLimitCounter | None:
    return session.exec(
        _daily_task_counter_statement(
            student_id=student_id,
            task_name=task_name,
            product_day=product_day,
        )
    ).first()


def _create_or_load_daily_task_counter_for_update(
    *,
    session: Session,
    student_id: str,
    task_name: str,
    product_day: str,
    limit: int,
) -> DailyTaskLimitCounter:
    counter = _load_daily_task_counter_for_update(
        session=session,
        student_id=student_id,
        task_name=task_name,
        product_day=product_day,
    )
    if counter is not None:
        return counter

    counter = DailyTaskLimitCounter(
        student_id=student_id,
        task_name=task_name,
        product_day=product_day,
        limit_value=limit,
        reserved_count=0,
        consumed_count=0,
        failed_count=0,
        released_count=0,
    )
    try:
        with session.begin_nested():
            session.add(counter)
            session.flush()
        return counter
    except IntegrityError:
        counter = _load_daily_task_counter_for_update(
            session=session,
            student_id=student_id,
            task_name=task_name,
            product_day=product_day,
        )
        if counter is None:
            raise
        return counter


def reserve_daily_task_limit_slot(
    *,
    session: Session,
    student_id: str,
    task_name: str,
    limit: int,
    timezone_name: str,
    now: datetime | None = None,
    reservation_ttl_seconds: int = 120,
) -> DailyLimitReservation:
    now = now or utcnow()
    if limit <= 0:
        return DailyLimitReservation(True, None, local_product_day(now, timezone_name))

    product_day = local_product_day(now, timezone_name)
    counter = _create_or_load_daily_task_counter_for_update(
        session=session,
        student_id=student_id,
        task_name=task_name,
        product_day=product_day,
        limit=limit,
    )

    _release_stale_reservation(counter, now)
    counter.limit_value = limit
    if counter.reserved_count + counter.consumed_count >= limit:
        session.add(counter)
        session.flush()
        return DailyLimitReservation(False, counter.id, product_day)

    counter.reserved_count += 1
    # This is a counter-level expiry, not per-slot. Refresh it on each new
    # reservation so older reservations cannot release newer ones early.
    counter.reservation_expires_at = now + timedelta(seconds=reservation_ttl_seconds)
    counter.updated_at = now
    session.add(counter)
    session.flush()
    return DailyLimitReservation(True, counter.id, product_day)


def consume_daily_task_reservation(*, session: Session, counter_id: str | None) -> None:
    if counter_id is None:
        return
    counter = session.get(DailyTaskLimitCounter, counter_id)
    if counter is None:
        return
    if counter.reserved_count > 0:
        counter.reserved_count -= 1
    counter.consumed_count += 1
    counter.reservation_expires_at = (
        None if counter.reserved_count == 0 else counter.reservation_expires_at
    )
    counter.updated_at = utcnow()
    session.add(counter)
    session.flush()


def release_daily_task_reservation(*, session: Session, counter_id: str | None) -> None:
    if counter_id is None:
        return
    counter = session.get(DailyTaskLimitCounter, counter_id)
    if counter is None:
        return
    if counter.reserved_count > 0:
        counter.reserved_count -= 1
        counter.released_count += 1
    counter.reservation_expires_at = (
        None if counter.reserved_count == 0 else counter.reservation_expires_at
    )
    counter.updated_at = utcnow()
    session.add(counter)
    session.flush()


def fail_daily_task_reservation(*, session: Session, counter_id: str | None) -> None:
    if counter_id is None:
        return
    counter = session.get(DailyTaskLimitCounter, counter_id)
    if counter is None:
        return
    if counter.reserved_count > 0:
        counter.reserved_count -= 1
    counter.failed_count += 1
    counter.reservation_expires_at = (
        None if counter.reserved_count == 0 else counter.reservation_expires_at
    )
    counter.updated_at = utcnow()
    session.add(counter)
    session.flush()
