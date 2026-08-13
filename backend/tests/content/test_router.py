from tests.content.test_service import _seed_minimal


def _login_as_owner(client, db_session):
    import pyotp

    from app.auth.security import hash_password
    from app.auth.totp import generate_totp_secret
    from app.models.user import User

    secret = generate_totp_secret()
    user = User(username="owner", password_hash=hash_password("s3cret-pass-1"), totp_secret=secret)
    db_session.add(user)
    db_session.commit()

    client.post("/api/v1/auth/login", json={"username": "owner", "password": "s3cret-pass-1"})
    code = pyotp.TOTP(secret).now()
    client.post("/api/v1/auth/mfa/verify", json={"code": code})


def test_list_domains_requires_auth(client):
    resp = client.get("/api/v1/content/domains")
    assert resp.status_code == 401


def test_list_domains_returns_seeded_tree(client, db_session):
    _seed_minimal(db_session)
    _login_as_owner(client, db_session)

    resp = client.get("/api/v1/content/domains")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["slug"] == "networking"


def test_get_concept_returns_404_for_unknown_slug(client, db_session):
    _login_as_owner(client, db_session)

    resp = client.get("/api/v1/content/concepts/does-not-exist")
    assert resp.status_code == 404


def test_get_concept_returns_lesson_for_known_slug(client, db_session):
    _seed_minimal(db_session)
    _login_as_owner(client, db_session)

    resp = client.get("/api/v1/content/concepts/net-02")
    assert resp.status_code == 200
    body = resp.json()
    assert body["lesson"]["regla_mental"] == "MAC = a quien se lo entrego."
    assert body["relationships"]["prerequisites"][0]["slug"] == "net-01"
