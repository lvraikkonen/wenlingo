from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import Settings, get_settings


def create_engine_from_settings(settings: Settings):
    return create_engine(settings.database_url, echo=False, pool_pre_ping=True)


engine = create_engine_from_settings(get_settings())


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
