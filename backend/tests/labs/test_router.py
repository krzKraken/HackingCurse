import pyotp

from app.auth.security import hash_password
from app.auth.totp import generate_totp_secret
from app.models.lab import Laboratory, LabInstance
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


def _seed_laboratory(db_session):
    lab = Laboratory(
        id="net-tcp-flagbox-001",
        title="FlagBox",
        type="black_box",
        difficulty="beginner",
        duration_estimate_min=30,
        docker_build_context="labs/flagbox",
        hints=[{"level": 1, "text": "Conéctate con netcat"}],
        cpu_limit="0.5",
        memory_limit_mb=128,
        max_lifetime_min=120,
        cleanup_remove_volumes=True,
    )
    db_session.add(lab)
    db_session.commit()
    return lab


def test_labs_require_auth(client):
    assert client.get("/api/v1/labs").status_code == 401


def test_list_labs(client, db_session):
    _seed_laboratory(db_session)
    _login_as_owner(client, db_session)

    resp = client.get("/api/v1/labs")
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == "net-tcp-flagbox-001"


def test_create_instance_and_get_it(client, db_session):
    _seed_laboratory(db_session)
    _login_as_owner(client, db_session)

    create_resp = client.post("/api/v1/labs/net-tcp-flagbox-001/instances")
    assert create_resp.status_code == 200
    instance_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "requested"

    get_resp = client.get(f"/api/v1/labs/instances/{instance_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == instance_id


def test_get_hint_increments_hints_used(client, db_session):
    _seed_laboratory(db_session)
    _login_as_owner(client, db_session)

    instance_id = client.post("/api/v1/labs/net-tcp-flagbox-001/instances").json()["id"]

    hint_resp = client.get(f"/api/v1/labs/instances/{instance_id}/hints/1")
    assert hint_resp.status_code == 200
    assert hint_resp.json()["text"] == "Conéctate con netcat"

    get_resp = client.get(f"/api/v1/labs/instances/{instance_id}")
    assert get_resp.json()["hints_used"] == 1


def test_submit_flag_correct_and_incorrect(client, db_session):
    _seed_laboratory(db_session)
    _login_as_owner(client, db_session)

    instance_id = client.post("/api/v1/labs/net-tcp-flagbox-001/instances").json()["id"]

    instance = db_session.query(LabInstance).filter(LabInstance.id == instance_id).first()
    instance.context_seed = {"flag_token": "FLAG{test}"}
    db_session.commit()

    wrong_resp = client.post(f"/api/v1/labs/instances/{instance_id}/submit", json={"flag": "FLAG{wrong}"})
    assert wrong_resp.json() == {"correct": False, "solved": False}

    correct_resp = client.post(f"/api/v1/labs/instances/{instance_id}/submit", json={"flag": "FLAG{test}"})
    assert correct_resp.json() == {"correct": True, "solved": True}
