import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TimerMode(str, enum.Enum):
    count_up = "count_up"
    pomodoro = "pomodoro"
    countdown = "countdown"
    no_timer = "no_timer"


class LearningSession(Base):
    __tablename__ = "learning_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    active_time_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_position: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    timer_mode: Mapped[TimerMode] = mapped_column(
        SAEnum(TimerMode, name="timer_mode"), nullable=False, default=TimerMode.count_up
    )
    pomodoro_preset: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    break_reminder_threshold_min: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    hyperfocus_reminder_min: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
