import pytest

from app.core.config import Settings
from app.services.ai_routing import (
    COST_REGISTRY,
    TASK_CONFIGS,
    PricingStatus,
    RoutingConfigError,
    TaskFinalStatus,
    TaskFallbackReason,
    configured_task_names,
    resolve_task_config,
    resolve_task_route,
    validate_ai_routing_startup,
)


def test_all_existing_ai_tasks_have_enabled_configs():
    assert configured_task_names() >= {
        "sentence_upgrade_feedback",
        "sentence_challenge_generation",
        "sentence_challenge_feedback",
        "essay_feedback",
        "essay_revision_comparison",
    }
    for task_name in {
        "sentence_upgrade_feedback",
        "sentence_challenge_generation",
        "sentence_challenge_feedback",
        "essay_feedback",
        "essay_revision_comparison",
    }:
        assert TASK_CONFIGS[task_name].enabled is True


def test_v06a_writing_castle_tasks_are_enabled_with_prompt_keys():
    for task_name in {
        "writing_topic_analysis",
        "material_questions",
        "material_card_generation",
        "outline_generation",
    }:
        config = resolve_task_config(task_name)
        assert config.enabled is True
        assert config.allowed_prompt_keys == (task_name,)
        assert config.default_prompt_key == task_name
        assert config.daily_limit == 5


def test_writing_topic_idea_generation_uses_low_cost_short_route():
    config = resolve_task_config("writing_topic_idea_generation")

    assert config.enabled is True
    assert config.primary_model == "cheap_fast"
    assert config.fallback_model == "strong_default"
    assert config.primary_timeout_seconds == 8
    assert config.fallback_timeout_seconds == 7
    assert config.max_total_latency_seconds == 15
    assert config.daily_limit == 5
    assert config.cost_tier == "low"
    assert config.allowed_prompt_keys == ("writing_topic_idea_generation",)


def test_outline_generation_uses_extended_timeout_budget():
    config = resolve_task_config("outline_generation")

    assert config.primary_timeout_seconds == 25
    assert config.fallback_timeout_seconds == 20
    assert config.max_total_latency_seconds == 45


def test_material_card_generation_stays_within_request_timeout_budget():
    config = resolve_task_config("material_card_generation")

    assert config.primary_timeout_seconds == 12
    assert config.fallback_timeout_seconds == 10
    assert config.max_total_latency_seconds == 22
    assert config.primary_timeout_seconds + config.fallback_timeout_seconds <= 25


def test_unknown_task_fails_closed():
    with pytest.raises(RoutingConfigError, match="Unknown AI task"):
        resolve_task_config("unknown_task")


def test_prompt_key_must_be_allowed_for_task():
    with pytest.raises(RoutingConfigError, match="not allowed"):
        resolve_task_route(
            settings=Settings(llm_provider="mock"),
            task_name="sentence_challenge_generation",
            prompt_key="essay_feedback",
        )


def test_task_resolves_through_logical_models_profiles_and_pricing():
    route = resolve_task_route(
        settings=Settings(llm_provider="mock"),
        task_name="sentence_challenge_generation",
        prompt_key="sentence_challenge_generation",
    )

    assert route.task.task_name == "sentence_challenge_generation"
    assert route.primary_model.logical_model_key == "cheap_fast"
    assert route.fallback_model.logical_model_key == "strong_default"
    assert route.primary_profile.profile_name == route.primary_model.provider_profile
    assert route.primary_pricing.pricing_key == route.primary_model.pricing_key
    assert route.task.primary_timeout_seconds > 0
    assert route.task.fallback_timeout_seconds > 0
    assert route.task.max_total_latency_seconds >= route.task.primary_timeout_seconds


