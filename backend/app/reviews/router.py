from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models.review import ReviewItem, ReviewSession
from app.models.user import User
from app.reviews import grading, selector
from app.reviews.schemas import (
    AnswerRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    ReviewItemPrompt,
    SelfRateRequest,
)

router = APIRouter()


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session(
    payload: CreateSessionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CreateSessionResponse:
    pairs = selector.build_items(
        db,
        user.id,
        payload.mode,
        domain_slug=payload.domain_slug,
        topic_slug=payload.topic_slug,
        concept_slugs=payload.concept_slugs,
        budget_count=payload.budget_count,
        budget_minutes=payload.budget_minutes,
    )

    session = ReviewSession(user_id=user.id, mode=payload.mode, started_at=datetime.now(timezone.utc))
    db.add(session)
    db.flush()

    prompts = []
    for concept, variant in pairs:
        item = ReviewItem(
            review_session_id=session.id,
            concept_id=concept.id,
            question_variant_id=variant.id,
            shown_at=datetime.now(timezone.utc),
        )
        db.add(item)
        db.flush()
        prompts.append(
            ReviewItemPrompt(
                item_id=item.id,
                concept_slug=concept.slug,
                type=variant.question.type.value,
                prompt_markdown=variant.prompt_markdown,
                options=variant.options,
            )
        )
    db.commit()

    return CreateSessionResponse(session_id=session.id, items=prompts)


def _get_item_or_404(db: Session, item_id: str) -> ReviewItem:
    item = db.query(ReviewItem).filter(ReviewItem.id == item_id).first()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review item not found")
    return item


@router.post("/items/{item_id}/answer")
def answer_item(
    item_id: str,
    payload: AnswerRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    item = _get_item_or_404(db, item_id)
    return grading.submit_answer(db, item, payload.user_response, payload.confidence_declared)


@router.post("/items/{item_id}/self-rate")
def self_rate_item(
    item_id: str,
    payload: SelfRateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    item = _get_item_or_404(db, item_id)
    if item.outcome is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Item already rated")
    return grading.submit_self_rate(db, item, payload.outcome)
