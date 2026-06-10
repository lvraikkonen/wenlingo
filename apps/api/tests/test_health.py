import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_returns_service_name():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"service": "wenlingo-api", "status": "ok"}


def test_create_app_runs_startup_settings_guard(monkeypatch):
    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(environment="staging", magic_code_dev_echo=True),
    )

    with pytest.raises(RuntimeError) as exc:
        create_app()

    assert "MAGIC_CODE_DEV_ECHO" in str(exc.value)
