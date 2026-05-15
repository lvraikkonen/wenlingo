import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import get_db_session
from app.main import create_app


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


@pytest.fixture
def client(session, force_mock_llm_provider):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
