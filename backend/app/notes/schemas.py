import uuid
from datetime import datetime

from pydantic import BaseModel


class NoteOut(BaseModel):
    id: uuid.UUID
    title: str
    body_markdown: str
    is_global: bool
    linked_concept_slug: str | None
    updated_at: datetime


class NoteWrite(BaseModel):
    title: str
    body_markdown: str
