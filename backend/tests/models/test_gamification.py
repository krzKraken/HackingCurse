import uuid
from datetime import datetime, timezone

from app.models.gamification import UserAchievement
from app.models.user import User


def _seed_user(db):
    user = User(username="owner", password_hash="x", totp_secret="x")
    db.add(user)
    db.commit()
    return user


def test_user_achievement_round_trips(db_session):
    user = _seed_user(db_session)
    row = UserAchievement(
        user_id=user.id,
        achievement_key="first_shell",
        unlocked_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    db_session.commit()

    fetched = db_session.query(UserAchievement).filter_by(user_id=user.id).first()
    assert fetched.achievement_key == "first_shell"


def test_user_achievement_unique_per_user_and_key(db_session):
    from sqlalchemy.exc import IntegrityError

    user = _seed_user(db_session)
    now = datetime.now(timezone.utc)
    db_session.add(UserAchievement(user_id=user.id, achievement_key="first_shell", unlocked_at=now))
    db_session.commit()

    db_session.add(UserAchievement(user_id=user.id, achievement_key="first_shell", unlocked_at=now))
    try:
        db_session.commit()
        assert False, "expected IntegrityError"
    except IntegrityError:
        db_session.rollback()
