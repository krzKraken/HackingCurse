from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.content import Concept
from app.models.lab import Laboratory, LabInstance, LabInstanceStatus, LaboratoryConcept


def list_laboratories(db: Session) -> list[dict]:
    labs = db.query(Laboratory).all()
    result = []
    for lab in labs:
        slugs = (
            db.query(Concept.slug)
            .join(LaboratoryConcept, LaboratoryConcept.concept_id == Concept.id)
            .filter(LaboratoryConcept.laboratory_id == lab.id)
            .all()
        )
        result.append({"laboratory": lab, "concept_slugs": [s[0] for s in slugs]})
    return result


def create_instance(db: Session, laboratory_id: str, user_id) -> LabInstance:
    instance = LabInstance(
        laboratory_id=laboratory_id,
        user_id=user_id,
        status=LabInstanceStatus.requested,
        context_seed={},
        requested_at=datetime.now(timezone.utc),
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)
    return instance


def get_instance(db: Session, instance_id: str, user_id) -> LabInstance | None:
    return (
        db.query(LabInstance)
        .filter(LabInstance.id == instance_id, LabInstance.user_id == user_id)
        .first()
    )


def reveal_hint(db: Session, instance: LabInstance, laboratory: Laboratory, level: int) -> dict | None:
    matching = next((h for h in laboratory.hints if h["level"] == level), None)
    if matching is None:
        return None
    if level > instance.hints_used:
        instance.hints_used = level
        db.commit()
    return matching


def submit_flag(db: Session, instance: LabInstance, flag: str) -> bool:
    correct = instance.context_seed.get("flag_token") == flag
    if correct and not instance.solved:
        instance.solved = True
        instance.solved_at = datetime.now(timezone.utc)
        db.commit()
    return correct
