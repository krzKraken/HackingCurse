from datetime import datetime, timezone

from app.models.content import Concept, Domain, Topic
from app.models.mastery import ConceptMastery
from app.models.question import Question, QuestionStatus, QuestionType, QuestionVariant
from app.models.review import ReviewItem, ReviewSession
from app.models.user import User
from app.reviews import grading


def _seed_user(db):
    user = User(username="owner", password_hash="x", totp_secret="x")
    db.add(user)
    db.commit()
    return user


def _seed_concept(db):
    domain = Domain(slug="networking", name="Networking")
    db.add(domain)
    db.flush()
    topic = Topic(domain_id=domain.id, slug="fundamentals", name="Fundamentos")
    db.add(topic)
    db.flush()
    concept = Concept(topic_id=topic.id, slug="net-01", name="Fundamentos de Redes")
    db.add(concept)
    db.commit()
    return concept


def _seed_mc_question(db, concept):
    question = Question(
        concept_id=concept.id, type=QuestionType.multiple_choice, difficulty=1, status=QuestionStatus.published
    )
    db.add(question)
    db.flush()
    variant = QuestionVariant(question_id=question.id, prompt_markdown="?", options=["a", "b"], correct_option_index=1)
    db.add(variant)
    db.commit()
    return question, variant


def _seed_free_question(db, concept):
    question = Question(
        concept_id=concept.id,
        type=QuestionType.free_explanation,
        difficulty=2,
        evaluation_criteria="debe mencionar X",
        expected_answer="respuesta modelo",
        status=QuestionStatus.published,
    )
    db.add(question)
    db.flush()
    variant = QuestionVariant(question_id=question.id, prompt_markdown="Explica X")
    db.add(variant)
    db.commit()
    return question, variant


def _create_item(db, user, concept, variant):
    session = ReviewSession(user_id=user.id, mode="general", started_at=datetime.now(timezone.utc))
    db.add(session)
    db.flush()
    item = ReviewItem(
        review_session_id=session.id,
        concept_id=concept.id,
        question_variant_id=variant.id,
        shown_at=datetime.now(timezone.utc),
    )
    db.add(item)
    db.commit()
    return item


def test_submit_answer_multiple_choice_correct_creates_mastery_and_schedule(db_session):
    user = _seed_user(db_session)
    concept = _seed_concept(db_session)
    _, variant = _seed_mc_question(db_session, concept)
    item = _create_item(db_session, user, concept, variant)

    result = grading.submit_answer(db_session, item, "1", "seguro")

    assert result["outcome"] == "correct"
    mastery = db_session.query(ConceptMastery).filter_by(user_id=user.id, concept_id=concept.id).one()
    assert mastery.mastery_score == 100.0
    assert mastery.schedule is not None
    assert mastery.schedule.stability_days > grading.engine.INITIAL_STABILITY_DAYS


def test_submit_answer_multiple_choice_incorrect(db_session):
    user = _seed_user(db_session)
    concept = _seed_concept(db_session)
    _, variant = _seed_mc_question(db_session, concept)
    item = _create_item(db_session, user, concept, variant)

    result = grading.submit_answer(db_session, item, "0", None)

    assert result["outcome"] == "incorrect"


def test_submit_answer_free_explanation_returns_criteria_without_outcome(db_session):
    user = _seed_user(db_session)
    concept = _seed_concept(db_session)
    _, variant = _seed_free_question(db_session, concept)
    item = _create_item(db_session, user, concept, variant)

    result = grading.submit_answer(db_session, item, "mi respuesta", None)

    assert result == {"evaluation_criteria": "debe mencionar X", "expected_answer": "respuesta modelo"}
    assert item.outcome is None


def test_submit_self_rate_finalizes_free_explanation(db_session):
    user = _seed_user(db_session)
    concept = _seed_concept(db_session)
    _, variant = _seed_free_question(db_session, concept)
    item = _create_item(db_session, user, concept, variant)
    grading.submit_answer(db_session, item, "mi respuesta", None)

    result = grading.submit_self_rate(db_session, item, "partial")

    assert result == {"outcome": "partial"}
    mastery = db_session.query(ConceptMastery).filter_by(user_id=user.id, concept_id=concept.id).one()
    assert mastery.mastery_score == 50.0
