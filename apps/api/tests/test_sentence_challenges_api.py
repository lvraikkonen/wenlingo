from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import get_ai_task_runner, get_db_session
from app.core.config import Settings, get_settings
from app.domain.enums import StudentPersona, TaskType
from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    GameEvent,
    LLMCallLog,
    ParentAccount,
    ParentSession,
    ParentUser,
    ProductEvent,
    SentenceTraining,
    StudentProfile,
)
from app.domain.seed import seed_demo_data
from app.main import create_app
from app.services.ai_runner import run_ai_task
from app.services.auth_security import hash_secret
from app.services.ai_routing import TASK_CONFIGS, TaskFinalStatus
from app.services.llm_provider import LLMProviderResponse
from app.services.sentence_challenges import fallback_challenge_feedback


CHALLENGE_RESPONSES = {
    "expand_sentence": {
        "source_sentence": "小花开了。",
        "challenge_prompt": "请把句子写具体，补充时间、地点或样子。",
        "hint": "可以想一想谁在什么地方，看到或听到了什么。",
        "focus": "扩句",
    },
    "action_expression": {
        "source_sentence": "小猫跑了。",
        "challenge_prompt": "请把句子写具体，加上动作和样子。",
        "hint": "可以写小猫怎么跑、跑到哪里、看起来怎么样。",
        "focus": "动作描写",
    },
    "feeling": {
        "source_sentence": "我走进教室。",
        "challenge_prompt": "请把句子写具体，加上一点心里想法。",
        "hint": "可以写人物当时在想什么，心情有什么变化。",
        "focus": "心理感受",
    },
}


