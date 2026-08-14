# Fase 2: Gamificación (sobria) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Achievements + XP/levels to the Dashboard, computed from existing data (labs solved, reviews answered, mastery, focus time), synced once per Dashboard load.

**Architecture:** One new table (`UserAchievement`) persists unlock facts. A static Python catalog (`app/gamification/achievements.py`) defines 7 achievements as `(key, title, description, xp_value, check_fn)`. `sync_achievements()` evaluates unmet checks and persists new unlocks; `get_xp_summary()` derives `xp_total`/`level` fresh from source tables each call (never a stored counter). Both are called once from `app/dashboard/service.py:get_summary()` — no other module is touched.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic (new migration), existing `LabInstance`/`ReviewItem`/`ReviewSession`/`ConceptMastery`/`LearningSession` models (read-only, no changes), React/TypeScript.

## Global Constraints

- Only one new table: `UserAchievement`. No changes to `LabInstance`, `ReviewItem`, `ReviewSession`, `ConceptMastery`, or `LearningSession`.
- `xp_total` is **computed on every call**, never stored as a mutable counter (per spec decision 3) — this is the same pattern `app/dashboard/service.py` already uses for every other metric.
- No-shame design (master prompt §60): no negative XP, no streak-loss messaging, no locked-achievement progress bars in the UI. The Dashboard only ever shows achievements the user has already unlocked (spec decision, UI section).
- `app/gamification/achievements.py` must not import anything from `app/dashboard/` — `dashboard` imports `gamification`, never the reverse.
- Achievement checks (per spec's catalog table, exact values):
  - `first_shell` (20 XP): ≥1 `LabInstance` with `solved=True`.
  - `no_hint_required` (15 XP): ≥1 `LabInstance` with `solved=True, hints_used=0`.
  - `independent_mind` (50 XP): ≥5 `LabInstance` with `solved=True, hints_used=0`.
  - `persistent` (40 XP): ≥10 `LabInstance` with `solved=True`.
  - `perfect_recall` (25 XP): ≥1 `ReviewSession` with ≥5 answered `ReviewItem` and 100% `outcome=correct`.
  - `domain_mastery` (60 XP): any domain averaging `ConceptMastery.mastery_score` ≥90 across its studied concepts.
  - `deep_focus` (30 XP): sum of `LearningSession.active_time_sec` for the user ≥36000 (10h).
- XP formula (exact, per spec): `xp_total = 2 * (correct ReviewItem count) + sum(max(10, 30 - 5*hints_used) for each solved LabInstance) + sum(xp_value of unlocked achievements)`; `level = 1 + xp_total // 100`.

---

### Task 1: `UserAchievement` model + migration

**Files:**
- Create: `backend/app/models/gamification.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0010_create_user_achievements.py` (via `alembic revision --autogenerate`, then reviewed/edited)
- Test: `backend/tests/models/test_gamification.py` (new file; check whether `backend/tests/models/` exists — if not, create it with an `__init__.py`, following the same package pattern as `backend/tests/dashboard/`, `backend/tests/labs/`, etc.)

**Interfaces:**
- Produces: `UserAchievement(id: UUID, user_id: UUID, achievement_key: str, unlocked_at: datetime)` SQLAlchemy model with a unique constraint on `(user_id, achievement_key)`. Consumed by Task 2's `sync_achievements`/`get_xp_summary`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/models/test_gamification.py
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
```

If `backend/tests/models/` does not already exist as a package, create `backend/tests/models/__init__.py` (empty file) alongside this test file.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/models/test_gamification.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.gamification'`

- [ ] **Step 3: Create the model**

```python
# backend/app/models/gamification.py
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_key", name="uq_user_achievement"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    achievement_key: Mapped[str] = mapped_column(String(64), nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 4: Register the model with Alembic**

In `backend/alembic/env.py`, add this line to the existing block of `from app.models import ...` lines (after the `lab` import):

```python
from app.models import gamification  # noqa: F401 — registers gamification models with Base.metadata
```

- [ ] **Step 5: Generate and review the migration**

Run (from `backend/`, with the dev Postgres running — check `docker ps` for the `cursohacking-postgres-1` container, or start it with `docker compose up -d` from the repo root if it's not running):

```bash
source .venv/bin/activate
alembic revision --autogenerate -m "create user achievements table"
```

This writes a new file under `alembic/versions/` (Alembic names it with an auto-generated hash-based filename, e.g. `alembic/versions/<hash>_create_user_achievements_table.py` — rename it to `0010_create_user_achievements.py` to match this project's existing `NNNN_description.py` numbering convention, and update the file's own `down_revision` line only if renaming changed anything Alembic reads by filename — it doesn't; Alembic tracks revisions by the `revision`/`down_revision` string identifiers inside the file, not the filename, so a plain `mv` is safe). Open the generated file and confirm it contains a `create_table('user_achievements', ...)` with columns `id`, `user_id`, `achievement_key`, `unlocked_at`, a `UniqueConstraint` on `(user_id, achievement_key)`, and a `ForeignKeyConstraint` on `user_id` — if the autogenerated file is missing the unique constraint (autogenerate sometimes misses table-level constraints depending on the Alembic/SQLAlchemy version pairing), add it manually to `upgrade()`:

```python
op.create_unique_constraint('uq_user_achievement', 'user_achievements', ['user_id', 'achievement_key'])
```

and the matching drop in `downgrade()`:

```python
op.drop_constraint('uq_user_achievement', 'user_achievements', type_='unique')
```

- [ ] **Step 6: Apply the migration**

```bash
alembic upgrade head
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd backend && pytest tests/models/test_gamification.py -v`
Expected: PASS (2 tests)

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/gamification.py backend/alembic/env.py backend/alembic/versions/0010_create_user_achievements.py backend/tests/models/
git commit -m "feat: add UserAchievement model and migration"
```

---

### Task 2: Achievement catalog + gamification service

**Files:**
- Create: `backend/app/gamification/__init__.py` (empty)
- Create: `backend/app/gamification/achievements.py`
- Create: `backend/app/gamification/service.py`
- Test: `backend/tests/gamification/__init__.py` (empty)
- Test: `backend/tests/gamification/test_service.py`

**Interfaces:**
- Consumes: `app.models.gamification.UserAchievement` (Task 1), `app.models.lab.LabInstance`, `app.models.review.ReviewItem`/`ReviewSession`/`ReviewOutcome`, `app.models.mastery.ConceptMastery`, `app.models.content.Concept`/`Topic`/`Domain`, `app.models.focus.LearningSession` (all existing, read-only).
- Produces:
  - `ACHIEVEMENTS: list[Achievement]` in `app/gamification/achievements.py`, where `Achievement` is a frozen dataclass `(key: str, title: str, description: str, xp_value: int, check: Callable[[Session, UUID], bool])`.
  - `sync_achievements(db: Session, user_id) -> list[str]` in `app/gamification/service.py` — inserts newly-met achievements, returns their keys.
  - `get_xp_summary(db: Session, user_id) -> dict` — returns `{"xp_total": int, "level": int, "achievements": list[dict]}` where each achievement dict has `{key, title, description, xp_value, unlocked_at}`. Consumed by Task 3.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/gamification/test_service.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/gamification/test_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.gamification'`

- [ ] **Step 3: Create the achievements catalog**

```python
# backend/app/gamification/achievements.py
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.content import Concept, Domain, Topic
from app.models.focus import LearningSession
from app.models.lab import LabInstance
from app.models.mastery import ConceptMastery
from app.models.review import ReviewItem, ReviewOutcome, ReviewSession


@dataclass(frozen=True)
class Achievement:
    key: str
    title: str
    description: str
    xp_value: int
    check: Callable[[Session, object], bool]


def _check_first_shell(db: Session, user_id) -> bool:
    return db.query(LabInstance).filter(LabInstance.user_id == user_id, LabInstance.solved == True).count() >= 1


def _check_no_hint_required(db: Session, user_id) -> bool:
    return (
        db.query(LabInstance)
        .filter(LabInstance.user_id == user_id, LabInstance.solved == True, LabInstance.hints_used == 0)
        .count()
        >= 1
    )


def _check_independent_mind(db: Session, user_id) -> bool:
    return (
        db.query(LabInstance)
        .filter(LabInstance.user_id == user_id, LabInstance.solved == True, LabInstance.hints_used == 0)
        .count()
        >= 5
    )


def _check_persistent(db: Session, user_id) -> bool:
    return db.query(LabInstance).filter(LabInstance.user_id == user_id, LabInstance.solved == True).count() >= 10


def _check_perfect_recall(db: Session, user_id) -> bool:
    sessions = db.query(ReviewSession).filter(ReviewSession.user_id == user_id).all()
    for review_session in sessions:
        items = (
            db.query(ReviewItem)
            .filter(ReviewItem.review_session_id == review_session.id, ReviewItem.outcome.isnot(None))
            .all()
        )
        if len(items) >= 5 and all(item.outcome == ReviewOutcome.correct for item in items):
            return True
    return False


def _check_domain_mastery(db: Session, user_id) -> bool:
    domains = db.query(Domain).all()
    for domain in domains:
        masteries = (
            db.query(ConceptMastery)
            .join(Concept, ConceptMastery.concept_id == Concept.id)
            .join(Topic, Concept.topic_id == Topic.id)
            .filter(Topic.domain_id == domain.id, ConceptMastery.user_id == user_id)
            .all()
        )
        if masteries:
            average = sum(m.mastery_score for m in masteries) / len(masteries)
            if average >= 90:
                return True
    return False


def _check_deep_focus(db: Session, user_id) -> bool:
    total = (
        db.query(func.sum(LearningSession.active_time_sec))
        .filter(LearningSession.user_id == user_id)
        .scalar()
    )
    return (total or 0) >= 36000


ACHIEVEMENTS: list[Achievement] = [
    Achievement("first_shell", "First Shell", "Resolviste tu primer laboratorio.", 20, _check_first_shell),
    Achievement(
        "no_hint_required", "No Hint Required", "Resolviste un laboratorio sin usar pistas.", 15, _check_no_hint_required
    ),
    Achievement(
        "independent_mind",
        "Independent Mind",
        "Resolviste 5 laboratorios sin pistas.",
        50,
        _check_independent_mind,
    ),
    Achievement("persistent", "Persistent", "Resolviste 10 laboratorios.", 40, _check_persistent),
    Achievement(
        "perfect_recall",
        "Perfect Recall",
        "Completaste una sesión de repaso con 100% de aciertos (mínimo 5 preguntas).",
        25,
        _check_perfect_recall,
    ),
    Achievement(
        "domain_mastery", "Domain Mastery", "Alcanzaste 90% de nivel en un dominio.", 60, _check_domain_mastery
    ),
    Achievement(
        "deep_focus", "Deep Focus", "Acumulaste 10 horas de tiempo de estudio activo.", 30, _check_deep_focus
    ),
]
```

- [ ] **Step 4: Create the service**

```python
# backend/app/gamification/service.py
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/gamification/test_service.py -v`
Expected: PASS (13 tests)

- [ ] **Step 6: Run the full backend test suite**

Run: `cd backend && pytest -q`
Expected: all pass (113 existing + 2 from Task 1 + 13 from this task = 128)

- [ ] **Step 7: Commit**

```bash
git add backend/app/gamification/ backend/tests/gamification/
git commit -m "feat: add achievement catalog and gamification service"
```

---

### Task 3: Dashboard integration

**Files:**
- Modify: `backend/app/dashboard/service.py`
- Modify: `backend/app/dashboard/schemas.py`
- Test: `backend/tests/dashboard/test_router.py`

**Interfaces:**
- Consumes: `app.gamification.service.sync_achievements(db, user_id) -> list[str]` and `get_xp_summary(db, user_id) -> dict` (Task 2).
- Produces: `DashboardSummary.xp_total: int`, `.level: int`, `.achievements: list[AchievementSummary]` where `AchievementSummary = {key: str, title: str, description: str, xp_value: int, unlocked_at: datetime}`. Consumed by Task 4's frontend types.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/dashboard/test_router.py` (this file already has `_login_as_owner` and imports `Domain`/`Topic`/`Concept`/`ConceptMastery`/`Question`/`QuestionStatus`/`QuestionType`/`QuestionVariant` from earlier work — reuse them, don't re-import if already present):

