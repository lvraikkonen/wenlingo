from fastapi import FastAPI

from app.api.routes import assessment, auth, dashboard, essays, readings, reports, sentences


def create_app() -> FastAPI:
    app = FastAPI(title="Wenlingo API")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"service": "wenlingo-api", "status": "ok"}

    app.include_router(auth.router)
    app.include_router(assessment.router)
    app.include_router(dashboard.router)
    app.include_router(essays.router)
    app.include_router(readings.router)
    app.include_router(reports.router)
    app.include_router(sentences.router)
    return app


app = create_app()
