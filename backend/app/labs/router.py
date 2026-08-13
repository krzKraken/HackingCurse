from fastapi import APIRouter, Depends, HTTPException, status
from redis import Redis
from rq import Queue
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.config import settings
from app.db import get_db
from app.labs import service
from app.labs.schemas import HintOut, LabInstanceOut, LaboratoryOut, SubmitFlagRequest, SubmitFlagResponse
from app.models.lab import Laboratory, LabInstance
from app.models.user import User

router = APIRouter()

_redis_conn = Redis.from_url(settings.redis_url)
_queue = Queue("labs", connection=_redis_conn)


def _to_laboratory_out(entry: dict) -> LaboratoryOut:
    lab: Laboratory = entry["laboratory"]
    return LaboratoryOut(
        id=lab.id,
        title=lab.title,
        type=lab.type,
        difficulty=lab.difficulty,
        duration_estimate_min=lab.duration_estimate_min,
        concept_slugs=entry["concept_slugs"],
    )


def _to_instance_out(instance: LabInstance) -> LabInstanceOut:
    return LabInstanceOut(
        id=instance.id,
        laboratory_id=instance.laboratory_id,
        status=instance.status.value,
        host_port=instance.host_port,
        hints_used=instance.hints_used,
        solved=instance.solved,
        requested_at=instance.requested_at,
        started_at=instance.started_at,
    )


@router.get("", response_model=list[LaboratoryOut])
def list_labs(db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> list[LaboratoryOut]:
    return [_to_laboratory_out(e) for e in service.list_laboratories(db)]


@router.post("/{laboratory_id}/instances", response_model=LabInstanceOut)
def create_instance(
    laboratory_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LabInstanceOut:
    laboratory = db.query(Laboratory).filter(Laboratory.id == laboratory_id).first()
    if laboratory is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Laboratory not found")
    instance = service.create_instance(db, laboratory_id, user.id)
    _queue.enqueue("worker.jobs.provision_lab", str(instance.id))
    return _to_instance_out(instance)


def _get_instance_or_404(db: Session, user: User, instance_id: str) -> LabInstance:
    instance = service.get_instance(db, instance_id, user.id)
    if instance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab instance not found")
    return instance


@router.get("/instances/{instance_id}", response_model=LabInstanceOut)
def get_instance(
    instance_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LabInstanceOut:
    return _to_instance_out(_get_instance_or_404(db, user, instance_id))


@router.post("/instances/{instance_id}/reset", response_model=LabInstanceOut)
def reset_instance(
    instance_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LabInstanceOut:
    instance = _get_instance_or_404(db, user, instance_id)
    _queue.enqueue("worker.jobs.reset_lab", str(instance.id))
    return _to_instance_out(instance)


@router.post("/instances/{instance_id}/destroy", response_model=LabInstanceOut)
def destroy_instance(
    instance_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LabInstanceOut:
    instance = _get_instance_or_404(db, user, instance_id)
    _queue.enqueue("worker.jobs.destroy_lab", str(instance.id))
    return _to_instance_out(instance)


@router.get("/instances/{instance_id}/hints/{level}", response_model=HintOut)
def get_hint(
    instance_id: str,
    level: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HintOut:
    instance = _get_instance_or_404(db, user, instance_id)
    laboratory = db.query(Laboratory).filter(Laboratory.id == instance.laboratory_id).first()
    hint = service.reveal_hint(db, instance, laboratory, level)
    if hint is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hint not found")
    return HintOut(**hint)


@router.post("/instances/{instance_id}/submit", response_model=SubmitFlagResponse)
def submit_flag(
    instance_id: str,
    payload: SubmitFlagRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubmitFlagResponse:
    instance = _get_instance_or_404(db, user, instance_id)
    correct = service.submit_flag(db, instance, payload.flag)
    return SubmitFlagResponse(correct=correct, solved=instance.solved)
