from dataclasses import dataclass
from typing import Literal

from app.core.config import Settings


class RoutingConfigError(ValueError):
    pass


class TaskFinalStatus:
    PRIMARY_SUCCESS = "primary_success"
    FALLBACK_SUCCESS = "fallback_success"
    DETERMINISTIC_FALLBACK_USED = "deterministic_fallback_used"
    DAILY_LIMIT_REACHED = "daily_limit_reached"
    FAILED = "failed"


class TaskFallbackReason:
    TIMEOUT = "timeout"
    API_ERROR = "api_error"
    RATE_LIMIT = "rate_limit"
    MALFORMED_JSON = "malformed_json"
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
    TASK_VALIDATION_FAILED = "task_validation_failed"
    PROVIDER_CONFIG_ERROR = "provider_config_error"
    PRICING_UNCONFIGURED = "pricing_unconfigured"
    UNKNOWN_ERROR = "unknown_error"


class PricingStatus:
    CONFIGURED = "configured"
    UNCONFIGURED = "pricing_unconfigured"
    UNAVAILABLE = "pricing_unavailable"


ProviderType = Literal["mock", "openai_compatible_http"]


@dataclass(frozen=True)
class ProviderProfile:
    profile_name: str
    provider_type: ProviderType
    base_url_env: str = ""
    api_key_env: str = ""
    timeout_seconds: int | None = None


@dataclass(frozen=True)
class LogicalModel:
    logical_model_key: str
    provider_profile: str
    model: str
    pricing_key: str
    cost_tier: str
    model_env: str = ""


@dataclass(frozen=True)
class TaskConfig:
    task_name: str
    primary_model: str
    fallback_model: str
    primary_timeout_seconds: int
    fallback_timeout_seconds: int
    max_total_latency_seconds: int
    daily_limit: int
    cost_tier: str
    allowed_prompt_keys: tuple[str, ...]
    default_prompt_key: str
    enabled: bool = True


@dataclass(frozen=True)
class ModelPricing:
    pricing_key: str
    provider_profile: str
    model: str
    input_cost_per_1k_tokens: float
    output_cost_per_1k_tokens: float
    effective_date: str
    cached_input_cost_per_1k_tokens: float | None = None
    reasoning_cost_per_1k_tokens: float | None = None
    thoughts_cost_per_1k_tokens: float | None = None
    delegates_to_provider_reported_cost: bool = False


@dataclass(frozen=True)
class ResolvedTaskRoute:
    task: TaskConfig
    primary_model: LogicalModel
    fallback_model: LogicalModel
    primary_profile: ProviderProfile
    fallback_profile: ProviderProfile
    primary_pricing: ModelPricing | None
    fallback_pricing: ModelPricing | None
    pricing_status: str
    prompt_key: str


PROVIDER_PROFILES: dict[str, ProviderProfile] = {
    "mock_primary": ProviderProfile("mock_primary", "mock"),
    "mock_fallback": ProviderProfile("mock_fallback", "mock"),
    "primary_http": ProviderProfile(
        "primary_http",
        "openai_compatible_http",
        base_url_env="llm_primary_http_base_url",
        api_key_env="llm_primary_http_api_key",
    ),
    "fallback_http": ProviderProfile(
        "fallback_http",
        "openai_compatible_http",
        base_url_env="llm_fallback_http_base_url",
        api_key_env="llm_fallback_http_api_key",
    ),
}


LOGICAL_MODELS: dict[str, LogicalModel] = {
    "cheap_fast": LogicalModel(
        "cheap_fast",
        "mock_primary",
        "cheap-fast",
        "mock:cheap-fast",
        "low",
        model_env="llm_primary_http_model",
    ),
    "strong_default": LogicalModel(
        "strong_default",
        "mock_fallback",
        "strong-default",
        "mock:strong-default",
        "high",
        model_env="llm_fallback_http_model",
    ),
}


