import smtplib
from email.message import EmailMessage

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.services.email_sender import SmtpEmailSender, get_email_sender


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.login_args = None
        self.sent_message = None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, message: EmailMessage):
        self.sent_message = message


def test_get_email_sender_returns_smtp_sender_when_configured(monkeypatch):
    settings = Settings(
        magic_code_dev_echo=False,
        magic_code_email_provider="smtp",
        magic_code_from_email="sender@qq.com",
        smtp_host="smtp.qq.com",
        smtp_port=465,
        smtp_username="sender@qq.com",
        smtp_password="auth-code",
        smtp_use_ssl=True,
        smtp_use_starttls=False,
    )

    sender = get_email_sender(settings)

    assert isinstance(sender, SmtpEmailSender)


def test_smtp_sender_sends_magic_code_with_ssl(monkeypatch):
    FakeSMTP.instances.clear()
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    settings = Settings(
        magic_code_from_email="sender@qq.com",
        smtp_host="smtp.qq.com",
        smtp_port=465,
        smtp_username="sender@qq.com",
        smtp_password="auth-code",
        smtp_use_ssl=True,
        smtp_use_starttls=False,
    )
    sender = SmtpEmailSender(settings)

    sent = sender.send_magic_code(
        to_email="parent@example.com",
        code="654321",
        ttl_minutes=10,
    )

    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.qq.com"
    assert smtp.port == 465
    assert smtp.timeout == 10
    assert smtp.login_args == ("sender@qq.com", "auth-code")
    assert smtp.sent_message["Subject"] == "WenLingo 登录验证码"
    assert smtp.sent_message["From"] == "sender@qq.com"
    assert smtp.sent_message["To"] == "parent@example.com"
    assert "654321" in smtp.sent_message.get_content()
    assert "10 分钟" in smtp.sent_message.get_content()
    assert sent.to_email == "parent@example.com"
    assert sent.subject == "WenLingo 登录验证码"


def test_smtp_sender_starttls_path(monkeypatch):
    FakeSMTP.instances.clear()
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    settings = Settings(
        magic_code_from_email="sender@qq.com",
        smtp_host="smtp.qq.com",
        smtp_port=587,
        smtp_username="sender@qq.com",
        smtp_password="auth-code",
        smtp_use_ssl=False,
        smtp_use_starttls=True,
    )

    SmtpEmailSender(settings).send_magic_code(
        to_email="parent@example.com",
        code="654321",
        ttl_minutes=10,
    )

    assert FakeSMTP.instances[0].started_tls is True


def test_smtp_sender_missing_config_fails_closed():
    settings = Settings(
        magic_code_dev_echo=False,
        magic_code_email_provider="smtp",
        magic_code_from_email="sender@qq.com",
        smtp_host="",
        smtp_username="sender@qq.com",
        smtp_password="auth-code",
    )

    with pytest.raises(HTTPException) as exc:
        get_email_sender(settings)

    assert exc.value.status_code == 503
    assert exc.value.detail == "email provider unavailable"


def test_smtp_sender_provider_error_returns_generic_message(monkeypatch, caplog):
    class FailingSMTP(FakeSMTP):
        def login(self, username, password):
            raise smtplib.SMTPAuthenticationError(535, b"auth failed")

    monkeypatch.setattr(smtplib, "SMTP_SSL", FailingSMTP)
    settings = Settings(
        magic_code_from_email="sender@qq.com",
        smtp_host="smtp.qq.com",
        smtp_port=465,
        smtp_username="sender@qq.com",
        smtp_password="super-secret",
        smtp_use_ssl=True,
        smtp_use_starttls=False,
    )

    with pytest.raises(HTTPException) as exc:
        SmtpEmailSender(settings).send_magic_code(
            to_email="parent@example.com",
            code="654321",
            ttl_minutes=10,
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "验证码发送失败，请稍后再试。"
    log_text = caplog.text
    assert "SMTPAuthenticationError" in log_text
    assert "super-secret" not in log_text
    assert "654321" not in log_text
    assert "parent@example.com" not in log_text
