from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import get_db_session
from app.domain.enums import BadgeCode, TaskType
from app.domain.models import AbilityProfile, Essay, EssayVersion, GameEvent, ReadingSession, Report, StudentProfile
from app.domain.seed import seed_demo_data
from app.main import create_app


def parent_students(session, parent_id: str):
    return session.exec(select(StudentProfile).where(StudentProfile.parent_id == parent_id)).all()


@contextmanager
def client_without_server_exceptions(session):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_reading_session_updates_transfer_tip_and_report(session, client):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    ability_before = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == student.id)
    ).one()
    comprehension_before = ability_before.comprehension
    summarization_before = ability_before.summarization

    reading = client.post(
        f"/api/students/{student.id}/readings",
        json={
            "article_id": "spring-sounds",
            "answers": {
                "main_idea": "鏄ュぉ鏉ヤ簡锛屽皬娌冲拰楦熷効閮藉緢鐑椆銆?",
                "detail": "灏忔渤鍙戝嚭鍝楀暒鍟︾殑澹伴煶銆?",
                "transfer": "鍐欐櫙鍙互鍐欏０闊炽€?",
            },
        },
    )

    assert reading.status_code == 201
    assert reading.json()["transfer_tip"] == "鍐欐櫙鏃跺彲浠ュ姞鍏ュ０闊炽€?"
    assert session.exec(select(ReadingSession)).one().article_title == "鏄ュぉ鐨勫０闊?"

    ability_after = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == student.id)
    ).one()
    assert ability_after.comprehension > comprehension_before
    assert ability_after.summarization > summarization_before
    event = session.exec(select(GameEvent).where(GameEvent.task_type == TaskType.reading)).one()
    assert event.xp_delta == 30
    assert event.badge_code == BadgeCode.reading_transfer

    report = client.post(f"/api/students/{student.id}/reports", json={"report_type": "stage"})

    assert report.status_code == 201
    payload = report.json()["content"]
    assert "鏈樁娈?" in payload["practice_summary"]
    assert len(payload["weak_points"]) <= 2
    assert session.exec(select(Report)).one().report_type == "stage"


def test_report_uses_only_requested_students_revision(session, client):
    parent = seed_demo_data(session)
    requested_student, other_student = parent_students(session, parent.id)[:2]

    requested_essay = Essay(student_id=requested_student.id, title="Requested", status="settled")
    other_essay = Essay(student_id=other_student.id, title="Other", status="settled")
    session.add(requested_essay)
    session.add(other_essay)
    session.flush()
    session.add(
        EssayVersion(
            essay_id=requested_essay.id,
            version_label="revision",
            content="REQUESTED_STUDENT_REVISION",
        )
    )
    session.add(
        EssayVersion(
            essay_id=other_essay.id,
            version_label="revision",
            content="OTHER_STUDENT_REVISION",
        )
    )
    session.commit()

    report = client.post(
        f"/api/students/{requested_student.id}/reports",
        json={"report_type": "stage"},
    )

    assert report.status_code == 201
    assert report.json()["content"]["best_revision"] == "REQUESTED_STUDENT_REVISION"


def test_report_returns_404_when_student_ability_is_missing(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student.id)).one()
    session.delete(ability)
    session.commit()

    with client_without_server_exceptions(session) as client:
        report = client.post(f"/api/students/{student.id}/reports", json={"report_type": "stage"})

    assert report.status_code == 404
    assert report.json()["detail"] == "report context not found"


def test_report_uses_latest_requested_students_revision(session, client):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    now = datetime.now(timezone.utc)
    newer_essay = Essay(student_id=student.id, title="Newer", status="settled")
    older_essay = Essay(student_id=student.id, title="Older", status="settled")
    session.add(newer_essay)
    session.add(older_essay)
    session.flush()
    session.add(
        EssayVersion(
            essay_id=newer_essay.id,
            version_label="revision",
            content="NEWER_REVISION",
            created_at=now,
        )
    )
    session.add(
        EssayVersion(
            essay_id=older_essay.id,
            version_label="revision",
            content="OLDER_REVISION",
            created_at=now - timedelta(days=1),
        )
    )
    session.commit()

    report = client.post(f"/api/students/{student.id}/reports", json={"report_type": "stage"})

    assert report.status_code == 201
    assert report.json()["content"]["best_revision"] == "NEWER_REVISION"


def test_report_rejects_weekly_report_type(session, client):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]

    report = client.post(f"/api/students/{student.id}/reports", json={"report_type": "weekly"})

    assert report.status_code == 400
    assert report.json()["detail"] == "only stage reports are supported"
