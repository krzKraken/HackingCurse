import random
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.learning import engine
from app.models.content import Concept, Domain, Topic
from app.models.mastery import ConceptMastery
from app.models.question import Question, QuestionStatus, QuestionVariant
from app.models.review import ReviewItem, ReviewSession

RECENT_VARIANT_EXCLUDE = 3


def _concepts_with_published_questions(
    db: Session, domain_slug: str | None = None, topic_slug: str | None = None, concept_slugs: list[str] | None = None
) -> list[Concept]:
    query = (
        db.query(Concept)
        .join(Question, Question.concept_id == Concept.id)
        .filter(Question.status == QuestionStatus.published)
        .join(Topic, Concept.topic_id == Topic.id)
        .join(Domain, Topic.domain_id == Domain.id)
    )
    if domain_slug:
        query = query.filter(Domain.slug == domain_slug)
    if topic_slug:
        query = query.filter(Topic.slug == topic_slug)
    if concept_slugs:
        query = query.filter(Concept.slug.in_(concept_slugs))
    return query.distinct().all()


def _mastery_map(db: Session, user_id, concept_ids: list) -> dict:
    if not concept_ids:
        return {}
    rows = (
        db.query(ConceptMastery)
        .filter(ConceptMastery.user_id == user_id, ConceptMastery.concept_id.in_(concept_ids))
        .all()
    )
    return {m.concept_id: m for m in rows}


def select_concepts(
    db: Session,
    user_id,
    mode: str,
    domain_slug: str | None = None,
    topic_slug: str | None = None,
    concept_slugs: list[str] | None = None,
) -> list[Concept]:
    now = datetime.now(timezone.utc)
    concepts = _concepts_with_published_questions(
        db,
        domain_slug=domain_slug,
        topic_slug=topic_slug if mode == "por_tema" else None,
        concept_slugs=concept_slugs if mode == "pre_lab" else None,
    )
    masteries = _mastery_map(db, user_id, [c.id for c in concepts])

    def risk(concept: Concept) -> float:
        mastery = masteries.get(concept.id)
        if mastery is None or mastery.schedule is None or mastery.last_tested is None:
            return 1.0
        days = (now - mastery.last_tested).total_seconds() / 86400
        return engine.forgetting_risk(mastery.schedule.stability_days, days)

    def mastery_score(concept: Concept) -> float:
        mastery = masteries.get(concept.id)
        return mastery.mastery_score if mastery else 0.0

    def is_due(concept: Concept) -> bool:
        mastery = masteries.get(concept.id)
        if mastery is None or mastery.schedule is None:
            return True
        return mastery.schedule.next_due_at <= now

    if mode == "general":
        concepts = [c for c in concepts if is_due(c)]
    elif mode == "debilidades":
        concepts = sorted(concepts, key=mastery_score)
    elif mode == "olvidado":
        concepts = sorted(concepts, key=risk, reverse=True)
    elif mode in ("mixto", "sorpresa"):
        random.shuffle(concepts)
    # por_tema / pre_lab ya quedaron filtrados arriba

    return concepts


def pick_variant(db: Session, user_id, concept_id) -> QuestionVariant | None:
    variants = (
        db.query(QuestionVariant)
        .join(Question, QuestionVariant.question_id == Question.id)
        .filter(Question.concept_id == concept_id, Question.status == QuestionStatus.published)
        .all()
    )
    if not variants:
        return None

    recent_variant_ids = {
        row[0]
        for row in (
            db.query(ReviewItem.question_variant_id)
            .join(ReviewSession, ReviewItem.review_session_id == ReviewSession.id)
            .filter(ReviewSession.user_id == user_id, ReviewItem.concept_id == concept_id)
            .order_by(ReviewItem.shown_at.desc())
            .limit(RECENT_VARIANT_EXCLUDE)
        )
    }

    unseen = [v for v in variants if v.id not in recent_variant_ids]
    pool = unseen if unseen else variants
    return random.choice(pool)


def build_items(
    db: Session,
    user_id,
    mode: str,
    domain_slug: str | None = None,
    topic_slug: str | None = None,
    concept_slugs: list[str] | None = None,
    budget_count: int | None = None,
    budget_minutes: int | None = None,
) -> list[tuple[Concept, QuestionVariant]]:
    concepts = select_concepts(db, user_id, mode, domain_slug, topic_slug, concept_slugs)

    if budget_count is None and budget_minutes is not None:
        budget_count = max(1, round(budget_minutes * 60 / 90))
    if budget_count is None:
        budget_count = 10

    concepts = concepts[:budget_count]

    items = []
    for concept in concepts:
        variant = pick_variant(db, user_id, concept.id)
        if variant is not None:
            items.append((concept, variant))
    return items
