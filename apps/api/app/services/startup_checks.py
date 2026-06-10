from app.core.config import Settings


def validate_startup_settings(settings: Settings) -> None:
    environment = settings.environment.strip().lower()
    if environment not in {"development", "staging", "production"}:
        raise RuntimeError("ENVIRONMENT must be development, staging, or production")
    if environment in {"staging", "production"} and settings.magic_code_dev_echo:
        raise RuntimeError("MAGIC_CODE_DEV_ECHO cannot be true in staging or production")
