"""
Test fixtures. Runs against the REAL dockerized Postgres (same DATABASE_URL as
dev) -- each test runs inside a transaction that is rolled back afterward, so
tests never leave data behind or depend on each other, but they do exercise real
SQL/pgvector behavior rather than mocks. Requires the `db` docker-compose service
to be up (see README "running tests").
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import get_db
from app.main import app


@pytest.fixture(scope="session")
def engine():
    settings = get_settings()
    return create_engine(settings.database_url, future=True)


@pytest.fixture()
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, future=True)
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
