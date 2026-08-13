from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.focus import recommendation, service
from app.focus.schemas import RecommendationOut, SessionOut, SessionUpdate
from app.models.focus import LearningSession
from app.models.user import User

router = APIRouter()


def _to_session_out(session: LearningSession) -> SessionOut:
    return SessionOut(
        id=session.id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        active_time_sec=session.active_time_sec,
        last_position=session.last_position,
        timer_mode=session.timer_mode.value,
        pomodoro_preset=session.pomodoro_preset,
        break_reminder_threshold_min=session.break_reminder_threshold_min,
        hyperfocus_reminder_min=session.hyperfocus_reminder_min,
    )


@router.post("/sessions", response_model=SessionOut)
def start_session(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SessionOut:
    return _to_session_out(service.start_session(db, user.id))


@router.get("/sessions/current", response_model=SessionOut)
def get_current_session_endpoint(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SessionOut:
    session = service.get_current_session(db, user.id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active session")
    return _to_session_out(session)


def _get_session_or_404(db: Session, user: User, learning_session_id: str) -> LearningSession:
    session = (
        db.query(LearningSession)
        .filter(LearningSession.id == learning_session_id, LearningSession.user_id == user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return session


@router.patch("/sessions/{learning_session_id}", response_model=SessionOut)
def update_session_endpoint(
    learning_session_id: str,
    payload: SessionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionOut:
    session = _get_session_or_404(db, user, learning_session_id)
    session = service.update_session(
        db,
        session,
        active_time_sec=payload.active_time_sec,
        last_position=payload.last_position,
        timer_mode=payload.timer_mode,
        pomodoro_preset=payload.pomodoro_preset,
    )
    return _to_session_out(session)


@router.post("/sessions/{learning_session_id}/end", response_model=SessionOut)
def end_session_endpoint(
    learning_session_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SessionOut:
    session = _get_session_or_404(db, user, learning_session_id)
    return _to_session_out(service.end_session(db, session))


@router.get("/recommendation")
def get_recommendation_endpoint(
    minutes: int = Query(default=15),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rec = recommendation.get_recommendation(db, user.id, minutes)
    if rec is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return RecommendationOut(**rec)
