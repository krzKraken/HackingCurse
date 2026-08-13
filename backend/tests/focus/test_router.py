import pyotp

from app.auth.security import hash_password
from app.auth.totp import generate_totp_secret
from app.models.user import User


def _login_as_owner(client, db_session):
    secret = generate_totp_secret()
    user = User(username="owner", password_hash=hash_password("s3cret-pass-1"), totp_secret=secret)
    db_session.add(user)
    db_session.commit()

    client.post("/api/v1/auth/login", json={"username": "owner", "password": "s3cret-pass-1"})
    code = pyotp.TOTP(secret).now()
    client.post("/api/v1/auth/mfa/verify", json={"code": code})
    return user


def test_sessions_require_auth(client):
    assert client.post("/api/v1/focus/sessions").status_code == 401


def test_start_get_update_end_session_flow(client, db_session):
    _login_as_owner(client, db_session)

    start_resp = client.post("/api/v1/focus/sessions")
    assert start_resp.status_code == 200
    session_id = start_resp.json()["id"]

    current_resp = client.get("/api/v1/focus/sessions/current")
    assert current_resp.status_code == 200
    assert current_resp.json()["id"] == session_id

    update_resp = client.patch(
        f"/api/v1/focus/sessions/{session_id}",
        json={"active_time_sec": 90, "last_position": "/lessons/net-01"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["active_time_sec"] == 90

    end_resp = client.post(f"/api/v1/focus/sessions/{session_id}/end")
    assert end_resp.status_code == 200
    assert end_resp.json()["ended_at"] is not None

    assert client.get("/api/v1/focus/sessions/current").status_code == 404


def test_recommendation_returns_204_with_no_content(client, db_session):
    _login_as_owner(client, db_session)
    resp = client.get("/api/v1/focus/recommendation")
    assert resp.status_code == 204
