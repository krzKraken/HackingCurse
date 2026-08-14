import uuid
from datetime import datetime, timedelta, timezone

from app.gamification import service
from app.models.content import Concept, Domain, Topic
from app.models.focus import LearningSession, TimerMode
from app.models.lab import Laboratory, LabInstance, LabInstanceStatus
from app.models.mastery import ConceptMastery
from app.models.question import Question, QuestionStatus, QuestionType, QuestionVariant
from app.models.review import ReviewItem, ReviewOutcome, ReviewSession
from app.models.user import User


def _seed_user(db):
    user = User(username="owner", password_hash="x", totp_secret="x")
    db.add(user)
    db.commit()
    return user


def _seed_laboratory(db, lab_id="gami-test-lab"):
    lab = db.query(Laboratory).filter_by(id=lab_id).first()
    if lab is not None:
        return lab
    lab = Laboratory(
        id=lab_id,
        title="Gamification Test Lab",
        type="black_box",
        difficulty="beginner",
        duration_estimate_min=10,
        docker_build_context="labs/flagbox",
        hints=[],
        cpu_limit="0.5",
        memory_limit_mb=128,
        max_lifetime_min=30,
        cleanup_remove_volumes=True,
    )
    db.add(lab)
    db.commit()
    return lab


def _seed_solved_instance(db, user, hints_used):
    lab = _seed_laboratory(db)
    instance = LabInstance(
        laboratory_id=lab.id,
        user_id=user.id,
        status=LabInstanceStatus.destroyed,
        context_seed={},
        requested_at=datetime.now(timezone.utc),
        solved=True,
        hints_used=hints_used,
    )
    db.add(instance)
    db.commit()
    return instance


def _seed_review_session_with_items(db, user, outcomes):
    session = ReviewSession(user_id=user.id, mode="general", started_at=datetime.now(timezone.utc))
    db.add(session)
    db.flush()

    domain = Domain(slug=f"domain-{uuid.uuid4().hex[:8]}", name="Test Domain")
    db.add(domain)
    db.flush()
    topic = Topic(domain_id=domain.id, slug="t1", name="t1")
    db.add(topic)
    db.flush()
    concept = Concept(topic_id=topic.id, slug=f"c-{uuid.uuid4().hex[:8]}", name="c")
    db.add(concept)
    db.flush()
    question = Question(
        concept_id=concept.id, type=QuestionType.true_false, difficulty=1, status=QuestionStatus.published
    )
    db.add(question)
    db.flush()
    variant = QuestionVariant(question_id=question.id, prompt_markdown="?", correct_bool=True)
    db.add(variant)
    db.flush()

    now = datetime.now(timezone.utc)
    for outcome in outcomes:
        db.add(
            ReviewItem(
                review_session_id=session.id,
                concept_id=concept.id,
                question_variant_id=variant.id,
                shown_at=now,
                answered_at=now,
                outcome=outcome,
            )
        )
    db.commit()
    return session


def test_sync_achievements_no_activity_unlocks_nothing(db_session):
    user = _seed_user(db_session)
    assert service.sync_achievements(db_session, user.id) == []


def test_sync_achievements_unlocks_first_shell_after_one_solved_lab(db_session):
    user = _seed_user(db_session)
    _seed_solved_instance(db_session, user, hints_used=1)

    unlocked = service.sync_achievements(db_session, user.id)

    assert "first_shell" in unlocked
    assert "no_hint_required" not in unlocked


def test_sync_achievements_is_idempotent(db_session):
    user = _seed_user(db_session)
    _seed_solved_instance(db_session, user, hints_used=0)

    first_run = service.sync_achievements(db_session, user.id)
    second_run = service.sync_achievements(db_session, user.id)

    assert "first_shell" in first_run
    assert second_run == []


def test_independent_mind_unlocks_at_exactly_five_hint_free_solves(db_session):
    user = _seed_user(db_session)
    for _ in range(4):
        _seed_solved_instance(db_session, user, hints_used=0)

    unlocked = service.sync_achievements(db_session, user.id)
    assert "independent_mind" not in unlocked

    _seed_solved_instance(db_session, user, hints_used=0)
    unlocked = service.sync_achievements(db_session, user.id)
    assert "independent_mind" in unlocked


