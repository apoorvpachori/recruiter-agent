"""SQLModel engine/session configuration for local SQLite persistence."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, event
from sqlmodel import Session, SQLModel, create_engine

from recruiter_agent.settings import get_settings


def _create_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine with SQLite foreign keys enabled."""
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)

    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide database engine."""
    return _create_engine(get_settings().database_url)


def get_db_session() -> Generator[Session]:
    """FastAPI dependency yielding one short-lived database session."""
    with Session(get_engine()) as session:
        yield session


def create_schema(engine: Engine | None = None) -> None:
    """Create the minimal schema for the local MVP."""
    from recruiter_agent.jobs.repository import Job  # noqa: F401

    SQLModel.metadata.create_all(engine or get_engine())
