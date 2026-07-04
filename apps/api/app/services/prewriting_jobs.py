from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.models import PrewritingAIJob, new_uuid, utcnow


PREWRITING_JOB_SCHEMA_VERSION = "v0.6e.1"
PREWRITING_JOB_RESULT_REF_TYPE = "essay"
PREWRITING_JOB_TASKS = {"material_card_generation", "outline_generation"}
DEFAULT_JOB_TTL = timedelta(hours=24)
DEFAULT_LEASE_TTL = timedelta(minutes=2)


def _job_by_idempotency_key(
    *,
    session: Session,
    student_id: str,
    essay_id: str,
    task_name: str,
    idempotency_key: str,
) -> PrewritingAIJob | None:
    return session.exec(
        select(PrewritingAIJob)
        .where(PrewritingAIJob.student_id == student_id)
        .where(PrewritingAIJob.essay_id == essay_id)
        .where(PrewritingAIJob.task_name == task_name)
        .where(PrewritingAIJob.idempotency_key == idempotency_key)
    ).first()


def _get_job_for_update(*, session: Session, job_id: str) -> PrewritingAIJob | None:
    return session.exec(
        select(PrewritingAIJob)
        .where(PrewritingAIJob.id == job_id)
        .with_for_update()
    ).first()


def _touch(job: PrewritingAIJob, now: datetime) -> None:
    job.updated_at = now


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _snapshot(job: PrewritingAIJob) -> dict[str, Any]:
    return {
        "schema_version": PREWRITING_JOB_SCHEMA_VERSION,
        "event_id": f"evt_{new_uuid()}",
        "seq": job.progress_event_seq,
        "job_id": job.id,
        "task_name": job.task_name,
        "stage": job.stage,
        "status": job.status,
        "result_ref_type": job.result_ref_type,
        "result_ref_id": job.result_ref_id,
    }


