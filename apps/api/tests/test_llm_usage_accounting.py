import pytest

from app.services.ai_routing import ModelPricing
from app.services.llm_usage_accounting import normalize_usage_and_cost


def model_pricing(**overrides):
    values = {
        "pricing_key": "registry:http:gpt-test:primary",
        "provider_profile": "primary_http",
        "model": "gpt-test",
        "input_cost_per_1k_tokens": 0.01,
        "output_cost_per_1k_tokens": 0.02,
        "effective_date": "2026-07-03",
        "cached_input_cost_per_1k_tokens": None,
        "reasoning_cost_per_1k_tokens": None,
        "thoughts_cost_per_1k_tokens": None,
        "delegates_to_provider_reported_cost": False,
    }
    values.update(overrides)
    return ModelPricing(**values)


def test_authoritative_provider_usage_sets_usage_available_true():
    record = normalize_usage_and_cost(
        provider="http",
        model="gpt-test",
        role="primary",
        provider_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        usage_source="provider_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=model_pricing(),
    )

    assert record.usage_available is True
    assert record.usage_source == "provider_final_chunk"
    assert record.usage_is_estimated is False
    assert record.prompt_tokens == 100
    assert record.completion_tokens == 50
    assert record.total_tokens == 150
    assert record.estimated_cost_usd == 0.002
    assert record.cost_source == "provider_usage_x_pricing_snapshot"
    assert record.pricing_snapshot_id == "registry:http:gpt-test:primary"
    assert record.pricing_snapshot_version == "2026-07-03"
    assert record.usage_details_json["provider_raw_usage"] == {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
    }
    assert "raw_usage" not in record.usage_details_json


