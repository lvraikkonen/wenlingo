from sqlmodel import select

from app.domain.enums import TaskType
from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    Assessment,
    Essay,
    EssayVersion,
    SentenceTraining,
    StudentProfile,
)
from app.domain.seed import seed_demo_data
from app.services.essay_workflow import ASSESSMENT_ESSAY_STATUS


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
    payload = response.json()
    assert payload["assessment"]["summary"] == "完成入门小试炼，生成第一张能力草图。"
    assert payload["assessment"]["sentence_training_id"]
    assert payload["assessment"]["essay_id"]
    assert set(payload["ability_sketch"]) == {
        "reading_power",
        "specific_writing_power",
        "revision_power",
    }
    assert payload["settlement"]["xp_delta"] == 20
    assert payload["game_event"]["xp_delta"] == 20

    assessment = session.exec(select(Assessment)).one()
    training = session.get(SentenceTraining, payload["assessment"]["sentence_training_id"])
    essay = session.get(Essay, payload["assessment"]["essay_id"])
    version = session.exec(
        select(EssayVersion).where(EssayVersion.essay_id == essay.id)
    ).one()
    history = session.exec(select(AbilityHistory)).all()

    assert assessment.sentence_training_id == training.id
    assert assessment.essay_id == essay.id
    assert essay.status == ASSESSMENT_ESSAY_STATUS
    assert {(row.source_type, row.source_id) for row in history} == {
        (TaskType.sentence, training.id),
        (TaskType.essay, version.id),
    }
    dashboard = client.get(f"/api/students/{student_id}/dashboard").json()
    assert dashboard["ability_note"] == "第一张能力草图"
    assert dashboard["assessment_completed"] is True
    assert dashboard["assessment_recommended"] is False
    assert dashboard["today_tasks"]["main"]["kind"] in {"essay", "sentence"}
    assert set(dashboard["child_abilities"].keys()) == {
        "reading_power",
        "specific_writing_power",
        "revision_power",
    }


def test_new_student_dashboard_recommends_initial_assessment(session, client):
    parent = seed_demo_data(session)
    student = StudentProfile(
        id="new-student",
        parent_id=parent.id,
        name="小新",
        persona="real_child",
        is_real_child=True,
    )
    session.add(student)
    session.add(AbilityProfile(student_id=student.id))
    session.commit()

    dashboard = client.get(f"/api/students/{student.id}/dashboard").json()

    assert dashboard["ability_note"] == "等待入门小试点"
    assert dashboard["assessment_completed"] is False
    assert dashboard["assessment_recommended"] is True
    assert dashboard["today_tasks"]["main"] == {
        "kind": "assessment",
        "title": "入门小试炼",
        "focus": "第一张能力草图",
        "minutes": "3-5",
    }


def test_four_demo_profiles_have_distinct_dashboard_shapes_and_recommendations(session, client):
    parent = seed_demo_data(session)
    students = sorted(parent_students(session, parent.id), key=lambda student: student.id)

    dashboards = {
        student.id: client.get(f"/api/students/{student.id}/dashboard").json()
        for student in students
    }

    ability_shapes = {
        tuple(dashboard["child_abilities"].values()) for dashboard in dashboards.values()
    }
    assert len(ability_shapes) == 4
    assert dashboards["s1"]["today_tasks"]["main"]["focus"] == "把细节写具体"
    assert dashboards["s2"]["today_tasks"]["main"]["focus"] == "把句子和细节写具体"
    assert dashboards["s2"]["today_tasks"]["quick"]["focus"] == "加动作或神态"
    assert dashboards["s3"]["today_tasks"]["main"]["focus"] == "把选材和结构说清楚"
    assert dashboards["s4"]["today_tasks"]["main"]["focus"] == "先把阅读内容概括清楚"
