from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    admin_alpha,
    alpha,
    assessment,
    auth,
    dashboard,
    essays,
    reactions,
    readings,
    reports,
    sentences,
)
from app.core.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="Wenlingo API")
    settings = get_settings()
    cors_allow_origins = [
        origin.strip()
        for origin in settings.cors_allow_origins.split(",")
        if origin.strip()
    ]

    if cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_allow_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"service": "wenlingo-api", "status": "ok"}

    app.include_router(auth.router)
    app.include_router(admin_alpha.router)
    app.include_router(alpha.router)
    app.include_router(reactions.router)
    app.include_router(assessment.router)
    app.include_router(dashboard.router)
    app.include_router(essays.router)
    app.include_router(readings.router)
    app.include_router(reports.router)
    app.include_router(sentences.router)
    return app


app = create_app()