COST_REGISTRY: dict[str, ModelPricing] = {
    "mock:cheap-fast": ModelPricing(
        "mock:cheap-fast",
        "mock_primary",
        "cheap-fast",
        0.0,
        0.0,
        "2026-06-17",
    ),
    "mock:strong-default": ModelPricing(
        "mock:strong-default",
        "mock_fallback",
        "strong-default",
        0.0,
        0.0,
        "2026-06-17",
    ),
    "primary_http:cheap-fast": ModelPricing(
        "primary_http:cheap-fast",
        "primary_http",
        "cheap-fast",
        0.0,
        0.0,
        "2026-06-17",
    ),
    "primary_http:strong-default": ModelPricing(
        "primary_http:strong-default",
        "primary_http",
        "strong-default",
        0.0,
        0.0,
        "2026-06-17",
    ),
    "fallback_http:strong-default": ModelPricing(
        "fallback_http:strong-default",
        "fallback_http",
        "strong-default",
        0.0,
        0.0,
        "2026-06-17",
    ),
}


TASK_CONFIGS: dict[str, TaskConfig] = {
    "sentence_upgrade_feedback": TaskConfig(
        task_name="sentence_upgrade_feedback",
        primary_model="cheap_fast",
        fallback_model="strong_default",
        primary_timeout_seconds=10,
        fallback_timeout_seconds=8,
        max_total_latency_seconds=18,
        daily_limit=5,
        cost_tier="low",
        allowed_prompt_keys=("sentence_upgrade_feedback",),
        default_prompt_key="sentence_upgrade_feedback",
    ),
    "sentence_challenge_generation": TaskConfig(
        task_name="sentence_challenge_generation",
        primary_model="cheap_fast",
        fallback_model="strong_default",
        primary_timeout_seconds=8,
        fallback_timeout_seconds=7,
        max_total_latency_seconds=15,
        daily_limit=10,
        cost_tier="low",
        allowed_prompt_keys=("sentence_challenge_generation",),
        default_prompt_key="sentence_challenge_generation",
    ),
    "sentence_challenge_feedback": TaskConfig(
        task_name="sentence_challenge_feedback",
        primary_model="cheap_fast",
        fallback_model="strong_default",
        primary_timeout_seconds=10,
        fallback_timeout_seconds=8,
        max_total_latency_seconds=18,
        daily_limit=10,
        cost_tier="low",
        allowed_prompt_keys=("sentence_challenge_feedback",),
        default_prompt_key="sentence_challenge_feedback",
    ),
    "essay_feedback": TaskConfig(
        task_name="essay_feedback",
        primary_model="strong_default",
        fallback_model="strong_default",
        primary_timeout_seconds=25,
        fallback_timeout_seconds=20,
        max_total_latency_seconds=45,
        daily_limit=5,
        cost_tier="high",
        allowed_prompt_keys=("essay_feedback",),
        default_prompt_key="essay_feedback",
    ),
    "essay_revision_comparison": TaskConfig(
        task_name="essay_revision_comparison",
        primary_model="strong_default",
        fallback_model="strong_default",
        primary_timeout_seconds=25,
        fallback_timeout_seconds=20,
        max_total_latency_seconds=45,
        daily_limit=5,
        cost_tier="high",
        allowed_prompt_keys=("essay_revision_comparison",),
        default_prompt_key="essay_revision_comparison",
    ),
    "writing_topic_analysis": TaskConfig(
        task_name="writing_topic_analysis",
        primary_model="cheap_fast",
        fallback_model="strong_default",
        primary_timeout_seconds=10,
        fallback_timeout_seconds=8,
        max_total_latency_seconds=18,
        daily_limit=5,
        cost_tier="low",
        allowed_prompt_keys=("writing_topic_analysis",),
        default_prompt_key="writing_topic_analysis",
    ),
    "material_questions": TaskConfig(
        task_name="material_questions",
        primary_model="cheap_fast",
        fallback_model="strong_default",
        primary_timeout_seconds=10,
        fallback_timeout_seconds=8,
        max_total_latency_seconds=18,
        daily_limit=5,
        cost_tier="low",
        allowed_prompt_keys=("material_questions",),
        default_prompt_key="material_questions",
    ),
    "material_card_generation": TaskConfig(
        task_name="material_card_generation",
        primary_model="cheap_fast",
        fallback_model="strong_default",
        primary_timeout_seconds=12,
        fallback_timeout_seconds=10,
        max_total_latency_seconds=22,
        daily_limit=5,
        cost_tier="low",
        allowed_prompt_keys=("material_card_generation",),
        default_prompt_key="material_card_generation",
    ),
    "outline_generation": TaskConfig(
        task_name="outline_generation",
        primary_model="cheap_fast",
        fallback_model="strong_default",
        primary_timeout_seconds=25,
        fallback_timeout_seconds=20,
        max_total_latency_seconds=45,
        daily_limit=5,
        cost_tier="low",
        allowed_prompt_keys=("outline_generation",),
        default_prompt_key="outline_generation",
    ),
    "writing_topic_idea_generation": TaskConfig(
        task_name="writing_topic_idea_generation",
        primary_model="cheap_fast",
        fallback_model="strong_default",
        primary_timeout_seconds=8,
        fallback_timeout_seconds=7,
        max_total_latency_seconds=15,
        daily_limit=5,
        cost_tier="low",
        allowed_prompt_keys=("writing_topic_idea_generation",),
        default_prompt_key="writing_topic_idea_generation",
    ),
}


