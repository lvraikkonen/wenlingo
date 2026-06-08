from dataclasses import dataclass, field
import logging
import re

from fastapi import HTTPException
from sqlmodel import Session, select

from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    AlphaInviteCode,
    Assessment,
    AuthMagicCode,
    Essay,
    EssayVersion,
    FeedbackReaction,
    GameEvent,
    LLMCallLog,
    ParentAccount,
    ParentFeedback,
    ParentSession,
    ParentUser,
    ProductEvent,
    ReadingSession,
    Report,
    SentenceTraining,
    StudentProfile,
)
from app.services.auth_security import mask_email

logger = logging.getLogger(__name__)

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


def _require_valid_request(
    session: Session, account_ids: list[str], confirm: str
) -> list[ParentAccount]:
    if confirm != DELETE_TEST_CONFIRMATION:
        raise HTTPException(status_code=400, detail="confirmation text is required")
    if not account_ids:
        raise HTTPException(status_code=400, detail="account_ids must not be empty")
    if len(account_ids) > MAX_DELETE_TEST_ACCOUNTS:
        raise HTTPException(status_code=400, detail="account_ids cannot exceed 20")

    accounts: list[ParentAccount] = []
    for account_id in account_ids:
        account = session.get(ParentAccount, account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="account not found")
        accounts.append(account)

    rejected = [
        account
        for account in accounts
        if _is_protected_account(session, account)
        or not is_test_account_email(account.email_normalized)
    ]
    if rejected:
        raise HTTPException(status_code=409, detail="batch contains non-test account")
    return accounts


def _delete_where_in(session: Session, model, field, values: set[str]) -> int:
    if not values:
        return 0
    rows = session.exec(select(model).where(field.in_(values))).all()
    for row in rows:
        session.delete(row)
    return len(rows)


def _flush_if_needed(session: Session, deleted_count: int) -> None:
    if deleted_count:
        session.flush()


def delete_test_accounts(
    session: Session, *, account_ids: list[str], confirm: str
) -> DeleteTestAccountsResult:
    accounts = _require_valid_request(session, account_ids, confirm)
    deleted_accounts: list[DeletedTestAccount] = []

    for account in accounts:
        parents = session.exec(
            select(ParentUser).where(ParentUser.account_id == account.id)
        ).all()
        parent_ids = {parent.id for parent in parents}
        children = (
            session.exec(
                select(StudentProfile).where(StudentProfile.parent_id.in_(parent_ids))
            ).all()
            if parent_ids
            else []
        )
        child_ids = {child.id for child in children}
        essays = (
            session.exec(select(Essay).where(Essay.student_id.in_(child_ids))).all()
            if child_ids
            else []
        )
        essay_ids = {essay.id for essay in essays}

        deleted_session_count = _delete_where_in(
            session, ParentSession, ParentSession.account_id, {account.id}
        )
        _delete_where_in(
            session,
            AuthMagicCode,
            AuthMagicCode.email_normalized,
            {account.email_normalized},
        )

        if child_ids:
            _flush_if_needed(
                session,
                _delete_where_in(session, Assessment, Assessment.student_id, child_ids),
            )
            _flush_if_needed(
                session,
                _delete_where_in(session, EssayVersion, EssayVersion.essay_id, essay_ids),
            )
            _flush_if_needed(
                session,
                _delete_where_in(session, Essay, Essay.student_id, child_ids),
            )
            _flush_if_needed(
                session,
                _delete_where_in(
                    session, SentenceTraining, SentenceTraining.student_id, child_ids
                ),
            )
            _delete_where_in(session, ReadingSession, ReadingSession.student_id, child_ids)
            _delete_where_in(session, GameEvent, GameEvent.student_id, child_ids)
            _delete_where_in(session, Report, Report.student_id, child_ids)
            _delete_where_in(session, AbilityHistory, AbilityHistory.student_id, child_ids)
            _delete_where_in(session, AbilityProfile, AbilityProfile.student_id, child_ids)
            _delete_where_in(session, LLMCallLog, LLMCallLog.student_id, child_ids)
            _delete_where_in(
                session, FeedbackReaction, FeedbackReaction.student_id, child_ids
            )
            _delete_where_in(session, ParentFeedback, ParentFeedback.student_id, child_ids)
            _delete_where_in(session, ProductEvent, ProductEvent.student_id, child_ids)
            session.flush()

        if parent_ids:
            _flush_if_needed(
                session,
                _delete_where_in(session, ProductEvent, ProductEvent.parent_id, parent_ids),
            )
            invites = session.exec(
                select(AlphaInviteCode).where(
                    AlphaInviteCode.consumed_by_parent_id.in_(parent_ids)
                )
            ).all()
        else:
            invites = []
        invite_ids = {invite.id for invite in invites}
        if invite_ids:
            _flush_if_needed(
                session,
                _delete_where_in(
                    session, ProductEvent, ProductEvent.invite_code_id, invite_ids
                ),
            )

        deleted_invite_count = len(invites)
        for invite in invites:
            session.delete(invite)
        if invites:
            session.flush()
        for child in children:
            session.delete(child)
        if children:
            session.flush()
        for parent in parents:
            session.delete(parent)
        if parents:
            session.flush()
        session.delete(account)
        session.flush()

        deleted_accounts.append(
            DeletedTestAccount(
                account_id=account.id,
                email_masked=mask_email(account.email_normalized),
                parent_ids=sorted(parent_ids),
                child_count=len(children),
                deleted_session_count=deleted_session_count,
                deleted_invite_count=deleted_invite_count,
            )
        )

    session.commit()
    logger.info(
        "Deleted alpha test accounts",
        extra={
            "account_ids": [row.account_id for row in deleted_accounts],
            "emails_masked": [row.email_masked for row in deleted_accounts],
            "deleted_count": len(deleted_accounts),
        },
    )
    return DeleteTestAccountsResult(deleted_accounts=deleted_accounts)
