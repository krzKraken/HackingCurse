from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.learning import engine
from app.models.mastery import ConceptMastery, ReviewSchedule
from app.models.question import QuestionType
from app.models.review import ReviewItem, ReviewOutcome

ROLLING_WINDOW = 5


def _get_or_create_mastery(db: Session, user_id, concept_id) -> ConceptMastery:
    mastery = (
        db.query(ConceptMastery)
        .filter(ConceptMastery.user_id == user_id, ConceptMastery.concept_id == concept_id)
        .first()
    )
    if mastery is None:
        mastery = ConceptMastery(user_id=user_id, concept_id=concept_id, mastery_score=0.0)
        db.add(mastery)
        db.flush()
    return mastery


def _finalize_item(db: Session, item: ReviewItem, outcome: str) -> None:
    now = datetime.now(timezone.utc)
    item.outcome = ReviewOutcome(outcome)
    item.answered_at = now

    mastery = _get_or_create_mastery(db, item.review_session.user_id, item.concept_id)
    mastery.last_seen = now
    mastery.last_tested = now

    schedule = mastery.schedule
    old_stability = schedule.stability_days if schedule else engine.INITIAL_STABILITY_DAYS
    new_stability = engine.update_stability(old_stability, outcome)
    next_due = engine.compute_next_due_at(new_stability, now)

    if schedule is None:
        schedule = ReviewSchedule(
            concept_mastery_id=mastery.id, stability_days=new_stability, next_due_at=next_due
        )
        db.add(schedule)
    else:
        schedule.stability_days = new_stability
        schedule.next_due_at = next_due

    recent_outcomes = (
        db.query(ReviewItem.outcome)
        .filter(ReviewItem.concept_id == item.concept_id, ReviewItem.outcome.isnot(None))
        .order_by(ReviewItem.answered_at.desc())
        .limit(ROLLING_WINDOW)
        .all()
    )
    mastery.mastery_score = engine.rolling_mastery_score([o[0].value for o in recent_outcomes])

    db.commit()


def submit_answer(db: Session, item: ReviewItem, user_response: str, confidence_declared: str | None) -> dict:
    item.user_response = user_response
    item.confidence_declared = confidence_declared

    variant = item.question_variant
    question = variant.question

    if question.type == QuestionType.multiple_choice:
        outcome = "correct" if str(variant.correct_option_index) == user_response else "incorrect"
        _finalize_item(db, item, outcome)
        return {"outcome": outcome, "correct_option_index": variant.correct_option_index}

    if question.type == QuestionType.true_false:
        outcome = "correct" if str(variant.correct_bool).lower() == user_response.lower() else "incorrect"
        _finalize_item(db, item, outcome)
        return {"outcome": outcome, "correct_bool": variant.correct_bool}

    db.commit()
    return {"evaluation_criteria": question.evaluation_criteria, "expected_answer": question.expected_answer}


def submit_self_rate(db: Session, item: ReviewItem, outcome: str) -> dict:
    _finalize_item(db, item, outcome)
    return {"outcome": outcome}