def configured_task_names() -> set[str]:
    return set(TASK_CONFIGS)


def _provider_mode(settings: Settings) -> str:
    return settings.llm_provider.strip().lower()


def resolve_task_config(task_name: str) -> TaskConfig:
    config = TASK_CONFIGS.get(task_name)
    if config is None:
        raise RoutingConfigError(f"Unknown AI task: {task_name}")
    if not config.enabled:
        raise RoutingConfigError(f"AI task is disabled: {task_name}")
    return config


def _model_with_override(
    settings: Settings,
    logical_model: LogicalModel,
    provider_profile: str,
    model_env: str,
) -> LogicalModel:
    if _provider_mode(settings) != "http":
        return logical_model
    override = getattr(settings, model_env, "").strip()
    model = override or logical_model.model
    pricing_key = f"{provider_profile}:{model}"
    return LogicalModel(
        logical_model.logical_model_key,
        provider_profile,
        model,
        pricing_key,
        logical_model.cost_tier,
        model_env,
    )


def _primary_model(settings: Settings, logical_model: LogicalModel) -> LogicalModel:
    return _model_with_override(
        settings,
        logical_model,
        provider_profile="primary_http",
        model_env="llm_primary_http_model",
    )


def _fallback_model(settings: Settings, logical_model: LogicalModel) -> LogicalModel:
    return _model_with_override(
        settings,
        logical_model,
        provider_profile="fallback_http",
        model_env="llm_fallback_http_model",
    )


def _environment(settings: Settings) -> str:
    return settings.environment.strip().lower()


def _pricing_has_billable_rates(pricing: ModelPricing) -> bool:
    return pricing.input_cost_per_1k_tokens > 0 and pricing.output_cost_per_1k_tokens > 0


def _registry_pricing_is_configured_for_mode(
    settings: Settings,
    pricing: ModelPricing,
) -> bool:
    if _provider_mode(settings) != "http":
        return True
    if pricing.delegates_to_provider_reported_cost:
        return True
    return _pricing_has_billable_rates(pricing)


