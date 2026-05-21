from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import get_db_session, get_llm_provider
from app.domain.enums import TaskType
from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    GameEvent,
    SentenceTraining,
    StudentProfile,
)
from app.domain.seed import seed_demo_data
from app.main import create_app
from app.services.llm_provider import LLMProviderResponse


def parent_students(session, parent_id: str):
    return session.exec(select(StudentProfile).where(StudentProfile.parent_id == parent_id)).all()


def test_sentence_training_persists_feedback_ability_and_game_event(session, client):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]

    response = client.post(
        f"/api/students/{student.id}/sentences",
        json={
            "source_sentence": "公园很美。",
            "upgraded_sentence": "清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。",
            "focus": "加细节",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["feedback"]["specific_improvement"] == "加入了可看见的细节"
    assert payload["settlement"]["xp_delta"] == 25
    assert payload["next_task"]["kind"] in {"essay", "sentence"}
    training = session.exec(select(SentenceTraining)).one()
    assert training.focus == "加细节"
    assert session.exec(select(GameEvent)).one().problem_monsters == ["空泛表达"]
    assert session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == student.id)
    ).one().expression > 40
    history = session.exec(
        select(AbilityHistory).where(AbilityHistory.student_id == student.id)
    ).all()
    assert {(row.ability_name, row.delta, row.source_type, row.source_id) for row in history} == {
        ("expression", 4, TaskType.sentence, training.id),
        ("observation", 4, TaskType.sentence, training.id),
    }


def test_sentence_training_uses_fallback_when_provider_returns_only_noncanonical_deltas(session):
    class NonCanonicalDeltaProvider:
        provider_name = "http"
        model_name = "test-model"

        async def complete_json(self, task_name, payload):
            response_payload = {
                "encouragement": "你把画面写得更清楚了。",
                "specific_improvement": "加入了可看见的细节",
                "next_step": "再加一个动作，会更生动。",
                "ability_delta": {"细节描写": 2, "比喻运用": 1},
                "problem_monsters": ["空泛表达"],
            }
            return LLMProviderResponse(
                parsed_json=response_payload,
                raw_response='{"ability_delta":{"细节描写":2,"比喻运用":1}}',
                provider=self.provider_name,
                model=self.model_name,
            )

    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    ability_before = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == student.id)
    ).one()
    expression_before = ability_before.expression
    observation_before = ability_before.observation
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_llm_provider] = lambda: NonCanonicalDeltaProvider()

    with TestClient(app) as test_client:
        response = test_client.post(
            f"/api/students/{student.id}/sentences",
            json={
                "source_sentence": "公园很美。",
                "upgraded_sentence": "清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。",
                "focus": "加细节",
            },
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    training = session.exec(select(SentenceTraining)).one()
    ability = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == student.id)
    ).one()
    assert ability.expression == expression_before + 2
    assert ability.observation == observation_before + 2
    history = session.exec(
        select(AbilityHistory).where(AbilityHistory.source_id == training.id)
    ).all()
    assert {(row.ability_name, row.delta, row.source_type, row.source_id) for row in history} == {
        ("expression", 2, TaskType.sentence, training.id),
        ("observation", 2, TaskType.sentence, training.id),
    }


def test_sentence_training_rejects_invalid_focus(session, client):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]

    response = client.post(
        f"/api/students/{student.id}/sentences",
        json={
            "source_sentence": "公园很美。",
            "upgraded_sentence": "公园里的花在风里轻轻摇。",
            "focus": "随便写",
        },
    )

    assert response.status_code == 422


def test_sentence_training_rejects_overlong_sentences(session, client):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    too_long = "细" * 501

    response = client.post(
        f"/api/students/{student.id}/sentences",
        json={
            "source_sentence": too_long,
            "upgraded_sentence": "公园里的花在风里轻轻摇。",
            "focus": "加细节",
        },
    )

    assert response.status_code == 422
