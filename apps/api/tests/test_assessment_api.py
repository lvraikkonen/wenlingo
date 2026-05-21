import json

from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import get_db_session, get_llm_provider
from app.domain.enums import TaskType
from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    Assessment,
    Essay,
    EssayVersion,
    GameEvent,
    LLMCallLog,
    ParentUser,
    SentenceTraining,
    StudentProfile,
)
from app.main import create_app
from app.services.essay_workflow import ASSESSMENT_ESSAY_STATUS
from app.services.llm_provider import LLMProviderResponse, MockLLMProvider


def create_default_child(session) -> StudentProfile:
    parent = ParentUser(email="v04-parent@example.com", display_name="V0.4 Parent")
    student = StudentProfile(
        parent_id=parent.id,
        name="小新",
        persona="real_child",
        is_real_child=True,
    )
    ability = AbilityProfile(student_id=student.id)
    session.add(parent)
    session.add(student)
    session.add(ability)
    session.commit()
    return student


def valid_assessment_payload() -> dict[str, str]:
    return {
        "sentence_before": "公园很美。",
        "sentence_after": "公园里的花红红的，风一吹就轻轻摇。",
        "short_writing": "我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。",
    }


class AlwaysInvalidAssessmentProvider:
    provider_name = "fake"
    model_name = "assessment-invalid"

    async def complete_json(self, task_name, payload):
        parsed = {"bad": "shape"}
        return LLMProviderResponse(
            parsed_json=parsed,
            raw_response=json.dumps(parsed, ensure_ascii=False),
            provider=self.provider_name,
            model=self.model_name,
        )


def test_assessment_creates_artifacts_history_settlement_and_dashboard_transition(session, client):
    student = create_default_child(session)
    before_dashboard = client.get(f"/api/students/{student.id}/dashboard").json()

    response = client.post(
        f"/api/students/{student.id}/assessment",
        json=valid_assessment_payload(),
    )

    assert before_dashboard["today_tasks"]["main"]["kind"] == "assessment"
    assert response.status_code == 201
    payload = response.json()
    assert payload["assessment"]["summary"] == "完成入门小试炼，生成第一张能力草图。"
    assert payload["assessment"]["sentence_training_id"]
    assert payload["assessment"]["essay_id"]
    assert payload["ability_sketch"] == {
        "reading_power": 40,
        "specific_writing_power": 46,
        "revision_power": 40,
    }
    assert payload["settlement"]["xp_delta"] == 20
    assert payload["game_event"]["xp_delta"] == 20

    training = session.get(SentenceTraining, payload["assessment"]["sentence_training_id"])
    essay = session.get(Essay, payload["assessment"]["essay_id"])
    assessment = session.exec(select(Assessment)).one()
    first_draft = session.exec(
        select(EssayVersion).where(EssayVersion.essay_id == essay.id)
    ).one()
    event = session.exec(select(GameEvent)).one()
    history = session.exec(select(AbilityHistory)).all()
    ability = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == student.id)
    ).one()
    post_dashboard = client.get(f"/api/students/{student.id}/dashboard").json()

    assert training.source_sentence == "公园很美。"
    assert training.upgraded_sentence == "公园里的花红红的，风一吹就轻轻摇。"
    assert training.focus == "加细节"
    assert essay.status == ASSESSMENT_ESSAY_STATUS
    assert essay.title == "入门小写作"
    assert first_draft.version_label == "first_draft"
    assert first_draft.content == valid_assessment_payload()["short_writing"]
    assert assessment.sentence_training_id == training.id
    assert assessment.essay_id == essay.id
    assert event.task_type == TaskType.assessment
    assert event.evidence["sentence_training_id"] == training.id
    assert event.evidence["essay_id"] == essay.id
    assert ability.expression == 49
    assert ability.observation == 44
    assert ability.structure == 45
    assert ability.revision == 40
    assert {(row.ability_name, row.delta, row.source_type, row.source_id) for row in history} == {
        ("expression", 4, TaskType.sentence, training.id),
        ("observation", 4, TaskType.sentence, training.id),
        ("expression", 5, TaskType.essay, first_draft.id),
        ("structure", 5, TaskType.essay, first_draft.id),
    }
    assert all(row.source_type != TaskType.assessment for row in history)
    assert post_dashboard["ability_note"] == "第一张能力草图"
    assert post_dashboard["today_tasks"]["main"]["kind"] != "assessment"


