from dataclasses import dataclass, field

from fastapi import HTTPException


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


def get_email_sender(settings) -> EmailSender:
    if settings.magic_code_dev_echo:
        return CapturedEmailSender()
    return DisabledProductionEmailSender()
