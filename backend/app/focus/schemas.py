import uuid
from datetime import datetime

from pydantic import BaseModel


class SessionOut(BaseModel):
    id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    active_time_sec: int
    last_position: str | None
    timer_mode: str
    pomodoro_preset: str | None
    break_reminder_threshold_min: int
    hyperfocus_reminder_min: int


class SessionUpdate(BaseModel):
    active_time_sec: int | None = None
    last_position: str | None = None
    timer_mode: str | None = None
    pomodoro_preset: str | None = None


class RecommendationOut(BaseModel):
    activity_type: str
    concept_slug: str
    concept_name: str
    reason: str
