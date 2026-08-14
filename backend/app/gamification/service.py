from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.gamification.achievements import ACHIEVEMENTS
from app.models.gamification import UserAchievement
from app.models.lab import LabInstance
from app.models.review import ReviewItem, ReviewOutcome, ReviewSession


def sync_achievements(db: Session, user_id) -> list[str]:
    existing_keys = {
        row.achievement_key
        for row in db.query(UserAchievement).filter(UserAchievement.user_id == user_id).all()
    }
    newly_unlocked = []
    for achievement in ACHIEVEMENTS:
        if achievement.key in existing_keys:
            continue
        if achievement.check(db, user_id):
            db.add(
                UserAchievement(
                    user_id=user_id,
                    achievement_key=achievement.key,
                    unlocked_at=datetime.now(timezone.utc),
                )
            )
            newly_unlocked.append(achievement.key)
    if newly_unlocked:
        db.commit()
    return newly_unlocked


def get_xp_summary(db: Session, user_id) -> dict:
    correct_reviews = (
        db.query(ReviewItem)
        .join(ReviewSession, ReviewItem.review_session_id == ReviewSession.id)
        .filter(ReviewSession.user_id == user_id, ReviewItem.outcome == ReviewOutcome.correct)
        .count()
    )
    solved_labs = db.query(LabInstance).filter(LabInstance.user_id == user_id, LabInstance.solved == True).all()

    xp_from_reviews = 2 * correct_reviews
    xp_from_labs = sum(max(10, 30 - 5 * instance.hints_used) for instance in solved_labs)

    unlocked_rows = (
        db.query(UserAchievement)
        .filter(UserAchievement.user_id == user_id)
        .order_by(UserAchievement.unlocked_at.desc())
        .all()
    )
    catalog_by_key = {a.key: a for a in ACHIEVEMENTS}
    xp_from_achievements = sum(
        catalog_by_key[row.achievement_key].xp_value for row in unlocked_rows if row.achievement_key in catalog_by_key
    )

    xp_total = xp_from_reviews + xp_from_labs + xp_from_achievements
    level = 1 + xp_total // 100

    achievements = [
        {
            "key": row.achievement_key,
            "title": catalog_by_key[row.achievement_key].title,
            "description": catalog_by_key[row.achievement_key].description,
            "xp_value": catalog_by_key[row.achievement_key].xp_value,
            "unlocked_at": row.unlocked_at,
        }
        for row in unlocked_rows
        if row.achievement_key in catalog_by_key
    ]

    return {"xp_total": xp_total, "level": level, "achievements": achievements}
