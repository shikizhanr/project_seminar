from datetime import date, timedelta

from fastapi.testclient import TestClient


def test_health_and_auth(client: TestClient):
    assert client.get("/health").json() == {"status": "ok"}
    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "display_name": "User",
            "password": "strong-pass",
            "timezone": "Asia/Yekaterinburg",
        },
    )
    assert register.status_code == 201
    token = register.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"


def test_habit_check_in_risk_and_dashboard(client: TestClient, auth_headers: dict[str, str]):
    created = client.post(
        "/api/v1/habits",
        headers=auth_headers,
        json={
            "title": "Читать 20 минут",
            "target_days_per_week": 5,
            "difficulty": 2,
            "color": "#22C55E",
            "reminder_time": "09:30:00",
        },
    )
    assert created.status_code == 201
    habit_id = created.json()["id"]
    today_before = client.get("/api/v1/habits/today", headers=auth_headers)
    assert today_before.status_code == 200
    assert today_before.json()[0]["completed_today"] is False
    assert today_before.json()[0]["reminder_time"] == "09:30:00"
    initial_risk = client.get(f"/api/v1/habits/{habit_id}/risk", headers=auth_headers)
    assert initial_risk.status_code == 200
    assert initial_risk.json()["risk_level"] == "insufficient_data"
    assert initial_risk.json()["probability"] is None
    assert initial_risk.json()["observed_opportunities"] == 0
    for offset in range(3):
        checked = client.put(
            f"/api/v1/habits/{habit_id}/check-ins",
            headers=auth_headers,
            json={"day": (date.today() - timedelta(days=offset)).isoformat(), "mood": 4},
        )
        assert checked.status_code == 200

    today_after = client.get("/api/v1/habits/today", headers=auth_headers)
    assert today_after.json()[0]["completed_today"] is True

    risk = client.get(f"/api/v1/habits/{habit_id}/risk", headers=auth_headers)
    assert risk.status_code == 200
    assert risk.json()["risk_level"] == "completed"
    assert risk.json()["probability"] is None

    dashboard = client.get("/api/v1/analytics/dashboard", headers=auth_headers)
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert payload["active_habits"] == 1
    assert payload["completed_today"] == 1
    assert payload["habit_analytics"][0]["current_streak"] == 3
    assert len(payload["trend"]) == 14


def test_cannot_access_another_users_habit(client: TestClient, auth_headers: dict[str, str]):
    created = client.post("/api/v1/habits", headers=auth_headers, json={"title": "Private"})
    other = client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "display_name": "Other", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    response = client.get(f"/api/v1/habits/{created.json()['id']}/risk", headers=other_headers)
    assert response.status_code == 404


def test_telegram_link_is_persisted(client: TestClient, auth_headers: dict[str, str]):
    linked = client.put("/api/v1/bot/link", headers=auth_headers, json={"chat_id": 123456789})
    assert linked.status_code == 200
    assert linked.json()["chat_id"] == 123456789
    loaded = client.get("/api/v1/bot/link", headers=auth_headers)
    assert loaded.json() == {"chat_id": 123456789}
