from datetime import datetime, timedelta, timezone
from itertools import count

from sqlmodel import select

from app.api.routes.alpha import hash_invite_code
from app.domain.enums import StudentPersona, TaskType
from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    AlphaInviteCode,
    Essay,
    EssayVersion,
    ParentUser,
    SentenceTraining,
    StudentProfile,
)
from tests.conftest import create_authenticated_family


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


def _writing_castle_state(
    *,
    topic_origin: str = "teacher_provided",
    selected_topic_idea: dict | None = None,
) -> tuple[dict, dict]:
    material = {"schema_version": "v0.6a.1", "answers": [], "cards": []}
    outline = {
        "schema_version": "v0.6a.1",
        "topic_origin": topic_origin,
    }
    if selected_topic_idea is not None:
        outline["selected_topic_idea"] = selected_topic_idea
    return material, outline


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
    family = create_authenticated_family(session)
    parent = family["parent"]
    student = family["student"]
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


def test_alpha_summary_includes_writing_castle_process_summary(session, client):
    parent = create_alpha_parent(client, session)
    child = create_alpha_child(client, parent["id"])
    student_id = child["id"]

    start = client.post(
        f"/api/students/{student_id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    assert start.status_code == 201
    essay_id = start.json()["essay"]["id"]
    selected = client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json={"topic_type": "person_portrait", "override_reason": "manual_choice"},
    )
    assert selected.status_code == 200
    client.post(f"/api/essays/{essay_id}/topic-analysis", json={})
    client.patch(
        f"/api/essays/{essay_id}/topic-focus",
        json={
            "text": "我想写学会骑车的过程。",
            "adopted_from_ai": False,
            "skipped": False,
        },
    )
    client.patch(
        f"/api/essays/{essay_id}/material-answers",
        json={
            "answers": [
                {
                    "id": "answer-1",
                    "question_id": "q-event",
                    "text": "我学会了骑车。",
                    "skipped": False,
                },
                {
                    "id": "answer-2",
                    "question_id": "q-detail",
                    "text": "",
                    "skipped": True,
                },
            ]
        },
    )

    response = client.get(
        f"/api/alpha/parents/{parent['id']}/children/{student_id}/summary"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["writing_castle_summary"] == {
        "topic": "我学会了骑车",
        "topic_origin": "teacher_provided",
        "topic_origin_label": "老师布置题目",
        "selected_topic_idea": None,
        "selected_topic_type": "写一个人",
        "selected_topic_type_parent": "写人类：特点 + 事例",
        "selection_source": "manual",
        "material_source_categories": ["real_experience"],
        "unsupported_future_type_overridden": False,
        "copy_ready_ai_body_generated": False,
        "topic_analysis_used": True,
        "topic_focus_confirmed": True,
        "topic_focus_edited": True,
        "material_questions_answered": 1,
        "material_cards_retained": 0,
        "outline_confirmed": False,
        "outline_edited": False,
        "first_draft_completed": False,
        "revision_completed": False,
        "settlement_completed": False,
        "essay_id": essay_id,
        "latest_version_id": None,
        "last_version_submitted_at": None,
        "latest_round_index": None,
        "revision_round_count": 0,
        "status": "not_archived",
        "summary_label": "还没有提交初稿",
        "hidden": False,
        "hidden_by": "",
        "hidden_at": None,
        "can_continue_revision": False,
        "can_retry_revision_attempt": False,
    }


def test_alpha_summary_allows_unselected_writing_castle_scaffold(session, client):
    parent = create_alpha_parent(client, session)
    child = create_alpha_child(client, parent["id"])
    student_id = child["id"]

    start = client.post(
        f"/api/students/{student_id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    assert start.status_code == 201

    response = client.get(
        f"/api/alpha/parents/{parent['id']}/children/{student_id}/summary"
    )

    assert response.status_code == 200
    summary = response.json()["writing_castle_summary"]
    assert summary["topic"] == "我学会了骑车"
    assert summary["selected_topic_type"] == ""
    assert summary["selected_topic_type_parent"] == ""
    assert summary["selection_source"] == ""


def test_alpha_summary_marks_teacher_provided_topic_origin_for_classroom_path(session, client):
    parent = create_alpha_parent(client, session)
    child = create_alpha_child(client, parent["id"])
    start = client.post(
        f"/api/students/{child['id']}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )

    response = client.get(
        f"/api/alpha/parents/{parent['id']}/children/{child['id']}/summary"
    )

    assert start.status_code == 201
    assert response.status_code == 200
    summary = response.json()["writing_castle_summary"]
    assert summary["topic_origin"] == "teacher_provided"
    assert summary["topic_origin_label"] == "老师布置题目"


def test_alpha_summary_marks_ai_topic_idea_origin(session, client):
    parent = create_alpha_parent(client, session)
    child = create_alpha_child(client, parent["id"])
    ideas = client.post(
        f"/api/students/{child['id']}/writing-castle/ai-topic-ideas",
        json={"interest_text": "足球"},
    ).json()
    client.post(
        f"/api/students/{child['id']}/writing-castle/ai-topic-essay",
        json={
            "idea_batch_id": ideas["idea_batch_id"],
            "selected_idea_id": ideas["ideas"][0]["id"],
        },
    )

    response = client.get(
        f"/api/alpha/parents/{parent['id']}/children/{child['id']}/summary"
    )

    assert response.status_code == 200
    summary = response.json()["writing_castle_summary"]
    assert summary["topic_origin"] == "ai_topic_idea"
    assert summary["topic_origin_label"] == "AI 出题灵感，孩子选择"
    assert summary["selected_topic_idea"]["id"] == ideas["ideas"][0]["id"]
    assert summary["copy_ready_ai_body_generated"] is False


def test_parent_summary_uses_latest_round_and_collapsed_archive_summary(session, client):
    parent = create_alpha_parent(client, session)
    child = create_alpha_child(client, parent["id"])
    material, outline = _writing_castle_state()
    essay = Essay(
        student_id=child["id"],
        title="多轮修改",
        status="settled",
        material_card=material,
        outline=outline,
    )
    session.add(essay)
    session.flush()
    now = datetime.now(timezone.utc)
    first_draft_text = "FIRST_DRAFT_FULL_TEXT_孩子第一稿写了很多完整内容。"
    round_two_text = "ROUND_2_FULL_DRAFT_TEXT_孩子第二稿补充了动作。"
    round_three_text = "ROUND_3_FULL_DRAFT_TEXT_孩子第三稿继续修改了结尾感受。"
    session.add(
        EssayVersion(
            essay_id=essay.id,
            version_label="first_draft",
            round_index=1,
            content=first_draft_text,
            created_at=now - timedelta(minutes=3),
        )
    )
    session.add(
        EssayVersion(
            essay_id=essay.id,
            version_label="revision",
            round_index=2,
            content=round_two_text,
            created_at=now - timedelta(minutes=2),
        )
    )
    session.add(
        EssayVersion(
            essay_id=essay.id,
            version_label="revision_round_3",
            round_index=3,
            content=round_three_text,
            ai_feedback={
                "improvement": "第三稿把结尾感受写得更清楚。",
                "next_step": "下次继续检查开头。",
            },
            created_at=now - timedelta(minutes=1),
        )
    )
    session.commit()

    response = client.get(
        f"/api/alpha/parents/{parent['id']}/children/{child['id']}/summary"
    )

    assert response.status_code == 200
    payload = response.json()
    summary = payload["writing_castle_summary"]
    assert summary["latest_round_index"] == 3
    assert summary["revision_round_count"] == 2
    assert summary["revision_round_count"] == summary["latest_round_index"] - 1
    assert summary["status"] == "multi_round_revision"
    assert summary["summary_label"] == "已完成 3 稿"
    assert summary["can_continue_revision"] is False
    assert summary["can_retry_revision_attempt"] is False
    assert summary["first_draft_completed"] is True
    assert summary["revision_completed"] is True
    assert first_draft_text not in str(payload)
    assert round_two_text not in str(payload)
    assert round_three_text not in str(payload)


def test_parent_summary_includes_child_hidden_essay_restore_metadata(session, client):
    parent = create_alpha_parent(client, session)
    child = create_alpha_child(client, parent["id"])
    material, outline = _writing_castle_state()
    hidden_at = datetime.now(timezone.utc)
    submitted_at = hidden_at - timedelta(minutes=1)
    essay = Essay(
        student_id=child["id"],
        title="孩子隐藏的作文",
        status="settled",
        material_card=material,
        outline=outline,
        last_version_submitted_at=submitted_at,
        hidden_by="child",
        hidden_at=hidden_at,
        visibility_changed_at=hidden_at,
    )
    session.add(essay)
    session.flush()
    first_draft = EssayVersion(
        essay_id=essay.id,
        version_label="first_draft",
        round_index=1,
        content="孩子隐藏的初稿完整内容。",
    )
    revision = EssayVersion(
        essay_id=essay.id,
        version_label="revision",
        round_index=2,
        content="孩子隐藏的二稿完整内容。",
    )
    expected_latest_version_id = revision.id
    session.add(first_draft)
    session.add(revision)
    session.commit()

    response = client.get(
        f"/api/alpha/parents/{parent['id']}/children/{child['id']}/summary"
    )

    assert response.status_code == 200
    hidden_item = response.json()["writing_castle_summary"]
    assert hidden_item["essay_id"] == essay.id
    assert hidden_item["latest_version_id"] == expected_latest_version_id
    assert hidden_item["last_version_submitted_at"] is not None
    assert hidden_item["status"] == "hidden_by_child"
    assert hidden_item["hidden"] is True
    assert hidden_item["hidden_by"] == "child"
    assert hidden_item["hidden_at"] is not None
    assert hidden_item["can_continue_revision"] is False
    assert hidden_item["can_retry_revision_attempt"] is False


def test_parent_summary_preserves_ai_topic_origin_for_archived_essay(session, client):
    parent = create_alpha_parent(client, session)
    child = create_alpha_child(client, parent["id"])
    selected_topic_idea = {
        "id": "idea-football",
        "title": "一次足球比赛",
    }
    material, outline = _writing_castle_state(
        topic_origin="ai_topic_idea",
        selected_topic_idea=selected_topic_idea,
    )
    essay = Essay(
        student_id=child["id"],
        title="一次足球比赛",
        status="settled",
        material_card=material,
        outline=outline,
    )
    session.add(essay)
    session.flush()
    session.add(
        EssayVersion(
            essay_id=essay.id,
            version_label="first_draft",
            round_index=1,
            content="我参加了一次足球比赛。",
        )
    )
    session.add(
        EssayVersion(
            essay_id=essay.id,
            version_label="revision",
            round_index=2,
            content="我参加了一次足球比赛，还写清楚了进球时的动作。",
        )
    )
    session.commit()

    response = client.get(
        f"/api/alpha/parents/{parent['id']}/children/{child['id']}/summary"
    )

    assert response.status_code == 200
    summary = response.json()["writing_castle_summary"]
    assert summary["topic_origin"] == "ai_topic_idea"
    assert summary["topic_origin_label"] == "AI 出题灵感，孩子选择"
    assert summary["selected_topic_idea"] == selected_topic_idea
    assert summary["status"] == "revised_once"
    assert summary["latest_round_index"] == 2


def test_alpha_summary_rejects_writing_castle_scaffold_ref_mismatch(session, client):
    parent = create_alpha_parent(client, session)
    child = create_alpha_child(client, parent["id"])
    student_id = child["id"]

    start = client.post(
        f"/api/students/{student_id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    assert start.status_code == 201
    essay_id = start.json()["essay"]["id"]
    selected = client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json={"topic_type": "generic_narrative", "topic_variant": "learned_skill"},
    )
    assert selected.status_code == 200
    saved = session.get(Essay, essay_id)
    material = dict(saved.material_card)
    material["scaffold_ref"] = {}
    saved.material_card = material
    session.add(saved)
    session.commit()

    response = client.get(
        f"/api/alpha/parents/{parent['id']}/children/{student_id}/summary"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "scaffold_ref mismatch"


def test_alpha_summary_tolerates_malformed_writing_castle_json(session, client):
    parent = create_alpha_parent(client, session)
    child = create_alpha_child(client, parent["id"])
    essay = Essay(
        student_id=child["id"],
        title="旧数据题目",
        material_card=["not", "a", "dict"],
        outline={
            "schema_version": "v0.6a.1",
            "topic_analysis": "not-a-dict",
            "child_topic_focus": ["not-a-dict"],
            "step_state": "not-a-dict",
            "sections": ["not-a-dict", {"child_edited": True}],
        },
    )
    session.add(essay)
    session.commit()

    response = client.get(
        f"/api/alpha/parents/{parent['id']}/children/{child['id']}/summary"
    )

    assert response.status_code == 200
    assert response.json()["writing_castle_summary"] == {
        "topic": "旧数据题目",
        "topic_origin": "teacher_provided",
        "topic_origin_label": "老师布置题目",
        "selected_topic_idea": None,
        "selected_topic_type": "",
        "selected_topic_type_parent": "",
        "selection_source": "",
        "material_source_categories": [],
        "unsupported_future_type_overridden": False,
        "copy_ready_ai_body_generated": False,
        "topic_analysis_used": False,
        "topic_focus_confirmed": False,
        "topic_focus_edited": False,
        "material_questions_answered": 0,
        "material_cards_retained": 0,
        "outline_confirmed": False,
        "outline_edited": True,
        "first_draft_completed": False,
        "revision_completed": False,
        "settlement_completed": False,
        "essay_id": essay.id,
        "latest_version_id": None,
        "last_version_submitted_at": None,
        "latest_round_index": None,
        "revision_round_count": 0,
        "status": "not_archived",
        "summary_label": "还没有提交初稿",
        "hidden": False,
        "hidden_by": "",
        "hidden_at": None,
        "can_continue_revision": False,
        "can_retry_revision_attempt": False,
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


def test_alpha_me_children_uses_session_parent(client, session, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED_FOR_ALPHA", "true")
    family = create_authenticated_family(session)

    response = client.get(
        "/api/alpha/parents/me/children",
        cookies=family["cookie"],
    )

    assert response.status_code == 200
    assert response.json()["parent"]["id"] == family["parent"].id
    assert response.json()["children"][0]["id"] == family["student"].id
