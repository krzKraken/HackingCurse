from datetime import datetime, timedelta, timezone

from app.focus import recommendation
from app.models.content import Concept, ConceptRelationship, Domain, RelationshipType, Topic
from app.models.mastery import ConceptMastery, ReviewSchedule
from app.models.question import Question, QuestionStatus, QuestionType, QuestionVariant
from app.models.user import User


def _seed_user(db):
    user = User(username="owner", password_hash="x", totp_secret="x")
    db.add(user)
    db.commit()
    return user


def _seed_concept(db, slug, prereq=None):
    domain = db.query(Domain).filter_by(slug="networking").first()
    if domain is None:
        domain = Domain(slug="networking", name="Networking")
        db.add(domain)
        db.flush()
    topic = db.query(Topic).filter_by(domain_id=domain.id, slug="t1").first()
    if topic is None:
        topic = Topic(domain_id=domain.id, slug="t1", name="t1")
        db.add(topic)
        db.flush()
    concept = Concept(topic_id=topic.id, slug=slug, name=slug)
    db.add(concept)
    db.flush()
    question = Question(
        concept_id=concept.id, type=QuestionType.true_false, difficulty=1, status=QuestionStatus.published
    )
    db.add(question)
    db.flush()
    db.add(QuestionVariant(question_id=question.id, prompt_markdown="?", correct_bool=True))
    if prereq is not None:
        db.add(ConceptRelationship(source_id=concept.id, target_id=prereq.id, type=RelationshipType.prerequisite))
    db.commit()
    return concept


def test_recommends_next_concept_for_fresh_user(db_session):
    user = _seed_user(db_session)
    _seed_concept(db_session, "net-01")

    rec = recommendation.get_recommendation(db_session, user.id)

    assert rec["activity_type"] == "learn"
    assert rec["concept_slug"] == "net-01"


def test_does_not_recommend_concept_with_unmet_prerequisite(db_session):
    user = _seed_user(db_session)
    c1 = _seed_concept(db_session, "net-01")
    _seed_concept(db_session, "net-02", prereq=c1)

    rec = recommendation.get_recommendation(db_session, user.id)

    assert rec["concept_slug"] == "net-01"


def test_recommends_next_concept_once_prerequisite_satisfied(db_session):
    user = _seed_user(db_session)
    c1 = _seed_concept(db_session, "net-01")
    _seed_concept(db_session, "net-02", prereq=c1)
    db_session.add(ConceptMastery(user_id=user.id, concept_id=c1.id, mastery_score=100.0))
    db_session.commit()

    rec = recommendation.get_recommendation(db_session, user.id)

    assert rec["concept_slug"] == "net-02"


def test_prioritizes_overdue_review_over_new_concept(db_session):
    user = _seed_user(db_session)
    c1 = _seed_concept(db_session, "net-01")
    _seed_concept(db_session, "net-02")
    mastery = ConceptMastery(
        user_id=user.id,
        concept_id=c1.id,
        mastery_score=80.0,
        last_tested=datetime.now(timezone.utc) - timedelta(days=10),
    )
    db_session.add(mastery)
    db_session.flush()
    db_session.add(
        ReviewSchedule(
            concept_mastery_id=mastery.id,
            stability_days=1.0,
            next_due_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    db_session.commit()

    rec = recommendation.get_recommendation(db_session, user.id)

    assert rec["activity_type"] == "review"
    assert rec["concept_slug"] == "net-01"


def test_returns_none_when_no_content_exists(db_session):
    user = _seed_user(db_session)
    assert recommendation.get_recommendation(db_session, user.id) is None
