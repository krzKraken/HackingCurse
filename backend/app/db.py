from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    # psycopg3 auto-prepares statements after a few executions on the same
    # connection. Our test suite drops/recreates tables around every test
    # (Base.metadata.create_all/drop_all), which invalidates any prepared
    # plan still cached on a pooled connection ("cached plan must not
    # change result type"). Disabling server-side prepare avoids that class
    # of error; the perf cost is negligible at this project's scale.
    connect_args={"prepare_threshold": None},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