def test_mock_route_ignores_http_model_overrides_for_pricing():
    route = resolve_task_route(
        settings=Settings(
            llm_provider="mock",
            llm_primary_http_model="cheap-prod-model",
            llm_fallback_http_model="strong-prod-model",
        ),
        task_name="sentence_challenge_generation",
        prompt_key="sentence_challenge_generation",
    )

    assert route.primary_model.provider_profile == "mock_primary"
    assert route.primary_model.model == "cheap-fast"
    assert route.primary_model.pricing_key == "mock:cheap-fast"
    assert route.primary_pricing.pricing_key == "mock:cheap-fast"
    assert route.fallback_model.provider_profile == "mock_fallback"
    assert route.fallback_model.model == "strong-default"
    assert route.fallback_model.pricing_key == "mock:strong-default"
    assert route.fallback_pricing.pricing_key == "mock:strong-default"
    assert route.pricing_status == PricingStatus.CONFIGURED


def test_http_route_uses_http_profiles_and_model_overrides():
    route = resolve_task_route(
        settings=Settings(
            llm_provider="http",
            llm_primary_http_model="cheap-prod-model",
            llm_fallback_http_model="strong-prod-model",
        ),
        task_name="sentence_challenge_generation",
        prompt_key="sentence_challenge_generation",
    )

    assert route.primary_profile.profile_name == "primary_http"
    assert route.fallback_profile.profile_name == "fallback_http"
    assert route.primary_model.provider_profile == "primary_http"
    assert route.fallback_model.provider_profile == "fallback_http"
    assert route.primary_model.model == "cheap-prod-model"
    assert route.fallback_model.model == "strong-prod-model"
    assert route.primary_model.pricing_key == "primary_http:cheap-prod-model"
    assert route.fallback_model.pricing_key == "fallback_http:strong-prod-model"
    assert route.primary_pricing is None
    assert route.fallback_pricing is None
    assert route.pricing_status == PricingStatus.UNCONFIGURED


def test_http_route_uses_env_cost_rates_for_overridden_models():
    route = resolve_task_route(
        settings=Settings(
            llm_provider="http",
            llm_primary_http_model="deepseek-v4-flash",
            llm_fallback_http_model="deepseek-v4-flash",
            llm_input_cost_per_1k_tokens=0.00014,
            llm_output_cost_per_1k_tokens=0.00028,
        ),
        task_name="outline_generation",
        prompt_key="outline_generation",
    )

    assert route.primary_pricing is not None
    assert route.fallback_pricing is not None
    assert route.primary_pricing.pricing_key == "primary_http:deepseek-v4-flash"
    assert route.fallback_pricing.pricing_key == "fallback_http:deepseek-v4-flash"
    assert route.primary_pricing.input_cost_per_1k_tokens == 0.00014
    assert route.primary_pricing.output_cost_per_1k_tokens == 0.00028
    assert route.pricing_status == PricingStatus.CONFIGURED


def test_http_route_uses_profile_specific_env_cost_rates_for_overridden_models():
    route = resolve_task_route(
        settings=Settings(
            llm_provider="http",
            llm_primary_http_model="primary-prod-model",
            llm_fallback_http_model="fallback-prod-model",
            llm_primary_input_cost_per_1k_tokens=0.00014,
            llm_primary_output_cost_per_1k_tokens=0.00028,
            llm_fallback_input_cost_per_1k_tokens=0.001,
            llm_fallback_output_cost_per_1k_tokens=0.002,
        ),
        task_name="outline_generation",
        prompt_key="outline_generation",
    )

    assert route.primary_pricing is not None
    assert route.fallback_pricing is not None
    assert route.primary_pricing.pricing_key == "primary_http:primary-prod-model"
    assert route.fallback_pricing.pricing_key == "fallback_http:fallback-prod-model"
    assert route.primary_pricing.input_cost_per_1k_tokens == 0.00014
    assert route.primary_pricing.output_cost_per_1k_tokens == 0.00028
    assert route.fallback_pricing.input_cost_per_1k_tokens == 0.001
    assert route.fallback_pricing.output_cost_per_1k_tokens == 0.002
    assert route.pricing_status == PricingStatus.CONFIGURED