```python
def test_dashboard_includes_gamification_fields_with_no_activity(client, db_session):
    _login_as_owner(client, db_session)

    resp = client.get("/api/v1/dashboard/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["xp_total"] == 0
    assert body["level"] == 1
    assert body["achievements"] == []


def test_dashboard_syncs_and_reports_achievement_after_solved_lab(client, db_session):
    import uuid
    from datetime import datetime, timezone

    from app.models.lab import Laboratory, LabInstance, LabInstanceStatus

    user = _login_as_owner(client, db_session)

    laboratory = Laboratory(
        id="gami-router-test-lab",
        title="Gami Router Test Lab",
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
    db_session.add(laboratory)
    db_session.commit()

    instance = LabInstance(
        laboratory_id=laboratory.id,
        user_id=user.id,
        status=LabInstanceStatus.destroyed,
        context_seed={},
        requested_at=datetime.now(timezone.utc),
        solved=True,
        hints_used=0,
    )
    db_session.add(instance)
    db_session.commit()

    resp = client.get("/api/v1/dashboard/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["xp_total"] > 0
    unlocked_keys = {a["key"] for a in body["achievements"]}
    assert "first_shell" in unlocked_keys
    assert "no_hint_required" in unlocked_keys
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/dashboard/test_router.py -k gamification -v`
Expected: FAIL — `KeyError: 'xp_total'` (field not in response yet)

