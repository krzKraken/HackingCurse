import glob
import sys

import yaml
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.content import Concept, ConceptRelationship, Domain, Lesson, RelationshipType, Topic

LESSON_FIELDS = {
    "concepto",
    "como_funciona",
    "por_que_importa",
    "visualizacion",
    "ejemplo",
    "comandos",
    "errores_frecuentes",
    "regla_mental",
    "perspectiva_ofensiva",
    "perspectiva_defensiva",
}


def _upsert_domain(db: Session, data: dict) -> Domain:
    domain = db.query(Domain).filter(Domain.slug == data["slug"]).first()
    if domain is None:
        domain = Domain(slug=data["slug"], name=data["name"])
        db.add(domain)
        db.flush()
    else:
        domain.name = data["name"]
    return domain


def _upsert_topic(db: Session, domain: Domain, data: dict) -> Topic:
    topic = (
        db.query(Topic)
        .filter(Topic.domain_id == domain.id, Topic.slug == data["slug"])
        .first()
    )
    if topic is None:
        topic = Topic(domain_id=domain.id, slug=data["slug"], name=data["name"])
        db.add(topic)
        db.flush()
    else:
        topic.name = data["name"]
    return topic


def _upsert_concept(db: Session, topic: Topic, data: dict) -> Concept:
    concept = db.query(Concept).filter(Concept.slug == data["slug"]).first()
    if concept is None:
        concept = Concept(topic_id=topic.id, slug=data["slug"], name=data["name"])
        db.add(concept)
        db.flush()
    else:
        concept.topic_id = topic.id
        concept.name = data["name"]
    return concept


def _upsert_lesson(db: Session, concept: Concept, data: dict) -> None:
    values = {field: data.get(field) for field in LESSON_FIELDS}
    lesson = db.query(Lesson).filter(Lesson.concept_id == concept.id).first()
    if lesson is None:
        db.add(Lesson(concept_id=concept.id, **values))
    else:
        for field, value in values.items():
            setattr(lesson, field, value)


def seed_content(content_dir: str = "content") -> None:
    db = SessionLocal()
    try:
        paths = sorted(glob.glob(f"{content_dir}/**/*.yaml", recursive=True))
        parsed: list[tuple[Concept, list[dict]]] = []

        for path in paths:
            with open(path) as f:
                data = yaml.safe_load(f)
            domain = _upsert_domain(db, data["domain"])
            topic = _upsert_topic(db, domain, data["topic"])
            concept = _upsert_concept(db, topic, data["concept"])
            _upsert_lesson(db, concept, data["lesson"])
            parsed.append((concept, data.get("relationships", [])))
        db.commit()

        for concept, relationships in parsed:
            for rel in relationships:
                target = db.query(Concept).filter(Concept.slug == rel["target_slug"]).first()
                if target is None:
                    print(
                        f"WARNING: unknown target_slug '{rel['target_slug']}' referenced by '{concept.slug}'",
                        file=sys.stderr,
                    )
                    continue
                rel_type = RelationshipType(rel["type"])
                existing = (
                    db.query(ConceptRelationship)
                    .filter_by(source_id=concept.id, target_id=target.id, type=rel_type)
                    .first()
                )
                if existing is None:
                    db.add(ConceptRelationship(source_id=concept.id, target_id=target.id, type=rel_type))
        db.commit()
        print(f"Seeded {len(parsed)} concepts from {content_dir}/")
    finally:
        db.close()


if __name__ == "__main__":
    seed_content()
