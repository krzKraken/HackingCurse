from datetime import datetime, timedelta, timezone

from app.dashboard import service
from app.models.content import Concept, Domain, Topic
from app.models.mastery import ConceptMastery, ReviewSchedule
from app.models.question import Question, QuestionStatus, QuestionType, QuestionVariant
from app.models.review import ReviewItem, ReviewOutcome, ReviewSession
from app.models.user import User


def _seed_user(db):
    user = User(username="owner", password_hash="x", totp_secret="x")
    db.add(user)
    db.commit()
    return user


def _seed_concept_with_question(db, domain_slug, topic_slug, concept_slug):
    domain = db.query(Domain).filter_by(slug=domain_slug).first()
    if domain is None:
        domain = Domain(slug=domain_slug, name=domain_slug)
        db.add(domain)
        db.flush()
    topic = db.query(Topic).filter_by(domain_id=domain.id, slug=topic_slug).first()
    if topic is None:
        topic = Topic(domain_id=domain.id, slug=topic_slug, name=topic_slug)
        db.add(topic)
        db.flush()
    concept = Concept(topic_id=topic.id, slug=concept_slug, name=concept_slug)
    db.add(concept)
    db.flush()
    question = Question(
        concept_id=concept.id, type=QuestionType.true_false, difficulty=1, status=QuestionStatus.published
    )
    db.add(question)
    db.flush()
    variant = QuestionVariant(question_id=question.id, prompt_markdown="?", correct_bool=True)
    db.add(variant)
    db.commit()
    return concept


def test_global_mastery_is_zero_with_no_history(db_session):
    user = _seed_user(db_session)
    assert service.get_global_mastery(db_session, user.id) == 0.0


def test_global_mastery_averages_all_concept_masteries(db_session):
    user = _seed_user(db_session)
    c1 = _seed_concept_with_question(db_session, "networking", "t1", "c1")
    c2 = _seed_concept_with_question(db_session, "networking", "t1", "c2")
    db_session.add(ConceptMastery(user_id=user.id, concept_id=c1.id, mastery_score=80.0))
    db_session.add(ConceptMastery(user_id=user.id, concept_id=c2.id, mastery_score=40.0))
    db_session.commit()

    assert service.get_global_mastery(db_session, user.id) == 60.0


def test_domains_summary_reports_studied_and_total(db_session):
    user = _seed_user(db_session)
    c1 = _seed_concept_with_question(db_session, "networking", "t1", "c1")
    _seed_concept_with_question(db_session, "networking", "t1", "c2")
    db_session.add(ConceptMastery(user_id=user.id, concept_id=c1.id, mastery_score=100.0))
    db_session.commit()

    domains = service.get_domains_summary(db_session, user.id)

    net = next(d for d in domains if d["slug"] == "networking")
    assert net["studied_count"] == 1
    assert net["total_count"] == 2
    assert net["mastery_percent"] == 100.0


def test_domain_with_no_studied_concepts_has_zero_mastery(db_session):
    user = _seed_user(db_session)
    _seed_concept_with_question(db_session, "networking", "t1", "c1")

    domains = service.get_domains_summary(db_session, user.id)

    net = next(d for d in domains if d["slug"] == "networking")
    assert net["studied_count"] == 0
    assert net["mastery_percent"] == 0.0


def test_reviews_due_count_and_overdue(db_session):
    user = _seed_user(db_session)
    c1 = _seed_concept_with_question(db_session, "networking", "t1", "c1")
    mastery = ConceptMastery(user_id=user.id, concept_id=c1.id, mastery_score=50.0)
    db_session.add(mastery)
    db_session.flush()
    past = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.add(ReviewSchedule(concept_mastery_id=mastery.id, stability_days=5.0, next_due_at=past))
    db_session.commit()

    assert service.get_reviews_due_count(db_session, user.id) == 1
    overdue = service.get_overdue_concepts(db_session, user.id)
    assert overdue[0]["slug"] == "c1"


def test_weak_concepts_sorted_ascending(db_session):
    user = _seed_user(db_session)
    c1 = _seed_concept_with_question(db_session, "networking", "t1", "c1")
    c2 = _seed_concept_with_question(db_session, "networking", "t1", "c2")
    db_session.add(ConceptMastery(user_id=user.id, concept_id=c1.id, mastery_score=90.0))
    db_session.add(ConceptMastery(user_id=user.id, concept_id=c2.id, mastery_score=10.0))
    db_session.commit()

    weak = service.get_weak_concepts(db_session, user.id)

    assert weak[0]["slug"] == "c2"


def test_recent_activity_orders_by_answered_at_desc(db_session):
    user = _seed_user(db_session)
    concept = _seed_concept_with_question(db_session, "networking", "t1", "c1")
    question = db_session.query(Question).filter_by(concept_id=concept.id).first()
    variant = question.variants[0]

    session = ReviewSession(user_id=user.id, mode="general", started_at=datetime.now(timezone.utc))
    db_session.add(session)
    db_session.flush()

    now = datetime.now(timezone.utc)
    db_session.add(
        ReviewItem(
            review_session_id=session.id,
            concept_id=concept.id,
            question_variant_id=variant.id,
            shown_at=now,
            answered_at=now - timedelta(minutes=5),
            outcome=ReviewOutcome.correct,
        )
    )
    db_session.add(
        ReviewItem(
            review_session_id=session.id,
            concept_id=concept.id,
            question_variant_id=variant.id,
            shown_at=now,
            answered_at=now,
            outcome=ReviewOutcome.incorrect,
        )
    )
    db_session.commit()

    activity = service.get_recent_activity(db_session, user.id)

    assert activity[0]["outcome"] == "incorrect"
    assert activity[1]["outcome"] == "correct"
