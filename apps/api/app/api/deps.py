from collections.abc import Generator

from fastapi import Depends, HTTPException
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session
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
