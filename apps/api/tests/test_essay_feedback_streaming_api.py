from datetime import timedelta

import pytest
from sqlmodel import select

from app.api.deps import get_ai_task_runner, get_db_session
from app.core.config import Settings, get_settings
from app.domain.models import (
    DailyTaskLimitCounter,
    EssayFeedbackSubmission,
    EssayVersion,
    LLMCallLog,
    utcnow,
)
from app.services.llm_usage import local_product_day
from app.services.essay_feedback_submission import (
    create_or_get_submission,
    mark_submission_status,
)
from tests.conftest import create_authenticated_family


def _attach_active_daily_limit_reservation(session, student_id, submission):
    reservation_expires_at = utcnow() + timedelta(seconds=120)
    reservation_token = f"reservation-{submission.client_submission_id}"
    counter = DailyTaskLimitCounter(
        student_id=student_id,
        task_name="essay_feedback",
        product_day=local_product_day(utcnow(), "Asia/Shanghai"),
        limit_value=5,
        reserved_count=1,
        consumed_count=0,
        active_reservations={reservation_token: reservation_expires_at.isoformat()},
        reservation_expires_at=reservation_expires_at,
    )
    session.add(counter)
    session.flush()
    submission.status = "reserved"
    submission.daily_limit_counter_id = counter.id
    submission.daily_limit_reservation_token = reservation_token
    session.add(submission)
    session.commit()
    session.refresh(counter)
    session.refresh(submission)
    return counter


def _exhaust_daily_limit(session, student_id, *, consumed_count: int = 999):
    counter = DailyTaskLimitCounter(
        student_id=student_id,
        task_name="essay_feedback",
        product_day=local_product_day(utcnow(), "Asia/Shanghai"),
        limit_value=consumed_count,
        reserved_count=0,
        consumed_count=consumed_count,
        active_reservations={},
    )
    session.add(counter)
    session.commit()
    session.refresh(counter)
    return counter


class RaisingRunner:
    async def run(self, **kwargs):
        raise RuntimeError("provider exploded")


def test_direct_draft_json_requires_client_submission_id(session, client):
    family = create_authenticated_family(session)
    student = family["student"]

    response = client.post(
        f"/api/students/{student.id}/essays",
        json={
            "title": "我学会了骑车",
            "draft": "刚开始我很害怕。后来我会了。我很开心。",
            "entry": "existing_draft",
        },
    )

    assert response.status_code == 422


def test_direct_draft_stream_returns_previews_and_done(session, client):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="mock",
        essay_feedback_streaming_enabled=True,
    )
    family = create_authenticated_family(session)
    student = family["student"]

    response = client.post(
        f"/api/students/{student.id}/essays/stream-feedback",
        json={
            "title": "我学会了骑车",
            "draft": "刚开始我很害怕。后来我会了。我很开心。",
            "entry": "existing_draft",
            "client_submission_id": "stream-direct-1",
        },
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert "event: start" in body
    assert "event: feedback_section_preview" in body
    assert "event: done" in body

    submission = session.exec(select(EssayFeedbackSubmission)).one()
    assert submission.status == "completed"
    assert submission.client_submission_id == "stream-direct-1"
    log = session.exec(select(LLMCallLog)).one()
    assert log.streaming_enabled is True
    assert log.stream_final_status == "completed"


def test_direct_draft_stream_uses_session_factory_not_request_session_dependency(
    session,
    client,
):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="mock",
        essay_feedback_streaming_enabled=True,
    )
    client.app.dependency_overrides[get_db_session] = lambda: (_ for _ in ()).throw(
        AssertionError("stream route must not depend on get_db_session")
    )
    family = create_authenticated_family(session)
    student = family["student"]

    response = client.post(
        f"/api/students/{student.id}/essays/stream-feedback",
        json={
            "title": "我学会了骑车",
            "draft": "刚开始我很害怕。后来我会了。我很开心。",
            "entry": "existing_draft",
            "client_submission_id": "stream-factory-only",
        },
    )

    assert response.status_code == 200
    assert "event: done" in response.text


