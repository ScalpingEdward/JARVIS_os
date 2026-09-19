from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def initialize_database() -> None:
    from . import db_models  # noqa: F401

    Base.metadata.create_all(engine)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


initialize_database()


class ProductionResetRefused(RuntimeError):
    """Raised instead of wiping a live database."""


def refuse_reset_in_production(what: str) -> None:
    """Guard every reset() that deletes whole tables.

    Learned the hard way on 2026-09-19: a pytest file was executed inside
    the running api container to reach its ffmpeg, and its fixture called
    MediaPoolService().reset(). That container is wired to the real
    Postgres, so the "clean slate for the test" deleted 223 analysed pool
    items and 50 curated drafts -- analyses that had been paid for.

    The tests genuinely need reset(); production never does. The two are
    distinguishable, and this is the line: ENVIRONMENT=production (set in
    docker-compose) refuses, anything else proceeds. A guard beats
    remembering to be careful, because the careless path was the
    convenient one.
    """
    from app.config import get_settings

    if get_settings().environment.lower() == "production":
        raise ProductionResetRefused(
            f"refusing to reset {what} against the production database. "
            f"Run tests outside the api container, or against a scratch database."
        )
