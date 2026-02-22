"""Tests for the Chuck Norris Jokes API."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Use SQLite for tests — fast, no external deps
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["ADMIN_SECRET"] = "test-admin-secret"

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

# Disable rate limiting for tests
app.state.limiter.enabled = False

engine = create_engine(
    "sqlite:///./test.db",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test and drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def api_key(client):
    """Generate a valid API key for testing."""
    resp = client.post(
        "/api-keys",
        json={"name": "test-key"},
        headers={"X-API-Key": "test-admin-secret"},
    )
    assert resp.status_code == 201
    return resp.json()["api_key"]


# ---- Health Check ----


class TestHealth:
    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "healthy"
        assert "timestamp" in data


# ---- Root ----


class TestRoot:
    def test_root_returns_welcome(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Chuck Norris" in resp.json()["message"]


# ---- Jokes - Read ----


class TestJokesRead:
    def _seed_joke(
        self, client, api_key, text="Chuck Norris can unit test in production."
    ):
        return client.post(
            "/jokes",
            json={"text": text},
            headers={"X-API-Key": api_key},
        )

    def test_list_jokes_empty(self, client):
        resp = client.get("/jokes")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_get_joke_by_id(self, client, api_key):
        create_resp = self._seed_joke(client, api_key)
        joke_id = create_resp.json()["id"]

        resp = client.get(f"/jokes/{joke_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == joke_id

    def test_get_joke_not_found(self, client):
        resp = client.get("/jokes/9999")
        assert resp.status_code == 404

    def test_random_joke_empty_db(self, client):
        resp = client.get("/jokes/random")
        assert resp.status_code == 404

    def test_random_joke_with_data(self, client, api_key):
        self._seed_joke(client, api_key)
        resp = client.get("/jokes/random")
        assert resp.status_code == 200
        assert "text" in resp.json()

    def test_list_jokes_pagination(self, client, api_key):
        for i in range(15):
            self._seed_joke(
                client,
                api_key,
                text=f"Chuck Norris joke number {i} is unique.",
            )

        resp = client.get("/jokes?page=1&per_page=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["jokes"]) == 10
        assert data["total"] == 15

        resp2 = client.get("/jokes?page=2&per_page=10")
        assert len(resp2.json()["jokes"]) == 5


# ---- Jokes - Write ----


class TestJokesWrite:
    def test_create_joke_requires_auth(self, client):
        resp = client.post("/jokes", json={"text": "A joke without auth."})
        assert resp.status_code == 401

    def test_create_joke_invalid_key(self, client):
        resp = client.post(
            "/jokes",
            json={"text": "A joke with bad key."},
            headers={"X-API-Key": "invalid-key"},
        )
        assert resp.status_code == 403

    def test_create_joke_success(self, client, api_key):
        resp = client.post(
            "/jokes",
            json={"text": "Chuck Norris can debug with his eyes closed."},
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["text"] == "Chuck Norris can debug with his eyes closed."
        assert "id" in data

    def test_create_joke_duplicate(self, client, api_key):
        joke = {"text": "Chuck Norris knows the last digit of pi."}
        client.post("/jokes", json=joke, headers={"X-API-Key": api_key})
        resp = client.post("/jokes", json=joke, headers={"X-API-Key": api_key})
        assert resp.status_code == 409

    def test_create_joke_too_short(self, client, api_key):
        resp = client.post(
            "/jokes",
            json={"text": "Short"},
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 422

    def test_create_joke_blank(self, client, api_key):
        resp = client.post(
            "/jokes",
            json={"text": "          "},
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 422


# ---- API Keys ----


class TestAPIKeys:
    def test_create_api_key_requires_admin(self, client):
        resp = client.post("/api-keys", json={"name": "hacker"})
        assert resp.status_code == 401

    def test_create_api_key_wrong_admin(self, client):
        resp = client.post(
            "/api-keys",
            json={"name": "hacker"},
            headers={"X-API-Key": "wrong-secret"},
        )
        assert resp.status_code == 403

    def test_create_api_key_success(self, client):
        resp = client.post(
            "/api-keys",
            json={"name": "my-app"},
            headers={"X-API-Key": "test-admin-secret"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "my-app"
        assert data["api_key"].startswith("cnj_")
        assert "Store this key" in data["message"]


# ---- Security ----


class TestSecurity:
    def test_request_id_header(self, client):
        resp = client.get("/health")
        assert "X-Request-ID" in resp.headers

    def test_sql_injection_attempt(self, client):
        resp = client.get("/jokes/1 OR 1=1")
        assert resp.status_code == 422  # FastAPI validates int param
