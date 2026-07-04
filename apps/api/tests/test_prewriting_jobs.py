import asyncio
import json
from datetime import timedelta
from types import SimpleNamespace

from sqlmodel import Session

from app.api.routes import writing_castle
from app.core.config import get_settings
from app.domain.enums import StudentPersona, TaskType
from app.domain.models import (
    AbilityProfile,
    Essay,
    LLMCallLog,
    PrewritingAIJob,
    StudentProfile,
    utcnow,
)
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
from tests.conftest import create_authenticated_family, create_second_authenticated_family


def _add_writing_castle_essay(
    session: Session,
    student_id: str,
    *,
    schema_version: str | None = None,
) -> Essay:
    essay = Essay(
        student_id=student_id,
        title="我学会了骑车",
        status=PREWRITING_STARTED_STATUS,
        material_card=init_material_card_state(
            schema_version=schema_version,
        ) if schema_version else init_material_card_state(),
        outline=init_outline_state(
            schema_version=schema_version,
        ) if schema_version else init_outline_state(),
    )
    session.add(essay)
    session.commit()
    session.refresh(essay)
    return essay


def _sse_data_payload(body: str) -> dict:
    for line in body.splitlines():
        if line.startswith("data: "):
            return json.loads(line.removeprefix("data: "))
    raise AssertionError(f"SSE body did not contain a data line: {body}")


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


def test_stale_worker_cannot_complete_job_after_lease_reacquired(session):
    job = create_or_get_prewriting_job(
        session=session,
        student_id="student-1",
        essay_id="essay-1",
        task_name="material_card_generation",
        idempotency_key="job-key-1",
    )
    first = acquire_job_lease(session=session, job_id=job.id, worker_id="worker-a")
    first.lease_expires_at = utcnow() - timedelta(seconds=1)
    session.add(first)
    session.commit()
    second = acquire_job_lease(session=session, job_id=job.id, worker_id="worker-b")

    stale = complete_job(
        session=session,
        job_id=job.id,
        result_ref_type="essay",
        result_ref_id="essay-1",
        expected_worker_id="worker-a",
    )

    saved = session.get(PrewritingAIJob, job.id)
    assert second is not None
    assert stale is None
    assert saved.status == "running"
    assert saved.locked_by == "worker-b"
    assert saved.result_ref_id is None
    assert saved.completed_at is None


def test_stale_worker_cannot_fail_job_after_lease_reacquired(session):
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

    stale = fail_job(
        session=session,
        job_id=job.id,
        error_code="STALE_PROVIDER_ERROR",
        error_message="provider failed after lease loss",
        expected_worker_id="worker-a",
    )

    saved = session.get(PrewritingAIJob, job.id)
    assert second is not None
    assert stale is None
    assert saved.status == "running"
    assert saved.locked_by == "worker-b"
    assert saved.error_code == ""
    assert saved.completed_at is None


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


async def test_background_material_job_extends_lease_while_provider_is_in_flight(
    session,
    monkeypatch,
):
    family = create_authenticated_family(session)
    essay = _add_writing_castle_essay(
        session,
        family["student"].id,
        schema_version=LEGACY_SCHEMA_VERSION,
    )
    job = create_or_get_prewriting_job(
        session=session,
        student_id=family["student"].id,
        essay_id=essay.id,
        task_name="material_card_generation",
        idempotency_key="job-key-1",
    )
    worker_id = "worker-a"
    acquire_job_lease(session=session, job_id=job.id, worker_id=worker_id)

    provider_started = asyncio.Event()
    provider_can_finish = asyncio.Event()

    class FakeCard:
        def model_dump(self):
            return {
                "id": "card-1",
                "category": "event",
                "text": "",
                "source_answer_ids": [],
                "source_refs": [],
                "placeholder": True,
            }

    async def fake_material_card_generation(
        runner,
        answers,
        session=None,
        student_id=None,
        scaffold=None,
    ):
        provider_started.set()
        await provider_can_finish.wait()
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

    monkeypatch.setattr(writing_castle, "material_card_generation", fake_material_card_generation)

    def session_factory():
        return Session(session.get_bind())

    task = asyncio.create_task(
        writing_castle._run_prewriting_job(
            session_factory=session_factory,
            job_id=job.id,
            essay_id=essay.id,
            task_name="material_card_generation",
            worker_id=worker_id,
            runner=object(),
            settings=get_settings(),
            heartbeat_interval_seconds=0.01,
        )
    )
    await provider_started.wait()
    session.refresh(job)
    lease_at_provider_start = job.lease_expires_at

    for _ in range(20):
        await asyncio.sleep(0.01)
        session.refresh(job)
        if job.lease_expires_at and job.lease_expires_at > lease_at_provider_start:
            break
    provider_can_finish.set()
    await task

    session.refresh(job)
    assert job.lease_expires_at is None
    assert job.status == "completed"
    assert job.completed_at is not None