- [ ] **Step 3: Wire the gamification service into `get_summary`**

In `backend/app/dashboard/service.py`, add the import and modify `get_summary`:

```python
from app.gamification.service import get_xp_summary, sync_achievements
```

(merge into the existing top-of-file import block, alongside `app.models.lab`)

```python
def get_summary(db: Session, user_id) -> dict:
    hint_dependency = get_hint_dependency(db, user_id)
    sync_achievements(db, user_id)
    xp_summary = get_xp_summary(db, user_id)
    return {
        "global_mastery": get_global_mastery(db, user_id),
        "domains": get_domains_summary(db, user_id),
        "reviews_due_count": get_reviews_due_count(db, user_id),
        "weak_concepts": get_weak_concepts(db, user_id),
        "overdue_concepts": get_overdue_concepts(db, user_id),
        "recent_activity": get_recent_activity(db, user_id),
        "hint_dependency": hint_dependency["breakdown"],
        "independence_score": hint_dependency["independence_score"],
        "xp_total": xp_summary["xp_total"],
        "level": xp_summary["level"],
        "achievements": xp_summary["achievements"],
    }
```

- [ ] **Step 4: Add the schema fields**

In `backend/app/dashboard/schemas.py`, add a new model and extend `DashboardSummary`:

```python
class AchievementSummary(BaseModel):
    key: str
    title: str
    description: str
    xp_value: int
    unlocked_at: datetime


class DashboardSummary(BaseModel):
    global_mastery: float
    domains: list[DomainMasterySummary]
    reviews_due_count: int
    weak_concepts: list[ConceptScoreSummary]
    overdue_concepts: list[OverdueConceptSummary]
    recent_activity: list[RecentActivityItem]
    hint_dependency: dict[int, int]
    independence_score: float | None
    xp_total: int
    level: int
    achievements: list[AchievementSummary]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/dashboard/ -v`