def _pricing_for(
    settings: Settings,
    logical_model: LogicalModel,
) -> tuple[ModelPricing | None, str]:
    pricing = COST_REGISTRY.get(logical_model.pricing_key)
    if pricing is not None and _registry_pricing_is_configured_for_mode(settings, pricing):
        return pricing, PricingStatus.CONFIGURED
    profile_rates = {
        "primary_http": (
            settings.llm_primary_input_cost_per_1k_tokens,
            settings.llm_primary_output_cost_per_1k_tokens,
        ),
        "fallback_http": (
            settings.llm_fallback_input_cost_per_1k_tokens,
            settings.llm_fallback_output_cost_per_1k_tokens,
        ),
    }
    input_cost, output_cost = profile_rates.get(logical_model.provider_profile, (0.0, 0.0))
    if _provider_mode(settings) == "http" and input_cost > 0 and output_cost > 0:
        return (
            ModelPricing(
                logical_model.pricing_key,
                logical_model.provider_profile,
                logical_model.model,
                input_cost,
                output_cost,
                "env",
            ),
            PricingStatus.CONFIGURED,
        )
    if (
        _provider_mode(settings) == "http"
        and _environment(settings) == "development"
        and settings.llm_input_cost_per_1k_tokens > 0
        and settings.llm_output_cost_per_1k_tokens > 0
    ):
        return (
            ModelPricing(
                logical_model.pricing_key,
                logical_model.provider_profile,
                logical_model.model,
                settings.llm_input_cost_per_1k_tokens,
                settings.llm_output_cost_per_1k_tokens,
                "env",
            ),
            PricingStatus.CONFIGURED,
        )
    if _environment(settings) in {"staging", "production"}:
        raise RoutingConfigError(
            f"Missing pricing for routed model: {logical_model.pricing_key}"
        )
    return None, PricingStatus.UNCONFIGURED


def resolve_task_route(
    settings: Settings,
    task_name: str,
    prompt_key: str | None = None,
) -> ResolvedTaskRoute:
    task = resolve_task_config(task_name)
    selected_prompt_key = prompt_key or task.default_prompt_key
    if selected_prompt_key not in task.allowed_prompt_keys:
        raise RoutingConfigError(
            f"Prompt key {selected_prompt_key} is not allowed for task {task_name}"
        )
    primary_model = _primary_model(settings, LOGICAL_MODELS[task.primary_model])
    fallback_model = _fallback_model(settings, LOGICAL_MODELS[task.fallback_model])
    primary_profile = PROVIDER_PROFILES[primary_model.provider_profile]
    fallback_profile = PROVIDER_PROFILES[fallback_model.provider_profile]
    primary_pricing, primary_status = _pricing_for(settings, primary_model)
    fallback_pricing, fallback_status = _pricing_for(settings, fallback_model)
    pricing_status = (
        PricingStatus.CONFIGURED
        if primary_status == fallback_status == PricingStatus.CONFIGURED
        else PricingStatus.UNCONFIGURED
    )
    return ResolvedTaskRoute(
        task=task,
        primary_model=primary_model,
        fallback_model=fallback_model,
        primary_profile=primary_profile,
        fallback_profile=fallback_profile,
        primary_pricing=primary_pricing,
        fallback_pricing=fallback_pricing,
        pricing_status=pricing_status,
        prompt_key=selected_prompt_key,
    )


def validate_ai_routing_startup(settings: Settings) -> None:
    for task in TASK_CONFIGS.values():
        if not task.enabled:
            continue
        resolve_task_route(settings, task.task_name, task.default_prompt_key)

    if (
        _environment(settings) in {"staging", "production"}
        and _provider_mode(settings) == "http"
    ):
        for profile in PROVIDER_PROFILES.values():
            if profile.provider_type == "openai_compatible_http":
                base_url = getattr(settings, profile.base_url_env).strip()
                api_key = getattr(settings, profile.api_key_env).strip()
                if not base_url or not api_key:
                    raise RoutingConfigError(
                        f"Missing provider credentials for {profile.profile_name}"
                    )
