from dataclasses import dataclass
from typing import Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.content import Concept, Domain, Topic
from app.models.focus import LearningSession
from app.models.lab import LabInstance
from app.models.mastery import ConceptMastery
from app.models.review import ReviewItem, ReviewOutcome, ReviewSession


@dataclass(frozen=True)
class Achievement:
    key: str
    title: str
    description: str
    xp_value: int
    check: Callable[[Session, object], bool]


def _check_first_shell(db: Session, user_id) -> bool:
    return db.query(LabInstance).filter(LabInstance.user_id == user_id, LabInstance.solved == True).count() >= 1


def _check_no_hint_required(db: Session, user_id) -> bool:
    return (
        db.query(LabInstance)
        .filter(LabInstance.user_id == user_id, LabInstance.solved == True, LabInstance.hints_used == 0)
        .count()
        >= 1
    )


def _check_independent_mind(db: Session, user_id) -> bool:
    return (
        db.query(LabInstance)
        .filter(LabInstance.user_id == user_id, LabInstance.solved == True, LabInstance.hints_used == 0)
        .count()
        >= 5
    )


def _check_persistent(db: Session, user_id) -> bool:
    return db.query(LabInstance).filter(LabInstance.user_id == user_id, LabInstance.solved == True).count() >= 10


def _check_perfect_recall(db: Session, user_id) -> bool:
    sessions = db.query(ReviewSession).filter(ReviewSession.user_id == user_id).all()
    for review_session in sessions:
        items = (
            db.query(ReviewItem)
            .filter(ReviewItem.review_session_id == review_session.id, ReviewItem.outcome.isnot(None))
            .all()
        )
        if len(items) >= 5 and all(item.outcome == ReviewOutcome.correct for item in items):
            return True
    return False


def _check_domain_mastery(db: Session, user_id) -> bool:
    domains = db.query(Domain).all()
    for domain in domains:
        masteries = (
            db.query(ConceptMastery)
            .join(Concept, ConceptMastery.concept_id == Concept.id)
            .join(Topic, Concept.topic_id == Topic.id)
            .filter(Topic.domain_id == domain.id, ConceptMastery.user_id == user_id)
            .all()
        )
        if masteries:
            average = sum(m.mastery_score for m in masteries) / len(masteries)
            if average >= 90:
                return True
    return False


def _check_deep_focus(db: Session, user_id) -> bool:
    total = (
        db.query(func.sum(LearningSession.active_time_sec))
        .filter(LearningSession.user_id == user_id)
        .scalar()
    )
    return (total or 0) >= 36000


ACHIEVEMENTS: list[Achievement] = [
    Achievement("first_shell", "First Shell", "Resolviste tu primer laboratorio.", 20, _check_first_shell),
    Achievement(
        "no_hint_required", "No Hint Required", "Resolviste un laboratorio sin usar pistas.", 15, _check_no_hint_required
    ),
    Achievement(
        "independent_mind",
        "Independent Mind",
        "Resolviste 5 laboratorios sin pistas.",
        50,
        _check_independent_mind,
    ),
    Achievement("persistent", "Persistent", "Resolviste 10 laboratorios.", 40, _check_persistent),
    Achievement(
        "perfect_recall",
        "Perfect Recall",
        "Completaste una sesión de repaso con 100% de aciertos (mínimo 5 preguntas).",
        25,
        _check_perfect_recall,
    ),
    Achievement(
        "domain_mastery", "Domain Mastery", "Alcanzaste 90% de nivel en un dominio.", 60, _check_domain_mastery
    ),
    Achievement(
        "deep_focus", "Deep Focus", "Acumulaste 10 horas de tiempo de estudio activo.", 30, _check_deep_focus
    ),
]
