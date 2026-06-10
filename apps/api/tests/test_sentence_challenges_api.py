from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import get_db_session, get_llm_provider
from app.core.config import Settings, get_settings
from app.domain.enums import StudentPersona, TaskType
from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    LLMCallLog,
    ParentUser,
    ProductEvent,
    SentenceTraining,
    StudentProfile,
)
from app.domain.seed import seed_demo_data
from app.main import create_app
from app.services.llm_provider import LLMProviderResponse


class ChallengeProvider:
    provider_name = "http"
    model_name = "test-model"

    def __init__(self):
        self.calls = []

    async def complete_json(self, task_name, payload):
        self.calls.append(task_name)
        if task_name == "sentence_challenge_generation":
            grade_label = payload["grade_label"]
            body = {
                "source_sentence": "小猫跑了。",
                "challenge_prompt": "请把句子写具体，加上动作和样子。",
                "hint": "可以写小猫怎么跑、跑到哪里、看起来怎么样。",
                "target_skill": "action_expression",
                "focus": "动作描写",
                "difficulty_label": f"{grade_label}基础",
                "grade_label": grade_label,
            }
        else:
            body = {
                "encouragement": "你写得很有画面感！",
                "highlight": "你加上了飞快地冲过去，动作更清楚了。",
                "suggestion": "还可以加一点表情或心情。",
                "example_upgrade": "小狗瞪大眼睛，飞快地冲过草地。",
            }
        return LLMProviderResponse(
            parsed_json=body,
            raw_response="{}",
            provider="http",
            model="test-model",
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        )


def parent_students(session, parent_id):
    return session.exec(select(StudentProfile).where(StudentProfile.parent_id == parent_id)).all()


def challenge_client(session, provider, settings=None):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_llm_provider] = lambda: provider
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings
    return app, TestClient(app)


