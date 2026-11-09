# pytest can read automatically from this file
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.base import Base
from app.main import app

# setup isolated in-memory SQlite for testing

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


#  Database Fixture: Creates clean tables before every test, drops them after
@pytest.fixture(scope="function")
def db_session():
    # Create all tables in the temporary database
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables so the next test starts with a 100% clean slate
        Base.metadata.drop_all(bind=engine)


# 3. Client Fixture: Replaces the real database with the test database
@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Instruct FastAPI: Whenever an endpoint asks for get_db, give it override_get_db instead
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clear overrides after the test completes
    app.dependency_overrides.clear()
