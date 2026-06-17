from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlmodel import Session, select

from app.domain.models import LLMCallLog


PRODUCT_OUTPUT_FINAL_STATUSES = {
    "primary_success",
    "fallback_success",
    "deterministic_fallback_used",
}


def local_day_start_utc(now: datetime, timezone_name: str) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    local_tz = ZoneInfo(timezone_name)
    local_today = now.astimezone(local_tz).date()
    local_start = datetime.combine(local_today, time.min, tzinfo=local_tz)
    return local_start.astimezone(timezone.utc)


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