def test_tokenizer_estimate_does_not_become_authoritative_usage():
    record = normalize_usage_and_cost(
        provider="http",
        model="gpt-test",
        role="primary",
        provider_usage=None,
        usage_source="tokenizer_estimate",
        tokenizer_estimate={"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100},
        provider_reported_cost_usd=None,
        pricing=model_pricing(),
    )

    assert record.usage_available is False
    assert record.usage_source == "tokenizer_estimate"
    assert record.usage_is_estimated is True
    assert record.prompt_tokens is None
    assert record.completion_tokens is None
    assert record.total_tokens is None
    assert record.estimated_cost_usd is None
    assert record.usage_details_json["prompt_tokens"] is None
    assert record.usage_details_json["estimated_prompt_tokens"] == 80


def test_missing_usage_records_unknown_not_zero():
    record = normalize_usage_and_cost(
        provider="http",
        model="gpt-test",
        role="primary",
        provider_usage=None,
        usage_source="unavailable",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=model_pricing(),
    )

    assert record.usage_available is False
    assert record.usage_details_json["prompt_tokens"] is None
    assert record.usage_details_json["usage_unavailable_reason"] == "provider_usage_missing"
    assert record.estimated_cost_usd is None
    assert record.cost_source == "unavailable"


def test_provider_usage_with_only_prompt_tokens_is_incomplete_not_authoritative():
    record = normalize_usage_and_cost(
        provider="http",
        model="gpt-test",
        role="primary",
        provider_usage={"prompt_tokens": 11},
        usage_source="provider_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=model_pricing(),
    )

    assert record.usage_available is False
    assert record.usage_details_json["usage_unavailable_reason"] == "provider_usage_incomplete"
    assert record.usage_details_json["provider_raw_usage"] == {"prompt_tokens": 11}
    assert record.prompt_tokens is None
    assert record.completion_tokens is None
    assert record.total_tokens is None
    assert record.estimated_cost_usd is None
    assert record.cost_source == "unavailable"


def test_provider_usage_with_only_completion_tokens_is_incomplete_not_authoritative():
    record = normalize_usage_and_cost(
        provider="http",
        model="gpt-test",
        role="primary",
        provider_usage={"completion_tokens": 7},
        usage_source="provider_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=model_pricing(),
    )

    assert record.usage_available is False
    assert record.usage_details_json["usage_unavailable_reason"] == "provider_usage_incomplete"
    assert record.usage_details_json["provider_raw_usage"] == {"completion_tokens": 7}
    assert record.prompt_tokens is None
    assert record.completion_tokens is None
    assert record.total_tokens is None
    assert record.estimated_cost_usd is None
    assert record.cost_source == "unavailable"


def test_provider_usage_with_only_total_tokens_is_incomplete_not_authoritative():
    record = normalize_usage_and_cost(
        provider="http",
        model="gpt-test",
        role="primary",
        provider_usage={"total_tokens": 18},
        usage_source="provider_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=model_pricing(),
    )

    assert record.usage_available is False
    assert record.usage_details_json["usage_unavailable_reason"] == "provider_usage_incomplete"
    assert record.usage_details_json["provider_raw_usage"] == {"total_tokens": 18}
    assert record.prompt_tokens is None
    assert record.completion_tokens is None
    assert record.total_tokens is None
    assert record.estimated_cost_usd is None
    assert record.cost_source == "unavailable"


def test_provider_usage_with_prompt_and_completion_derives_missing_total_tokens():
    record = normalize_usage_and_cost(
        provider="http",
        model="gpt-test",
        role="primary",
        provider_usage={"prompt_tokens": 11, "completion_tokens": 7},
        usage_source="provider_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=model_pricing(),
    )

    assert record.usage_available is True
    assert record.prompt_tokens == 11
    assert record.completion_tokens == 7
    assert record.total_tokens == 18
    assert record.estimated_cost_usd == 0.00025
    assert record.cost_source == "provider_usage_x_pricing_snapshot"


def test_explicit_zero_provider_usage_is_authoritative_zero_usage():
    record = normalize_usage_and_cost(
        provider="http",
        model="gpt-test",
        role="primary",
        provider_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        usage_source="provider_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=model_pricing(),
    )

    assert record.usage_available is True
    assert record.prompt_tokens == 0
    assert record.completion_tokens == 0
    assert record.total_tokens == 0
    assert record.estimated_cost_usd == 0.0
    assert record.cost_source == "provider_usage_x_pricing_snapshot"


def test_provider_reported_cost_is_audit_only_without_delegation():
    record = normalize_usage_and_cost(
        provider="gateway",
        model="routed-model",
        role="primary",
        provider_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        usage_source="gateway_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=0.1234,
        pricing=model_pricing(pricing_key="registry:routed-model:v1"),
    )

    assert record.estimated_cost_usd == 0.002
    assert record.provider_reported_cost_usd == 0.1234
    assert record.cost_source == "provider_usage_x_pricing_snapshot"


def test_provider_reported_cost_can_be_used_only_when_registry_delegates():
    record = normalize_usage_and_cost(
        provider="gateway",
        model="routed-model",
        role="primary",
        provider_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        usage_source="gateway_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=0.1234,
        pricing=model_pricing(
            pricing_key="registry:routed-model:delegated:v1",
            delegates_to_provider_reported_cost=True,
        ),
    )

    assert record.estimated_cost_usd == 0.1234
    assert record.provider_reported_cost_usd == 0.1234
    assert record.cost_source == "provider_reported_cost"
    assert record.pricing_snapshot_id == "registry:routed-model:delegated:v1"


def test_delegated_provider_reported_cost_missing_makes_cost_unavailable():
    record = normalize_usage_and_cost(
        provider="gateway",
        model="routed-model",
        role="primary",
        provider_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        usage_source="gateway_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=model_pricing(
            pricing_key="registry:routed-model:delegated:v1",
            delegates_to_provider_reported_cost=True,
        ),
    )

    assert record.estimated_cost_usd is None
    assert record.cost_source == "unavailable"
    assert record.cost_error_code == "PROVIDER_REPORTED_COST_MISSING"
    assert record.pricing_snapshot_id is None
    assert record.pricing_snapshot_version == ""


def test_delegated_provider_reported_cost_can_be_used_without_token_usage():
    record = normalize_usage_and_cost(
        provider="gateway",
        model="routed-model",
        role="primary",
        provider_usage=None,
        usage_source="unavailable",
        tokenizer_estimate=None,
        provider_reported_cost_usd=0.1234,
        pricing=model_pricing(
            pricing_key="registry:routed-model:delegated:v1",
            delegates_to_provider_reported_cost=True,
        ),
    )

    assert record.usage_available is False
    assert record.estimated_cost_usd == 0.1234
    assert record.provider_reported_cost_usd == 0.1234
    assert record.cost_source == "provider_reported_cost"
    assert record.cost_error_code == ""
    assert record.pricing_snapshot_id == "registry:routed-model:delegated:v1"


def test_delegated_provider_reported_cost_missing_with_incomplete_usage_records_error():
    record = normalize_usage_and_cost(
        provider="gateway",
        model="routed-model",
        role="primary",
        provider_usage={"prompt_tokens": 100},
        usage_source="gateway_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=model_pricing(
            pricing_key="registry:routed-model:delegated:v1",
            delegates_to_provider_reported_cost=True,
        ),
    )

    assert record.usage_available is False
    assert record.estimated_cost_usd is None
    assert record.cost_source == "unavailable"
    assert record.cost_error_code == "PROVIDER_REPORTED_COST_MISSING"
    assert record.pricing_snapshot_id is None


