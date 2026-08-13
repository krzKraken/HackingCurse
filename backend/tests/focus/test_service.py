from app.focus import service
from app.models.user import User


def _seed_user(db):
    user = User(username="owner", password_hash="x", totp_secret="x")
    db.add(user)
    db.commit()
    return user


def test_start_session_creates_active_session(db_session):
    user = _seed_user(db_session)
    session = service.start_session(db_session, user.id)
    assert session.ended_at is None
    assert service.get_current_session(db_session, user.id).id == session.id


def test_start_session_closes_previous_active_session(db_session):
    user = _seed_user(db_session)
    first = service.start_session(db_session, user.id)
    second = service.start_session(db_session, user.id)

    db_session.refresh(first)
    assert first.ended_at is not None
    assert second.ended_at is None


def test_get_current_session_returns_none_when_no_active(db_session):
    user = _seed_user(db_session)
    assert service.get_current_session(db_session, user.id) is None


def test_update_session_updates_fields(db_session):
    user = _seed_user(db_session)
    session = service.start_session(db_session, user.id)

    updated = service.update_session(
        db_session,
        session,
        active_time_sec=120,
        last_position="/lessons/net-01",
        timer_mode="pomodoro",
        pomodoro_preset="25/5",
    )

    assert updated.active_time_sec == 120
    assert updated.last_position == "/lessons/net-01"
    assert updated.timer_mode.value == "pomodoro"
    assert updated.pomodoro_preset == "25/5"


def test_end_session_sets_ended_at(db_session):
    user = _seed_user(db_session)
    session = service.start_session(db_session, user.id)

    ended = service.end_session(db_session, session)

    assert ended.ended_at is not None
    assert service.get_current_session(db_session, user.id) is None
