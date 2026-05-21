import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.api.routes.essays import EssayRevisionCreate, submit_revision
from app.core.config import get_settings
from app.domain.enums import TaskType
from app.domain.models import AbilityHistory, Essay, EssayVersion, GameEvent, LLMCallLog, StudentProfile
from app.domain.seed import seed_demo_data
from app.services.essay_workflow import draft_ability_deltas
from app.services.llm_provider import MockLLMProvider


def parent_students(session, parent_id: str):
    return session.exec(select(StudentProfile).where(StudentProfile.parent_id == parent_id)).all()


class EmptyScalarResult:
    def first(self):
        return None


class StaleRevisionReadSession:
    def __init__(self, session):
        self.session = session
        self.exec_count = 0

    def exec(self, statement):
        self.exec_count += 1
        if self.exec_count == 2:
            return EmptyScalarResult()
        return self.session.exec(statement)

    def __getattr__(self, name):
        return getattr(self.session, name)


def test_essay_from_existing_draft_feedback_and_revision(session, client):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]

    start = client.post(
        f"/api/students/{student.id}/essays",
        json={
            "title": "我学会了骑车",
            "draft": "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
            "entry": "existing_draft",
        },
    )
    assert start.status_code == 201
    essay_id = start.json()["essay"]["id"]
    assert start.json()["feedback"]["revision_tasks"][0]["instruction"] == "给第二段加一个动作描写"
    first_draft = session.exec(
        select(EssayVersion).where(EssayVersion.version_label == "first_draft")
    ).one()
    draft_history = session.exec(
        select(AbilityHistory).where(AbilityHistory.source_id == first_draft.id)
    ).all()
    assert {(row.ability_name, row.delta, row.source_type) for row in draft_history} == {
        ("expression", 5, TaskType.essay),
        ("structure", 5, TaskType.essay),
    }

    revision = client.post(
        f"/api/essays/{essay_id}/revision",
        json={
            "content": "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。爸爸松手后，我摇摇晃晃骑过了花坛。我开心得跳了起来。",
            "completed_tasks": ["给第二段加一个动作描写"],
            "skipped_tasks": [],
            "duration_seconds": 420,
        },
    )

    assert revision.status_code == 201
    assert revision.json()["comparison"]["improved_dimensions"] == ["细节更多", "动作更具体"]
    assert revision.json()["revision"]["completed_tasks"] == ["给第二段加一个动作描写"]
    assert revision.json()["revision"]["skipped_tasks"] == []
    assert revision.json()["revision"]["duration_seconds"] == 420
    assert len(session.exec(select(Essay)).all()) == 1
    assert len(session.exec(select(EssayVersion)).all()) == 2
    event = session.exec(select(GameEvent)).one()
    assert event.xp_delta == 60
    assert event.evidence["completed_task_count"] == 1
    assert event.evidence["completed_tasks"] == ["给第二段加一个动作描写"]
    assert event.evidence["ability_deltas"] == {"revision": 5}
    saved_revision = session.exec(
        select(EssayVersion).where(EssayVersion.version_label == "revision")
    ).one()
    revision_history = session.exec(
        select(AbilityHistory).where(AbilityHistory.source_id == saved_revision.id)
    ).all()
    assert {(row.ability_name, row.delta, row.source_type) for row in revision_history} == {
        ("revision", 5, TaskType.essay),
    }
    assert saved_revision.completed_tasks == ["给第二段加一个动作描写"]
    assert saved_revision.skipped_tasks == []
    assert saved_revision.duration_seconds == 420
    assert saved_revision.llm_call_log_id is not None
    logs = session.exec(select(LLMCallLog).where(LLMCallLog.student_id == student.id)).all()
    assert {log.task_name for log in logs} == {"essay_feedback", "essay_revision_comparison"}
    assert {log.task_type for log in logs} == {TaskType.essay}


