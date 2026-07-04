from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import get_db_session, get_session_factory
from app.domain.enums import StudentPersona
from app.domain.models import (
    AbilityProfile,
    ParentAccount,
    ParentSession,
    ParentUser,
    StudentProfile,
    utcnow,
)
from app.main import create_app
from app.services.auth_security import hash_secret


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def force_mock_llm_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")


@pytest.fixture(autouse=True)
def force_test_auth_settings(monkeypatch, request):
    if request.node.get_closest_marker("no_test_auth_settings"):
        return

    monkeypatch.setenv("AUTH_SECRET_PEPPER", "test-pepper")
    monkeypatch.setenv("AUTH_SESSION_COOKIE_NAME", "wenlingo_parent_session")
    monkeypatch.setenv("AUTH_SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("AUTH_SESSION_DAYS", "30")
    monkeypatch.setenv("AUTH_SESSION_LAST_SEEN_THROTTLE_MINUTES", "15")


@pytest.fixture
def client(session, force_mock_llm_provider):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_session_factory] = lambda: (
        lambda: Session(session.get_bind())
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_authenticated_family(
    session: Session,
    *,
    token: str = "session-token",
    account_email: str = "parent@example.com",
    parent_id: str = "parent-1",
    parent_email: str = "parent@example.com",
    child_id: str = "student-1",
    child_name: str = "小星",
    grade_label: str = "四年级",
):
    account = ParentAccount(
        email_normalized=account_email,
        email_verified_at=utcnow(),
        last_login_at=utcnow(),
    )
    session.add(account)
    session.flush()

    parent = ParentUser(
        id=parent_id,
        email=parent_email,
        display_name="Alpha Parent",
        account_id=account.id,
        account_linked_at=utcnow(),
    )
    session.add(parent)
    session.flush()

    student = StudentProfile(
        id=child_id,
        parent_id=parent.id,
        name=child_name,
        grade_label=grade_label,
        persona=StudentPersona.real_child,
        is_real_child=True,
    )
    session.add(student)
    session.add(
        AbilityProfile(
            student_id=student.id,
            expression=44,
            observation=38,
            structure=42,
            revision=36,
        )
    )

    parent_session = ParentSession(
        account_id=account.id,
        token_hash=hash_secret(
            token,
            purpose="session-token",
            pepper="test-pepper",
        ),
        expires_at=utcnow() + timedelta(days=30),
    )
    session.add(parent_session)
    session.commit()
    session.refresh(account)
    session.refresh(parent)
    session.refresh(student)
    session.refresh(parent_session)

    return {
        "account": account,
        "parent": parent,
        "student": student,
        "session": parent_session,
        "token": token,
        "cookie": {"wenlingo_parent_session": token},
    }


def create_second_authenticated_family(session: Session):
    return create_authenticated_family(
        session,
        token="second-session-token",
        account_email="other-parent@example.com",
        parent_id="parent-2",
        parent_email="other-parent@example.com",
        child_id="student-2",
        child_name="小月",
    )
