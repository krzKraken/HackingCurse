from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.content import Concept, Domain, Topic
from app.models.mastery import ConceptMastery, ReviewSchedule
from app.models.question import Question, QuestionStatus
from app.models.review import ReviewItem, ReviewSession


def get_global_mastery(db: Session, user_id) -> float:
    masteries = db.query(ConceptMastery).filter(ConceptMastery.user_id == user_id).all()
    if not masteries:
        return 0.0
    return sum(m.mastery_score for m in masteries) / len(masteries)


def get_domains_summary(db: Session, user_id) -> list[dict]:
    domains = db.query(Domain).order_by(Domain.name).all()
    result = []
    for domain in domains:
        total_count = (
            db.query(Concept)
            .join(Topic, Concept.topic_id == Topic.id)
            .join(Question, Question.concept_id == Concept.id)
            .filter(Topic.domain_id == domain.id, Question.status == QuestionStatus.published)
            .distinct()
            .count()
        )
        masteries = (
            db.query(ConceptMastery)
            .join(Concept, ConceptMastery.concept_id == Concept.id)
            .join(Topic, Concept.topic_id == Topic.id)
            .filter(Topic.domain_id == domain.id, ConceptMastery.user_id == user_id)
            .all()
        )
        studied_count = len(masteries)
        mastery_percent = sum(m.mastery_score for m in masteries) / studied_count if studied_count else 0.0
        result.append(
            {
                "slug": domain.slug,
                "name": domain.name,
                "mastery_percent": mastery_percent,
                "studied_count": studied_count,
                "total_count": total_count,
            }
        )
    return result


def get_reviews_due_count(db: Session, user_id) -> int:
    now = datetime.now(timezone.utc)
    return (
        db.query(ReviewSchedule)
        .join(ConceptMastery, ReviewSchedule.concept_mastery_id == ConceptMastery.id)
        .filter(ConceptMastery.user_id == user_id, ReviewSchedule.next_due_at <= now)
        .count()
    )


def get_weak_concepts(db: Session, user_id, limit: int = 5) -> list[dict]:
    masteries = (
        db.query(ConceptMastery)
        .filter(ConceptMastery.user_id == user_id)
        .order_by(ConceptMastery.mastery_score.asc())
        .limit(limit)
        .all()
    )
    return [{"slug": m.concept.slug, "name": m.concept.name, "mastery_score": m.mastery_score} for m in masteries]


def get_overdue_concepts(db: Session, user_id, limit: int = 5) -> list[dict]:
    now = datetime.now(timezone.utc)
    schedules = (
        db.query(ReviewSchedule)
        .join(ConceptMastery, ReviewSchedule.concept_mastery_id == ConceptMastery.id)
        .filter(ConceptMastery.user_id == user_id, ReviewSchedule.next_due_at <= now)
        .order_by(ReviewSchedule.next_due_at.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "slug": s.concept_mastery.concept.slug,
            "name": s.concept_mastery.concept.name,
            "next_due_at": s.next_due_at,
        }
        for s in schedules
    ]


def get_recent_activity(db: Session, user_id, limit: int = 10) -> list[dict]:
    items = (
        db.query(ReviewItem)
        .join(ReviewSession, ReviewItem.review_session_id == ReviewSession.id)
        .filter(ReviewSession.user_id == user_id, ReviewItem.outcome.isnot(None))
        .order_by(ReviewItem.answered_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "concept_slug": item.concept.slug,
            "concept_name": item.concept.name,
            "outcome": item.outcome.value,
            "answered_at": item.answered_at,
        }
        for item in items
    ]


def get_summary(db: Session, user_id) -> dict:
    return {
        "global_mastery": get_global_mastery(db, user_id),
        "domains": get_domains_summary(db, user_id),
        "reviews_due_count": get_reviews_due_count(db, user_id),
        "weak_concepts": get_weak_concepts(db, user_id),
        "overdue_concepts": get_overdue_concepts(db, user_id),
        "recent_activity": get_recent_activity(db, user_id),
    }
