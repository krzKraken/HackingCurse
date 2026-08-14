import pyotp

from app.auth.security import hash_password
from app.auth.totp import generate_totp_secret
from app.models.content import Concept, Domain, Topic
from app.models.mastery import ConceptMastery
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


def test_dashboard_requires_auth(client):
    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 401


def test_dashboard_returns_summary_shape(client, db_session):
    user = _login_as_owner(client, db_session)

    domain = Domain(slug="networking", name="Networking")
    db_session.add(domain)
    db_session.flush()
    topic = Topic(domain_id=domain.id, slug="t1", name="t1")
    db_session.add(topic)
    db_session.flush()
    concept = Concept(topic_id=topic.id, slug="net-01", name="Fundamentos")
    db_session.add(concept)
    db_session.flush()
    question = Question(
        concept_id=concept.id, type=QuestionType.true_false, difficulty=1, status=QuestionStatus.published
    )
    db_session.add(question)
    db_session.flush()
    db_session.add(QuestionVariant(question_id=question.id, prompt_markdown="?", correct_bool=True))
    db_session.add(ConceptMastery(user_id=user.id, concept_id=concept.id, mastery_score=75.0))
    db_session.commit()

    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["global_mastery"] == 75.0
    assert body["domains"][0]["slug"] == "networking"


def test_dashboard_includes_hint_dependency_with_no_solved_labs(client, db_session):
    _login_as_owner(client, db_session)

    resp = client.get("/api/v1/dashboard/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["hint_dependency"] == {}
    assert body["independence_score"] is None


def test_dashboard_includes_hint_dependency_for_solved_lab(client, db_session):
    from datetime import datetime, timezone

    from app.models.lab import LabInstance, LabInstanceStatus, Laboratory

    user = _login_as_owner(client, db_session)

    laboratory = Laboratory(
        id="hint-dep-test-lab",
        title="Hint Dep Test Lab",
        type="black_box",
        difficulty="beginner",
        duration_estimate_min=10,
        docker_build_context="labs/flagbox",
        hints=[],
        cpu_limit="0.5",
        memory_limit_mb=128,
        max_lifetime_min=30,
        cleanup_remove_volumes=True,
    )
    db_session.add(laboratory)
    db_session.commit()

    instance = LabInstance(
        laboratory_id=laboratory.id,
        user_id=user.id,
        status=LabInstanceStatus.destroyed,
        context_seed={},
        requested_at=datetime.now(timezone.utc),
        solved=True,
        hints_used=0,
    )
    db_session.add(instance)
    db_session.commit()

    resp = client.get("/api/v1/dashboard/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["hint_dependency"] == {"0": 1}
    assert body["independence_score"] == 100.0


def test_dashboard_includes_gamification_fields_with_no_activity(client, db_session):
    _login_as_owner(client, db_session)

    resp = client.get("/api/v1/dashboard/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["xp_total"] == 0
    assert body["level"] == 1
    assert body["achievements"] == []


def test_dashboard_syncs_and_reports_achievement_after_solved_lab(client, db_session):
    from datetime import datetime, timezone

    from app.models.lab import Laboratory, LabInstance, LabInstanceStatus

    user = _login_as_owner(client, db_session)

    laboratory = Laboratory(
        id="gami-router-test-lab",
        title="Gami Router Test Lab",
        type="black_box",
        difficulty="beginner",
        duration_estimate_min=10,
        docker_build_context="labs/flagbox",
        hints=[],
        cpu_limit="0.5",
        memory_limit_mb=128,
        max_lifetime_min=30,
        cleanup_remove_volumes=True,
    )
    db_session.add(laboratory)
    db_session.commit()

    instance = LabInstance(
        laboratory_id=laboratory.id,
        user_id=user.id,
        status=LabInstanceStatus.destroyed,
        context_seed={},
        requested_at=datetime.now(timezone.utc),
        solved=True,
        hints_used=0,
    )
    db_session.add(instance)
    db_session.commit()

    resp = client.get("/api/v1/dashboard/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["xp_total"] > 0
    unlocked_keys = {a["key"] for a in body["achievements"]}
    assert "first_shell" in unlocked_keys
    assert "no_hint_required" in unlocked_keys
