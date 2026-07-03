from dataclasses import dataclass
from typing import Any

from app.services.ai_routing import ModelPricing


COST_CALCULATION_VERSION = "v0.6e.1"
COST_SOURCE_PRICING = "provider_usage_x_pricing_snapshot"
COST_SOURCE_PROVIDER_REPORTED = "provider_reported_cost"
COST_SOURCE_UNAVAILABLE = "unavailable"
ERROR_PRICING_UNCONFIGURED = "PRICING_UNCONFIGURED"
ERROR_UNSUPPORTED_USAGE_CLASS = "UNSUPPORTED_USAGE_CLASS"
ERROR_PROVIDER_REPORTED_COST_MISSING = "PROVIDER_REPORTED_COST_MISSING"
NON_BILLABLE_TOKEN_METADATA_KEYS = {
    "cached_input_tokens_included_in_prompt_tokens",
}
INPUT_TOKEN_USAGE_KEYS = {"prompt_tokens", "total_tokens"}
OUTPUT_TOKEN_USAGE_KEYS = {"completion_tokens"}


@dataclass(frozen=True)
class NormalizedUsage:
    usage_available: bool
    usage_source: str
    usage_is_estimated: bool
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    usage_details_json: dict[str, Any]


@dataclass(frozen=True)
class UsageCostRecord:
    provider: str
    model: str
    role: str
    usage_available: bool
    usage_source: str
    usage_is_estimated: bool
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    usage_details_json: dict[str, Any]
    estimated_cost_usd: float | None
    cost_source: str
    cost_error_code: str
    pricing_snapshot_id: str | None
    pricing_snapshot_version: str
    provider_reported_cost_usd: float | None
    cost_calculation_version: str = COST_CALCULATION_VERSION


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_or_false(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def normalize_usage(
    *,
    provider_usage: dict[str, Any] | None,
    usage_source: str,
    tokenizer_estimate: dict[str, Any] | None,
) -> NormalizedUsage:
    details: dict[str, Any] = {
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
    }
    if provider_usage and usage_source != "tokenizer_estimate":
        prompt_tokens = _int_or_none(provider_usage.get("prompt_tokens"))
        completion_tokens = _int_or_none(provider_usage.get("completion_tokens"))
        total_tokens = _int_or_none(provider_usage.get("total_tokens"))
        raw_usage = provider_usage.get("provider_raw_usage")
        if not isinstance(raw_usage, dict):
            raw_usage = dict(provider_usage)
        if prompt_tokens is None or completion_tokens is None:
            details.update(
                {
                    "provider_raw_usage": dict(raw_usage),
                    "usage_unavailable_reason": "provider_usage_incomplete",
                }
            )
            return NormalizedUsage(
                usage_available=False,
                usage_source=usage_source,
                usage_is_estimated=False,
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
                usage_details_json=details,
            )
        if total_tokens is None or (
            total_tokens <= 0 and prompt_tokens + completion_tokens > 0
        ):
            total_tokens = prompt_tokens + completion_tokens

        details.update(
            {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "provider_raw_usage": dict(raw_usage),
            }
        )
        for usage in (raw_usage, provider_usage):
            for usage_key, usage_value in usage.items():
                if usage_key == "provider_raw_usage":
                    continue
                if (
                    usage_key == "cached_input_tokens_included_in_prompt_tokens"
                    or usage_key.endswith("_tokens")
                ):
                    details.setdefault(usage_key, usage_value)
        return NormalizedUsage(
            usage_available=True,
            usage_source=usage_source,
            usage_is_estimated=False,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            usage_details_json=details,
        )

    if tokenizer_estimate:
        details.update(
            {
                "estimated_prompt_tokens": _int_or_none(
                    tokenizer_estimate.get("prompt_tokens")
                ),
                "estimated_completion_tokens": _int_or_none(
                    tokenizer_estimate.get("completion_tokens")
                ),
                "estimated_total_tokens": _int_or_none(
                    tokenizer_estimate.get("total_tokens")
                ),
                "usage_unavailable_reason": "tokenizer_estimate_not_authoritative",
            }
        )
        return NormalizedUsage(
            usage_available=False,
            usage_source="tokenizer_estimate",
            usage_is_estimated=True,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            usage_details_json=details,
        )

    details["usage_unavailable_reason"] = "provider_usage_missing"
    return NormalizedUsage(
        usage_available=False,
        usage_source=usage_source or "unavailable",
        usage_is_estimated=False,
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        usage_details_json=details,
    )


def _unsupported_usage_class(
    usage_details_json: dict[str, Any],
    pricing: ModelPricing,
) -> bool:
    return _has_unsupported_token_usage(usage_details_json, pricing)


def _token_usage_class_is_unsupported(
    usage_key: str,
    usage_value: Any,
    pricing: ModelPricing,
) -> bool:
    token_count = _int_or_none(usage_value) or 0
    if token_count <= 0:
        return False
    if usage_key in INPUT_TOKEN_USAGE_KEYS | OUTPUT_TOKEN_USAGE_KEYS:
        return False
    if usage_key in NON_BILLABLE_TOKEN_METADATA_KEYS:
        return False
    if usage_key in {"cached_input_tokens", "cached_tokens"}:
        return pricing.cached_input_cost_per_1k_tokens is None
    if usage_key == "reasoning_tokens":
        return pricing.reasoning_cost_per_1k_tokens is None
    if usage_key == "thoughts_tokens":
        return pricing.thoughts_cost_per_1k_tokens is None
    return usage_key.endswith("_tokens")


def _has_unsupported_token_usage(
    usage_value: Any,
    pricing: ModelPricing,
) -> bool:
    if isinstance(usage_value, dict):
        for usage_key, nested_value in usage_value.items():
            if _token_usage_class_is_unsupported(usage_key, nested_value, pricing):
                return True
            if _has_unsupported_token_usage(nested_value, pricing):
                return True
    elif isinstance(usage_value, list):
        for nested_value in usage_value:
            if _has_unsupported_token_usage(nested_value, pricing):
                return True
    return False


def _billable_prompt_tokens(
    *,
    prompt_tokens: int,
    cached_input_tokens: int,
    cached_input_included: bool,
) -> int:
    if cached_input_tokens <= 0 or not cached_input_included:
        return prompt_tokens
    return max(prompt_tokens - cached_input_tokens, 0)


def calculate_cost(
    *,
    usage: NormalizedUsage,
    pricing: ModelPricing | None,
    provider_reported_cost_usd: float | None,
) -> tuple[float | None, str, str]:
    if pricing is None:
        return None, COST_SOURCE_UNAVAILABLE, ERROR_PRICING_UNCONFIGURED

    provider_reported_cost = _float_or_none(provider_reported_cost_usd)
    if pricing.delegates_to_provider_reported_cost and provider_reported_cost is None:
        return None, COST_SOURCE_UNAVAILABLE, ERROR_PROVIDER_REPORTED_COST_MISSING
    if pricing.delegates_to_provider_reported_cost and provider_reported_cost is not None:
        return provider_reported_cost, COST_SOURCE_PROVIDER_REPORTED, ""

    if not usage.usage_available:
        return None, COST_SOURCE_UNAVAILABLE, ""

    if pricing.input_cost_per_1k_tokens <= 0 or pricing.output_cost_per_1k_tokens <= 0:
        return None, COST_SOURCE_UNAVAILABLE, ERROR_PRICING_UNCONFIGURED

    if _unsupported_usage_class(usage.usage_details_json, pricing):
        return None, COST_SOURCE_UNAVAILABLE, ERROR_UNSUPPORTED_USAGE_CLASS

    prompt_tokens = usage.prompt_tokens or 0
    completion_tokens = usage.completion_tokens or 0
    cached_input_tokens = _int_or_none(
        usage.usage_details_json.get("cached_input_tokens")
    ) or 0
    reasoning_tokens = _int_or_none(usage.usage_details_json.get("reasoning_tokens")) or 0
    thoughts_tokens = _int_or_none(usage.usage_details_json.get("thoughts_tokens")) or 0
    cached_input_included = True
    if "cached_input_tokens_included_in_prompt_tokens" in usage.usage_details_json:
        cached_input_included = _bool_or_false(
            usage.usage_details_json.get("cached_input_tokens_included_in_prompt_tokens")
        )

    cost = (
        _billable_prompt_tokens(
            prompt_tokens=prompt_tokens,
            cached_input_tokens=cached_input_tokens,
            cached_input_included=cached_input_included,
        )
        / 1000
        * pricing.input_cost_per_1k_tokens
    )
    cost += completion_tokens / 1000 * pricing.output_cost_per_1k_tokens
    if cached_input_tokens:
        cost += cached_input_tokens / 1000 * (
            pricing.cached_input_cost_per_1k_tokens or 0.0
        )
    if reasoning_tokens:
        cost += reasoning_tokens / 1000 * (pricing.reasoning_cost_per_1k_tokens or 0.0)
    if thoughts_tokens:
        cost += thoughts_tokens / 1000 * (pricing.thoughts_cost_per_1k_tokens or 0.0)
    return cost, COST_SOURCE_PRICING, ""


def normalize_usage_and_cost(
    *,
    provider: str,
    model: str,
    role: str,
    provider_usage: dict[str, Any] | None,
    usage_source: str,
    tokenizer_estimate: dict[str, Any] | None,
    provider_reported_cost_usd: float | None,
    pricing: ModelPricing | None,
) -> UsageCostRecord:
    normalized_usage = normalize_usage(
        provider_usage=provider_usage,
        usage_source=usage_source,
        tokenizer_estimate=tokenizer_estimate,
    )
    estimated_cost, cost_source, cost_error_code = calculate_cost(
        usage=normalized_usage,
        pricing=pricing,
        provider_reported_cost_usd=provider_reported_cost_usd,
    )
    uses_pricing_snapshot = cost_source in {
        COST_SOURCE_PRICING,
        COST_SOURCE_PROVIDER_REPORTED,
    }
    return UsageCostRecord(
        provider=provider,
        model=model,
        role=role,
        usage_available=normalized_usage.usage_available,
        usage_source=normalized_usage.usage_source,
        usage_is_estimated=normalized_usage.usage_is_estimated,
        prompt_tokens=normalized_usage.prompt_tokens,
        completion_tokens=normalized_usage.completion_tokens,
        total_tokens=normalized_usage.total_tokens,
        usage_details_json=normalized_usage.usage_details_json,
        estimated_cost_usd=estimated_cost,
        cost_source=cost_source,
        cost_error_code=cost_error_code,
        pricing_snapshot_id=(
            pricing.pricing_key
            if pricing is not None and uses_pricing_snapshot
            else None
        ),
        pricing_snapshot_version=(
            pricing.effective_date
            if pricing is not None and uses_pricing_snapshot
            else ""
        ),
        provider_reported_cost_usd=_float_or_none(provider_reported_cost_usd),
    )
