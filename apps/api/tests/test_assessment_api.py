import json

from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import get_db_session, get_llm_provider
from app.core.config import Settings, get_settings
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
    ProductEvent,
    SentenceTraining,
    StudentProfile,
)
from app.main import create_app
from app.services.essay_workflow import ASSESSMENT_ESSAY_STATUS
from app.services.ai_routing import TaskFinalStatus
from app.services.llm_provider import LLMProviderResponse


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


class RaiseOnEssayFeedbackProvider:
    provider_name = "fake"
    model_name = "assessment-essay-error"

    async def complete_json(self, task_name, payload):
        if task_name == "sentence_upgrade_feedback":
            parsed = {
                "encouragement": "你把画面写得更清楚了。",
                "specific_improvement": "加入了可看见的细节",
                "next_step": "再加一个动作，会更生动。",
                "ability_delta": {"expression": 4, "observation": 4},
                "problem_monsters": ["空泛表达"],
            }
            return LLMProviderResponse(
                parsed_json=parsed,
                raw_response=json.dumps(parsed, ensure_ascii=False),
                provider=self.provider_name,
                model=self.model_name,
            )
        if task_name == "essay_feedback":
            raise RuntimeError("essay pipeline exploded")
        raise ValueError(f"Unknown LLM task: {task_name}")


class QuotaLimitedAssessmentProvider:
    provider_name = "http"
    model_name = "assessment-quota"

    async def complete_json(self, task_name, payload):
        if task_name == "essay_feedback":
            parsed = {
                "strengths": ["能写清楚发生了什么", "写出了自己的心情"],
                "improvements": ["再补一个动作细节"],
                "problem_monsters": ["细节缺口"],
                "sentence_notes": ["把害怕换成看得见的动作。"],
                "revision_tasks": [{"instruction": "补一个动作", "target": "中间段"}],
            }
            return LLMProviderResponse(
                parsed_json=parsed,
                raw_response=json.dumps(parsed, ensure_ascii=False),
                provider=self.provider_name,
                model=self.model_name,
            )
        raise RuntimeError(f"daily limit branch should run before provider call: {task_name}")


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


def test_daily_limit_assessment_uses_fallback_without_failure_event(session):
    student = create_default_child(session)
    session.add(
        LLMCallLog(
            student_id=student.id,
            task_type=TaskType.sentence,
            task_name="sentence_upgrade_feedback",
            provider=QuotaLimitedAssessmentProvider.provider_name,
            model=QuotaLimitedAssessmentProvider.model_name,
            input_summary="previous assessment sentence request",
            validation_ok=True,
            final_status=TaskFinalStatus.PRIMARY_SUCCESS,
        )
    )
    session.commit()
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_llm_provider] = lambda: QuotaLimitedAssessmentProvider()
    app.dependency_overrides[get_settings] = lambda: Settings(
        llm_daily_limit_enabled=True,
        llm_daily_limit_per_student_task=1,
        sentence_feedback_daily_limit_per_student=1,
    )

    with TestClient(app) as test_client:
        response = test_client.post(
            f"/api/students/{student.id}/assessment",
            json=valid_assessment_payload(),
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert session.exec(select(Assessment)).one().sentence_training_id
    assert session.exec(select(SentenceTraining)).one().ai_feedback["encouragement"]
    assert session.exec(select(Essay)).one().title == "入门小写作"
    assert session.exec(select(EssayVersion)).one().llm_call_log_id is not None
    assert session.exec(select(GameEvent)).one().task_type == TaskType.assessment
    assert session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "ai_feedback_failed")
    ).all() == []
    logs = session.exec(select(LLMCallLog)).all()
    assert [log.provider for log in logs] == ["http", "local_fallback", "http"]
    assert logs[1].error_message == "daily limit reached"
    assert logs[1].validation_ok is False
    ability = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == student.id)
    ).one()
    assert ability.expression > 40
    assert ability.observation > 40
    assert ability.structure > 40


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


def test_unhandled_assessment_error_rolls_back_partial_rows(session):
    student = create_default_child(session)
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_llm_provider] = lambda: RaiseOnEssayFeedbackProvider()

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

    before_response = client.post(
        f"/api/students/{student.id}/assessment",
        json={
            "sentence_before": "细" * 501,
            "sentence_after": "公园里的花在风里轻轻摇。",
            "short_writing": valid_assessment_payload()["short_writing"],
        },
    )
    after_response = client.post(
        f"/api/students/{student.id}/assessment",
        json={
            "sentence_before": "公园很美。",
            "sentence_after": "细" * 501,
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

    assert before_response.status_code == 422
    assert after_response.status_code == 422
    assert writing_response.status_code == 422
    assert session.exec(select(Assessment)).all() == []


def test_assessment_created_essay_is_not_revisable(session, client):
    student = create_default_child(session)
    created = client.post(
        f"/api/students/{student.id}/assessment",
        json=valid_assessment_payload(),
    )
    assert created.status_code == 201
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
