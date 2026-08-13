from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.focus import LearningSession, TimerMode


def start_session(db: Session, user_id) -> LearningSession:
    active = get_current_session(db, user_id)
    if active is not None:
        end_session(db, active)

    session = LearningSession(user_id=user_id, started_at=datetime.now(timezone.utc))
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_current_session(db: Session, user_id) -> LearningSession | None:
    return (
        db.query(LearningSession)
        .filter(LearningSession.user_id == user_id, LearningSession.ended_at.is_(None))
        .order_by(LearningSession.started_at.desc())
        .first()
    )


def update_session(
    db: Session,
    session: LearningSession,
    active_time_sec: int | None = None,
    last_position: str | None = None,
    timer_mode: str | None = None,
    pomodoro_preset: str | None = None,
) -> LearningSession:
    if active_time_sec is not None:
        session.active_time_sec = active_time_sec
    if last_position is not None:
        session.last_position = last_position
    if timer_mode is not None:
        session.timer_mode = TimerMode(timer_mode)
    if pomodoro_preset is not None:
        session.pomodoro_preset = pomodoro_preset
    db.commit()
    db.refresh(session)
    return session


def end_session(db: Session, session: LearningSession) -> LearningSession:
    session.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session
