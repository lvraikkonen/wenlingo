from datetime import timedelta
from types import SimpleNamespace

from sqlmodel import Session

from app.api.routes import writing_castle
from app.core.config import get_settings
from app.domain.enums import StudentPersona, TaskType
from app.domain.models import AbilityProfile, Essay, LLMCallLog, StudentProfile, utcnow
from app.services.prewriting_jobs import (
    acquire_job_lease,
    complete_job,
    create_or_get_prewriting_job,
    fail_job,
    next_progress_snapshot,
)
from app.services.writing_castle_state import (
    LEGACY_SCHEMA_VERSION,
    PREWRITING_STARTED_STATUS,
    init_material_card_state,
    init_outline_state,
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


def test_acquired_job_lease_keeps_allowed_stage_until_progress_update(session):
    job = create_or_get_prewriting_job(
        session=session,
        student_id="student-1",
        essay_id="essay-1",
        task_name="outline_generation",
        idempotency_key="job-key-1",
    )

    leased = acquire_job_lease(session=session, job_id=job.id, worker_id="worker-a")

    assert leased is not None
    assert leased.status == "running"
    assert leased.stage == "queued"


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


def test_complete_job_advances_terminal_progress_sequence(session):
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
    )

    assert completed.status == "completed"
    assert completed.stage == "completed"
    assert completed.progress_event_seq == 1


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


async def test_background_material_job_uses_separate_sessions_for_provider_and_result_save(
    session,
    monkeypatch,
):
    material = init_material_card_state(schema_version=LEGACY_SCHEMA_VERSION)
    material["answers"] = [
        {
            "id": "answer-1",
            "question_id": "q-event",
            "text": "我学会了骑车。",
            "skipped": False,
        }
    ]
    essay = Essay(
        student_id="student-1",
        title="我学会了骑车",
        status=PREWRITING_STARTED_STATUS,
        material_card=material,
        outline=init_outline_state(schema_version=LEGACY_SCHEMA_VERSION),
    )
    session.add(StudentProfile(
        id="student-1",
        parent_id="parent-1",
        name="小星",
        persona=StudentPersona.real_child,
        is_real_child=True,
    ))
    session.add(AbilityProfile(student_id="student-1"))
    session.add(essay)
    session.commit()

    job = create_or_get_prewriting_job(
        session=session,
        student_id="student-1",
        essay_id=essay.id,
        task_name="material_card_generation",
        idempotency_key="job-key-1",
    )
    worker_id = "worker-a"
    acquire_job_lease(session=session, job_id=job.id, worker_id=worker_id)

    provider_sessions = []
    result_save_sessions = []

    class FakeCard:
        def model_dump(self):
            return {
                "id": "card-1",
                "category": "event",
                "text": "我学会了骑车。",
                "source_answer_ids": ["answer-1"],
                "placeholder": False,
            }

    async def fake_material_card_generation(
        runner,
        answers,
        session=None,
        student_id=None,
        scaffold=None,
    ):
        provider_sessions.append(session)
        log = LLMCallLog(
            student_id=student_id,
            task_type=TaskType.essay,
            task_name="material_card_generation",
            prompt_key="material_card_generation",
            input_summary=f"answers={len(answers)}",
            validation_ok=True,
        )
        session.add(log)
        session.flush()
        return SimpleNamespace(output=SimpleNamespace(cards=[FakeCard()]), log=log)

    def fake_record_product_event(session, *args, **kwargs):
        result_save_sessions.append(session)

    monkeypatch.setattr(writing_castle, "material_card_generation", fake_material_card_generation)
    monkeypatch.setattr(writing_castle, "record_product_event", fake_record_product_event)

    def session_factory():
        return Session(session.get_bind())

    await writing_castle._run_prewriting_job(
        session_factory=session_factory,
        job_id=job.id,
        essay_id=essay.id,
        task_name="material_card_generation",
        worker_id=worker_id,
        runner=object(),
        settings=get_settings(),
    )

    session.refresh(job)

    assert provider_sessions
    assert result_save_sessions
    assert provider_sessions[0] is not result_save_sessions[0]
    assert job.status == "completed"
    assert job.llm_call_log_id is not None
    assert job.result_payload_json == {}
