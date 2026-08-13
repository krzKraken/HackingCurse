import uuid
from datetime import datetime

from pydantic import BaseModel


class LaboratoryOut(BaseModel):
    id: str
    title: str
    type: str
    difficulty: str
    duration_estimate_min: int
    concept_slugs: list[str]


class LabInstanceOut(BaseModel):
    id: uuid.UUID
    laboratory_id: str
    status: str
    host_port: int | None
    hints_used: int
    solved: bool
    requested_at: datetime
    started_at: datetime | None


class SubmitFlagRequest(BaseModel):
    flag: str


class SubmitFlagResponse(BaseModel):
    correct: bool
    solved: bool


class HintOut(BaseModel):
    level: int
    text: str