def test_persistent_unlocks_at_ten_solved_labs(db_session):
    user = _seed_user(db_session)
    for _ in range(9):
        _seed_solved_instance(db_session, user, hints_used=2)

    unlocked = service.sync_achievements(db_session, user.id)
    assert "persistent" not in unlocked

    _seed_solved_instance(db_session, user, hints_used=2)
    unlocked = service.sync_achievements(db_session, user.id)
    assert "persistent" in unlocked


def test_perfect_recall_requires_five_correct_items(db_session):
    user = _seed_user(db_session)
    _seed_review_session_with_items(db_session, user, [ReviewOutcome.correct] * 4)

    unlocked = service.sync_achievements(db_session, user.id)
    assert "perfect_recall" not in unlocked

    _seed_review_session_with_items(db_session, user, [ReviewOutcome.correct] * 5)
    unlocked = service.sync_achievements(db_session, user.id)
    assert "perfect_recall" in unlocked


def test_perfect_recall_not_unlocked_if_any_incorrect(db_session):
    user = _seed_user(db_session)
    _seed_review_session_with_items(db_session, user, [ReviewOutcome.correct] * 4 + [ReviewOutcome.incorrect])

    unlocked = service.sync_achievements(db_session, user.id)
    assert "perfect_recall" not in unlocked


def test_domain_mastery_unlocks_at_ninety_percent_average(db_session):
    user = _seed_user(db_session)
    domain = Domain(slug="networking", name="Networking")
    db_session.add(domain)
    db_session.flush()
    topic = Topic(domain_id=domain.id, slug="t1", name="t1")
    db_session.add(topic)
    db_session.flush()
    concept = Concept(topic_id=topic.id, slug="c1", name="c1")
    db_session.add(concept)
    db_session.flush()
    db_session.add(ConceptMastery(user_id=user.id, concept_id=concept.id, mastery_score=95.0))
    db_session.commit()

    unlocked = service.sync_achievements(db_session, user.id)

    assert "domain_mastery" in unlocked


def test_domain_mastery_not_unlocked_below_threshold(db_session):
    user = _seed_user(db_session)
    domain = Domain(slug="networking", name="Networking")
    db_session.add(domain)
    db_session.flush()
    topic = Topic(domain_id=domain.id, slug="t1", name="t1")
    db_session.add(topic)
    db_session.flush()
    concept = Concept(topic_id=topic.id, slug="c1", name="c1")
    db_session.add(concept)
    db_session.flush()
    db_session.add(ConceptMastery(user_id=user.id, concept_id=concept.id, mastery_score=50.0))
    db_session.commit()

    unlocked = service.sync_achievements(db_session, user.id)

    assert "domain_mastery" not in unlocked


def test_deep_focus_unlocks_at_ten_accumulated_hours(db_session):
    user = _seed_user(db_session)
    db_session.add(
        LearningSession(
            user_id=user.id,
            started_at=datetime.now(timezone.utc) - timedelta(hours=10),
            ended_at=datetime.now(timezone.utc),
            active_time_sec=36000,
            timer_mode=TimerMode.count_up,
        )
    )
    db_session.commit()

    unlocked = service.sync_achievements(db_session, user.id)

    assert "deep_focus" in unlocked


def test_xp_summary_with_no_activity(db_session):
    user = _seed_user(db_session)
    summary = service.get_xp_summary(db_session, user.id)
    assert summary == {"xp_total": 0, "level": 1, "achievements": []}


def test_xp_summary_combines_reviews_labs_and_achievements(db_session):
    user = _seed_user(db_session)
    _seed_review_session_with_items(db_session, user, [ReviewOutcome.correct] * 3)
    _seed_solved_instance(db_session, user, hints_used=0)
    service.sync_achievements(db_session, user.id)

    summary = service.get_xp_summary(db_session, user.id)

    # 3 correct reviews * 2 = 6 XP
    # 1 solved lab, 0 hints -> max(10, 30-0) = 30 XP
    # achievements unlocked: first_shell (20) + no_hint_required (15) = 35 XP
    assert summary["xp_total"] == 6 + 30 + 35
    assert summary["level"] == 1
    assert len(summary["achievements"]) == 2
    assert {a["key"] for a in summary["achievements"]} == {"first_shell", "no_hint_required"}
