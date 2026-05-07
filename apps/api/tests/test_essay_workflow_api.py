from sqlmodel import select

from app.domain.models import Essay, EssayVersion, GameEvent, StudentProfile
from app.domain.seed import seed_demo_data


def parent_students(session, parent_id: str):
    return session.exec(select(StudentProfile).where(StudentProfile.parent_id == parent_id)).all()


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

    revision = client.post(
        f"/api/essays/{essay_id}/revision",
        json={
            "content": "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。爸爸松手后，我摇摇晃晃骑过了花坛。我开心得跳了起来。"
        },
    )

    assert revision.status_code == 201
    assert revision.json()["comparison"]["improved_dimensions"] == ["细节更多", "动作更具体"]
    assert len(session.exec(select(Essay)).all()) == 1
    assert len(session.exec(select(EssayVersion)).all()) == 2
    assert session.exec(select(GameEvent)).one().xp_delta == 60