class ChallengeRunner:
    provider_name = "http"
    model_name = "test-model"

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.calls = []
        self.payloads = []

    async def run(self, **kwargs):
        return await run_ai_task(
            settings=self.settings,
            primary_provider=self,
            fallback_provider=self,
            **kwargs,
        )

    async def complete_json(self, task_name, payload):
        self.calls.append(task_name)
        self.payloads.append(payload)
        if task_name == "sentence_challenge_generation":
            grade_label = payload["grade_label"]
            target_skill = payload["target_skill"]
            body = {
                **CHALLENGE_RESPONSES[target_skill],
                "target_skill": target_skill,
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


def challenge_client(session, runner, settings=None):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    if settings is not None:
        runner.settings = settings
    app.dependency_overrides[get_ai_task_runner] = lambda: runner
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings
    return app, TestClient(app)


def link_parent_session(session, parent, token="session-token"):
    account = ParentAccount(
        email_normalized=f"{parent.id}@example.com",
        email_verified_at=datetime.now(UTC),
        last_login_at=datetime.now(UTC),
    )
    session.add(account)
    session.flush()
    parent.account_id = account.id
    parent.account_linked_at = datetime.now(UTC)
    session.add(parent)
    session.add(
        ParentSession(
            account_id=account.id,
            token_hash=hash_secret(
                token,
                purpose="session-token",
                pepper="test-pepper",
            ),
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    )
    session.commit()
    return token


def test_challenge_generation_declares_empty_request_body_contract():
    app = create_app()

    request_body = app.openapi()["paths"]["/api/students/{student_id}/sentence-challenges"][
        "post"
    ].get("requestBody")

    assert request_body is not None


def test_challenge_generation_persists_generated_training(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    runner = ChallengeRunner()
    app, client = challenge_client(session, runner)

    with client:
        response = client.post(
            f"/api/students/{student.id}/sentence-challenges",
            json={},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    payload = response.json()
    training = session.exec(select(SentenceTraining)).one()
    challenge = payload["challenge"]
    assert training.status == "generated"
    assert training.upgraded_sentence == ""
    assert training.target_skill == "expand_sentence"
    assert challenge["id"] == training.id
    assert challenge["source_sentence"] == "小花开了。"
    assert challenge["grade_label"] == student.grade_label
    assert runner.calls == ["sentence_challenge_generation"]
    assert runner.payloads[0]["target_skill"] == "expand_sentence"


@pytest.mark.parametrize(
    ("completed_count", "expected_target_skill"),
    [
        (0, "expand_sentence"),
        (1, "action_expression"),
        (2, "feeling"),
    ],
)
def test_challenge_generation_cycles_target_skill_by_completed_count(
    session,
    completed_count,
    expected_target_skill,
):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    for index in range(completed_count):
        target_skill = tuple(CHALLENGE_RESPONSES)[index]
        session.add(
            SentenceTraining(
                student_id=student.id,
                source_sentence=CHALLENGE_RESPONSES[target_skill]["source_sentence"],
                upgraded_sentence="这个句子已经写具体了。",
                focus=CHALLENGE_RESPONSES[target_skill]["focus"],
                ai_feedback={},
                status="completed",
                challenge_prompt=CHALLENGE_RESPONSES[target_skill]["challenge_prompt"],
                hint=CHALLENGE_RESPONSES[target_skill]["hint"],
                target_skill=target_skill,
                completed_at=datetime.now(UTC),
            )
        )
    session.commit()
    runner = ChallengeRunner()
    app, client = challenge_client(session, runner)

    with client:
        response = client.post(
            f"/api/students/{student.id}/sentence-challenges",
            json={},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert runner.payloads[0]["target_skill"] == expected_target_skill
    assert response.json()["challenge"]["target_skill"] == expected_target_skill


def test_challenge_generation_uses_student_grade_label(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    student.grade_label = "五年级"
    session.add(student)
    session.commit()
    runner = ChallengeRunner()
    app, client = challenge_client(session, runner)

    with client:
        response = client.post(
            f"/api/students/{student.id}/sentence-challenges",
            json={},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    challenge = response.json()["challenge"]
    assert challenge["grade_label"] == "五年级"
    assert challenge["difficulty_label"] == "五年级基础"


def test_challenge_completion_updates_same_row_and_settles_once(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    session.add(
        SentenceTraining(
            student_id=student.id,
            source_sentence="小花开了。",
            upgraded_sentence="春天的小花在墙角静静地开了。",
            focus="扩句",
            ai_feedback={},
            status="completed",
            challenge_prompt="请把句子写具体，补充时间、地点或样子。",
            hint="可以想一想谁在什么地方，看到或听到了什么。",
            target_skill="expand_sentence",
            completed_at=datetime.now(UTC),
        )
    )
    session.commit()
    runner = ChallengeRunner()
    app, client = challenge_client(session, runner)

    with client:
        generation = client.post(
            f"/api/students/{student.id}/sentence-challenges",
            json={},
        )
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


def test_auth_required_challenge_generation_rejects_unauthenticated_request(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    runner = ChallengeRunner()
    app, client = challenge_client(
        session,
        runner,
        Settings(auth_required_for_alpha=True, auth_secret_pepper="test-pepper"),
    )

    with client:
        response = client.post(
            f"/api/students/{student.id}/sentence-challenges",
            json={},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"] == "parent session required"
    assert runner.calls == []


def test_auth_required_challenge_generation_accepts_empty_json_body(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    token = link_parent_session(session, parent)
    runner = ChallengeRunner()
    app, client = challenge_client(
        session,
        runner,
        Settings(auth_required_for_alpha=True, auth_secret_pepper="test-pepper"),
    )

    with client:
        response = client.post(
            f"/api/students/{student.id}/sentence-challenges",
            json={},
            cookies={"wenlingo_parent_session": token},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["challenge"]["target_skill"] == "expand_sentence"
    assert runner.calls == ["sentence_challenge_generation"]


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
    runner = ChallengeRunner()
    app, client = challenge_client(session, runner)

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
    runner = ChallengeRunner()
    app, client = challenge_client(session, runner)

    with client:
        response = client.post(
            f"/api/students/{student.id}/sentences/{other_training.id}/complete",
            json={"upgraded_sentence": "小猫瞪大眼睛，飞快地跑过草地。"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "sentence training not found"


def test_challenge_completion_rejects_malformed_generated_row_without_award(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    ability = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == student.id)
    ).one()
    expression_before = ability.expression
    observation_before = ability.observation
    training = SentenceTraining(
        student_id=student.id,
        source_sentence="小猫跑了。",
        focus="动作描写",
        status="generated",
        challenge_prompt="请把句子写具体，加上动作和样子。",
        hint="可以写小猫怎么跑。",
        target_skill="",
    )
    session.add(training)
    session.commit()
    runner = ChallengeRunner()
    app, client = challenge_client(session, runner)

    with client:
        response = client.post(
            f"/api/students/{student.id}/sentences/{training.id}/complete",
            json={"upgraded_sentence": "小猫瞪大眼睛，飞快地跑过草地。"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "sentence training not found"
    assert runner.calls == []
    session.refresh(training)
    session.refresh(ability)
    assert training.status == "generated"
    assert training.upgraded_sentence == ""
    assert ability.expression == expression_before
    assert ability.observation == observation_before
    assert session.exec(select(AbilityHistory)).all() == []
    assert session.exec(select(GameEvent)).all() == []


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
    runner = ChallengeRunner()
    app, client = challenge_client(session, runner)

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
    for index in range(TASK_CONFIGS["sentence_challenge_generation"].daily_limit):
        session.add(
            LLMCallLog(
                student_id=student.id,
                task_type=TaskType.sentence,
                task_name="sentence_challenge_generation",
                prompt_key="sentence_challenge_generation",
                provider="http",
                model="test-model",
                prompt_version="test",
                input_summary=f"句子挑战生成 {index}",
                output_json={},
                validation_ok=True,
                final_status=TaskFinalStatus.PRIMARY_SUCCESS,
                created_at=datetime.now(UTC),
            )
        )
    session.commit()
    runner = ChallengeRunner()
    app, client = challenge_client(
        session,
        runner,
        Settings(
            llm_daily_limit_enabled=True,
            llm_daily_limit_timezone="Asia/Shanghai",
        ),
    )

    with client:
        response = client.post(
            f"/api/students/{student.id}/sentence-challenges",
            json={},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.json()["detail"] == "今天的句子挑战已经完成很多啦，休息一下，明天继续闯关！"
    assert runner.calls == []


def test_feedback_provider_failure_still_completes_with_fallback_feedback(session):
    class FailingFeedbackRunner(ChallengeRunner):
        async def complete_json(self, task_name, payload):
            if task_name == "sentence_challenge_feedback":
                self.calls.append(task_name)
                raise RuntimeError("feedback unavailable")
            return await super().complete_json(task_name, payload)

    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    session.add(
        SentenceTraining(
            student_id=student.id,
            source_sentence="小花开了。",
            upgraded_sentence="春天的小花在墙角静静地开了。",
            focus="扩句",
            ai_feedback={},
            status="completed",
            challenge_prompt="请把句子写具体，补充时间、地点或样子。",
            hint="可以想一想谁在什么地方，看到或听到了什么。",
            target_skill="expand_sentence",
            completed_at=datetime.now(UTC),
        )
    )
    session.commit()
    runner = FailingFeedbackRunner()
    app, client = challenge_client(session, runner)

    with client:
        generation = client.post(
            f"/api/students/{student.id}/sentence-challenges",
            json={},
        )
        training_id = generation.json()["challenge"]["id"]
        response = client.post(
            f"/api/students/{student.id}/sentences/{training_id}/complete",
            json={"upgraded_sentence": "小猫瞪大眼睛，飞快地跑过草地。"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    training = session.get(SentenceTraining, training_id)
    fallback = fallback_challenge_feedback("action_expression")
    assert training.status == "completed"
    assert training.ai_feedback == fallback.model_dump()
    assert payload["feedback"]["encouragement"] == fallback.encouragement
    assert payload["feedback"]["example_upgrade"] == fallback.example_upgrade
    event = session.exec(
        select(ProductEvent).where(
            ProductEvent.event_type == "sentence_challenge_feedback_failed"
        )
    ).one()
    assert event.payload["task_type"] == "sentence_challenge_feedback"
