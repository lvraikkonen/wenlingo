from sqlmodel import select

from app.domain.models import StudentProfile
from app.domain.seed import seed_demo_data


def parent_students(session, parent_id: str):
    return session.exec(select(StudentProfile).where(StudentProfile.parent_id == parent_id)).all()


def test_demo_login_returns_four_students(session, client):
    seed_demo_data(session)

    response = client.post("/api/auth/demo-login")

    assert response.status_code == 200
    payload = response.json()
    assert payload["parent"]["email"] == "demo@wenlingo.local"
    assert len(payload["students"]) == 4


def test_assessment_creates_first_ability_sketch_and_dashboard(session, client):
    parent = seed_demo_data(session)
    student_id = parent_students(session, parent.id)[0].id

    response = client.post(
        f"/api/students/{student_id}/assessment",
        json={
            "sentence_before": "公园很美。",
            "sentence_after": "公园里的花红红的，风一吹就轻轻摇。",
            "short_writing": "我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。",
        },
    )

    assert response.status_code == 201
    assert response.json()["assessment"]["summary"] == "完成入门小试炼，生成第一张能力草图。"
    dashboard = client.get(f"/api/students/{student_id}/dashboard").json()
    assert dashboard["ability_note"] == "第一张能力草图"
    assert dashboard["today_tasks"]["main"]["kind"] in {"essay", "sentence"}
    assert set(dashboard["child_abilities"].keys()) == {
        "reading_power",
        "specific_writing_power",
        "revision_power",
    }
