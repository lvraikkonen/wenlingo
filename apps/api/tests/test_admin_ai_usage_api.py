from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.deps import get_db_session
from app.domain.enums import TaskType
from app.domain.models import LLMCallLog, ProductEvent
from app.main import create_app


def create_admin_client(session, monkeypatch, token: str = "secret"):
    monkeypatch.setenv("ALPHA_ADMIN_TOKEN", token)
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    return app


def test_admin_ai_usage_returns_daily_aggregates_with_limit_hits(session, monkeypatch):
    day = datetime(2026, 6, 8, 10, 30, tzinfo=timezone.utc)
    session.add(
        LLMCallLog(
            task_type=TaskType.sentence,
            task_name="sentence_challenge_generation",
            prompt_key="challenge",
            provider="test-provider",
            model="test-model",
            input_summary="sensitive child text",
            raw_response="sensitive raw response",
            output_json={"child_text": "sensitive"},
            validation_ok=True,
            prompt_tokens=10,
            completion_tokens=3,
            total_tokens=13,
            estimated_cost=0.001,
            created_at=day,
        )
    )
    session.add(
        LLMCallLog(
            task_type=TaskType.sentence,
            task_name="sentence_challenge_generation",
            prompt_key="challenge",
            provider="test-provider",
            model="test-model",
            input_summary="other sensitive child text",
            raw_response="other sensitive raw response",
            output_json={"child_text": "other sensitive"},
            validation_ok=False,
            error_message="provider failed",
            prompt_tokens=8,
            completion_tokens=2,
            total_tokens=10,
            estimated_cost=0.0005,
            created_at=datetime(2026, 6, 8, 18, 45, tzinfo=timezone.utc),
        )
    )
    session.add(
        ProductEvent(
            event_type="ai_daily_limit_reached",
            payload={"task_type": "sentence_challenge_generation"},
            created_at=datetime(2026, 6, 8, 20, 0, tzinfo=timezone.utc),
        )
    )
    session.commit()
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        response = client.get(
            "/api/admin/alpha/ai-usage",
            headers={"X-Alpha-Admin-Token": "secret"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "usage": [
            {
                "date": "2026-06-08",
                "task_type": "sentence_challenge_generation",
                "model": "test-model",
                "call_count": 2,
                "prompt_tokens": 18,
                "completion_tokens": 5,
                "total_tokens": 23,
                "estimated_cost": 0.0015,
                "failure_count": 1,
                "daily_limit_hit_count": 1,
            }
        ]
    }
    assert "raw_response" not in response.text
    assert "input_summary" not in response.text
    assert "sensitive child text" not in response.text


def test_admin_ai_usage_returns_empty_state(session, monkeypatch):
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        response = client.get(
            "/api/admin/alpha/ai-usage",
            headers={"X-Alpha-Admin-Token": "secret"},
        )

    assert response.status_code == 200
    assert response.json() == {"usage": []}