Expected: all pass, including the 2 new tests.

- [ ] **Step 6: Run the full backend test suite**

Run: `cd backend && pytest -q`
Expected: all pass (128 from Task 2 + 2 new = 130).

- [ ] **Step 7: Commit**

```bash
git add backend/app/dashboard/service.py backend/app/dashboard/schemas.py backend/tests/dashboard/test_router.py
git commit -m "feat: wire achievements and XP into dashboard summary"
```

---

### Task 4: Dashboard UI for achievements and XP

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/features/dashboard/DashboardPage.tsx`

**Interfaces:**
- Consumes: `DashboardSummary.xp_total: number`, `.level: number`, `.achievements: { key, title, description, xp_value, unlocked_at }[]` (Task 3, JSON field names verbatim).

No backend tests apply to this task — pure frontend UI, verified manually per this project's established pattern (see Sub-plan A/B and the Hint Dependency sub-plan, none of which have an automated frontend suite).

- [ ] **Step 1: Add the fields to the `DashboardSummary` type**

In `frontend/src/lib/api.ts`, modify the `DashboardSummary` type:

```typescript
export type DashboardSummary = {
  global_mastery: number;
  domains: {
    slug: string;
    name: string;
    mastery_percent: number;
    studied_count: number;
    total_count: number;
  }[];
  reviews_due_count: number;
  weak_concepts: { slug: string; name: string; mastery_score: number }[];
  overdue_concepts: { slug: string; name: string; next_due_at: string }[];
  recent_activity: { concept_slug: string; concept_name: string; outcome: string; answered_at: string }[];
  hint_dependency: Record<string, number>;
  independence_score: number | null;
  xp_total: number;
  level: number;
  achievements: { key: string; title: string; description: string; xp_value: number; unlocked_at: string }[];
};
```

- [ ] **Step 2: Render the new section and trim `COMING_SOON`**

In `frontend/src/features/dashboard/DashboardPage.tsx`, remove `"Logros"` from `COMING_SOON`:

```tsx
const COMING_SOON = [
  "Fragmentación",
  "Knowledge Connectivity",
  "Error Memory",
  "Labs recomendados",
  "Tiempo de práctica",
  "Transfer / Methodology Score",
];
```

Add a new `<section>` immediately after the "Uso de pistas en labs" section (before "Próximamente"):

```tsx
<section>
  <h2>Logros</h2>
  <p>
    Nivel {summary.level} — {summary.xp_total} XP
  </p>
  {summary.achievements.length === 0 ? (
    <p>Todavía no desbloqueaste ningún logro.</p>
  ) : (
    <ul>
      {summary.achievements.map((a) => (
        <li key={a.key}>
          <strong>{a.title}</strong> — {a.description} ({new Date(a.unlocked_at).toLocaleDateString()})
        </li>
      ))}
    </ul>
  )}
