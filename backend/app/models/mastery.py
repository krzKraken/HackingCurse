import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.content import Concept


class ConceptMastery(Base):
    __tablename__ = "concept_masteries"
    __table_args__ = (UniqueConstraint("user_id", "concept_id", name="uq_concept_mastery_user_concept"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    concept_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=False)
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_tested: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    concept: Mapped[Concept] = relationship()
    schedule: Mapped[Optional["ReviewSchedule"]] = relationship(back_populates="concept_mastery", uselist=False)


class ReviewSchedule(Base):
    __tablename__ = "review_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_mastery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concept_masteries.id"), unique=True, nullable=False
    )
    stability_days: Mapped[float] = mapped_column(Float, nullable=False)
    next_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    concept_mastery: Mapped["ConceptMastery"] = relationship(back_populates="schedule")
