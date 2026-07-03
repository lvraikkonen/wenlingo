from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.domain.enums import TaskType
from app.domain.models import EssayFeedbackSubmission, LLMCallLog, PrewritingAIJob, utcnow


def test_llm_call_log_v06e_defaults_for_non_streaming_rows(session):
    log = LLMCallLog(
        student_id="student-1",
        task_type=TaskType.essay,
        task_name="essay_feedback",
        prompt_key="essay_feedback",
        input_summary="作文反馈；初稿长度：24",
    )

    session.add(log)
    session.commit()

    saved = session.exec(select(LLMCallLog)).one()
    assert saved.streaming_enabled is False
    assert saved.stream_protocol == "none"
    assert saved.usage_available is False
    assert saved.usage_source == "unavailable"
    assert saved.usage_is_estimated is False
    assert saved.usage_details_json == {}
    assert saved.cost_source == "unavailable"
    assert saved.cost_error_code == ""
    assert saved.stream_final_status == "not_streaming"
    assert saved.provider_request_id is None
    assert saved.provider_generation_id is None


def test_prewriting_ai_job_unique_by_student_essay_task_and_idempotency_key(session):
    expires_at = utcnow() + timedelta(minutes=30)
    first = PrewritingAIJob(
        student_id="student-1",
        essay_id="essay-1",
        task_name="material_card_generation",
        idempotency_key="job-key-1",
        status="queued",
        stage="queued",
        expires_at=expires_at,
    )
    duplicate = PrewritingAIJob(
        student_id="student-1",
        essay_id="essay-1",
        task_name="material_card_generation",
        idempotency_key="job-key-1",
        status="queued",
        stage="queued",
        expires_at=expires_at,
    )

    session.add(first)
    session.commit()
    session.add(duplicate)

    with pytest.raises(IntegrityError):
        session.commit()


def test_prewriting_ai_job_v06e_reliability_fields_default(session):
    job = PrewritingAIJob(
        student_id="student-1",
        essay_id="essay-1",
        task_name="outline_generation",
        idempotency_key="job-key-2",
        status="queued",
        stage="queued",
        expires_at=utcnow() + timedelta(minutes=30),
    )

    session.add(job)
    session.commit()
    saved = session.exec(select(PrewritingAIJob)).one()

    assert saved.llm_call_log_id is None
    assert saved.started_at is None
    assert saved.completed_at is None
    assert saved.progress_event_seq == 0


def test_essay_feedback_submission_unique_normalized_scope(session):
    first = EssayFeedbackSubmission(
        student_id="student-1",
        essay_id=None,
        idempotency_scope="direct:student-1",
        route_scope="direct_draft",
        task_name="essay_feedback",
        client_submission_id="submission-1",
        payload_hash="hash-a",
        status="created",
    )
    duplicate = EssayFeedbackSubmission(
        student_id="student-1",
        essay_id=None,
        idempotency_scope="direct:student-1",
        route_scope="direct_draft",
        task_name="essay_feedback",
        client_submission_id="submission-1",
        payload_hash="hash-a",
        status="created",
    )

    session.add(first)
    session.commit()
    session.add(duplicate)

    with pytest.raises(IntegrityError):
        session.commit()