def test_challenge_generation_persists_generated_training(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    provider = ChallengeProvider()
    app, client = challenge_client(session, provider)

    with client:
        response = client.post(f"/api/students/{student.id}/sentence-challenges")
    app.dependency_overrides.clear()

    assert response.status_code == 201
    payload = response.json()
    training = session.exec(select(SentenceTraining)).one()
    challenge = payload["challenge"]
    assert training.status == "generated"
    assert training.upgraded_sentence == ""
    assert training.target_skill == "action_expression"
    assert challenge["id"] == training.id
    assert challenge["source_sentence"] == "小猫跑了。"
    assert challenge["grade_label"] == student.grade_label
    assert provider.calls == ["sentence_challenge_generation"]


def test_challenge_generation_uses_student_grade_label(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    student.grade_label = "五年级"
    session.add(student)
    session.commit()
    provider = ChallengeProvider()
    app, client = challenge_client(session, provider)

    with client:
        response = client.post(f"/api/students/{student.id}/sentence-challenges")
    app.dependency_overrides.clear()

    assert response.status_code == 201
    challenge = response.json()["challenge"]
    assert challenge["grade_label"] == "五年级"
    assert challenge["difficulty_label"] == "五年级基础"


def test_challenge_completion_updates_same_row_and_settles_once(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    provider = ChallengeProvider()
    app, client = challenge_client(session, provider)

    with client:
        generation = client.post(f"/api/students/{student.id}/sentence-challenges")
        training_id = generation.json()["challenge"]["id"]
        response = client.post(
            f"/api/students/{student.id}/sentences/{training_id}/complete",
            json={"upgraded_sentence": "小猫瞪大眼睛，飞快地跑过草地。"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    training = session.get(SentenceTraining, training_id)
    assert training.status == "completed"
    assert training.upgraded_sentence == "小猫瞪大眼睛，飞快地跑过草地。"
    assert training.completed_at is not None
    assert payload["feedback"]["example_upgrade"]
    assert payload["settlement"]["xp_delta"] == 25
    history = session.exec(
        select(AbilityHistory).where(AbilityHistory.source_id == training_id)
    ).all()
    assert {(row.ability_name, row.delta, row.source_type) for row in history} == {
        ("expression", 3, TaskType.sentence),
        ("observation", 2, TaskType.sentence),
    }


def test_repeated_challenge_completion_returns_409(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    training = SentenceTraining(
        student_id=student.id,
        source_sentence="小猫跑了。",
        upgraded_sentence="小猫飞快地跑过草地。",
        focus="动作描写",
        ai_feedback={"encouragement": "写得好。"},
        status="completed",
        challenge_prompt="请把句子写具体，加上动作和样子。",
        hint="可以写小猫怎么跑。",
        target_skill="action_expression",
        completed_at=datetime.now(UTC),
    )
    session.add(training)
    session.commit()
    provider = ChallengeProvider()
    app, client = challenge_client(session, provider)

    with client:
        response = client.post(
            f"/api/students/{student.id}/sentences/{training.id}/complete",
            json={"upgraded_sentence": "小猫瞪大眼睛，飞快地跑过草地。"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "sentence challenge already completed"


def test_challenge_completion_rejects_cross_family_training_with_404(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    other_parent = ParentUser(
        email="other-parent@example.com",
        display_name="Other Parent",
    )
    session.add(other_parent)
    session.flush()
    other_student = StudentProfile(
        parent_id=other_parent.id,
        name="Other Child",
        grade_label="四年级",
        persona=StudentPersona.real_child,
        is_real_child=True,
    )
    session.add(other_student)
    session.flush()
    session.add(AbilityProfile(student_id=other_student.id))
    other_training = SentenceTraining(
        student_id=other_student.id,
        source_sentence="小猫跑了。",
        focus="动作描写",
        status="generated",
        challenge_prompt="请把句子写具体，加上动作和样子。",
        hint="可以写小猫怎么跑。",
        target_skill="action_expression",
    )
    session.add(other_training)
    session.commit()
    provider = ChallengeProvider()
    app, client = challenge_client(session, provider)

    with client:
        response = client.post(
            f"/api/students/{student.id}/sentences/{other_training.id}/complete",
            json={"upgraded_sentence": "小猫瞪大眼睛，飞快地跑过草地。"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "sentence training not found"


def test_challenge_completion_rejects_short_answer(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    training = SentenceTraining(
        student_id=student.id,
        source_sentence="小猫跑了。",
        focus="动作描写",
        status="generated",
        challenge_prompt="请把句子写具体，加上动作和样子。",
        hint="可以写小猫怎么跑。",
        target_skill="action_expression",
    )
    session.add(training)
    session.commit()
    provider = ChallengeProvider()
    app, client = challenge_client(session, provider)

    with client:
        response = client.post(
            f"/api/students/{student.id}/sentences/{training.id}/complete",
            json={"upgraded_sentence": "短。"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 422


def test_daily_generation_limit_returns_rest_message_without_provider_call(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    session.add(
        LLMCallLog(
            student_id=student.id,
            task_type=TaskType.sentence,
            task_name="sentence_challenge_generation",
            prompt_key="sentence_challenge_generation",
            provider="http",
            model="test-model",
            prompt_version="test",
            input_summary="句子挑战生成",
            output_json={},
            validation_ok=True,
            created_at=datetime.now(UTC),
        )
    )
    session.commit()
    provider = ChallengeProvider()
    app, client = challenge_client(
        session,
        provider,
        Settings(
            llm_daily_limit_enabled=True,
            sentence_challenge_daily_limit_per_student=1,
            llm_daily_limit_timezone="Asia/Shanghai",
        ),
    )

    with client:
        response = client.post(f"/api/students/{student.id}/sentence-challenges")
    app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.json()["detail"] == "今天的句子挑战已经完成很多啦，休息一下，明天继续闯关！"
    assert provider.calls == []


def test_feedback_provider_failure_still_completes_with_fallback_feedback(session):
    class FailingFeedbackProvider(ChallengeProvider):
        async def complete_json(self, task_name, payload):
            if task_name == "sentence_challenge_feedback":
                self.calls.append(task_name)
                raise RuntimeError("feedback unavailable")
            return await super().complete_json(task_name, payload)

    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    provider = FailingFeedbackProvider()
    app, client = challenge_client(session, provider)

    with client:
        generation = client.post(f"/api/students/{student.id}/sentence-challenges")
        training_id = generation.json()["challenge"]["id"]
        response = client.post(
            f"/api/students/{student.id}/sentences/{training_id}/complete",
            json={"upgraded_sentence": "小猫瞪大眼睛，飞快地跑过草地。"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    event = session.exec(
        select(ProductEvent).where(
            ProductEvent.event_type == "sentence_challenge_feedback_failed"
        )
    ).one()
    assert event.payload["task_type"] == "sentence_challenge_feedback"
