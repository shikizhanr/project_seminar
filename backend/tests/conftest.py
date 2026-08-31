import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

TEST_DB = Path("/tmp/habit_coach_test.db")
TEST_DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-longer-than-32-bytes"
os.environ["OLLAMA_ENABLED"] = "false"

from backend.app.main import app  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    email = f"alex-{uuid4().hex}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "display_name": "Алекс",
            "password": "password123",
            "timezone": "Asia/Yekaterinburg",
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
