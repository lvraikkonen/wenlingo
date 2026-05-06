from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Wenlingo API")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"service": "wenlingo-api", "status": "ok"}

    return app


app = create_app()
