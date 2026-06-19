from sqlmodel import select

from app.domain.enums import StudentPersona, TaskType
from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    Assessment,
    Essay,
    EssayVersion,
    SentenceTraining,
    StudentProfile,
)
from app.services.essay_workflow import ASSESSMENT_ESSAY_STATUS
from tests.conftest import create_authenticated_family, create_second_authenticated_family


def create_profiled_students(session, parent_id: str):
    profile_data = [
        (
            "s1",
            "小宇",
            StudentPersona.real_child,
            True,
            dict(expression=44, observation=38, structure=42, revision=36),
        ),
        (
            "s2",
            "小晴",
            StudentPersona.vague_expression,
            False,
            dict(expression=28, observation=26, structure=45, revision=34),
        ),
        (
            "s3",
            "小川",
            StudentPersona.weak_structure,
            False,
            dict(expression=48, observation=46, structure=24, revision=32),
        ),
        (
            "s4",
            "小禾",
            StudentPersona.weak_reading_summary,
            False,
            dict(comprehension=30, summarization=24, expression=42),
        ),
    ]
    students = []
    for student_id, name, persona, is_real_child, ability_values in profile_data:
        student = StudentProfile(
            id=student_id,
            parent_id=parent_id,
            name=name,
            persona=persona,
            is_real_child=is_real_child,
        )
        session.add(student)
        session.add(AbilityProfile(student_id=student_id, **ability_values))
        students.append(student)
    session.commit()
    return students


def test_demo_login_route_is_not_available(client):
    response = client.post("/api/auth/demo-login")

    assert response.status_code == 404


def test_authenticated_dashboard_returns_own_child(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    family = create_authenticated_family(session)

    response = client.get(
        f"/api/students/{family['student'].id}/dashboard",
        cookies=family["cookie"],
    )

    assert response.status_code == 200
    assert response.json()["student"]["id"] == family["student"].id


def test_authenticated_parent_cannot_access_another_family_dashboard(
    client, session, monkeypatch
):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    family = create_authenticated_family(session)
    other_family = create_second_authenticated_family(session)

    response = client.get(
        f"/api/students/{other_family['student'].id}/dashboard",
        cookies=family["cookie"],
    )

    assert response.status_code == 404


def test_assessment_creates_first_ability_sketch_and_dashboard(session, client):
    family = create_authenticated_family(session)
    student_id = family["student"].id

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
    family = create_authenticated_family(session)
    student = StudentProfile(
        id="new-student",
        parent_id=family["parent"].id,
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
    family = create_authenticated_family(session)
    students = create_profiled_students(session, family["parent"].id)

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
