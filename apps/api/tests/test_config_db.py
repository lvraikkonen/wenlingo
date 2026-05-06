from app.core.config import Settings
from app.db.session import create_engine_from_settings


def test_settings_load_database_url():
    settings = Settings(database_url="postgresql+psycopg://wenlingo:wenlingo@localhost:5432/wenlingo")

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.llm_provider == "mock"


def test_engine_uses_configured_url():
    settings = Settings(database_url="sqlite:///test.db")
    engine = create_engine_from_settings(settings)

    assert str(engine.url) == "sqlite:///test.db"
