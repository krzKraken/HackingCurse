from datetime import datetime, timezone

from app.models.content import Concept, Domain, Topic
from app.models.mastery import ConceptMastery
from app.models.question import Question, QuestionStatus, QuestionType, QuestionVariant
from app.models.review import ReviewItem, ReviewSession
from app.models.user import User
from app.reviews import selector


def _seed_user(db):
    user = User(username="owner", password_hash="x", totp_secret="x")
    db.add(user)
    db.commit()
    return user


def _seed_domain_topic(db, domain_slug="networking", topic_slug="fundamentals"):
    domain = Domain(slug=domain_slug, name=domain_slug)
    db.add(domain)
    db.flush()
    topic = Topic(domain_id=domain.id, slug=topic_slug, name=topic_slug)
    db.add(topic)
    db.flush()
    return domain, topic


def _seed_concept_with_question(db, topic, slug):
    concept = Concept(topic_id=topic.id, slug=slug, name=slug)
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
    return concept, variant


def test_general_mode_includes_never_studied_concepts(db_session):
    user = _seed_user(db_session)
    _, topic = _seed_domain_topic(db_session)
    concept, _ = _seed_concept_with_question(db_session, topic, "net-01")

    concepts = selector.select_concepts(db_session, user.id, "general")

    assert concept.id in [c.id for c in concepts]


def test_debilidades_mode_sorts_by_mastery_ascending(db_session):
    user = _seed_user(db_session)
    _, topic = _seed_domain_topic(db_session)
    weak, _ = _seed_concept_with_question(db_session, topic, "net-01")
    strong, _ = _seed_concept_with_question(db_session, topic, "net-02")

    db_session.add(ConceptMastery(user_id=user.id, concept_id=weak.id, mastery_score=20.0))
    db_session.add(ConceptMastery(user_id=user.id, concept_id=strong.id, mastery_score=90.0))
    db_session.commit()

    concepts = selector.select_concepts(db_session, user.id, "debilidades")

    assert [c.id for c in concepts[:2]] == [weak.id, strong.id]


def test_por_tema_filters_by_topic_slug(db_session):
    user = _seed_user(db_session)
    domain, topic_a = _seed_domain_topic(db_session, topic_slug="topic-a")
    topic_b = Topic(domain_id=domain.id, slug="topic-b", name="topic-b")
    db_session.add(topic_b)
    db_session.commit()
    concept_a, _ = _seed_concept_with_question(db_session, topic_a, "net-a")
    _seed_concept_with_question(db_session, topic_b, "net-b")

    concepts = selector.select_concepts(db_session, user.id, "por_tema", topic_slug="topic-a")

    assert [c.id for c in concepts] == [concept_a.id]


def test_pre_lab_filters_by_concept_slugs(db_session):
    user = _seed_user(db_session)
    _, topic = _seed_domain_topic(db_session)
    a, _ = _seed_concept_with_question(db_session, topic, "net-a")
    _seed_concept_with_question(db_session, topic, "net-b")

    concepts = selector.select_concepts(db_session, user.id, "pre_lab", concept_slugs=["net-a"])

    assert [c.id for c in concepts] == [a.id]


def test_pick_variant_avoids_recently_shown(db_session):
    user = _seed_user(db_session)
    _, topic = _seed_domain_topic(db_session)
    concept = Concept(topic_id=topic.id, slug="net-01", name="net-01")
    db_session.add(concept)
    db_session.flush()

    question = Question(
        concept_id=concept.id, type=QuestionType.true_false, difficulty=1, status=QuestionStatus.published
    )
    db_session.add(question)
    db_session.flush()
    variant_a = QuestionVariant(question_id=question.id, prompt_markdown="A", correct_bool=True)
    variant_b = QuestionVariant(question_id=question.id, prompt_markdown="B", correct_bool=True)
    db_session.add_all([variant_a, variant_b])
    db_session.commit()

    session = ReviewSession(user_id=user.id, mode="general", started_at=datetime.now(timezone.utc))
    db_session.add(session)
    db_session.flush()
    db_session.add(
        ReviewItem(
            review_session_id=session.id,
            concept_id=concept.id,
            question_variant_id=variant_a.id,
            shown_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    picked = selector.pick_variant(db_session, user.id, concept.id)

    assert picked.id == variant_b.id