def create_or_get_prewriting_job(
    *,
    session: Session,
    student_id: str,
    essay_id: str,
    task_name: str,
    idempotency_key: str,
    now: datetime | None = None,
    ttl: timedelta = DEFAULT_JOB_TTL,
) -> PrewritingAIJob:
    if task_name not in PREWRITING_JOB_TASKS:
        raise ValueError("unsupported prewriting job task")
    existing = _job_by_idempotency_key(
        session=session,
        student_id=student_id,
        essay_id=essay_id,
        task_name=task_name,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        return existing

    created_at = now or utcnow()
    job = PrewritingAIJob(
        student_id=student_id,
        essay_id=essay_id,
        task_name=task_name,
        idempotency_key=idempotency_key,
        status="queued",
        stage="queued",
        schema_version=PREWRITING_JOB_SCHEMA_VERSION,
        result_payload_json={},
        expires_at=created_at + ttl,
        created_at=created_at,
        updated_at=created_at,
    )
    try:
        with session.begin_nested():
            session.add(job)
            session.flush()
        return job
    except IntegrityError:
        with session.no_autoflush:
            existing = _job_by_idempotency_key(
                session=session,
                student_id=student_id,
                essay_id=essay_id,
                task_name=task_name,
                idempotency_key=idempotency_key,
            )
        if existing is None:
            raise
        return existing


def acquire_job_lease(
    *,
    session: Session,
    job_id: str,
    worker_id: str,
    now: datetime | None = None,
    lease_ttl: timedelta = DEFAULT_LEASE_TTL,
) -> PrewritingAIJob | None:
    current_time = now or utcnow()
    job = _get_job_for_update(session=session, job_id=job_id)
    if job is None:
        return None
    if job.status in {"completed", "failed"}:
        return None
    has_active_lease = (
        job.locked_by is not None
        and job.lease_expires_at is not None
        and _ensure_utc(job.lease_expires_at) > _ensure_utc(current_time)
    )
    if has_active_lease:
        return None
    job.status = "running"
    job.locked_by = worker_id
    job.lease_expires_at = current_time + lease_ttl
    job.last_heartbeat_at = current_time
    job.started_at = job.started_at or current_time
    job.attempt_count += 1
    _touch(job, current_time)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def heartbeat_job(
    *,
    session: Session,
    job_id: str,
    worker_id: str,
    now: datetime | None = None,
    lease_ttl: timedelta = DEFAULT_LEASE_TTL,
) -> PrewritingAIJob | None:
    current_time = now or utcnow()
    job = _get_job_for_update(session=session, job_id=job_id)
    if job is None or job.status != "running" or job.locked_by != worker_id:
        return None
    job.last_heartbeat_at = current_time
    job.lease_expires_at = current_time + lease_ttl
    _touch(job, current_time)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def next_progress_snapshot(
    *,
    session: Session,
    job_id: str,
    stage: str,
    status: str | None = None,
) -> dict[str, Any]:
    current_time = utcnow()
    job = _get_job_for_update(session=session, job_id=job_id)
    if job is None:
        raise ValueError("prewriting job not found")
    job.progress_event_seq += 1
    job.stage = stage
    if status is not None:
        job.status = status
    job.last_heartbeat_at = current_time if job.status == "running" else job.last_heartbeat_at
    _touch(job, current_time)
    session.add(job)
    session.commit()
    session.refresh(job)
    return _snapshot(job)


def complete_job(
    *,
    session: Session,
    job_id: str,
    result_ref_type: str,
    result_ref_id: str,
    llm_call_log_id: str | None = None,
    expected_worker_id: str | None = None,
) -> PrewritingAIJob | None:
    current_time = utcnow()
    job = _get_job_for_update(session=session, job_id=job_id)
    if job is None:
        raise ValueError("prewriting job not found")
    if expected_worker_id is not None and (
        job.status != "running" or job.locked_by != expected_worker_id
    ):
        return None
    job.status = "completed"
    job.stage = "completed"
    job.progress_event_seq += 1
    job.completed_at = current_time
    job.result_ref_type = result_ref_type
    job.result_ref_id = result_ref_id
    job.result_payload_json = {}
    job.error_code = ""
    job.error_message = ""
    job.llm_call_log_id = llm_call_log_id
    job.locked_by = None
    job.lease_expires_at = None
    _touch(job, current_time)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def fail_job(
    *,
    session: Session,
    job_id: str,
    error_code: str,
    error_message: str,
    llm_call_log_id: str | None = None,
    expected_worker_id: str | None = None,
) -> PrewritingAIJob | None:
    current_time = utcnow()
    job = _get_job_for_update(session=session, job_id=job_id)
    if job is None:
        raise ValueError("prewriting job not found")
    if expected_worker_id is not None and (
        job.status != "running" or job.locked_by != expected_worker_id
    ):
        return None
    job.status = "failed"
    job.stage = "failed"
    job.progress_event_seq += 1
    job.completed_at = current_time
    job.error_code = error_code
    job.error_message = error_message
    job.llm_call_log_id = llm_call_log_id
    job.result_payload_json = {}
    job.locked_by = None
    job.lease_expires_at = None
    _touch(job, current_time)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _recover_stale_job_row(
    *,
    job: PrewritingAIJob,
    now: datetime,
    max_attempts: int,
) -> bool:
    lease_is_current = (
        job.lease_expires_at is not None
        and _ensure_utc(job.lease_expires_at) > _ensure_utc(now)
    )
    if job.status != "running" or job.lease_expires_at is None or lease_is_current:
        return False
    if job.attempt_count >= max_attempts:
        job.status = "failed"
        job.stage = "failed"
        job.progress_event_seq += 1
        job.completed_at = now
        job.error_code = "STALE_JOB_LEASE_EXPIRED"
        job.error_message = "prewriting job lease expired"
    else:
        job.status = "queued"
        job.stage = "queued"
    job.locked_by = None
    job.lease_expires_at = None
    job.result_payload_json = {}
    _touch(job, now)
    return True


def recover_stale_job(
    *,
    session: Session,
    job_id: str,
    now: datetime | None = None,
    max_attempts: int = 2,
) -> PrewritingAIJob | None:
    current_time = now or utcnow()
    job = _get_job_for_update(session=session, job_id=job_id)
    if job is None:
        return None
    changed = _recover_stale_job_row(job=job, now=current_time, max_attempts=max_attempts)
    if changed:
        session.add(job)
        session.commit()
        session.refresh(job)
    return job


def recover_stale_jobs(
    *,
    session: Session,
    now: datetime | None = None,
    max_attempts: int = 2,
) -> list[PrewritingAIJob]:
    current_time = now or utcnow()
    candidates = session.exec(
        select(PrewritingAIJob)
        .where(PrewritingAIJob.status == "running")
        .where(PrewritingAIJob.lease_expires_at.is_not(None))
        .with_for_update()
    ).all()
    recovered: list[PrewritingAIJob] = []
    for job in candidates:
        if not _recover_stale_job_row(job=job, now=current_time, max_attempts=max_attempts):
            continue
        session.add(job)
        recovered.append(job)
    session.commit()
    for job in recovered:
        session.refresh(job)
    return recovered