def test_essay_create_rejects_overlong_title_and_draft(session, client):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]

    title_response = client.post(
        f"/api/students/{student.id}/essays",
        json={"title": "题" * 101, "draft": "我学会了骑车。刚开始我很害怕。后来我会了。", "entry": "existing_draft"},
    )
    draft_response = client.post(
        f"/api/students/{student.id}/essays",
        json={"title": "我学会了骑车", "draft": "文" * 3001, "entry": "existing_draft"},
    )

    assert title_response.status_code == 422
    assert draft_response.status_code == 422


def test_draft_ability_deltas_use_five_unless_exactly_three_improvements():
    assert draft_ability_deltas(2) == {"expression": 5, "structure": 5}
    assert draft_ability_deltas(3) == {"expression": 3, "structure": 3}
    assert draft_ability_deltas(4) == {"expression": 5, "structure": 5}


def test_revision_without_first_draft_returns_conflict(session, client):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    essay = Essay(student_id=student.id, title="我学会了骑车", status="revision_requested")
    session.add(essay)
    session.commit()

    response = client.post(
        f"/api/essays/{essay.id}/revision",
        json={"content": "我学会了骑车。刚开始我很害怕。后来我慢慢练习，终于能稳稳骑过小路。"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "first draft not found"
    assert len(session.exec(select(EssayVersion)).all()) == 0
    assert len(session.exec(select(GameEvent)).all()) == 0


def test_revision_missing_student_or_ability_returns_not_found(session, client):
    essay = Essay(student_id="missing-student", title="我学会了骑车", status="revision_requested")
    session.add(essay)
    session.flush()
    session.add(
        EssayVersion(
            essay_id=essay.id,
            version_label="first_draft",
            content="我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
        )
    )
    session.commit()

    response = client.post(
        f"/api/essays/{essay.id}/revision",
        json={"content": "我学会了骑车。刚开始我很害怕。后来我慢慢练习，终于能稳稳骑过小路。"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "student not found"
    assert len(session.exec(select(GameEvent)).all()) == 0


def test_revision_cannot_be_settled_twice(session, client):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]

    start = client.post(
        f"/api/students/{student.id}/essays",
        json={
            "title": "我学会了骑车",
            "draft": "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
            "entry": "existing_draft",
        },
    )
    essay_id = start.json()["essay"]["id"]
    revision_payload = {
        "content": "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。爸爸松手后，我摇摇晃晃骑过了花坛。我开心得跳了起来。"
    }

    first_revision = client.post(f"/api/essays/{essay_id}/revision", json=revision_payload)
    xp_after_first_revision = parent_students(session, parent.id)[0].xp
    second_revision = client.post(f"/api/essays/{essay_id}/revision", json=revision_payload)

    assert first_revision.status_code == 201
    assert second_revision.status_code == 409
    assert second_revision.json()["detail"] == "essay already settled"
    assert len(session.exec(select(EssayVersion)).all()) == 2
    assert len(session.exec(select(GameEvent)).all()) == 1
    assert len(session.exec(select(AbilityHistory)).all()) == 3
    assert parent_students(session, parent.id)[0].xp == xp_after_first_revision


@pytest.mark.asyncio
async def test_revision_integrity_conflict_returns_409_before_settlement(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    essay = Essay(student_id=student.id, title="我学会了骑车", status="revision_requested")
    session.add(essay)
    session.flush()
    session.add(
        EssayVersion(
            essay_id=essay.id,
            version_label="first_draft",
            content="我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
        )
    )
    session.add(
        EssayVersion(
            essay_id=essay.id,
            version_label="revision",
            content="我学会了骑车。第一次修改已经保存。",
        )
    )
    session.commit()
    xp_before = parent_students(session, parent.id)[0].xp

    with pytest.raises(HTTPException) as exc_info:
        await submit_revision(
            essay.id,
            EssayRevisionCreate(
                content="我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。爸爸松手后，我摇摇晃晃骑过了花坛。"
            ),
            StaleRevisionReadSession(session),
            MockLLMProvider(),
            get_settings(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "essay already settled"
    assert len(session.exec(select(GameEvent)).all()) == 0
    assert len(session.exec(select(AbilityHistory)).all()) == 0
    assert parent_students(session, parent.id)[0].xp == xp_before
