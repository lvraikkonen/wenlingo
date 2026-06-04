from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://wenlingo:wenlingo@localhost:5432/wenlingo"
    test_database_url: str = "postgresql+psycopg://wenlingo:wenlingo@localhost:5433/wenlingo_test"
    api_base_url: str = "http://localhost:8000"
    alpha_admin_token: str = ""
    cors_allow_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    llm_provider: str = "mock"
    llm_prompt_version: str = "v0.2-quality-spine-2026-05-14"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""
    llm_daily_limit_enabled: bool = False
    llm_daily_limit_per_student_task: int = 5
    auth_required_for_alpha: bool = False
    auth_session_cookie_name: str = "wenlingo_parent_session"
    auth_session_cookie_secure: bool = True
    auth_session_cookie_samesite: str = "lax"
    auth_session_days: int = 30
    auth_session_last_seen_throttle_minutes: int = 15
    auth_secret_pepper: str = ""
    magic_code_ttl_minutes: int = 10
    magic_code_max_attempts: int = 5
    magic_code_email_rate_limit: int = 3
    magic_code_ip_rate_limit: int = 20
    magic_code_alpha_session_rate_limit: int = 5
    magic_code_from_email: str = ""
    magic_code_email_provider: str = ""
    magic_code_dev_echo: bool = False
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_ssl: bool = True
    smtp_use_starttls: bool = False
    smtp_timeout_seconds: int = 10
    legacy_bind_window_days: int = 14
    auth_allowed_origins: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


def get_settings() -> Settings:
    return Settings()
