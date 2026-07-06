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


def v06e_zero_metrics(**overrides):
    metrics = {
        "streaming_enabled_count": 0,
        "stream_completed_count": 0,
        "client_disconnect_count": 0,
        "provider_failed_before_visible_content_count": 0,
        "provider_failed_after_visible_content_count": 0,
        "usage_available_count": 0,
        "usage_missing_count": 0,
        "calls_with_usage_applicable": 0,
        "usage_available_rate": 0.0,
        "first_provider_delta_p50_ms": 0,
        "first_visible_content_p50_ms": 0,
        "provider_stream_duration_p50_ms": 0,
        "live_llm_success_count": 0,
        "timeout_count": 0,
        "schema_validation_success_count": 0,
        "source_reference_success_count": 0,
    }
    metrics.update(overrides)
    return metrics


def provider_attempt_summary(
    *,
    provider: str = "test-provider",
    model: str = "test-model",
    status: str = "schema_validation_failed",
    usage_available: bool = False,
):
    return {
        "attempt_index": 1,
        "role": "primary",
        "provider": provider,
        "model": model,
        "status": status,
        "error_class": "",
        "latency_ms": 100,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "estimated_cost": None,
        "pricing_status": "pricing_configured",
        "provider_response_received": True,
        "usage_available": usage_available,
        "usage_source": "provider" if usage_available else "unavailable",
        "usage_is_estimated": False,
        "usage_details_json": {},
        "cost_source": "unavailable",
        "cost_error_code": "",
        "pricing_snapshot_id": None,
        "pricing_snapshot_version": "",
        "provider_reported_cost_usd": None,
        "cost_calculation_version": "v0.6e.1",
    }


def material_card_output():
    return {
        "cards": [
            {
                "id": "card-1",
                "category": "event",
                "text": "素材卡",
                "source_answer_ids": ["answer-1"],
                "source_refs": [
                    {"source_type": "real_experience", "answer_id": "answer-1"}
                ],
            }
        ]
    }


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
            usage_available=True,
            usage_source="provider",
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
            usage_available=True,
            usage_source="provider",
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
                "final_status": "mixed",
                "call_count": 2,
                "success_count": 1,
                "fallback_success_count": 0,
                "deterministic_fallback_count": 0,
                "failure_count": 1,
                "daily_limit_hit_count": 1,
                "prompt_tokens": 18,
                "completion_tokens": 5,
                "total_tokens": 23,
                "estimated_cost": 0.0015,
                "pricing_status": "pricing_unconfigured",
                "avg_latency_ms": 0,
                **v06e_zero_metrics(
                    usage_available_count=2,
                    calls_with_usage_applicable=2,
                    usage_available_rate=1.0,
                ),
            },
        ],
    }
    assert "raw_response" not in response.text
    assert "input_summary" not in response.text
    assert "sensitive child text" not in response.text


