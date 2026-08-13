import enum
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RelationshipType(str, enum.Enum):
    prerequisite = "prerequisite"
    related = "related"
    continues_with = "continues_with"


class Domain(Base):
    __tablename__ = "domains"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    topics: Mapped[list["Topic"]] = relationship(back_populates="domain", order_by="Topic.name")


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("domain_id", "slug", name="uq_topic_domain_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("domains.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    domain: Mapped["Domain"] = relationship(back_populates="topics")
    concepts: Mapped[list["Concept"]] = relationship(back_populates="topic", order_by="Concept.name")


class Concept(Base):
    __tablename__ = "concepts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    topic: Mapped["Topic"] = relationship(back_populates="concepts")
    lesson: Mapped[Optional["Lesson"]] = relationship(back_populates="concept", uselist=False)


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id"), unique=True, nullable=False
    )

    concepto: Mapped[str | None] = mapped_column(Text, nullable=True)
    como_funciona: Mapped[str | None] = mapped_column(Text, nullable=True)
    por_que_importa: Mapped[str | None] = mapped_column(Text, nullable=True)
    visualizacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    ejemplo: Mapped[str | None] = mapped_column(Text, nullable=True)
    comandos: Mapped[str | None] = mapped_column(Text, nullable=True)
    errores_frecuentes: Mapped[str | None] = mapped_column(Text, nullable=True)
    regla_mental: Mapped[str | None] = mapped_column(Text, nullable=True)
    perspectiva_ofensiva: Mapped[str | None] = mapped_column(Text, nullable=True)
    perspectiva_defensiva: Mapped[str | None] = mapped_column(Text, nullable=True)

    concept: Mapped["Concept"] = relationship(back_populates="lesson")


class ConceptRelationship(Base):
    __tablename__ = "concept_relationships"
    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "type", name="uq_concept_relationship"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=False)
    type: Mapped[RelationshipType] = mapped_column(
        SAEnum(RelationshipType, name="relationship_type"), nullable=False
    )

    source: Mapped["Concept"] = relationship(foreign_keys=[source_id])
    target: Mapped["Concept"] = relationship(foreign_keys=[target_id])
