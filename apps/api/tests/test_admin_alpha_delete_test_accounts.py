from datetime import timedelta

from fastapi.testclient import TestClient

from app.api.deps import get_db_session
from app.api.routes.alpha import hash_invite_code
from app.domain.enums import ReportType, StudentPersona, TaskType
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
    utcnow,
)
from app.main import create_app
from app.services.admin_test_account_cleanup import is_test_account_email
from app.services.auth_security import hash_secret


def create_admin_client(session, monkeypatch, token: str = "secret"):
    monkeypatch.setenv("ALPHA_ADMIN_TOKEN", token)
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    return app


def add_account(session, email: str, status: str = "active") -> ParentAccount:
    account = ParentAccount(
        email_normalized=email,
        email_verified_at=utcnow(),
        status=status,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def test_test_account_email_allowlist_accepts_only_dev_qa_patterns():
    allowed = [
        "parent@example.com",
        "qa-parent@real-domain.invalid",
        "alpha-test@domain.invalid",
        "dev-family@test.local",
        "playwright-family@wenlingo.local",
    ]
    rejected = [
        "parent@gmail.com",
        "family@qq.com",
        "invited-family@school.example.org",
        "demo@wenlingo.local",
        "devon@gmail.com",
        "contest@school.org",
        "seqa@example.org",
    ]

    for email in allowed:
        assert is_test_account_email(email) is True
    for email in rejected:
        assert is_test_account_email(email) is False


def test_delete_test_accounts_requires_admin_token(session, monkeypatch):
    account = add_account(session, "qa-parent@example.com")
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        response = client.post(
            "/api/admin/alpha/accounts/delete-test",
            json={
                "account_ids": [account.id],
                "confirm": "DELETE TEST ACCOUNTS",
            },
        )

    assert response.status_code == 403


def test_delete_test_accounts_rejects_wrong_confirmation(session, monkeypatch):
    account = add_account(session, "qa-parent@example.com")
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        response = client.post(
            "/api/admin/alpha/accounts/delete-test",
            headers={"X-Alpha-Admin-Token": "secret"},
            json={"account_ids": [account.id], "confirm": "delete"},
        )

    assert response.status_code == 400
    assert "confirmation" in response.json()["detail"]
    assert session.get(ParentAccount, account.id) is not None


def test_delete_test_accounts_rejects_mixed_batch_and_deletes_none(session, monkeypatch):
    test_account = add_account(session, "qa-parent@example.com")
    real_account = add_account(session, "family@qq.com")
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        response = client.post(
            "/api/admin/alpha/accounts/delete-test",
            headers={"X-Alpha-Admin-Token": "secret"},
            json={
                "account_ids": [test_account.id, real_account.id],
                "confirm": "DELETE TEST ACCOUNTS",
            },
        )

    assert response.status_code == 409
    assert session.get(ParentAccount, test_account.id) is not None
    assert session.get(ParentAccount, real_account.id) is not None


def seed_test_family_graph(session, account: ParentAccount):
    parent = ParentUser(
        email="alpha-test-parent@wenlingo.local",
        display_name="QA Parent",
        account_id=account.id,
        account_linked_at=utcnow(),
    )
    session.add(parent)
    session.flush()

    invite = AlphaInviteCode(
        code_hash=hash_invite_code("ALPHA-QA-DELETE"),
        label="QA Delete",
        status="consumed",
        consumed_by_parent_id=parent.id,
        consumed_at=utcnow(),
    )
    child = StudentProfile(
        parent_id=parent.id,
        name="QA Child",
        grade_label="四年级",
        persona=StudentPersona.real_child,
        is_real_child=True,
    )
    session.add(invite)
    session.add(child)
    session.flush()

    sentence = SentenceTraining(
        student_id=child.id,
        source_sentence="before",
        upgraded_sentence="after",
        focus="加细节",
    )
    essay = Essay(student_id=child.id, title="QA Essay")
    llm_log = LLMCallLog(
        student_id=child.id,
        task_type=TaskType.assessment,
        task_name="qa",
        input_summary="qa",
    )
    session.add(sentence)
    session.add(essay)
    session.add(llm_log)
    session.flush()

    rows = [
        ParentSession(
            account_id=account.id,
            token_hash="token-hash",
            expires_at=utcnow() + timedelta(days=1),
        ),
        AuthMagicCode(
            email_normalized=account.email_normalized,
            code_hash=hash_secret("123456", purpose="magic-code", pepper="test-pepper"),
            purpose="parent_login",
            expires_at=utcnow() + timedelta(minutes=10),
        ),
        ProductEvent(
            event_type="qa",
            parent_id=parent.id,
            student_id=child.id,
            invite_code_id=invite.id,
        ),
        FeedbackReaction(
            parent_id=parent.id,
            student_id=child.id,
            target_type="assessment",
            target_id="target-1",
            reaction="positive",
        ),
        ParentFeedback(
            parent_id=parent.id,
            student_id=child.id,
            target_type="alpha_summary",
            target_id="summary",
            usefulness="helpful",
        ),
        AbilityProfile(student_id=child.id),
        AbilityHistory(
            student_id=child.id,
            ability_name="expression",
            old_value=40,
            new_value=45,
            delta=5,
            source_type=TaskType.assessment,
            source_id="source",
        ),
        Assessment(
            student_id=child.id,
            sentence_before="a",
            sentence_after="b",
            short_writing="c",
            summary="d",
            sentence_training_id=sentence.id,
            essay_id=essay.id,
        ),
        EssayVersion(
            essay_id=essay.id,
            version_label="first_draft",
            content="draft",
            llm_call_log_id=llm_log.id,
        ),
        ReadingSession(student_id=child.id, article_title="Spring", transfer_tip="tip"),
        GameEvent(
            student_id=child.id,
            task_type=TaskType.assessment,
            xp_delta=1,
            level_after=1,
        ),
        Report(student_id=child.id, report_type=ReportType.stage),
    ]
    for row in rows:
        session.add(row)
    session.commit()
    return parent, child, invite


def test_delete_test_accounts_removes_account_family_and_dependent_rows(
    session, monkeypatch
):
    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    account = add_account(session, "qa-delete@example.com")
    parent, child, invite = seed_test_family_graph(session, account)
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as client:
        response = client.post(
            "/api/admin/alpha/accounts/delete-test",
            headers={"X-Alpha-Admin-Token": "secret"},
            json={
                "account_ids": [account.id],
                "confirm": "DELETE TEST ACCOUNTS",
            },
        )
        overview = client.get(
            "/api/admin/alpha/overview",
            headers={"X-Alpha-Admin-Token": "secret"},
        )

    assert response.status_code == 200
    assert response.json()["deleted_count"] == 1
    assert session.get(ParentAccount, account.id) is None
    assert session.get(ParentUser, parent.id) is None
    assert session.get(StudentProfile, child.id) is None
    assert session.get(AlphaInviteCode, invite.id) is None
    assert overview.status_code == 200