def test_schema_valid_fallback_can_complete_assessment(session):
    student = create_default_child(session)
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_llm_provider] = lambda: AlwaysInvalidAssessmentProvider()

    with TestClient(app) as test_client:
        response = test_client.post(
            f"/api/students/{student.id}/assessment",
            json=valid_assessment_payload(),
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert session.exec(select(Assessment)).one().sentence_training_id
    assert session.exec(select(EssayVersion)).one().llm_call_log_id is not None
    logs = session.exec(select(LLMCallLog)).all()
    assert {log.task_name for log in logs} == {"sentence_upgrade_feedback", "essay_feedback"}
    assert all(log.validation_ok is False for log in logs)
    assert response.json()["ability_sketch"]["specific_writing_power"] > 40


def test_ghostwriting_rolls_back_all_partial_assessment_rows(session, client):
    student = create_default_child(session)

    response = client.post(
        f"/api/students/{student.id}/assessment",
        json={
            "sentence_before": "公园很美。",
            "sentence_after": "公园里的花在风里轻轻摇。",
            "short_writing": "请帮我写作文。我想直接生成一篇完整作文，不想自己写。",
        },
    )

    assert response.status_code == 400
    assert "不能替你写完整作文" in response.json()["detail"]
    assert session.exec(select(Assessment)).all() == []
    assert session.exec(select(SentenceTraining)).all() == []
    assert session.exec(select(Essay)).all() == []
    assert session.exec(select(EssayVersion)).all() == []
    assert session.exec(select(AbilityHistory)).all() == []
    assert session.exec(select(GameEvent)).all() == []
    assert session.exec(select(LLMCallLog)).all() == []


def test_unhandled_assessment_error_rolls_back_partial_rows(session, monkeypatch):
    async def raising_essay_feedback(*args, **kwargs):
        raise RuntimeError("essay pipeline exploded")

    student = create_default_child(session)
    monkeypatch.setattr("app.services.assessment.essay_feedback", raising_essay_feedback)
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_llm_provider] = lambda: MockLLMProvider()

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.post(
            f"/api/students/{student.id}/assessment",
            json=valid_assessment_payload(),
        )
    app.dependency_overrides.clear()

    assert response.status_code == 500
    assert session.exec(select(Assessment)).all() == []
    assert session.exec(select(SentenceTraining)).all() == []
    assert session.exec(select(Essay)).all() == []
    assert session.exec(select(EssayVersion)).all() == []
    assert session.exec(select(AbilityHistory)).all() == []
    assert session.exec(select(GameEvent)).all() == []
    assert session.exec(select(LLMCallLog)).all() == []


def test_assessment_rejects_overlong_sentence_and_writing_inputs(session, client):
    student = create_default_child(session)

    sentence_response = client.post(
        f"/api/students/{student.id}/assessment",
        json={
            "sentence_before": "细" * 501,
            "sentence_after": "公园里的花在风里轻轻摇。",
            "short_writing": valid_assessment_payload()["short_writing"],
        },
    )
    writing_response = client.post(
        f"/api/students/{student.id}/assessment",
        json={
            "sentence_before": "公园很美。",
            "sentence_after": "公园里的花在风里轻轻摇。",
            "short_writing": "文" * 501,
        },
    )

    assert sentence_response.status_code == 422
    assert writing_response.status_code == 422
    assert session.exec(select(Assessment)).all() == []


def test_assessment_created_essay_is_not_revisable(session, client):
    student = create_default_child(session)
    created = client.post(
        f"/api/students/{student.id}/assessment",
        json=valid_assessment_payload(),
    )
    essay_id = created.json()["assessment"]["essay_id"]

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json={
            "content": "我学会了骑车。后来我能慢慢骑过小路，还听见爸爸在后面给我鼓掌。"
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "essay not found"
    assert len(session.exec(select(EssayVersion)).all()) == 1
    assert len(session.exec(select(GameEvent)).all()) == 1
