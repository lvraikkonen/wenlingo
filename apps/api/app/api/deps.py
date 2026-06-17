from collections.abc import Generator

from fastapi import Depends, HTTPException
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.services.ai_routing import LogicalModel, ProviderProfile
from app.services.llm_provider import HttpJsonLLMProvider, LLMProvider, MockLLMProvider


def get_db_session() -> Generator[Session, None, None]:
    yield from get_session()


def get_llm_provider(settings: Settings = Depends(get_settings)) -> LLMProvider:
    provider = settings.llm_provider.strip().lower()
    if provider == "mock":
        return MockLLMProvider()
    if provider == "http":
        missing = [
            name
            for name, value in {
                "LLM_API_KEY": settings.llm_api_key,
                "LLM_MODEL": settings.llm_model,
                "LLM_BASE_URL": settings.llm_base_url,
            }.items()
            if not value.strip()
        ]
        if missing:
            raise HTTPException(
                status_code=503,
                detail=f"LLM http provider is missing configuration: {', '.join(missing)}",
            )
        return HttpJsonLLMProvider(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
        )
    raise HTTPException(
        status_code=503,
        detail=f"Unsupported LLM_PROVIDER: {settings.llm_provider}",
    )


def provider_for_profile(
    *,
    settings: Settings,
    profile: ProviderProfile,
    logical_model: LogicalModel,
    timeout_seconds: int,
) -> LLMProvider:
    if profile.provider_type == "mock":
        return MockLLMProvider()
    if profile.provider_type == "openai_compatible_http":
        base_url = getattr(settings, profile.base_url_env).strip()
        api_key = getattr(settings, profile.api_key_env).strip()
        model_override = (
            getattr(settings, logical_model.model_env).strip()
            if logical_model.model_env
            else ""
        )
        model = model_override or logical_model.model
        model_env_name = logical_model.model_env.upper() if logical_model.model_env else "MODEL"
        missing = [
            name
            for name, value in {
                profile.base_url_env.upper(): base_url,
                profile.api_key_env.upper(): api_key,
                model_env_name: model,
            }.items()
            if not value
        ]
        if missing:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"LLM provider profile {profile.profile_name} is missing configuration: "
                    f"{', '.join(missing)}"
                ),
            )
        return HttpJsonLLMProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
    raise HTTPException(
        status_code=503,
        detail=f"Unsupported LLM provider profile type: {profile.provider_type}",
    )