def test_prewriting_job_create_routes_return_metadata_only_and_are_idempotent(
    session,
    client,
    monkeypatch,
):
    family = create_authenticated_family(session)
    essay = _add_writing_castle_essay(session, family["student"].id)
    scheduled_job_ids = []

    def fake_schedule_prewriting_job(*, job, worker_id, session_factory, runner, settings):
        scheduled_job_ids.append(job.id)

    monkeypatch.setattr(writing_castle, "_schedule_prewriting_job", fake_schedule_prewriting_job)

    first = client.post(
        f"/api/essays/{essay.id}/material-cards/jobs",
        json={"idempotency_key": "material-job-key"},
    )
    repeated = client.post(
        f"/api/essays/{essay.id}/material-cards/jobs",
        json={"idempotency_key": "material-job-key"},
    )
    outline = client.post(
        f"/api/essays/{essay.id}/outline/jobs",
        json={"idempotency_key": "outline-job-key"},
    )

    assert first.status_code == 202
    assert repeated.status_code == 202
    assert outline.status_code == 202
    assert repeated.json()["job_id"] == first.json()["job_id"]
    assert scheduled_job_ids == [first.json()["job_id"], outline.json()["job_id"]]
    for response in (first, repeated, outline):
        payload = response.json()
        assert payload["schema_version"] == "v0.6e.1"
        assert payload["status"] == "running"
        assert payload["result_ref_id"] is None
        assert "material_card" not in payload
        assert "outline" not in payload
        assert "result_payload_json" not in payload


def test_prewriting_status_recovers_stale_job_before_returning_snapshot(session, client):
    family = create_authenticated_family(session)
    essay = _add_writing_castle_essay(session, family["student"].id)
    job = create_or_get_prewriting_job(
        session=session,
        student_id=family["student"].id,
        essay_id=essay.id,
        task_name="material_card_generation",
        idempotency_key="job-key-1",
    )
    leased = acquire_job_lease(session=session, job_id=job.id, worker_id="worker-a")
    leased.lease_expires_at = utcnow() - timedelta(seconds=1)
    session.add(leased)
    session.commit()

    response = client.get(f"/api/prewriting/jobs/{job.id}")

    session.refresh(job)
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert job.status == "queued"
    assert job.locked_by is None


def test_prewriting_status_redacts_internal_failure_message(session, client):
    family = create_authenticated_family(session)
    essay = _add_writing_castle_essay(session, family["student"].id)
    job = create_or_get_prewriting_job(
        session=session,
        student_id=family["student"].id,
        essay_id=essay.id,
        task_name="outline_generation",
        idempotency_key="job-key-1",
    )
    fail_job(
        session=session,
        job_id=job.id,
        error_code="PROVIDER_STACKTRACE",
        error_message="secret provider stack trace with child draft details",
    )

    response = client.get(f"/api/prewriting/jobs/{job.id}")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error_message"] == "prewriting job failed"
    assert "secret provider" not in response.text


def test_prewriting_status_requires_owner_when_auth_enabled(session, client, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    first = create_authenticated_family(session)
    second = create_second_authenticated_family(session)
    essay = _add_writing_castle_essay(session, second["student"].id)
    job = create_or_get_prewriting_job(
        session=session,
        student_id=second["student"].id,
        essay_id=essay.id,
        task_name="material_card_generation",
        idempotency_key="job-key-1",
    )

    unauthenticated = client.get(f"/api/prewriting/jobs/{job.id}")
    cross_family = client.get(
        f"/api/prewriting/jobs/{job.id}",
        cookies=first["cookie"],
    )
    owner = client.get(
        f"/api/prewriting/jobs/{job.id}",
        cookies=second["cookie"],
    )

    assert unauthenticated.status_code == 401
    assert cross_family.status_code == 404
    assert owner.status_code == 200


def test_prewriting_events_emit_current_terminal_snapshot_without_partial_payload(session, client):
    family = create_authenticated_family(session)
    essay = _add_writing_castle_essay(session, family["student"].id)
    job = create_or_get_prewriting_job(
        session=session,
        student_id=family["student"].id,
        essay_id=essay.id,
        task_name="material_card_generation",
        idempotency_key="job-key-1",
    )
    complete_job(
        session=session,
        job_id=job.id,
        result_ref_type="essay",
        result_ref_id=essay.id,
    )

    response = client.get(f"/api/prewriting/jobs/{job.id}/events")
    payload = _sse_data_payload(response.text)

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: completed" in response.text
    assert payload["job_id"] == job.id
    assert payload["status"] == "completed"
    assert payload["result_ref_type"] == "essay"
    assert payload["result_ref_id"] == essay.id
    assert "material_card" not in payload
    assert "outline" not in payload
    assert "result_payload_json" not in payload
