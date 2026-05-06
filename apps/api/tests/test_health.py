from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_service_name():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"service": "wenlingo-api", "status": "ok"}
