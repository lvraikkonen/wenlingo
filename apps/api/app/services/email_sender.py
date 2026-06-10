import logging
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage

import httpx
from fastapi import HTTPException


logger = logging.getLogger(__name__)
SMTP_SEND_ERROR = "验证码发送失败，请稍后再试。"


@dataclass(frozen=True)
class SentEmail:
    to_email: str
    subject: str
    body: str


class EmailSender:
    def send_magic_code(self, *, to_email: str, code: str, ttl_minutes: int) -> SentEmail:
        raise NotImplementedError


@dataclass
class CapturedEmailSender(EmailSender):
    sent: list[SentEmail] = field(default_factory=list)

    def send_magic_code(self, *, to_email: str, code: str, ttl_minutes: int) -> SentEmail:
        email = SentEmail(
            to_email=to_email,
            subject="WenLingo 登录验证码",
            body=f"你的 WenLingo 登录验证码是 {code}，{ttl_minutes} 分钟内有效。",
        )
        self.sent.append(email)
        return email


class DisabledProductionEmailSender(EmailSender):
    def send_magic_code(self, *, to_email: str, code: str, ttl_minutes: int) -> SentEmail:
        raise HTTPException(status_code=503, detail="email provider unavailable")


@dataclass
class SmtpEmailSender(EmailSender):
    settings: object

    def send_magic_code(self, *, to_email: str, code: str, ttl_minutes: int) -> SentEmail:
        subject = "WenLingo 登录验证码"
        body = f"你的 WenLingo 登录验证码是 {code}，{ttl_minutes} 分钟内有效。"
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.settings.magic_code_from_email
        message["To"] = to_email
        message.set_content(body)

        smtp_class = smtplib.SMTP_SSL if self.settings.smtp_use_ssl else smtplib.SMTP

        try:
            with smtp_class(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=self.settings.smtp_timeout_seconds,
            ) as smtp:
                if self.settings.smtp_use_starttls:
                    smtp.starttls()
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            logger.error("SMTP email send failed: %s", exc.__class__.__name__)
            raise HTTPException(status_code=503, detail=SMTP_SEND_ERROR) from None

        return SentEmail(to_email=to_email, subject=subject, body=body)


@dataclass
class ResendEmailSender(EmailSender):
    settings: object

    def send_magic_code(self, *, to_email: str, code: str, ttl_minutes: int) -> SentEmail:
        subject = "WenLingo 登录验证码"
        body = f"你的 WenLingo 登录验证码是 {code}，{ttl_minutes} 分钟内有效。"
        payload = {
            "from": self.settings.magic_code_from_email,
            "to": [to_email],
            "subject": subject,
            "text": body,
            "html": f"<p>你的 WenLingo 登录验证码是 <strong>{code}</strong>，{ttl_minutes} 分钟内有效。</p>",
        }
        headers = {"Authorization": f"Bearer {self.settings.resend_api_key}"}

        try:
            with httpx.Client(timeout=self.settings.resend_timeout_seconds) as client:
                response = client.post(
                    "https://api.resend.com/emails",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
        except Exception as exc:
            logger.warning("Resend email send failed: %s", exc.__class__.__name__)
            raise HTTPException(status_code=503, detail="email provider unavailable") from None

        return SentEmail(to_email=to_email, subject=subject, body=body)


def _smtp_configured(settings) -> bool:
    return bool(
        settings.magic_code_from_email
        and settings.smtp_host
        and settings.smtp_port
        and settings.smtp_username
        and settings.smtp_password
    )


def _resend_configured(settings) -> bool:
    return bool(settings.magic_code_from_email and settings.resend_api_key)


def get_email_sender(settings) -> EmailSender:
    if settings.magic_code_dev_echo:
        return CapturedEmailSender()
    if settings.magic_code_email_provider == "smtp":
        if not _smtp_configured(settings):
            raise HTTPException(status_code=503, detail="email provider unavailable")
        return SmtpEmailSender(settings)
    if settings.magic_code_email_provider == "resend":
        if not _resend_configured(settings):
            raise HTTPException(status_code=503, detail="email provider unavailable")
        return ResendEmailSender(settings)
    return DisabledProductionEmailSender()
