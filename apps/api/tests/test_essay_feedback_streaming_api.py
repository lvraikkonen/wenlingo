from sqlmodel import select

from app.core.config import Settings, get_settings
from app.domain.models import EssayFeedbackSubmission, LLMCallLog
from app.services.essay_feedback_submission import (
    create_or_get_submission,
    mark_submission_status,
)
from tests.conftest import create_authenticated_family


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