</section>
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: no errors. If stray `.js` files appear next to `.tsx` sources (known `tsc -b` side effect in this project, no `outDir` configured), delete them: `find src -name "*.js" -delete` from `frontend/`.

- [ ] **Step 4: Manual verification**

Check what's already running before starting anything: `ss -ltnp | grep -E ':8001|:517[0-9]|:8765'`. Note port 5173 on this machine may belong to an unrelated project (SimuCenter-OS) — never assume it's CyberLearn's without checking `cat /proc/<pid>/cwd`.

If the backend isn't running: `cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8001 > /tmp/api.log 2>&1 &` (background it properly per this project's established pattern: `setsid nohup ... > logfile 2>&1 < /dev/null & disown`).

If the frontend isn't running: `cd frontend && npm run dev` (check its own log output for the port it actually bound to).

To get an authenticated session for the existing `owner` user without knowing the password, mint one directly:

```bash
cd backend && source .venv/bin/activate && python3 -c "
from app.auth.sessions import create_session
from app.config import settings
from app.db import SessionLocal
from app.models.user import User
db = SessionLocal()
user = db.query(User).filter_by(username='owner').first()
print(create_session(str(user.id), True, settings.session_ttl_authenticated_seconds))
"
```

Set that value as a `cl_session` cookie in the browser (via browser dev tools or automation), navigate to `/dashboard`, and confirm the "Logros" section renders "Nivel 1 — 0 XP" and "Todavía no desbloqueaste ningún logro." for a fresh user with no activity. To see a populated state, solve a lab via the API (`POST /api/v1/labs/net-tcp-flagbox-001/instances`, poll until `running`, read the flag token from `LabInstance.context_seed`, `POST .../submit`) and reload `/dashboard` — confirm "First Shell" and "No Hint Required" (or whichever achievements actually apply) now appear with real unlock dates, and XP/level reflect the formula.

