import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.services.email_sender import get_email_sender


class FakeResendResponse:
    def __init__(self):
        self.raise_for_status_called = False

    def raise_for_status(self):
        self.raise_for_status_called = True


class FakeResendClient:
    instances = []

    def __init__(self, timeout):
        self.timeout = timeout
        self.post_calls = []
        FakeResendClient.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, *, headers, json):
        response = FakeResendResponse()
        self.post_calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "response": response,
            }
        )
        return response


class FailingResendClient(FakeResendClient):
    def post(self, url, *, headers, json):
        raise RuntimeError("provider unavailable")


def test_get_email_sender_returns_resend_sender_when_configured():
    settings = Settings(
        magic_code_dev_echo=False,
        magic_code_email_provider="resend",
        magic_code_from_email="login@wenlingo.example",
        resend_api_key="fake-resend-key",
    )

    sender = get_email_sender(settings)

    assert sender.__class__.__name__ == "ResendEmailSender"


def test_resend_sender_posts_magic_code_payload(monkeypatch):
    import app.services.email_sender as email_sender
    from app.services.email_sender import ResendEmailSender

    FakeResendClient.instances.clear()
    monkeypatch.setattr(email_sender.httpx, "Client", FakeResendClient)
    settings = Settings(
        magic_code_from_email="login@wenlingo.example",
        resend_api_key="fake-resend-key",
        resend_timeout_seconds=7,
    )
    sender = ResendEmailSender(settings)

    sent = sender.send_magic_code(
        to_email="parent@example.com",
        code="654321",
        ttl_minutes=10,
    )

    client = FakeResendClient.instances[0]
    call = client.post_calls[0]
    assert client.timeout == 7
    assert call["url"] == "https://api.resend.com/emails"
    assert call["headers"] == {
        "Authorization": "Bearer fake-resend-key",
        "Content-Type": "application/json",
    }
    assert call["json"]["from"] == "login@wenlingo.example"
    assert call["json"]["to"] == ["parent@example.com"]
    assert call["json"]["subject"] == "WenLingo 登录验证码"
    assert "654321" in call["json"]["text"]
    assert "654321" in call["json"]["html"]
    assert call["response"].raise_for_status_called is True
    assert sent.to_email == "parent@example.com"
    assert sent.subject == "WenLingo 登录验证码"


@pytest.mark.parametrize(
    "from_email,resend_api_key",
    [
        ("", "fake-resend-key"),
        ("   ", "fake-resend-key"),
        ("login@wenlingo.example", ""),
        ("login@wenlingo.example", "   "),
    ],
)
def test_resend_sender_missing_config_fails_closed(from_email, resend_api_key):
    settings = Settings(
        magic_code_dev_echo=False,
        magic_code_email_provider="resend",
        magic_code_from_email=from_email,
        resend_api_key=resend_api_key,
    )

    with pytest.raises(HTTPException) as exc:
        get_email_sender(settings)

    assert exc.value.status_code == 503
    assert exc.value.detail == "email provider unavailable"


def test_resend_sender_provider_error_logs_warning_and_fails_closed(monkeypatch, caplog):
    import app.services.email_sender as email_sender
    from app.services.email_sender import ResendEmailSender

    monkeypatch.setattr(email_sender.httpx, "Client", FailingResendClient)
    settings = Settings(
        magic_code_from_email="login@wenlingo.example",
        resend_api_key="fake-resend-key",
    )

    with pytest.raises(HTTPException) as exc:
        ResendEmailSender(settings).send_magic_code(
            to_email="parent@example.com",
            code="654321",
            ttl_minutes=10,
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "email provider unavailable"
    assert "Resend email send failed: RuntimeError" in caplog.text
    assert "fake-resend-key" not in caplog.text
    assert "654321" not in caplog.text
    assert "parent@example.com" not in caplog.text


def test_validate_startup_settings_rejects_invalid_environment():
    from app.services.startup_checks import validate_startup_settings

    settings = Settings(environment="qa", magic_code_dev_echo=False)

    with pytest.raises(RuntimeError) as exc:
        validate_startup_settings(settings)

    assert str(exc.value) == "ENVIRONMENT must be development, staging, or production"


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_validate_startup_settings_rejects_dev_echo_outside_development(environment):
    from app.services.startup_checks import validate_startup_settings

    settings = Settings(environment=environment, magic_code_dev_echo=True)

    with pytest.raises(RuntimeError) as exc:
        validate_startup_settings(settings)

    assert "MAGIC_CODE_DEV_ECHO" in str(exc.value)


def test_validate_startup_settings_allows_dev_echo_in_development():
    from app.services.startup_checks import validate_startup_settings

    settings = Settings(environment="development", magic_code_dev_echo=True)

    validate_startup_settings(settings)


@pytest.mark.parametrize(
    "environment,magic_code_dev_echo",
    [
        (" Production ", False),
        (" DEVELOPMENT ", True),
    ],
)
def test_validate_startup_settings_strips_and_lowercases_environment(
    environment,
    magic_code_dev_echo,
):
    from app.services.startup_checks import validate_startup_settings

    settings = Settings(
        environment=environment,
        magic_code_dev_echo=magic_code_dev_echo,
    )

    validate_startup_settings(settings)