def test_admin_ai_usage_aggregates_streaming_usage_and_material_reliability(
    session,
    monkeypatch,
):
    day = datetime(2026, 7, 3, 2, 0, tzinfo=timezone.utc)
    session.add(
        LLMCallLog(
            task_type=TaskType.essay,
            task_name="essay_feedback",
            prompt_key="essay_feedback",
            provider="test-provider",
            model="test-model",
            input_summary="private child draft",
            raw_response="private response",
            output_json={"feedback": "private"},
            validation_ok=True,
            final_status="primary_success",
            pricing_status="pricing_configured",
            prompt_tokens=20,
            completion_tokens=10,
            total_tokens=30,
            estimated_cost=0.002,
            latency_ms=400,
            streaming_enabled=True,
            stream_protocol="sse",
            stream_started_at=day,
            first_provider_delta_at=datetime(
                2026,
                7,
                3,
                2,
                0,
                0,
                100000,
                tzinfo=timezone.utc,
            ),
            first_visible_content_at=datetime(
                2026,
                7,
                3,
                2,
                0,
                0,
                250000,
                tzinfo=timezone.utc,
            ),
            provider_stream_completed_at=datetime(
                2026,
                7,
                3,
                2,
                0,
                1,
                tzinfo=timezone.utc,
            ),
            usage_available=True,
            usage_source="provider",
            stream_final_status="completed",
            created_at=day,
        )
    )
    session.add(
        LLMCallLog(
            task_type=TaskType.essay,
            task_name="essay_feedback",
            prompt_key="essay_feedback",
            provider="test-provider",
            model="test-model",
            input_summary="another private child draft",
            raw_response="another private response",
            output_json={"feedback": "private"},
            validation_ok=True,
            final_status="primary_success",
            pricing_status="pricing_configured",
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            estimated_cost=None,
            latency_ms=600,
            streaming_enabled=True,
            stream_protocol="sse",
            stream_started_at=datetime(2026, 7, 3, 2, 1, tzinfo=timezone.utc),
            first_provider_delta_at=datetime(
                2026,
                7,
                3,
                2,
                1,
                0,
                125000,
                tzinfo=timezone.utc,
            ),
            first_visible_content_at=datetime(
                2026,
                7,
                3,
                2,
                1,
                0,
                300000,
                tzinfo=timezone.utc,
            ),
            provider_stream_completed_at=datetime(
                2026,
                7,
                3,
                2,
                1,
                1,
                200000,
                tzinfo=timezone.utc,
            ),
            usage_available=False,
            usage_source="unavailable",
            stream_final_status="completed",
            created_at=datetime(2026, 7, 3, 2, 1, tzinfo=timezone.utc),
        )
    )
    session.add(
        LLMCallLog(
            task_type=TaskType.essay,
            task_name="material_card_generation",
            prompt_key="material_card_generation",
            provider="local_fallback",
            model="local_fallback",
            resolved_provider="local_fallback",
            resolved_model="local_fallback",
            input_summary="material inputs",
            output_json=material_card_output(),
            validation_ok=False,
            final_status="deterministic_fallback_used",
            pricing_status="pricing_configured",
            usage_available=False,
            stream_final_status="not_streaming",
            created_at=day,
        )
    )
    session.add(
        LLMCallLog(
            task_type=TaskType.essay,
            task_name="material_card_generation",
            prompt_key="material_card_generation",
            provider="local_fallback",
            model="local_fallback",
            resolved_provider="local_fallback",
            resolved_model="local_fallback",
            primary_provider="test-provider",
            primary_model="test-model",
            input_summary="material inputs",
            output_json=material_card_output(),
            validation_ok=False,
            final_status="deterministic_fallback_used",
            pricing_status="pricing_configured",
            attempt_count=1,
            attempt_summaries=[provider_attempt_summary()],
            usage_available=False,
            usage_source="unavailable",
            stream_final_status="not_streaming",
            created_at=datetime(2026, 7, 3, 2, 0, 30, tzinfo=timezone.utc),
        )
    )
    session.add(
        LLMCallLog(
            task_type=TaskType.essay,
            task_name="material_card_generation",
            prompt_key="material_card_generation",
            provider="test-provider",
            model="test-model",
            resolved_provider="test-provider",
            resolved_model="test-model",
            input_summary="material inputs",
            output_json=material_card_output(),
            validation_ok=True,
            final_status="primary_success",
            pricing_status="pricing_configured",
            prompt_tokens=12,
            completion_tokens=8,
            total_tokens=20,
            estimated_cost=0.001,
            latency_ms=300,
            usage_available=True,
            usage_source="provider",
            stream_final_status="not_streaming",
            created_at=datetime(2026, 7, 3, 2, 2, tzinfo=timezone.utc),
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
    rows = response.json()["usage"]
    row = next(item for item in rows if item["task_type"] == "essay_feedback")
    assert row["usage_available_rate"] == 0.5
    assert row["usage_missing_count"] == 1
    assert row["first_visible_content_p50_ms"] == 250
    assert row["stream_completed_count"] == 2
    assert row["calls_with_usage_applicable"] == 2
    assert row["prompt_tokens"] == 20
    assert row["completion_tokens"] == 10
    assert row["total_tokens"] == 30
    assert row["estimated_cost"] == 0.002
    assert (
        row["usage_available_rate"]
        == row["usage_available_count"] / row["calls_with_usage_applicable"]
    )

    material_rows = [
        item for item in rows if item["task_type"] == "material_card_generation"
    ]
    material_row = next(
        item
        for item in material_rows
        if item["provider"] == "test-provider" and item["model"] == "test-model"
    )
    assert material_row["call_count"] == 2
    assert material_row["deterministic_fallback_count"] == 1
    assert material_row["live_llm_success_count"] == 1
    assert material_row["calls_with_usage_applicable"] == 2
    assert material_row["usage_available_count"] == 1
    assert material_row["usage_missing_count"] == 1
    assert material_row["usage_available_rate"] == 0.5
    assert material_row["schema_validation_success_count"] == 2
    assert material_row["source_reference_success_count"] == 2

    local_material_row = next(
        item
        for item in material_rows
        if item["provider"] == "local_fallback" and item["model"] == "local_fallback"
    )
    assert local_material_row["call_count"] == 1
    assert local_material_row["deterministic_fallback_count"] == 1
    assert local_material_row["calls_with_usage_applicable"] == 0
    assert local_material_row["schema_validation_success_count"] == 1
    assert local_material_row["source_reference_success_count"] == 1


def test_admin_ai_usage_groups_failed_provider_attempts_with_blank_resolved_provider(
    session,
    monkeypatch,
):
    session.add(
        LLMCallLog(
            task_type=TaskType.essay,
            task_name="essay_feedback",
            prompt_key="essay_feedback",
            provider="",
            model="",
            resolved_provider="",
            resolved_model="",
            primary_provider="failed-provider",
            primary_model="failed-model",
            input_summary="private child draft",
            output_json={},
            validation_ok=False,
            final_status="failed",
            pricing_status="pricing_configured",
            attempt_count=1,
            attempt_summaries=[
                provider_attempt_summary(
                    provider="failed-provider",
                    model="failed-model",
                    status="api_error",
                )
            ],
            usage_available=False,
            usage_source="unavailable",
            created_at=datetime(2026, 7, 3, 3, 0, tzinfo=timezone.utc),
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
    row = response.json()["usage"][0]
    assert row["provider"] == "failed-provider"
    assert row["model"] == "failed-model"
    assert row["call_count"] == 1
    assert row["failure_count"] == 1
    assert row["calls_with_usage_applicable"] == 1
    assert row["usage_missing_count"] == 1


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
                **v06e_zero_metrics(),
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
            usage_available=True,
            usage_source="provider",
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
                **v06e_zero_metrics(
                    usage_available_count=1,
                    calls_with_usage_applicable=1,
                    usage_available_rate=1.0,
                ),
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
            usage_available=True,
            usage_source="provider",
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
