import pyotp

from app.auth.security import hash_password
from app.auth.totp import generate_totp_secret
from app.models.user import User


def _create_user(db_session, username="owner", password="s3cret-pass-1"):
    secret = generate_totp_secret()
    user = User(username=username, password_hash=hash_password(password), totp_secret=secret)
    db_session.add(user)
    db_session.commit()
    return user, password, secret


def test_login_then_mfa_verify_grants_access(client, db_session):
    user, password, secret = _create_user(db_session)

    login_resp = client.post("/api/v1/auth/login", json={"username": user.username, "password": password})
    assert login_resp.status_code == 200
    assert login_resp.json()["mfa_required"] is True

    me_before_mfa = client.get("/api/v1/auth/me")
    assert me_before_mfa.status_code == 401

    code = pyotp.TOTP(secret).now()
    mfa_resp = client.post("/api/v1/auth/mfa/verify", json={"code": code})
    assert mfa_resp.status_code == 200
    assert mfa_resp.json()["username"] == user.username

    me_after_mfa = client.get("/api/v1/auth/me")
    assert me_after_mfa.status_code == 200


def test_login_wrong_password_rejected(client, db_session):
    user, _password, _secret = _create_user(db_session)

    resp = client.post("/api/v1/auth/login", json={"username": user.username, "password": "wrong"})
    assert resp.status_code == 401


def test_login_lockout_after_max_attempts(client, db_session):
    user, password, _secret = _create_user(db_session)

    for _ in range(5):
        client.post("/api/v1/auth/login", json={"username": user.username, "password": "wrong"})

    resp = client.post("/api/v1/auth/login", json={"username": user.username, "password": password})
    assert resp.status_code == 429


def test_logout_clears_session(client, db_session):
    user, password, secret = _create_user(db_session)
    client.post("/api/v1/auth/login", json={"username": user.username, "password": password})
    code = pyotp.TOTP(secret).now()
    client.post("/api/v1/auth/mfa/verify", json={"code": code})

    logout_resp = client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 204

    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == 401
