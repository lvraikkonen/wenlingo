from app.core.config import Settings
from app.db.session import create_engine_from_settings


def test_settings_load_database_url():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://wenlingo:wenlingo@localhost:5432/wenlingo",
    )

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.llm_provider == "mock"


def test_settings_ignores_unrelated_frontend_env_keys(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=sqlite:///from-env-file.db",
                "NEXT_PUBLIC_API_BASE_URL=http://localhost:3000",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.database_url == "sqlite:///from-env-file.db"
    assert not hasattr(settings, "next_public_api_base_url")


def test_engine_uses_configured_url():
    settings = Settings(database_url="sqlite:///test.db")
    engine = create_engine_from_settings(settings)

    assert str(engine.url) == "sqlite:///test.db"
    assert engine.pool._pre_ping is True


def test_settings_load_alpha_admin_token():
    settings = Settings(_env_file=None, alpha_admin_token="secret-token")

    assert settings.alpha_admin_token == "secret-token"