def test_production_http_override_requires_profile_specific_or_registry_pricing():
    with pytest.raises(RoutingConfigError, match="pricing"):
        validate_ai_routing_startup(
            Settings(
                environment="production",
                llm_provider="http",
                llm_primary_http_base_url="https://primary.example/v1",
                llm_primary_http_api_key="primary-key",
                llm_primary_http_model="primary-prod-model",
                llm_fallback_http_base_url="https://fallback.example/v1",
                llm_fallback_http_api_key="fallback-key",
                llm_fallback_http_model="fallback-prod-model",
                llm_input_cost_per_1k_tokens=0.00014,
                llm_output_cost_per_1k_tokens=0.00028,
            )
        )


def test_production_http_override_accepts_profile_specific_env_pricing():
    validate_ai_routing_startup(
        Settings(
            environment="production",
            llm_provider="http",
            llm_primary_http_base_url="https://primary.example/v1",
            llm_primary_http_api_key="primary-key",
            llm_primary_http_model="primary-prod-model",
            llm_fallback_http_base_url="https://fallback.example/v1",
            llm_fallback_http_api_key="fallback-key",
            llm_fallback_http_model="fallback-prod-model",
            llm_primary_input_cost_per_1k_tokens=0.00014,
            llm_primary_output_cost_per_1k_tokens=0.00028,
            llm_fallback_input_cost_per_1k_tokens=0.001,
            llm_fallback_output_cost_per_1k_tokens=0.002,
        )
    )


def test_staging_missing_pricing_fails_fast(monkeypatch):
    monkeypatch.delitem(COST_REGISTRY, "mock:cheap-fast", raising=False)

    with pytest.raises(RoutingConfigError, match="pricing"):
        validate_ai_routing_startup(Settings(environment="staging", llm_provider="mock"))


def test_staging_missing_pricing_normalizes_environment(monkeypatch):
    monkeypatch.delitem(COST_REGISTRY, "mock:cheap-fast", raising=False)

    with pytest.raises(RoutingConfigError, match="pricing"):
        validate_ai_routing_startup(Settings(environment=" STAGING ", llm_provider="mock"))


def test_development_missing_pricing_is_allowed(monkeypatch):
    monkeypatch.delitem(COST_REGISTRY, "mock:cheap-fast", raising=False)

    validate_ai_routing_startup(Settings(environment="development", llm_provider="mock"))


def test_production_requires_http_profile_credentials():
    with pytest.raises(RoutingConfigError, match="provider credentials"):
        validate_ai_routing_startup(Settings(environment="production", llm_provider="http"))


def test_production_mock_provider_does_not_require_http_profile_credentials():
    validate_ai_routing_startup(Settings(environment="production", llm_provider="mock"))


def test_production_accepts_configured_http_profiles():
    validate_ai_routing_startup(
        Settings(
            environment=" Production ",
            llm_provider="http",
            llm_primary_http_base_url="https://primary.example/v1",
            llm_primary_http_api_key="primary-key",
            llm_fallback_http_base_url="https://fallback.example/v1",
            llm_fallback_http_api_key="fallback-key",
        )
    )


def test_status_and_reason_enums_are_fixed():
    assert TaskFinalStatus.PRIMARY_SUCCESS == "primary_success"
    assert TaskFinalStatus.FALLBACK_SUCCESS == "fallback_success"
    assert TaskFinalStatus.DETERMINISTIC_FALLBACK_USED == "deterministic_fallback_used"
    assert TaskFinalStatus.DAILY_LIMIT_REACHED == "daily_limit_reached"
    assert TaskFinalStatus.FAILED == "failed"
    assert TaskFallbackReason.SCHEMA_VALIDATION_FAILED == "schema_validation_failed"
    assert TaskFallbackReason.PRICING_UNCONFIGURED == "pricing_unconfigured"
    assert PricingStatus.CONFIGURED == "configured"
    assert PricingStatus.UNCONFIGURED == "pricing_unconfigured"
