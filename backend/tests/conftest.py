import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://cyberlearn:cyberlearn@localhost:55432/cyberlearn_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/1")
os.environ.setdefault("COOKIE_SECURE", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.sessions import redis_client
from app.config import settings
from app.db import Base, get_db
from app.main import app

engine = create_engine(settings.database_url)
TestSessionLocal = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def _clean_state():
    Base.metadata.create_all(engine)
    redis_client.flushdb()
    yield
    Base.metadata.drop_all(engine)
    redis_client.flushdb()


@pytest.fixture
def db_session():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
