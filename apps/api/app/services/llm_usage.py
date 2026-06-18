from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.models import DailyTaskLimitCounter, LLMCallLog, new_uuid, utcnow


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
    reservation_token: str | None = None
    reservation_expires_at: datetime | None = None


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


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _reservation_expiry_from_iso(value: str) -> datetime:
    return _ensure_utc(datetime.fromisoformat(value))


def _refresh_reservation_state(counter: DailyTaskLimitCounter) -> None:
    active_reservations = dict(counter.active_reservations or {})
    counter.active_reservations = active_reservations
    counter.reserved_count = len(active_reservations)
    if not active_reservations:
        counter.reservation_expires_at = None
        return
    counter.reservation_expires_at = max(
        _reservation_expiry_from_iso(expires_at)
        for expires_at in active_reservations.values()
    )


def _release_stale_reservations(counter: DailyTaskLimitCounter, now: datetime) -> None:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    active_reservations = dict(counter.active_reservations or {})
    if not active_reservations and counter.reserved_count > 0:
        active_reservations = {
            "__legacy__": _ensure_utc(counter.reservation_expires_at).isoformat()
        } if counter.reservation_expires_at is not None else {}

    current_reservations = {
        token: expires_at
        for token, expires_at in active_reservations.items()
        if _reservation_expiry_from_iso(expires_at) > now
    }
    released_count = len(active_reservations) - len(current_reservations)
    if released_count > 0:
        counter.released_count += released_count
        counter.active_reservations = current_reservations
        _refresh_reservation_state(counter)
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


def _load_daily_task_counter_by_id_for_update(
    *,
    session: Session,
    counter_id: str,
) -> DailyTaskLimitCounter | None:
    return session.exec(
        select(DailyTaskLimitCounter)
        .where(DailyTaskLimitCounter.id == counter_id)
        .with_for_update()
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

    _release_stale_reservations(counter, now)
    counter.limit_value = limit
    if counter.reserved_count + counter.consumed_count >= limit:
        session.add(counter)
        session.flush()
        return DailyLimitReservation(False, counter.id, product_day)

    reservation_token = new_uuid()
    reservation_expires_at = now + timedelta(seconds=reservation_ttl_seconds)
    active_reservations = dict(counter.active_reservations or {})
    active_reservations[reservation_token] = _ensure_utc(reservation_expires_at).isoformat()
    counter.active_reservations = active_reservations
    _refresh_reservation_state(counter)
    counter.updated_at = now
    session.add(counter)
    session.flush()
    return DailyLimitReservation(
        True,
        counter.id,
        product_day,
        reservation_token,
        reservation_expires_at,
    )


def _finalize_daily_task_reservation(
    *,
    session: Session,
    counter_id: str | None,
    reservation_token: str | None,
    final_status: str,
) -> None:
    if counter_id is None:
        return
    counter = _load_daily_task_counter_by_id_for_update(session=session, counter_id=counter_id)
    if counter is None:
        return
    now = utcnow()

    if reservation_token is not None:
        active_reservations = dict(counter.active_reservations or {})
        if reservation_token not in active_reservations:
            session.add(counter)
            session.flush()
            return
        del active_reservations[reservation_token]
        counter.active_reservations = active_reservations
    elif counter.reserved_count > 0:
        counter.reserved_count -= 1
    else:
        if final_status in {"consume", "fail"}:
            counter.updated_at = now
            session.add(counter)
            session.flush()
        return

    if final_status == "consume":
        counter.consumed_count += 1
    elif final_status == "release":
        counter.released_count += 1
    elif final_status == "fail":
        counter.failed_count += 1

    if reservation_token is not None:
        _refresh_reservation_state(counter)
    else:
        counter.reservation_expires_at = (
            None if counter.reserved_count == 0 else counter.reservation_expires_at
        )
    counter.updated_at = now
    session.add(counter)
    session.flush()


def consume_daily_task_reservation(
    *,
    session: Session,
    counter_id: str | None,
    reservation_token: str | None = None,
) -> None:
    _finalize_daily_task_reservation(
        session=session,
        counter_id=counter_id,
        reservation_token=reservation_token,
        final_status="consume",
    )


def release_daily_task_reservation(
    *,
    session: Session,
    counter_id: str | None,
    reservation_token: str | None = None,
) -> None:
    _finalize_daily_task_reservation(
        session=session,
        counter_id=counter_id,
        reservation_token=reservation_token,
        final_status="release",
    )


def fail_daily_task_reservation(
    *,
    session: Session,
    counter_id: str | None,
    reservation_token: str | None = None,
) -> None:
    _finalize_daily_task_reservation(
        session=session,
        counter_id=counter_id,
        reservation_token=reservation_token,
        final_status="fail",
    )
