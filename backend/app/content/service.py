from sqlalchemy.orm import Session, selectinload

from app.content.schemas import (
    ConceptDetail,
    ConceptRelationships,
    ConceptSummary,
    DomainSummary,
    LessonOut,
    TopicSummary,
)
from app.models.content import Concept, ConceptRelationship, Domain, RelationshipType, Topic


def get_domains_tree(db: Session) -> list[DomainSummary]:
    domains = (
        db.query(Domain)
        .options(selectinload(Domain.topics).selectinload(Topic.concepts))
        .order_by(Domain.name)
        .all()
    )
    return [
        DomainSummary(
            slug=d.slug,
            name=d.name,
            topics=[
                TopicSummary(
                    slug=t.slug,
                    name=t.name,
                    concepts=[ConceptSummary(slug=c.slug, name=c.name) for c in t.concepts],
                )
                for t in d.topics
            ],
        )
        for d in domains
    ]


def get_concept_detail(db: Session, slug: str) -> ConceptDetail | None:
    concept = db.query(Concept).filter(Concept.slug == slug).first()
    if concept is None:
        return None

    lesson_out = LessonOut.model_validate(concept.lesson) if concept.lesson is not None else None

    rels = db.query(ConceptRelationship).filter(ConceptRelationship.source_id == concept.id).all()
    by_type: dict[RelationshipType, list[ConceptSummary]] = {t: [] for t in RelationshipType}
    for rel in rels:
        by_type[rel.type].append(ConceptSummary(slug=rel.target.slug, name=rel.target.name))

    return ConceptDetail(
        slug=concept.slug,
        name=concept.name,
        lesson=lesson_out,
        relationships=ConceptRelationships(
            prerequisites=by_type[RelationshipType.prerequisite],
            related=by_type[RelationshipType.related],
            continues_with=by_type[RelationshipType.continues_with],
        ),
    )