def test_same_stream_submission_same_payload_returns_existing_result(session, client):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="mock",
        essay_feedback_streaming_enabled=True,
    )
    family = create_authenticated_family(session)
    student = family["student"]
    payload = {
        "title": "我的一天",
        "draft": "今天我去了公园。",
        "entry": "existing_draft",
        "client_submission_id": "same-stream-key",
    }

    first = client.post(f"/api/students/{student.id}/essays/stream-feedback", json=payload)
    second = client.post(f"/api/students/{student.id}/essays/stream-feedback", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(session.exec(select(EssayFeedbackSubmission)).all()) == 1


def test_json_fallback_active_streaming_started_returns_202_not_second_provider_call(
    session,
    client,
):
    family = create_authenticated_family(session)
    student = family["student"]
    payload = {
        "title": "我的一天",
        "draft": "今天我去了公园。后来我观察了一棵树。最后我很开心。",
        "entry": "existing_draft",
        "client_submission_id": "active-stream-key",
    }
    submission = create_or_get_submission(
        session=session,
        student_id=student.id,
        essay_id=None,
        task_name="essay_feedback",
        route_scope="direct_draft",
        client_submission_id="active-stream-key",
        payload=payload,
    )
    mark_submission_status(
        session=session,
        submission_id=submission.id,
        status="streaming_started",
    )
    session.commit()

    response = client.post(f"/api/students/{student.id}/essays", json=payload)

    assert response.status_code == 202
    assert response.json()["status"] == "IN_PROGRESS"
    assert response.json()["submission_id"] == submission.id
    assert len(session.exec(select(LLMCallLog)).all()) == 0


def test_direct_draft_json_uses_submission_ledger_as_daily_limit_owner(session, client):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="mock",
        llm_daily_limit_enabled=True,
    )
    family = create_authenticated_family(session)
    student = family["student"]
    payload = {
        "title": "我的一天",
        "draft": "今天我去了公园。后来我观察了一棵树。最后我很开心。",
        "entry": "existing_draft",
        "client_submission_id": "json-ledger-limit-owner",
    }

    first = client.post(f"/api/students/{student.id}/essays", json=payload)
    second = client.post(f"/api/students/{student.id}/essays", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["status"] == "COMPLETED"
    counter = session.exec(select(DailyTaskLimitCounter)).one()
    assert counter.consumed_count == 1
    assert counter.reserved_count == 0
    assert counter.active_reservations == {}
    submission = session.exec(select(EssayFeedbackSubmission)).one()
    assert submission.status == "completed"
    assert submission.daily_limit_counter_id == counter.id
    assert len(session.exec(select(LLMCallLog)).all()) == 1


def test_direct_draft_json_provider_error_releases_ledger_reservation(session, client):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="mock",
        llm_daily_limit_enabled=True,
    )
    client.app.dependency_overrides[get_ai_task_runner] = lambda: RaisingRunner()
    family = create_authenticated_family(session)
    student = family["student"]
    payload = {
        "title": "我的一天",
        "draft": "今天我去了公园。后来我观察了一棵树。最后我很开心。",
        "entry": "existing_draft",
        "client_submission_id": "json-provider-error-release",
    }

    with pytest.raises(RuntimeError, match="provider exploded"):
        client.post(f"/api/students/{student.id}/essays", json=payload)

    submission = session.exec(select(EssayFeedbackSubmission)).one()
    assert submission.status == "failed_released"
    counter = session.exec(select(DailyTaskLimitCounter)).one()
    assert counter.consumed_count == 0
    assert counter.reserved_count == 0
    assert counter.released_count == 1
    assert len(session.exec(select(EssayVersion)).all()) == 0
    assert len(session.exec(select(LLMCallLog)).all()) == 0


def test_direct_draft_json_daily_limit_exhaustion_returns_429_without_provider_call(
    session,
    client,
):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="mock",
        llm_daily_limit_enabled=True,
    )
    family = create_authenticated_family(session)
    student = family["student"]
    counter = _exhaust_daily_limit(session, student.id)

    response = client.post(
        f"/api/students/{student.id}/essays",
        json={
            "title": "我的一天",
            "draft": "今天我去了公园。后来我观察了一棵树。最后我很开心。",
            "entry": "existing_draft",
            "client_submission_id": "json-daily-limit-exhausted",
        },
    )

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "DAILY_LIMIT_REACHED"
    session.refresh(counter)
    assert counter.consumed_count == 999
    assert counter.reserved_count == 0
    assert len(session.exec(select(LLMCallLog)).all()) == 0
    assert len(session.exec(select(EssayVersion)).all()) == 0


def test_direct_draft_json_reserved_in_flight_returns_202_without_provider_call(
    session,
    client,
):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="mock",
        llm_daily_limit_enabled=True,
    )
    family = create_authenticated_family(session)
    student = family["student"]
    payload = {
        "title": "我的一天",
        "draft": "今天我去了公园。后来我观察了一棵树。最后我很开心。",
        "entry": "existing_draft",
        "client_submission_id": "json-reserved-in-flight",
    }
    submission = create_or_get_submission(
        session=session,
        student_id=student.id,
        essay_id=None,
        task_name="essay_feedback",
        route_scope="direct_draft",
        client_submission_id="json-reserved-in-flight",
        payload=payload,
    )
    counter = _attach_active_daily_limit_reservation(session, student.id, submission)

    response = client.post(f"/api/students/{student.id}/essays", json=payload)

    assert response.status_code == 202
    assert response.json()["status"] == "IN_PROGRESS"
    assert response.json()["submission_id"] == submission.id
    refreshed_counter = session.get(DailyTaskLimitCounter, counter.id)
    assert refreshed_counter.consumed_count == 0
    assert refreshed_counter.reserved_count == 1
    assert len(refreshed_counter.active_reservations) == 1
    assert len(session.exec(select(LLMCallLog)).all()) == 0


