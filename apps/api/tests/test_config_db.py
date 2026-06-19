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


def test_settings_load_ai_routing_provider_profile_defaults():
    settings = Settings(_env_file=None)

    assert settings.llm_primary_http_base_url == ""
    assert settings.llm_primary_http_api_key == ""
    assert settings.llm_primary_http_model == ""
    assert settings.llm_fallback_http_base_url == ""
    assert settings.llm_fallback_http_api_key == ""
    assert settings.llm_fallback_http_model == ""


def test_settings_default_prompt_version_uses_registry_version():
    settings = Settings(_env_file=None)

    assert settings.llm_prompt_version == ""


def test_settings_load_v05a_auth_defaults():
    settings = Settings(_env_file=None)

    assert settings.auth_required_for_alpha is False
    assert settings.auth_session_cookie_name == "wenlingo_parent_session"
    assert settings.auth_session_days == 30
    assert settings.auth_session_last_seen_throttle_minutes == 15
    assert settings.auth_secret_pepper == ""
    assert settings.magic_code_ttl_minutes == 10
    assert settings.magic_code_max_attempts == 5
    assert settings.magic_code_email_rate_limit == 3
    assert settings.magic_code_ip_rate_limit == 20
    assert settings.magic_code_alpha_session_rate_limit == 5
    assert settings.magic_code_from_email == ""
    assert settings.magic_code_email_provider == ""
    assert settings.magic_code_dev_echo is False
    assert settings.legacy_bind_window_days == 14
    assert settings.auth_allowed_origins == ""
