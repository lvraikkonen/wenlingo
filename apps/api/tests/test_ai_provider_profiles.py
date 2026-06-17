import pytest
from fastapi import HTTPException

from app.api.deps import provider_for_profile
from app.core.config import Settings
from app.services.ai_routing import LOGICAL_MODELS, PROVIDER_PROFILES
from app.services.llm_provider import HttpJsonLLMProvider, MockLLMProvider


def test_mock_profile_returns_mock_provider():
    provider = provider_for_profile(
        settings=Settings(llm_provider="mock"),
        profile=PROVIDER_PROFILES["mock_primary"],
        logical_model=LOGICAL_MODELS["cheap_fast"],
        timeout_seconds=8,
    )

    assert isinstance(provider, MockLLMProvider)
    assert provider.provider_name == "mock"


def test_http_profile_requires_profile_specific_config():
    with pytest.raises(HTTPException, match="missing configuration"):
        provider_for_profile(
            settings=Settings(llm_provider="http"),
            profile=PROVIDER_PROFILES["primary_http"],
            logical_model=LOGICAL_MODELS["cheap_fast"],
            timeout_seconds=8,
        )


def test_http_profile_uses_profile_model_override():
    provider = provider_for_profile(
        settings=Settings(
            llm_provider="http",
            llm_primary_http_base_url="https://example.test/v1",
            llm_primary_http_api_key="key",
            llm_primary_http_model="cheap-prod-model",
        ),
        profile=PROVIDER_PROFILES["primary_http"],
        logical_model=LOGICAL_MODELS["cheap_fast"],
        timeout_seconds=8,
    )

    assert isinstance(provider, HttpJsonLLMProvider)
    assert provider.base_url == "https://example.test/v1"
    assert provider.model_name == "cheap-prod-model"
    assert provider.timeout_seconds == 8
