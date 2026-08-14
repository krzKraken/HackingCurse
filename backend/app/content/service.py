from sqlalchemy.orm import Session, selectinload

from app.content.schemas import (
    ConceptDetail,
    ConceptRelationships,
    ConceptSummary,
    DomainSummary,
    GraphEdge,
    GraphNode,
    GraphResponse,
    LessonOut,
    TopicSummary,
)
from app.models.content import Concept, ConceptRelationship, Domain, RelationshipType, Topic
from app.models.mastery import ConceptMastery, ReviewSchedule


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


def get_knowledge_graph(db: Session, user_id) -> GraphResponse:
    rows = (
        db.query(Concept, Topic, Domain, ConceptMastery, ReviewSchedule)
        .join(Topic, Concept.topic_id == Topic.id)
        .join(Domain, Topic.domain_id == Domain.id)
        .outerjoin(
            ConceptMastery,
            (ConceptMastery.concept_id == Concept.id) & (ConceptMastery.user_id == user_id),
        )
        .outerjoin(ReviewSchedule, ReviewSchedule.concept_mastery_id == ConceptMastery.id)
        .all()
    )

    nodes = [
        GraphNode(
            slug=concept.slug,
            name=concept.name,
            domain_slug=domain.slug,
            topic_slug=topic.slug,
            mastery_score=mastery.mastery_score if mastery is not None else 0.0,
            studied=mastery is not None,
            next_due_at=schedule.next_due_at if schedule is not None else None,
        )
        for concept, topic, domain, mastery, schedule in rows
    ]
    slug_by_concept_id = {concept.id: concept.slug for concept, *_ in rows}

    relationships = db.query(ConceptRelationship).all()
    edges = [
        GraphEdge(
            source_slug=slug_by_concept_id[rel.source_id],
            target_slug=slug_by_concept_id[rel.target_id],
            type=rel.type,
        )
        for rel in relationships
        if rel.source_id in slug_by_concept_id and rel.target_id in slug_by_concept_id
    ]

    return GraphResponse(nodes=nodes, edges=edges)