Clean up afterward: destroy any created lab instance (`POST /api/v1/labs/instances/{id}/destroy`), stop any process you started by exact PID (`ss -ltnp | grep <port>` → `kill <pid>`, never `pkill` by name/pattern).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/features/dashboard/DashboardPage.tsx
git commit -m "feat: show achievements and XP/level on the dashboard"
```

---

### Task 5: Update checklist

**Files:**
- Modify: `PROJECT_MASTER_CHECKLIST.md`

- [ ] **Step 1: Update the Fase 2 section**

The current `## Fase 2` section (after the previous sub-plan) looks like:

```markdown
## Fase 2

### Challenges + hints progresivos
- [x] Challenges: cubierto por `Laboratory.type` (campo ya existente, sin modelo nuevo — ver `docs/superpowers/specs/2026-08-14-challenges-hints-design.md` decisión 1)
- [x] Hint Dependency + Independence Score en el Dashboard

### Pendientes de Fase 2
- [ ] Gamificación (sobria)
- [ ] Knowledge graph navegable — vista visual interactiva (hoy solo lista jerárquica vía relaciones)
- [ ] Base de datos de vulnerabilidades
- [ ] Error Memory completo (`ErrorPattern`)
- [ ] Fragmentation score + ejercicios integradores
- [ ] Export/Import Obsidian (notas y lecciones)
- [ ] Búsqueda global / Command Palette (Ctrl+K)
```

Replace it with:

```markdown
## Fase 2

### Challenges + hints progresivos
- [x] Challenges: cubierto por `Laboratory.type` (campo ya existente, sin modelo nuevo — ver `docs/superpowers/specs/2026-08-14-challenges-hints-design.md` decisión 1)
- [x] Hint Dependency + Independence Score en el Dashboard

### Gamificación (sobria)
- [x] Achievements basados en habilidad (7 en el catálogo v1: first_shell, no_hint_required, independent_mind, persistent, perfect_recall, domain_mastery, deep_focus)
- [x] XP y niveles (calculado, no almacenado) en el Dashboard
- [ ] Skill tree — explícitamente fuera de alcance del v1 (ver `docs/superpowers/specs/2026-08-14-gamificacion-design.md`)

### Pendientes de Fase 2
- [ ] Knowledge graph navegable — vista visual interactiva (hoy solo lista jerárquica vía relaciones)
- [ ] Base de datos de vulnerabilidades
- [ ] Error Memory completo (`ErrorPattern`)
- [ ] Fragmentation score + ejercicios integradores
- [ ] Export/Import Obsidian (notas y lecciones)
- [ ] Búsqueda global / Command Palette (Ctrl+K)
```

- [ ] **Step 2: Commit**

```bash
git add PROJECT_MASTER_CHECKLIST.md
git commit -m "docs: update checklist — Fase 2 Gamificación (sobria) complete"
```
