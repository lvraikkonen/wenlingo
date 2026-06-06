from dataclasses import dataclass, field
import re

from sqlmodel import Session, select

from app.domain.models import (
    ParentAccount,
    ParentUser,
)

DELETE_TEST_CONFIRMATION = "DELETE TEST ACCOUNTS"
MAX_DELETE_TEST_ACCOUNTS = 20
PROTECTED_EMAILS = {"demo@wenlingo.local"}
ALLOWLIST_DOMAINS = {"example.com", "test.local", "wenlingo.local"}
ALLOWLIST_LOCAL_MARKERS = ("qa", "test", "dev")
LOCAL_PART_TOKEN_SEPARATOR_RE = re.compile(r"[._+-]+")


@dataclass
class DeletedTestAccount:
    account_id: str
    email_masked: str
    parent_ids: list[str] = field(default_factory=list)
    child_count: int = 0
    deleted_session_count: int = 0
    deleted_invite_count: int = 0


@dataclass
class DeleteTestAccountsResult:
    deleted_accounts: list[DeletedTestAccount]

    @property
    def deleted_count(self) -> int:
        return len(self.deleted_accounts)


def is_test_account_email(email_normalized: str) -> bool:
    email = email_normalized.strip().lower()
    if email in PROTECTED_EMAILS:
        return False
    if "@" not in email:
        return False
    local_part, domain = email.rsplit("@", 1)
    if domain in ALLOWLIST_DOMAINS:
        return True
    local_tokens = {
        token for token in LOCAL_PART_TOKEN_SEPARATOR_RE.split(local_part) if token
    }
    return any(marker in local_tokens for marker in ALLOWLIST_LOCAL_MARKERS)


def _is_protected_account(session: Session, account: ParentAccount) -> bool:
    if account.email_normalized.lower() in PROTECTED_EMAILS:
        return True
    parent = session.exec(
        select(ParentUser).where(ParentUser.account_id == account.id)
    ).first()
    return bool(parent and parent.email.lower().startswith("demo@wenlingo.local"))
