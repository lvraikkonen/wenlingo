from datetime import datetime, timezone

from app.domain.enums import TaskType
from app.domain.models import LLMCallLog
from app.services.llm_usage import (
    llm_daily_limit_reached,
    local_day_start_utc,
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
