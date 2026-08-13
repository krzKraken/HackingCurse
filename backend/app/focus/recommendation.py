from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.learning import engine
from app.models.content import Concept, ConceptRelationship, RelationshipType
from app.models.mastery import ConceptMastery
from app.models.question import Question, QuestionStatus


def _concepts_with_questions(db: Session) -> list[Concept]:
    return (
        db.query(Concept)
        .join(Question, Question.concept_id == Concept.id)
        .filter(Question.status == QuestionStatus.published)
        .distinct()
        .all()
    )


def _mastery_map(db: Session, user_id, concept_ids: list) -> dict:
    if not concept_ids:
        return {}
    rows = (
        db.query(ConceptMastery)
        .filter(ConceptMastery.user_id == user_id, ConceptMastery.concept_id.in_(concept_ids))
        .all()
    )
    return {m.concept_id: m for m in rows}


def _prerequisites_satisfied(db: Session, concept_id, mastery_map: dict) -> bool:
    prereqs = (
        db.query(ConceptRelationship)
        .filter(
            ConceptRelationship.source_id == concept_id,
            ConceptRelationship.type == RelationshipType.prerequisite,
        )
        .all()
    )
    return all(rel.target_id in mastery_map for rel in prereqs)


def get_recommendation(db: Session, user_id, minutes: int = 15) -> dict | None:
    now = datetime.now(timezone.utc)
    concepts = _concepts_with_questions(db)
    if not concepts:
        return None
    mastery_map = _mastery_map(db, user_id, [c.id for c in concepts])

    due = []
    for c in concepts:
        mastery = mastery_map.get(c.id)
        if mastery is None or mastery.schedule is None:
            continue
        if mastery.schedule.next_due_at <= now:
            days = (now - mastery.last_tested).total_seconds() / 86400 if mastery.last_tested else 0
            risk = engine.forgetting_risk(mastery.schedule.stability_days, days)
            due.append((risk, c))
    if due:
        due.sort(key=lambda pair: pair[0], reverse=True)
        concept = due[0][1]
        return {
            "activity_type": "review",
            "concept_slug": concept.slug,
            "concept_name": concept.name,
            "reason": f"{concept.name} tiene retención baja y está vencido para repaso.",
        }

    if minutes >= 10:
        for c in concepts:
            if c.id in mastery_map:
                continue
            if _prerequisites_satisfied(db, c.id, mastery_map):
                return {
                    "activity_type": "learn",
                    "concept_slug": c.slug,
                    "concept_name": c.name,
                    "reason": f"{c.name} es el siguiente concepto en tu ruta — ya tienes los prerequisitos.",
                }

    studied = [(m.mastery_score, c) for c in concepts if (m := mastery_map.get(c.id)) is not None]
    if studied:
        studied.sort(key=lambda pair: pair[0])
        concept = studied[0][1]
        return {
            "activity_type": "review",
            "concept_slug": concept.slug,
            "concept_name": concept.name,
            "reason": f"{concept.name} es tu concepto más débil actualmente.",
        }

    return None
