from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://wenlingo:wenlingo@localhost:5432/wenlingo"
    test_database_url: str = "postgresql+psycopg://wenlingo:wenlingo@localhost:5433/wenlingo_test"
    api_base_url: str = "http://localhost:8000"
    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


def get_settings() -> Settings:
    return Settings()