def test_active_streaming_reentry_does_not_emit_fake_completed_done(session, client):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="mock",
        essay_feedback_streaming_enabled=True,
    )
    family = create_authenticated_family(session)
    student = family["student"]
    payload = {
        "title": "我的一天",
        "draft": "今天我去了公园。后来我观察了一棵树。最后我很开心。",
        "entry": "existing_draft",
        "client_submission_id": "active-stream-reentry",
    }
    submission = create_or_get_submission(
        session=session,
        student_id=student.id,
        essay_id=None,
        task_name="essay_feedback",
        route_scope="direct_draft",
        client_submission_id="active-stream-reentry",
        payload=payload,
    )
    mark_submission_status(
        session=session,
        submission_id=submission.id,
        status="streaming_started",
    )
    session.commit()

    response = client.post(
        f"/api/students/{student.id}/essays/stream-feedback",
        json=payload,
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert "event: start" in body
    assert "event: done" not in body
    assert '"stream_final_status":"completed"' not in body
    assert '"status":"IN_PROGRESS"' in body


def test_reserved_streaming_reentry_returns_in_progress_without_second_reservation(
    session,
    client,
):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="mock",
        llm_daily_limit_enabled=True,
        essay_feedback_streaming_enabled=True,
    )
    family = create_authenticated_family(session)
    student = family["student"]
    payload = {
        "title": "我的一天",
        "draft": "今天我去了公园。后来我观察了一棵树。最后我很开心。",
        "entry": "existing_draft",
        "client_submission_id": "stream-reserved-in-flight",
    }
    submission = create_or_get_submission(
        session=session,
        student_id=student.id,
        essay_id=None,
        task_name="essay_feedback",
        route_scope="direct_draft",
        client_submission_id="stream-reserved-in-flight",
        payload=payload,
    )
    counter = _attach_active_daily_limit_reservation(session, student.id, submission)

    response = client.post(
        f"/api/students/{student.id}/essays/stream-feedback",
        json=payload,
    )

    assert response.status_code == 200
    assert "event: start" in response.text
    assert "event: done" not in response.text
    assert '"stream_final_status":"completed"' not in response.text
    assert '"status":"IN_PROGRESS"' in response.text
    refreshed_counter = session.get(DailyTaskLimitCounter, counter.id)
    assert refreshed_counter.consumed_count == 0
    assert refreshed_counter.reserved_count == 1
    assert len(refreshed_counter.active_reservations) == 1
    assert len(session.exec(select(LLMCallLog)).all()) == 0


def test_direct_draft_stream_daily_limit_exhaustion_returns_429_without_provider_call(
    session,
    client,
):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="mock",
        llm_daily_limit_enabled=True,
        essay_feedback_streaming_enabled=True,
    )
    family = create_authenticated_family(session)
    student = family["student"]
    counter = _exhaust_daily_limit(session, student.id)

    response = client.post(
        f"/api/students/{student.id}/essays/stream-feedback",
        json={
            "title": "我的一天",
            "draft": "今天我去了公园。后来我观察了一棵树。最后我很开心。",
            "entry": "existing_draft",
            "client_submission_id": "stream-daily-limit-exhausted",
        },
    )

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "DAILY_LIMIT_REACHED"
    session.refresh(counter)
    assert counter.consumed_count == 999
    assert counter.reserved_count == 0
    assert len(session.exec(select(LLMCallLog)).all()) == 0
    assert len(session.exec(select(EssayVersion)).all()) == 0


