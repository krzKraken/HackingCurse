import enum
import uuid
from typing import Optional

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.content import Concept


class QuestionType(str, enum.Enum):
    multiple_choice = "multiple_choice"
    true_false = "true_false"
    free_explanation = "free_explanation"


class QuestionStatus(str, enum.Enum):
    draft = "draft"
    published = "published"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=False)
    type: Mapped[QuestionType] = mapped_column(SAEnum(QuestionType, name="question_type"), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    evaluation_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[QuestionStatus] = mapped_column(
        SAEnum(QuestionStatus, name="question_status"), nullable=False, default=QuestionStatus.published
    )

    concept: Mapped[Concept] = relationship()
    variants: Mapped[list["QuestionVariant"]] = relationship(back_populates="question")


class QuestionVariant(Base):
    __tablename__ = "question_variants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    prompt_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    correct_option_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    correct_bool: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    question: Mapped["Question"] = relationship(back_populates="variants")
