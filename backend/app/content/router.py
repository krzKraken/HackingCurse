from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.content import service
from app.content.schemas import ConceptDetail, DomainSummary
from app.db import get_db
from app.models.user import User

router = APIRouter()


@router.get("/domains", response_model=list[DomainSummary])
def list_domains(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[DomainSummary]:
    return service.get_domains_tree(db)


@router.get("/concepts/{slug}", response_model=ConceptDetail)
def get_concept(
    slug: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> ConceptDetail:
    detail = service.get_concept_detail(db, slug)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Concept not found")
    return detail
