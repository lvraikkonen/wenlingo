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
    day = datetime(2026, 6, 8, 1, 30, tzinfo=timezone.utc)
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
            final_status="primary_success",
            pricing_status="pricing_unconfigured",
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
            final_status="failed",
            pricing_status="pricing_unconfigured",
            error_message="provider failed",
            prompt_tokens=8,
            completion_tokens=2,
            total_tokens=10,
            estimated_cost=0.0005,
            created_at=datetime(2026, 6, 8, 5, 45, tzinfo=timezone.utc),
        )
    )
    session.add(
        ProductEvent(
            event_type="ai_daily_limit_reached",
            payload={"task_type": "sentence_challenge_generation"},
            created_at=datetime(2026, 6, 8, 6, 0, tzinfo=timezone.utc),
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
        "pricing_configured": False,
        "usage": [
            {
                "date": "2026-06-08",
                "task_type": "sentence_challenge_generation",
                "provider": "test-provider",
                "model": "test-model",
                "final_status": "failed",
                "call_count": 1,
                "success_count": 0,
                "fallback_success_count": 0,
                "deterministic_fallback_count": 0,
                "failure_count": 1,
                "daily_limit_hit_count": 1,
                "prompt_tokens": 8,
                "completion_tokens": 2,
                "total_tokens": 10,
                "estimated_cost": 0.0005,
                "pricing_status": "pricing_unconfigured",
                "avg_latency_ms": 0,
            },
            {
                "date": "2026-06-08",
                "task_type": "sentence_challenge_generation",
                "provider": "test-provider",
                "model": "test-model",
                "final_status": "primary_success",
                "call_count": 1,
                "success_count": 1,
                "fallback_success_count": 0,
                "deterministic_fallback_count": 0,
                "failure_count": 0,
                "daily_limit_hit_count": 1,
                "prompt_tokens": 10,
                "completion_tokens": 3,
                "total_tokens": 13,
                "estimated_cost": 0.001,
                "pricing_status": "pricing_unconfigured",
                "avg_latency_ms": 0,
            },
        ],
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
    assert response.json() == {"pricing_configured": False, "usage": []}


def test_admin_ai_usage_uses_product_events_for_limit_hit_count(
    session,
    monkeypatch,
):
    blocked_at = datetime(2026, 6, 8, 7, 0, tzinfo=timezone.utc)
    session.add(
        LLMCallLog(
            task_type=TaskType.sentence,
            task_name="sentence_challenge_generation",
            prompt_key="challenge",
            provider="legacy-provider",
            model="legacy-model",
            resolved_provider="resolved-provider",
            resolved_model="resolved-model",
            input_summary="safe summary",
            validation_ok=False,
            final_status="daily_limit_reached",
            pricing_status="pricing_unconfigured",
            latency_ms=125,
            created_at=blocked_at,
        )
    )
    session.add(
        ProductEvent(
            event_type="ai_daily_limit_reached",
            payload={"task_type": "sentence_challenge_generation"},
            created_at=blocked_at,
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
        "pricing_configured": False,
        "usage": [
            {
                "date": "2026-06-08",
                "task_type": "sentence_challenge_generation",
                "provider": "resolved-provider",
                "model": "resolved-model",
                "final_status": "daily_limit_reached",
                "call_count": 1,
                "success_count": 0,
                "fallback_success_count": 0,
                "deterministic_fallback_count": 0,
                "failure_count": 0,
                "daily_limit_hit_count": 1,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_cost": 0.0,
                "pricing_status": "pricing_unconfigured",
                "avg_latency_ms": 125,
            }
        ],
    }


def test_admin_ai_usage_uses_configured_product_timezone_for_dates(session, monkeypatch):
    monkeypatch.setenv("LLM_DAILY_LIMIT_TIMEZONE", "Asia/Shanghai")
    utc_boundary_time = datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc)
    session.add(
        LLMCallLog(
            task_type=TaskType.sentence,
            task_name="sentence_challenge_generation",
            prompt_key="challenge",
            provider="test-provider",
            model="test-model",
            input_summary="timezone boundary input",
            validation_ok=True,
            prompt_tokens=4,
            completion_tokens=2,
            total_tokens=6,
            estimated_cost=0.0002,
            created_at=utc_boundary_time,
        )
    )
    session.add(
        ProductEvent(
            event_type="ai_daily_limit_reached",
            payload={"task_type": "sentence_challenge_generation"},
            created_at=utc_boundary_time,
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
        "pricing_configured": False,
        "usage": [
            {
                "date": "2026-06-08",
                "task_type": "sentence_challenge_generation",
                "provider": "test-provider",
                "model": "test-model",
                "final_status": "primary_success",
                "call_count": 1,
                "success_count": 1,
                "fallback_success_count": 0,
                "deterministic_fallback_count": 0,
                "failure_count": 0,
                "daily_limit_hit_count": 1,
                "prompt_tokens": 4,
                "completion_tokens": 2,
                "total_tokens": 6,
                "estimated_cost": 0.0002,
                "pricing_status": "pricing_unconfigured",
                "avg_latency_ms": 0,
            }
        ],
    }


def test_admin_ai_usage_reports_pricing_configured_when_rates_are_set(
    session,
    monkeypatch,
):
    monkeypatch.setenv("LLM_INPUT_COST_PER_1K_TOKENS", "0.001")
    monkeypatch.setenv("LLM_OUTPUT_COST_PER_1K_TOKENS", "0.002")
    session.add(
        LLMCallLog(
            task_type=TaskType.sentence,
            task_name="sentence_challenge_feedback",
            prompt_key="feedback",
            provider="test-provider",
            model="test-model",
            input_summary="safe summary",
            validation_ok=True,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost=0.0002,
            created_at=datetime(2026, 6, 8, 1, 30, tzinfo=timezone.utc),
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
    assert response.json()["pricing_configured"] is True
    assert response.json()["usage"][0]["estimated_cost"] == 0.0002


def test_admin_ai_usage_reports_pricing_configured_when_profile_rates_are_set(
    session,
    monkeypatch,
):
    monkeypatch.setenv("LLM_PRIMARY_INPUT_COST_PER_1K_TOKENS", "0.001")
    monkeypatch.setenv("LLM_PRIMARY_OUTPUT_COST_PER_1K_TOKENS", "0.002")
    monkeypatch.setenv("LLM_FALLBACK_INPUT_COST_PER_1K_TOKENS", "0.003")
    monkeypatch.setenv("LLM_FALLBACK_OUTPUT_COST_PER_1K_TOKENS", "0.004")
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        response = client.get(
            "/api/admin/alpha/ai-usage",
            headers={"X-Alpha-Admin-Token": "secret"},
        )

    assert response.status_code == 200
    assert response.json() == {"pricing_configured": True, "usage": []}
