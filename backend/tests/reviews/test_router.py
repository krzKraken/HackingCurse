import pyotp

from app.auth.security import hash_password
from app.auth.totp import generate_totp_secret
from app.models.content import Concept, Domain, Topic
from app.models.question import Question, QuestionStatus, QuestionType, QuestionVariant
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


def _seed_mc_concept(db_session):
    domain = Domain(slug="networking", name="Networking")
    db_session.add(domain)
    db_session.flush()
    topic = Topic(domain_id=domain.id, slug="fundamentals", name="Fundamentos")
    db_session.add(topic)
    db_session.flush()
    concept = Concept(topic_id=topic.id, slug="net-01", name="Fundamentos de Redes")
    db_session.add(concept)
    db_session.flush()
    question = Question(
        concept_id=concept.id, type=QuestionType.multiple_choice, difficulty=1, status=QuestionStatus.published
    )
    db_session.add(question)
    db_session.flush()
    variant = QuestionVariant(question_id=question.id, prompt_markdown="?", options=["a", "b"], correct_option_index=1)
    db_session.add(variant)
    db_session.commit()
    return concept


def test_create_session_requires_auth(client):
    resp = client.post("/api/v1/reviews/sessions", json={"mode": "general"})
    assert resp.status_code == 401


def test_create_session_does_not_leak_correct_answer(client, db_session):
    _seed_mc_concept(db_session)
    _login_as_owner(client, db_session)

    resp = client.post("/api/v1/reviews/sessions", json={"mode": "general"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert "correct_option_index" not in body["items"][0]


def test_answer_flow_multiple_choice(client, db_session):
    _seed_mc_concept(db_session)
    _login_as_owner(client, db_session)

    session_resp = client.post("/api/v1/reviews/sessions", json={"mode": "general"})
    item_id = session_resp.json()["items"][0]["item_id"]

    answer_resp = client.post(f"/api/v1/reviews/items/{item_id}/answer", json={"user_response": "1"})
    assert answer_resp.status_code == 200
    assert answer_resp.json()["outcome"] == "correct"
