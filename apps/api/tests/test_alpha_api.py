from itertools import count

from sqlmodel import select

from app.api.routes.alpha import hash_invite_code
from app.domain.enums import StudentPersona, TaskType
from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    AlphaInviteCode,
    Assessment,
    ParentUser,
    SentenceTraining,
    StudentProfile,
)
from app.domain.seed import seed_demo_data


ASSESSMENT_PAYLOAD = {
    "sentence_before": "公园很美。",
    "sentence_after": "公园里的花红红的，风一吹就轻轻摇。",
    "short_writing": "我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。",
}

_invite_counter = count(1)


def create_invite(session, code: str = "ALPHA-TEST") -> AlphaInviteCode:
    invite = AlphaInviteCode(
        code_hash=hash_invite_code(code),
        label="测试家庭",
        status="issued",
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return invite


def create_alpha_parent(client, session, display_name: str = "阿尔法家长") -> dict:
    code = f"ALPHA-TEST-{next(_invite_counter)}"
    create_invite(session, code)
    response = client.post(
        "/api/alpha/parents",
        json={
            "display_name": display_name,
            "invite_code": code,
            "alpha_session_id": "session-test",
        },
    )
    assert response.status_code == 201
    return response.json()["parent"]


def create_alpha_child(client, parent_id: str, nickname: str = " 小文 ", grade: int = 4) -> dict:
    response = client.post(
        f"/api/alpha/parents/{parent_id}/children",
        json={"nickname": nickname, "grade": grade},
    )
    assert response.status_code == 201
    return response.json()["child"]


def parent_students(session, parent_id: str):
    return session.exec(
        select(StudentProfile).where(StudentProfile.parent_id == parent_id)
    ).all()


def test_create_alpha_parent_persists_real_parent_and_returns_children_url(session, client):
    create_invite(session)

    response = client.post(
        "/api/alpha/parents",
        json={
            "display_name": " 阿尔法家长 ",
            "invite_code": "ALPHA-TEST",
            "alpha_session_id": "session-test",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    parent = payload["parent"]
    saved = session.get(ParentUser, parent["id"])
    assert saved is not None
    assert saved.display_name == "阿尔法家长"
    assert parent["display_name"] == "阿尔法家长"
    assert parent["email"].startswith("alpha-")
    assert parent["email"].endswith("@wenlingo.local")
    assert payload["children_url"] == "/parent/children"


def test_create_alpha_parent_blank_name_falls_back_to_default(session, client):
    create_invite(session)

    response = client.post(
        "/api/alpha/parents",
        json={
            "display_name": "   ",
            "invite_code": "ALPHA-TEST",
            "alpha_session_id": "session-test",
        },
    )

    assert response.status_code == 201
    assert response.json()["parent"]["display_name"] == "Alpha 家长"


def test_create_alpha_child_trims_validates_and_creates_default_ability(session, client):
    parent = create_alpha_parent(client, session)

    response = client.post(
        f"/api/alpha/parents/{parent['id']}/children",
        json={"nickname": " 小文 ", "grade": 4},
    )

    assert response.status_code == 201
    payload = response.json()
    child = payload["child"]
    student = session.get(StudentProfile, child["id"])
    ability = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == child["id"])
    ).one()
    assert student is not None
    assert student.parent_id == parent["id"]
    assert student.name == "小文"
    assert student.persona == StudentPersona.real_child
    assert student.is_real_child is True
    assert student.grade_label == "四年级"
    assert child["nickname"] == "小文"
    assert child["grade_label"] == "四年级"
    assert child["persona"] == "real_child"
    assert child["is_real_child"] is True
    assert ability.expression == 40
    assert ability.observation == 40
    assert ability.structure == 40
    assert ability.revision == 40
    assert ability.comprehension == 40
    assert ability.summarization == 40
    assert payload["dashboard_url"] == f"/children/{child['id']}"
    assert payload["summary_url"] == f"/parent/children/{child['id']}/summary"


def test_create_alpha_child_rejects_invalid_inputs(session, client):
    parent = create_alpha_parent(client, session)
    invalid_payloads = [
        {"nickname": "   ", "grade": 4},
        {"nickname": "小" * 25, "grade": 4},
        {"nickname": "小文", "grade": 2},
        {"nickname": "小文", "grade": 7},
    ]

    for payload in invalid_payloads:
        response = client.post(f"/api/alpha/parents/{parent['id']}/children", json=payload)
        assert response.status_code == 422


def test_create_alpha_child_missing_parent_returns_404(client):
    response = client.post(
        "/api/alpha/parents/missing-parent/children",
        json={"nickname": "小文", "grade": 4},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "alpha parent not found"


def test_list_alpha_children_is_scoped_to_parent_and_includes_urls(session, client):
    parent = create_alpha_parent(client, session, "家长甲")
    other_parent = create_alpha_parent(client, session, "家长乙")
    first_child = create_alpha_child(client, parent["id"], "小甲", 3)
    second_child = create_alpha_child(client, parent["id"], "小乙", 5)
    create_alpha_child(client, other_parent["id"], "小丙", 4)

    response = client.get(f"/api/alpha/parents/{parent['id']}/children")

    assert response.status_code == 200
    payload = response.json()
    assert payload["parent"] == parent
    assert [child["id"] for child in payload["children"]] == [
        first_child["id"],
        second_child["id"],
    ]
    assert payload["children"][0]["assessment_completed"] is False
    assert payload["children"][0]["dashboard_url"] == f"/children/{first_child['id']}"
    assert (
        payload["children"][0]["summary_url"]
        == f"/parent/children/{first_child['id']}/summary"
    )


def test_alpha_summary_for_new_child_returns_empty_state(session, client):
    parent = create_alpha_parent(client, session)
    child = create_alpha_child(client, parent["id"])

    response = client.get(
        f"/api/alpha/parents/{parent['id']}/children/{child['id']}/summary"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["assessment_completed"] is False
    assert payload["practice_counts"] == {
        "assessments": 0,
        "sentence_trainings": 0,
        "essays": 0,
    }
    assert payload["ability_changes"] == []
    assert payload["empty_state"] == "还没有训练记录。完成入门小试炼后，这里会出现第一份成长摘要。"
    assert payload["next_suggestion"] == "先完成入门小试炼，生成第一张能力草图。"


def test_alpha_summary_with_sentence_training_but_no_assessment_is_not_empty(
    session, client
):
    parent = create_alpha_parent(client, session)
    child = create_alpha_child(client, parent["id"])
    training = SentenceTraining(
        student_id=child["id"],
        source_sentence="公园很美。",
        upgraded_sentence="公园里的花红红的，风一吹就轻轻摇。",
        focus="加细节",
        ai_feedback={},
    )
    session.add(training)
    session.flush()
    session.add(
        AbilityHistory(
            student_id=child["id"],
            ability_name="expression",
            old_value=40,
            new_value=44,
            delta=4,
            source_type=TaskType.sentence,
            source_id=training.id,
        )
    )
    session.commit()

    response = client.get(
        f"/api/alpha/parents/{parent['id']}/children/{child['id']}/summary"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["assessment_completed"] is False
    assert payload["practice_counts"]["sentence_trainings"] == 1
    assert payload["empty_state"] is None
    assert payload["next_suggestion"] == "继续练习把句子写具体。"


def test_alpha_summary_counts_only_completed_sentence_training_and_reports_focus(
    session, client
):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    session.add(
        SentenceTraining(
            student_id=student.id,
            source_sentence="小猫跑了。",
            upgraded_sentence="小猫飞快地跑过草地。",
            focus="动作描写",
            status="completed",
            target_skill="action_expression",
            ai_feedback={},
        )
    )
    session.add(
        SentenceTraining(
            student_id=student.id,
            source_sentence="花开了。",
            upgraded_sentence="",
            focus="扩句",
            status="generated",
            target_skill="expand_sentence",
            ai_feedback={},
        )
    )
    session.commit()

    response = client.get(
        f"/api/alpha/parents/{parent.id}/children/{student.id}/summary"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["practice_counts"]["sentence_trainings"] == 1
    assert payload["sentence_training_summary"] == "本周完成 1 次句子挑战，主要练习了“动作描写”。"
    assert "小猫飞快地跑过草地" not in str(payload)


def test_alpha_summary_after_assessment_returns_counts_and_ability_changes(
    session, client
):
    parent = create_alpha_parent(client, session)
    child = create_alpha_child(client, parent["id"])
    assessment_response = client.post(
        f"/api/students/{child['id']}/assessment",
        json=ASSESSMENT_PAYLOAD,
    )
    assert assessment_response.status_code == 201

    response = client.get(
        f"/api/alpha/parents/{parent['id']}/children/{child['id']}/summary"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["assessment_completed"] is True
    assert payload["practice_counts"] == {
        "assessments": 1,
        "sentence_trainings": 1,
        "essays": 1,
    }
    assert payload["ability_changes"] == [
        {"ability": "expression", "label": "表达力", "delta": 9},
        {"ability": "observation", "label": "观察力", "delta": 4},
        {"ability": "structure", "label": "结构力", "delta": 5},
    ]
    assert payload["recent_highlight"] == "孩子完成了第一次能力草图。"
    assert payload["next_suggestion"] == "继续练习把句子写具体。"
    assert payload["empty_state"] is None
    assert {row.source_type for row in session.exec(select(AbilityHistory)).all()} == {
        TaskType.sentence,
        TaskType.essay,
    }


def test_alpha_summary_rejects_child_from_other_parent(session, client):
    parent = create_alpha_parent(client, session, "家长甲")
    other_parent = create_alpha_parent(client, session, "家长乙")
    other_child = create_alpha_child(client, other_parent["id"])

    response = client.get(
        f"/api/alpha/parents/{parent['id']}/children/{other_child['id']}/summary"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "student not found"


def test_alpha_routes_do_not_break_seeded_demo_login(session, client):
    seed_demo_data(session)

    response = client.post("/api/auth/demo-login")

    assert response.status_code == 200
    payload = response.json()
    assert payload["parent"]["email"] == "demo@wenlingo.local"
    assert len(payload["students"]) == 4
    assert session.exec(select(Assessment)).all() == []