def test_unsupported_billable_usage_class_makes_cost_unavailable():
    record = normalize_usage_and_cost(
        provider="http",
        model="thinking-model",
        role="primary",
        provider_usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 180,
            "reasoning_tokens": 30,
        },
        usage_source="provider_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=model_pricing(reasoning_cost_per_1k_tokens=None),
    )

    assert record.usage_available is True
    assert record.estimated_cost_usd is None
    assert record.cost_source == "unavailable"
    assert record.cost_error_code == "UNSUPPORTED_USAGE_CLASS"
    assert record.pricing_snapshot_id is None
    assert record.pricing_snapshot_version == ""


@pytest.mark.parametrize(
    "unsupported_usage_key",
    ["audio_tokens", "image_tokens", "custom_provider_tokens"],
)
def test_unknown_billable_usage_class_makes_cost_unavailable_without_pricing_support(
    unsupported_usage_key,
):
    record = normalize_usage_and_cost(
        provider="http",
        model="multimodal-model",
        role="primary",
        provider_usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 180,
            unsupported_usage_key: 30,
        },
        usage_source="provider_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=model_pricing(),
    )

    assert record.usage_available is True
    assert record.estimated_cost_usd is None
    assert record.cost_source == "unavailable"
    assert record.cost_error_code == "UNSUPPORTED_USAGE_CLASS"
    assert record.usage_details_json[unsupported_usage_key] == 30


def test_nested_unknown_billable_usage_class_makes_cost_unavailable():
    record = normalize_usage_and_cost(
        provider="http",
        model="multimodal-model",
        role="primary",
        provider_usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 180,
            "provider_raw_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 180,
                "completion_tokens_details": {"audio_tokens": 30},
            },
        },
        usage_source="provider_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=model_pricing(),
    )

    assert record.usage_available is True
    assert record.estimated_cost_usd is None
    assert record.cost_source == "unavailable"
    assert record.cost_error_code == "UNSUPPORTED_USAGE_CLASS"


def test_cached_input_tokens_are_not_double_counted_when_included_in_prompt_tokens():
    record = normalize_usage_and_cost(
        provider="http",
        model="cached-model",
        role="primary",
        provider_usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cached_input_tokens": 40,
            "cached_input_tokens_included_in_prompt_tokens": True,
        },
        usage_source="provider_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=model_pricing(cached_input_cost_per_1k_tokens=0.001),
    )

    assert record.estimated_cost_usd == 0.00164
    assert record.cost_source == "provider_usage_x_pricing_snapshot"


def test_cached_input_tokens_default_to_included_in_prompt_tokens():
    record = normalize_usage_and_cost(
        provider="http",
        model="cached-model",
        role="primary",
        provider_usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cached_input_tokens": 40,
        },
        usage_source="provider_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=model_pricing(cached_input_cost_per_1k_tokens=0.001),
    )

    assert record.estimated_cost_usd == 0.00164
    assert record.cost_source == "provider_usage_x_pricing_snapshot"


def test_pricing_unconfigured_records_unavailable_cost():
    record = normalize_usage_and_cost(
        provider="http",
        model="unpriced-model",
        role="primary",
        provider_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        usage_source="provider_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=None,
    )

    assert record.estimated_cost_usd is None
    assert record.cost_source == "unavailable"
    assert record.cost_error_code == "PRICING_UNCONFIGURED"
    assert record.pricing_snapshot_id is None
    assert record.pricing_snapshot_version == ""


def test_zero_rate_non_delegated_pricing_records_unconfigured_cost():
    record = normalize_usage_and_cost(
        provider="http",
        model="zero-priced-model",
        role="primary",
        provider_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        usage_source="provider_final_chunk",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=model_pricing(
            pricing_key="primary_http:zero-priced-model",
            input_cost_per_1k_tokens=0.0,
            output_cost_per_1k_tokens=0.0,
            delegates_to_provider_reported_cost=False,
        ),
    )

    assert record.estimated_cost_usd is None
    assert record.cost_source == "unavailable"
    assert record.cost_error_code == "PRICING_UNCONFIGURED"
    assert record.pricing_snapshot_id is None
    assert record.pricing_snapshot_version == ""


def test_missing_usage_with_unconfigured_pricing_records_pricing_error():
    record = normalize_usage_and_cost(
        provider="http",
        model="unpriced-model",
        role="primary",
        provider_usage=None,
        usage_source="unavailable",
        tokenizer_estimate=None,
        provider_reported_cost_usd=None,
        pricing=None,
    )

    assert record.estimated_cost_usd is None
    assert record.cost_source == "unavailable"
    assert record.cost_error_code == "PRICING_UNCONFIGURED"
    assert record.pricing_snapshot_id is None
    assert record.pricing_snapshot_version == ""
