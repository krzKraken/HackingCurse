import pyotp

from app.auth.security import hash_password
from app.auth.totp import generate_totp_secret
from app.models.content import Concept, Domain, Topic
from app.models.user import User


def _login_as_owner(client, db_session):
    secret = generate_totp_secret()
    user = User(username="owner", password_hash=hash_password("s3cret-pass-1"), totp_secret=secret)
    db_session.add(user)
    db_session.commit()

    client.post("/api/v1/auth/login", json={"username": "owner", "password": "s3cret-pass-1"})
    code = pyotp.TOTP(secret).now()
    client.post("/api/v1/auth/mfa/verify", json={"code": code})


def _seed_concept(db_session):
    domain = Domain(slug="networking", name="Networking")
    db_session.add(domain)
    db_session.flush()
    topic = Topic(domain_id=domain.id, slug="fundamentals", name="Fundamentos")
    db_session.add(topic)
    db_session.flush()
    concept = Concept(topic_id=topic.id, slug="net-01", name="Fundamentos de Redes")
    db_session.add(concept)
    db_session.commit()
    return concept


def test_notes_require_auth(client):
    assert client.get("/api/v1/notes").status_code == 401


def test_create_list_update_delete_global_note(client, db_session):
    _login_as_owner(client, db_session)

    create_resp = client.post("/api/v1/notes", json={"title": "Nota", "body_markdown": "cuerpo"})
    assert create_resp.status_code == 201
    note_id = create_resp.json()["id"]

    list_resp = client.get("/api/v1/notes")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    update_resp = client.put(f"/api/v1/notes/{note_id}", json={"title": "Nota", "body_markdown": "actualizado"})
    assert update_resp.status_code == 200
    assert update_resp.json()["body_markdown"] == "actualizado"

    delete_resp = client.delete(f"/api/v1/notes/{note_id}")
    assert delete_resp.status_code == 204
    assert client.get(f"/api/v1/notes/{note_id}").status_code == 404


def test_note_by_concept_upsert_flow(client, db_session):
    concept = _seed_concept(db_session)
    _login_as_owner(client, db_session)

    assert client.get(f"/api/v1/notes/by-concept/{concept.slug}").status_code == 404

    put_resp = client.put(
        f"/api/v1/notes/by-concept/{concept.slug}",
        json={"title": "Mis notas", "body_markdown": "primera versión"},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["linked_concept_slug"] == concept.slug

    get_resp = client.get(f"/api/v1/notes/by-concept/{concept.slug}")
    assert get_resp.status_code == 200
    assert get_resp.json()["body_markdown"] == "primera versión"

    client.put(
        f"/api/v1/notes/by-concept/{concept.slug}",
        json={"title": "Mis notas", "body_markdown": "segunda versión"},
    )
    assert len(client.get("/api/v1/notes").json()) == 1


def test_note_by_concept_unknown_slug_returns_404(client, db_session):
    _login_as_owner(client, db_session)
    resp = client.put(
        "/api/v1/notes/by-concept/does-not-exist", json={"title": "t", "body_markdown": "b"}
    )
    assert resp.status_code == 404
