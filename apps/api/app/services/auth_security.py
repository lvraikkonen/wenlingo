import hmac
import re
import secrets
from hashlib import sha256


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CHINA_MOBILE_RE = re.compile(r"^1\d{10}$")


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not _EMAIL_RE.match(normalized):
        raise ValueError("invalid email")
    return normalized


def normalize_phone(phone: str) -> str:
    normalized = re.sub(r"[\s\-()]", "", phone.strip())
    if _CHINA_MOBILE_RE.match(normalized):
        return f"+86{normalized}"
    if normalized.startswith("+") and len(normalized) > 1 and normalized[1:].isdigit():
        return normalized
    raise ValueError("invalid phone")


def generate_magic_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(value: str, *, purpose: str, pepper: str) -> str:
    if not pepper:
        raise ValueError("pepper is required")
    message = f"{purpose}:{value}".encode("utf-8")
    return hmac.new(pepper.encode("utf-8"), message, sha256).hexdigest()


def mask_email(email: str) -> str:
    local, domain = normalize_email(email).split("@", 1)
    return f"{local[:2]}***@{domain}"


def mask_phone(phone: str) -> str:
    normalized = normalize_phone(phone)
    if normalized.startswith("+86") and len(normalized) == 14:
        local_number = normalized[3:]
        return f"{local_number[:3]}****{local_number[-4:]}"
    return f"{normalized[:3]}****{normalized[-4:]}"
