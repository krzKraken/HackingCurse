from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.dashboard import service
from app.dashboard.schemas import DashboardSummary
from app.db import get_db
from app.models.user import User

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> DashboardSummary:
    return service.get_summary(db, user.id)
