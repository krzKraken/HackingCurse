import uuid

from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    mode: str
    domain_slug: str | None = None
    topic_slug: str | None = None
    concept_slugs: list[str] | None = None
    budget_count: int | None = None
    budget_minutes: int | None = None


class ReviewItemPrompt(BaseModel):
    item_id: uuid.UUID
    concept_slug: str
    type: str
    prompt_markdown: str
    options: list[str] | None = None


class CreateSessionResponse(BaseModel):
    session_id: uuid.UUID
    items: list[ReviewItemPrompt]


class AnswerRequest(BaseModel):
    user_response: str
    confidence_declared: str | None = None


class SelfRateRequest(BaseModel):
    outcome: str