def test_prewriting_first_draft_stream_returns_previews_and_done(session, client):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="mock",
        essay_feedback_streaming_enabled=True,
    )
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]

    response = client.post(
        f"/api/essays/{essay_id}/first-draft/stream-feedback",
        json={
            "draft": "我学会了骑车。刚开始我很害怕，手紧紧抓着车把。后来我慢慢练习，终于能自己骑了。我很开心。",
            "client_submission_id": "stream-prewriting-1",
        },
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert "event: start" in body
    assert "event: feedback_section_preview" in body
    assert "event: done" in body

    submission = session.exec(select(EssayFeedbackSubmission)).one()
    assert submission.status == "completed"
    assert submission.client_submission_id == "stream-prewriting-1"
    assert submission.route_scope == "prewriting_first_draft"
    log = session.exec(select(LLMCallLog)).one()
    assert log.streaming_enabled is True
    assert log.stream_final_status == "completed"


def test_prewriting_stream_existing_first_draft_rejects_before_provider_call(session, client):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="mock",
        essay_feedback_streaming_enabled=True,
    )
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]
    first_draft = client.post(
        f"/api/essays/{essay_id}/first-draft",
        json={
            "draft": "我学会了骑车。刚开始我很害怕，手紧紧抓着车把。后来我慢慢练习，终于能自己骑了。我很开心。",
            "client_submission_id": "prewriting-json-existing",
        },
    )
    submission_count = len(session.exec(select(EssayFeedbackSubmission)).all())
    log_count = len(session.exec(select(LLMCallLog)).all())

    response = client.post(
        f"/api/essays/{essay_id}/first-draft/stream-feedback",
        json={
            "draft": "我又写了一稿，但这个作文已经提交过初稿了。",
            "client_submission_id": "prewriting-stream-blocked",
        },
    )

    assert first_draft.status_code == 201
    assert response.status_code == 409
    assert len(session.exec(select(EssayFeedbackSubmission)).all()) == submission_count
    assert len(session.exec(select(LLMCallLog)).all()) == log_count


def test_prewriting_json_same_completed_submission_replays_without_new_result(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]
    payload = {
        "draft": "我学会了骑车。刚开始我很害怕，手紧紧抓着车把。后来我慢慢练习，终于能自己骑了。我很开心。",
        "client_submission_id": "prewriting-json-replay",
    }

    first = client.post(f"/api/essays/{essay_id}/first-draft", json=payload)
    version_count = len(session.exec(select(EssayVersion)).all())
    log_count = len(session.exec(select(LLMCallLog)).all())
    second = client.post(f"/api/essays/{essay_id}/first-draft", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["status"] == "COMPLETED"
    assert len(session.exec(select(EssayVersion)).all()) == version_count
    assert len(session.exec(select(LLMCallLog)).all()) == log_count


def test_prewriting_json_reserved_in_flight_returns_202_without_provider_call(
    session,
    client,
):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="mock",
        llm_daily_limit_enabled=True,
    )
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]
    payload = {
        "draft": "我学会了骑车。刚开始我很害怕，手紧紧抓着车把。后来我慢慢练习，终于能自己骑了。我很开心。",
        "client_submission_id": "prewriting-reserved-in-flight",
    }
    submission = create_or_get_submission(
        session=session,
        student_id=student.id,
        essay_id=essay_id,
        task_name="essay_feedback",
        route_scope="prewriting_first_draft",
        client_submission_id="prewriting-reserved-in-flight",
        payload=payload,
    )
    counter = _attach_active_daily_limit_reservation(session, student.id, submission)

    response = client.post(f"/api/essays/{essay_id}/first-draft", json=payload)

    assert response.status_code == 202
    assert response.json()["status"] == "IN_PROGRESS"
    assert response.json()["submission_id"] == submission.id
    refreshed_counter = session.get(DailyTaskLimitCounter, counter.id)
    assert refreshed_counter.consumed_count == 0
    assert refreshed_counter.reserved_count == 1
    assert len(refreshed_counter.active_reservations) == 1
    assert len(session.exec(select(EssayVersion)).all()) == 0
    assert len(session.exec(select(LLMCallLog)).all()) == 0


def test_prewriting_stream_same_completed_submission_replays_done_without_new_result(
    session,
    client,
):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="mock",
        essay_feedback_streaming_enabled=True,
    )
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]
    payload = {
        "draft": "我学会了骑车。刚开始我很害怕，手紧紧抓着车把。后来我慢慢练习，终于能自己骑了。我很开心。",
        "client_submission_id": "prewriting-stream-replay",
    }

    first = client.post(
        f"/api/essays/{essay_id}/first-draft/stream-feedback",
        json=payload,
    )
    version_count = len(session.exec(select(EssayVersion)).all())
    log_count = len(session.exec(select(LLMCallLog)).all())
    second = client.post(
        f"/api/essays/{essay_id}/first-draft/stream-feedback",
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert "event: start" in second.text
    assert "event: done" in second.text
    assert '"stream_final_status":"completed"' in second.text
    assert len(session.exec(select(EssayVersion)).all()) == version_count
    assert len(session.exec(select(LLMCallLog)).all()) == log_count


def test_prewriting_first_draft_json_requires_client_submission_id(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]

    response = client.post(
        f"/api/essays/{essay_id}/first-draft",
        json={"draft": "我学会了骑车。刚开始我很害怕，后来我慢慢练习，终于能自己骑了。我很开心。"},
    )

    assert response.status_code == 422
