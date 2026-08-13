import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class LabInstanceStatus(str, enum.Enum):
    requested = "requested"
    provisioning = "provisioning"
    running = "running"
    stopped = "stopped"
    destroyed = "destroyed"
    expired = "expired"
    failed = "failed"


class Laboratory(Base):
    __tablename__ = "laboratories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_estimate_min: Mapped[int] = mapped_column(Integer, nullable=False)
    docker_build_context: Mapped[str] = mapped_column(String(255), nullable=False)
    hints: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cpu_limit: Mapped[str] = mapped_column(String(16), nullable=False)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    max_lifetime_min: Mapped[int] = mapped_column(Integer, nullable=False)
    cleanup_remove_volumes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LaboratoryConcept(Base):
    __tablename__ = "laboratory_concepts"

    laboratory_id: Mapped[str] = mapped_column(String(64), ForeignKey("laboratories.id"), primary_key=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("concepts.id"), primary_key=True)


class LabInstance(Base):
    __tablename__ = "lab_instances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    laboratory_id: Mapped[str] = mapped_column(String(64), ForeignKey("laboratories.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[LabInstanceStatus] = mapped_column(
        SAEnum(LabInstanceStatus, name="lab_instance_status"),
        nullable=False,
        default=LabInstanceStatus.requested,
    )
    container_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    network_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    host_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    context_seed: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    solved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    solved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    destroyed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    laboratory: Mapped["Laboratory"] = relationship()
