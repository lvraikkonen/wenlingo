from datetime import timedelta

from app.domain.models import utcnow
from app.services.prewriting_jobs import (
    acquire_job_lease,
    complete_job,
    create_or_get_prewriting_job,
    fail_job,
    next_progress_snapshot,
)


def test_create_or_get_prewriting_job_is_idempotent(session):
    first = create_or_get_prewriting_job(
        session=session,
        student_id="student-1",
        essay_id="essay-1",
        task_name="material_card_generation",
        idempotency_key="job-key-1",
    )
    second = create_or_get_prewriting_job(
        session=session,
        student_id="student-1",
        essay_id="essay-1",
        task_name="material_card_generation",
        idempotency_key="job-key-1",
    )

    assert second.id == first.id


def test_job_lease_can_be_acquired_once(session):
    job = create_or_get_prewriting_job(
        session=session,
        student_id="student-1",
        essay_id="essay-1",
        task_name="outline_generation",
        idempotency_key="job-key-1",
    )

    first = acquire_job_lease(session=session, job_id=job.id, worker_id="worker-a")
    second = acquire_job_lease(session=session, job_id=job.id, worker_id="worker-b")

    assert first is not None
    assert second is None


def test_expired_lease_can_be_reacquired(session):
    job = create_or_get_prewriting_job(
        session=session,
        student_id="student-1",
        essay_id="essay-1",
        task_name="outline_generation",
        idempotency_key="job-key-1",
    )
    first = acquire_job_lease(session=session, job_id=job.id, worker_id="worker-a")
    first.lease_expires_at = utcnow() - timedelta(seconds=1)
    session.add(first)
    session.commit()

    second = acquire_job_lease(session=session, job_id=job.id, worker_id="worker-b")

    assert second is not None
    assert second.locked_by == "worker-b"
    assert second.attempt_count == 2


def test_progress_snapshot_increments_sequence(session):
    job = create_or_get_prewriting_job(
        session=session,
        student_id="student-1",
        essay_id="essay-1",
        task_name="material_card_generation",
        idempotency_key="job-key-1",
    )

    first = next_progress_snapshot(session=session, job_id=job.id, stage="primary_started")
    second = next_progress_snapshot(session=session, job_id=job.id, stage="completed")

    assert first["seq"] == 1
    assert second["seq"] == 2


def test_complete_job_sets_completed_at_and_result_ref(session):
    job = create_or_get_prewriting_job(
        session=session,
        student_id="student-1",
        essay_id="essay-1",
        task_name="material_card_generation",
        idempotency_key="job-key-1",
    )

    completed = complete_job(
        session=session,
        job_id=job.id,
        result_ref_type="essay",
        result_ref_id="essay-1",
        llm_call_log_id="llm-1",
    )

    assert completed.status == "completed"
    assert completed.completed_at is not None
    assert completed.result_ref_type == "essay"
    assert completed.result_ref_id == "essay-1"
    assert completed.llm_call_log_id == "llm-1"


def test_fail_job_sets_terminal_error_and_does_not_store_partial_payload(session):
    job = create_or_get_prewriting_job(
        session=session,
        student_id="student-1",
        essay_id="essay-1",
        task_name="outline_generation",
        idempotency_key="job-key-1",
    )

    failed = fail_job(
        session=session,
        job_id=job.id,
        error_code="PROVIDER_TIMEOUT",
        error_message="provider timed out",
    )

    assert failed.status == "failed"
    assert failed.completed_at is not None
    assert failed.error_code == "PROVIDER_TIMEOUT"
    assert failed.result_payload_json == {}
