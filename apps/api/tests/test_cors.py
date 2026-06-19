import pytest


@pytest.fixture(autouse=True)
def fixed_cors_origins(monkeypatch):
    monkeypatch.setenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )


def test_local_next_origin_is_allowed(client):
    response = client.options(
        "/api/auth/magic-codes/request",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


def test_unknown_origin_is_not_allowed(client):
    response = client.options(
        "/api/auth/magic-codes/request",
        headers={
            "Origin": "http://malicious.local",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_demo_login_route_removed(client):
    assert client.post("/api/auth/demo-login").status_code == 404
