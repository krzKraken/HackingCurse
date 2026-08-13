# Questions + Retention Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal real question bank (multiple_choice, true_false, free_explanation) and the spaced-repetition retention engine (forgetting curve, difficulty engine, 7-mode `ReviewSelector`), then load real questions for the 10 existing Networking lessons and wire up a `/review` flow end-to-end.

**Architecture:** Two new backend concerns: `app/learning/` (pure retention-curve math, no DB access) and `app/reviews/` (grading + selection + API, using `app/learning/engine.py`). New models: `Question`/`QuestionVariant` (content/models.py-style), `ConceptMastery`/`ReviewSchedule` (per-user progress), `ReviewSession`/`ReviewItem` (a repaso session and its individual questions). Frontend adds a `/review` route with mode/budget selection and a per-item answer flow.

**Tech Stack:** Same as prior plans (FastAPI, SQLAlchemy 2.0.52, Alembic, Postgres, React+Vite).

## Global Constraints

- Model and API shape must match `docs/superpowers/specs/2026-08-13-questions-retention-design.md` exactly, including its 5 documented simplifications (no separate `Answer`/`Evaluation` tables, no `QuestionVariant` templating, unified `mastery_score`, `confidence_declared` captured but not acted on yet, `pre_lab` mode takes explicit `concept_slugs`).
- Retention formulas are implemented exactly as specified: `THRESHOLD = 0.85`, `INITIAL_STABILITY_DAYS = 1 / -ln(0.85)`, outcome factors `{correct: 1.6, partial: 1.1, incorrect: 0.5}`.
- `POST /reviews/sessions` and the `answer` endpoint must never leak `correct_option_index`, `correct_bool`, `evaluation_criteria`, or `expected_answer` before the user has submitted a response for that item.
- All new routes live under `/api/v1/reviews/...` and require authentication (`get_current_user`).
- Every task's DB-touching tests use the existing `client`/`db_session` fixtures from `backend/tests/conftest.py` — do not create new fixture infrastructure.

---

## File Structure

```
backend/
├── app/
│   ├── models/
│   │   ├── question.py       # Question, QuestionType, QuestionStatus, QuestionVariant
│   │   ├── mastery.py        # ConceptMastery, ReviewSchedule
│   │   └── review.py         # ReviewSession, ReviewOutcome, ReviewItem
│   ├── learning/
│   │   ├── __init__.py
│   │   └── engine.py         # retention(), update_stability(), compute_next_due_at(), rolling_mastery_score(), suggest_difficulty_delta()
│   └── reviews/
│       ├── __init__.py
│       ├── grading.py        # submit_answer(), submit_self_rate()
│       ├── selector.py       # select_concepts(), pick_variant(), build_items()
│       ├── schemas.py
│       └── router.py
├── alembic/
│   ├── env.py                 # import question, mastery, review models
│   └── versions/
│       ├── 0004_create_question_tables.py
│       ├── 0005_create_mastery_tables.py
│       └── 0006_create_review_tables.py
├── scripts/
│   └── seed_questions.py
└── tests/
    ├── learning/{__init__.py, test_engine.py}
    ├── reviews/{__init__.py, test_grading.py, test_selector.py, test_router.py}
    └── test_seed_questions.py

content/networking/                  # 10 new sibling files, written in Task 10
├── net-01-fundamentals.questions.yaml
├── ... (net-02 .. net-10)

frontend/src/
├── lib/api.ts                       # add review types + API calls
├── features/reviews/ReviewPage.tsx
└── App.tsx                          # add /review route
```

---

### Task 1: `Question`/`QuestionVariant` models + migration

**Files:**
- Create: `backend/app/models/question.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0004_create_question_tables.py`

**Interfaces:**
- Consumes: `app.db.Base`, `app.models.content.Concept`.
- Produces: `app.models.question.Question`, `QuestionType` (enum: `multiple_choice`, `true_false`, `free_explanation`), `QuestionStatus` (enum: `draft`, `published`), `app.models.question.QuestionVariant`.

- [ ] **Step 1: Write `backend/app/models/question.py`**

```python
import enum
import uuid
from typing import Optional

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.content import Concept


class QuestionType(str, enum.Enum):
    multiple_choice = "multiple_choice"
    true_false = "true_false"
    free_explanation = "free_explanation"


class QuestionStatus(str, enum.Enum):
    draft = "draft"
    published = "published"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=False)
    type: Mapped[QuestionType] = mapped_column(SAEnum(QuestionType, name="question_type"), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    evaluation_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[QuestionStatus] = mapped_column(
        SAEnum(QuestionStatus, name="question_status"), nullable=False, default=QuestionStatus.published
    )

    concept: Mapped[Concept] = relationship()
    variants: Mapped[list["QuestionVariant"]] = relationship(back_populates="question")


class QuestionVariant(Base):
    __tablename__ = "question_variants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    prompt_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    correct_option_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    correct_bool: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    question: Mapped["Question"] = relationship(back_populates="variants")
```

- [ ] **Step 2: Register with Alembic**

In `backend/alembic/env.py`, add after the `note` import:
```python
from app.models import question  # noqa: F401 — registers question models with Base.metadata
```

- [ ] **Step 3: Generate and apply the migration**

Run:
```bash
cd backend
alembic revision --autogenerate -m "create question tables"
mv alembic/versions/<generated_hash>_create_question_tables.py alembic/versions/0004_create_question_tables.py
alembic upgrade head
```

- [ ] **Step 4: Verify**

Run: `PGPASSWORD=cyberlearn psql -h localhost -p 55432 -U cyberlearn -d cyberlearn -c "\dt"`
Expected: `questions` and `question_variants` present.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/question.py backend/alembic/env.py backend/alembic/versions/0004_create_question_tables.py
git commit -m "feat: add Question and QuestionVariant models"
```

---

### Task 2: `ConceptMastery`/`ReviewSchedule` models + migration

**Files:**
- Create: `backend/app/models/mastery.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0005_create_mastery_tables.py`

**Interfaces:**
- Consumes: `app.db.Base`, `app.models.content.Concept`, `app.models.user.User`.
- Produces: `app.models.mastery.ConceptMastery`, `app.models.mastery.ReviewSchedule` — consumed by Tasks 5-7.

- [ ] **Step 1: Write `backend/app/models/mastery.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.content import Concept


class ConceptMastery(Base):
    __tablename__ = "concept_masteries"
    __table_args__ = (UniqueConstraint("user_id", "concept_id", name="uq_concept_mastery_user_concept"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    concept_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=False)
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_tested: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    concept: Mapped[Concept] = relationship()
    schedule: Mapped[Optional["ReviewSchedule"]] = relationship(back_populates="concept_mastery", uselist=False)


class ReviewSchedule(Base):
    __tablename__ = "review_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_mastery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concept_masteries.id"), unique=True, nullable=False
    )
    stability_days: Mapped[float] = mapped_column(Float, nullable=False)
    next_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    concept_mastery: Mapped["ConceptMastery"] = relationship(back_populates="schedule")
```

- [ ] **Step 2: Register with Alembic**

In `backend/alembic/env.py`, add after the `question` import:
```python
from app.models import mastery  # noqa: F401 — registers mastery models with Base.metadata
```

- [ ] **Step 3: Generate and apply the migration**

Run:
```bash
alembic revision --autogenerate -m "create mastery tables"
mv alembic/versions/<generated_hash>_create_mastery_tables.py alembic/versions/0005_create_mastery_tables.py
alembic upgrade head
```

- [ ] **Step 4: Verify**

Run: `PGPASSWORD=cyberlearn psql -h localhost -p 55432 -U cyberlearn -d cyberlearn -c "\d concept_masteries"`
Expected: table with the `uq_concept_mastery_user_concept` unique constraint listed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/mastery.py backend/alembic/env.py backend/alembic/versions/0005_create_mastery_tables.py
git commit -m "feat: add ConceptMastery and ReviewSchedule models"
```

---

### Task 3: `ReviewSession`/`ReviewItem` models + migration

**Files:**
- Create: `backend/app/models/review.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0006_create_review_tables.py`

**Interfaces:**
- Consumes: `app.db.Base`, `app.models.content.Concept`, `app.models.question.QuestionVariant`, `app.models.user.User`.
- Produces: `app.models.review.ReviewSession`, `app.models.review.ReviewOutcome` (enum: `correct`, `partial`, `incorrect`), `app.models.review.ReviewItem` (with a `.review_session` relationship back to `ReviewSession`) — consumed by Tasks 5-7.

- [ ] **Step 1: Write `backend/app/models/review.py`**

```python
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.content import Concept
from app.models.question import QuestionVariant


class ReviewOutcome(str, enum.Enum):
    correct = "correct"
    partial = "partial"
    incorrect = "incorrect"


class ReviewSession(Base):
    __tablename__ = "review_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewItem(Base):
    __tablename__ = "review_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_sessions.id"), nullable=False
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=False)
    question_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("question_variants.id"), nullable=False
    )
    user_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_declared: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    outcome: Mapped[Optional[ReviewOutcome]] = mapped_column(
        SAEnum(ReviewOutcome, name="review_outcome"), nullable=True
    )
    shown_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    concept: Mapped[Concept] = relationship()
    question_variant: Mapped[QuestionVariant] = relationship()
    review_session: Mapped["ReviewSession"] = relationship()
```

- [ ] **Step 2: Register with Alembic**

In `backend/alembic/env.py`, add after the `mastery` import:
```python
from app.models import review  # noqa: F401 — registers review models with Base.metadata
```

- [ ] **Step 3: Generate and apply the migration**

Run:
```bash
alembic revision --autogenerate -m "create review tables"
mv alembic/versions/<generated_hash>_create_review_tables.py alembic/versions/0006_create_review_tables.py
alembic upgrade head
```

- [ ] **Step 4: Verify**

Run: `PGPASSWORD=cyberlearn psql -h localhost -p 55432 -U cyberlearn -d cyberlearn -c "\dt"`
Expected: `review_sessions` and `review_items` present alongside everything else.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/review.py backend/alembic/env.py backend/alembic/versions/0006_create_review_tables.py
git commit -m "feat: add ReviewSession and ReviewItem models"
```

---

### Task 4: Retention engine (`app/learning/engine.py`)

**Files:**
- Create: `backend/app/learning/__init__.py`
- Create: `backend/app/learning/engine.py`
- Test: `backend/tests/learning/__init__.py`
- Test: `backend/tests/learning/test_engine.py`

**Interfaces:**
- Produces: `retention(stability_days, days_since_tested) -> float`, `forgetting_risk(stability_days, days_since_tested) -> float`, `update_stability(old_stability_days, outcome) -> float`, `compute_next_due_at(stability_days, now) -> datetime`, `rolling_mastery_score(outcomes: list[str]) -> float`, `suggest_difficulty_delta(accuracy_rolling, consecutive_failures) -> int`, and the constants `THRESHOLD`, `MIN_STABILITY_DAYS`, `INITIAL_STABILITY_DAYS` — consumed by `app/reviews/grading.py` and `app/reviews/selector.py` (Tasks 5-6).

This module has **no DB access** — pure functions, easy to test in isolation.

- [ ] **Step 1: Write the failing test**

`backend/tests/learning/__init__.py`: empty file.

`backend/tests/learning/test_engine.py`:
```python
import math
from datetime import datetime, timezone

from app.learning import engine


def test_retention_at_zero_days_is_one():
    assert engine.retention(stability_days=10, days_since_tested=0) == 1.0


def test_retention_decays_over_time():
    r1 = engine.retention(stability_days=10, days_since_tested=5)
    r2 = engine.retention(stability_days=10, days_since_tested=10)
    assert r1 > r2


def test_forgetting_risk_is_complement_of_retention():
    risk = engine.forgetting_risk(stability_days=10, days_since_tested=5)
    assert math.isclose(risk, 1 - engine.retention(10, 5))


def test_update_stability_increases_on_correct():
    new = engine.update_stability(old_stability_days=5, outcome="correct")
    assert new > 5


def test_update_stability_decreases_on_incorrect_but_floors():
    new = engine.update_stability(old_stability_days=1, outcome="incorrect")
    assert new >= engine.MIN_STABILITY_DAYS


def test_compute_next_due_at_initial_stability_is_about_one_day():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    due = engine.compute_next_due_at(engine.INITIAL_STABILITY_DAYS, now)
    delta_days = (due - now).total_seconds() / 86400
    assert math.isclose(delta_days, 1.0, rel_tol=0.01)


def test_rolling_mastery_score_averages_outcomes():
    score = engine.rolling_mastery_score(["correct", "correct", "incorrect"])
    assert math.isclose(score, (100 + 100 + 0) / 3)


def test_rolling_mastery_score_empty_is_zero():
    assert engine.rolling_mastery_score([]) == 0.0


def test_suggest_difficulty_delta_up_when_accuracy_high():
    assert engine.suggest_difficulty_delta(accuracy_rolling=0.9, consecutive_failures=0) == 1


def test_suggest_difficulty_delta_down_after_three_failures():
    assert engine.suggest_difficulty_delta(accuracy_rolling=0.2, consecutive_failures=3) == -1


def test_suggest_difficulty_delta_neutral_otherwise():
    assert engine.suggest_difficulty_delta(accuracy_rolling=0.5, consecutive_failures=1) == 0
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && pytest tests/learning/test_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.learning'`

- [ ] **Step 3: Write `backend/app/learning/__init__.py`** (empty file)

- [ ] **Step 4: Write `backend/app/learning/engine.py`**

```python
import math
from datetime import datetime, timedelta

THRESHOLD = 0.85
MIN_STABILITY_DAYS = 0.5
INITIAL_STABILITY_DAYS = 1 / -math.log(THRESHOLD)

OUTCOME_FACTORS = {"correct": 1.6, "partial": 1.1, "incorrect": 0.5}
OUTCOME_SCORES = {"correct": 100.0, "partial": 50.0, "incorrect": 0.0}


def retention(stability_days: float, days_since_tested: float) -> float:
    if stability_days <= 0:
        return 0.0
    return math.exp(-days_since_tested / stability_days)


def forgetting_risk(stability_days: float, days_since_tested: float) -> float:
    return 1 - retention(stability_days, days_since_tested)


def update_stability(old_stability_days: float, outcome: str) -> float:
    factor = OUTCOME_FACTORS[outcome]
    return max(old_stability_days * factor, MIN_STABILITY_DAYS)


def compute_next_due_at(stability_days: float, now: datetime) -> datetime:
    days_until_threshold = -stability_days * math.log(THRESHOLD)
    return now + timedelta(days=days_until_threshold)


def rolling_mastery_score(outcomes: list[str]) -> float:
    if not outcomes:
        return 0.0
    return sum(OUTCOME_SCORES[o] for o in outcomes) / len(outcomes)


def suggest_difficulty_delta(accuracy_rolling: float, consecutive_failures: int) -> int:
    if accuracy_rolling >= 0.8:
        return 1
    if consecutive_failures >= 3:
        return -1
    return 0
```

- [ ] **Step 5: Run it to verify it passes**

Run: `pytest tests/learning/test_engine.py -v`
Expected: PASS (11 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/learning backend/tests/learning
git commit -m "feat: add retention curve and difficulty engine formulas"
```

---

### Task 5: Grading service (`app/reviews/grading.py`)

**Files:**
- Create: `backend/app/reviews/__init__.py`
- Create: `backend/app/reviews/grading.py`
- Test: `backend/tests/reviews/__init__.py`
- Test: `backend/tests/reviews/test_grading.py`

**Interfaces:**
- Consumes: `app.learning.engine.*` (Task 4), `app.models.mastery.*` (Task 2), `app.models.question.*` (Task 1), `app.models.review.*` (Task 3).
- Produces: `submit_answer(db, item, user_response, confidence_declared) -> dict`, `submit_self_rate(db, item, outcome) -> dict` — consumed by Task 7's router.

- [ ] **Step 1: Write the failing test**

`backend/tests/reviews/__init__.py`: empty file.

`backend/tests/reviews/test_grading.py`:
```python
from datetime import datetime, timezone

from app.models.content import Concept, Domain, Topic
from app.models.mastery import ConceptMastery
from app.models.question import Question, QuestionStatus, QuestionType, QuestionVariant
from app.models.review import ReviewItem, ReviewSession
from app.models.user import User
from app.reviews import grading


def _seed_user(db):
    user = User(username="owner", password_hash="x", totp_secret="x")
    db.add(user)
    db.commit()
    return user


def _seed_concept(db):
    domain = Domain(slug="networking", name="Networking")
    db.add(domain)
    db.flush()
    topic = Topic(domain_id=domain.id, slug="fundamentals", name="Fundamentos")
    db.add(topic)
    db.flush()
    concept = Concept(topic_id=topic.id, slug="net-01", name="Fundamentos de Redes")
    db.add(concept)
    db.commit()
    return concept


def _seed_mc_question(db, concept):
    question = Question(
        concept_id=concept.id, type=QuestionType.multiple_choice, difficulty=1, status=QuestionStatus.published
    )
    db.add(question)
    db.flush()
    variant = QuestionVariant(question_id=question.id, prompt_markdown="?", options=["a", "b"], correct_option_index=1)
    db.add(variant)
    db.commit()
    return question, variant


def _seed_free_question(db, concept):
    question = Question(
        concept_id=concept.id,
        type=QuestionType.free_explanation,
        difficulty=2,
        evaluation_criteria="debe mencionar X",
        expected_answer="respuesta modelo",
        status=QuestionStatus.published,
    )
    db.add(question)
    db.flush()
    variant = QuestionVariant(question_id=question.id, prompt_markdown="Explica X")
    db.add(variant)
    db.commit()
    return question, variant


def _create_item(db, user, concept, variant):
    session = ReviewSession(user_id=user.id, mode="general", started_at=datetime.now(timezone.utc))
    db.add(session)
    db.flush()
    item = ReviewItem(
        review_session_id=session.id,
        concept_id=concept.id,
        question_variant_id=variant.id,
        shown_at=datetime.now(timezone.utc),
    )
    db.add(item)
    db.commit()
    return item


def test_submit_answer_multiple_choice_correct_creates_mastery_and_schedule(db_session):
    user = _seed_user(db_session)
    concept = _seed_concept(db_session)
    _, variant = _seed_mc_question(db_session, concept)
    item = _create_item(db_session, user, concept, variant)

    result = grading.submit_answer(db_session, item, "1", "seguro")

    assert result["outcome"] == "correct"
    mastery = db_session.query(ConceptMastery).filter_by(user_id=user.id, concept_id=concept.id).one()
    assert mastery.mastery_score == 100.0
    assert mastery.schedule is not None
    assert mastery.schedule.stability_days > grading.engine.INITIAL_STABILITY_DAYS


def test_submit_answer_multiple_choice_incorrect(db_session):
    user = _seed_user(db_session)
    concept = _seed_concept(db_session)
    _, variant = _seed_mc_question(db_session, concept)
    item = _create_item(db_session, user, concept, variant)

    result = grading.submit_answer(db_session, item, "0", None)

    assert result["outcome"] == "incorrect"


def test_submit_answer_free_explanation_returns_criteria_without_outcome(db_session):
    user = _seed_user(db_session)
    concept = _seed_concept(db_session)
    _, variant = _seed_free_question(db_session, concept)
    item = _create_item(db_session, user, concept, variant)

    result = grading.submit_answer(db_session, item, "mi respuesta", None)

    assert result == {"evaluation_criteria": "debe mencionar X", "expected_answer": "respuesta modelo"}
    assert item.outcome is None


def test_submit_self_rate_finalizes_free_explanation(db_session):
    user = _seed_user(db_session)
    concept = _seed_concept(db_session)
    _, variant = _seed_free_question(db_session, concept)
    item = _create_item(db_session, user, concept, variant)
    grading.submit_answer(db_session, item, "mi respuesta", None)

    result = grading.submit_self_rate(db_session, item, "partial")

    assert result == {"outcome": "partial"}
    mastery = db_session.query(ConceptMastery).filter_by(user_id=user.id, concept_id=concept.id).one()
    assert mastery.mastery_score == 50.0
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/reviews/test_grading.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.reviews'`

- [ ] **Step 3: Write `backend/app/reviews/__init__.py`** (empty file)

- [ ] **Step 4: Write `backend/app/reviews/grading.py`**

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.learning import engine
from app.models.mastery import ConceptMastery, ReviewSchedule
from app.models.question import QuestionType
from app.models.review import ReviewItem, ReviewOutcome

ROLLING_WINDOW = 5


def _get_or_create_mastery(db: Session, user_id, concept_id) -> ConceptMastery:
    mastery = (
        db.query(ConceptMastery)
        .filter(ConceptMastery.user_id == user_id, ConceptMastery.concept_id == concept_id)
        .first()
    )
    if mastery is None:
        mastery = ConceptMastery(user_id=user_id, concept_id=concept_id, mastery_score=0.0)
        db.add(mastery)
        db.flush()
    return mastery


def _finalize_item(db: Session, item: ReviewItem, outcome: str) -> None:
    now = datetime.now(timezone.utc)
    item.outcome = ReviewOutcome(outcome)
    item.answered_at = now

    mastery = _get_or_create_mastery(db, item.review_session.user_id, item.concept_id)
    mastery.last_seen = now
    mastery.last_tested = now

    schedule = mastery.schedule
    old_stability = schedule.stability_days if schedule else engine.INITIAL_STABILITY_DAYS
    new_stability = engine.update_stability(old_stability, outcome)
    next_due = engine.compute_next_due_at(new_stability, now)

    if schedule is None:
        schedule = ReviewSchedule(
            concept_mastery_id=mastery.id, stability_days=new_stability, next_due_at=next_due
        )
        db.add(schedule)
    else:
        schedule.stability_days = new_stability
        schedule.next_due_at = next_due

    recent_outcomes = (
        db.query(ReviewItem.outcome)
        .filter(ReviewItem.concept_id == item.concept_id, ReviewItem.outcome.isnot(None))
        .order_by(ReviewItem.answered_at.desc())
        .limit(ROLLING_WINDOW)
        .all()
    )
    mastery.mastery_score = engine.rolling_mastery_score([o[0].value for o in recent_outcomes])

    db.commit()


def submit_answer(db: Session, item: ReviewItem, user_response: str, confidence_declared: str | None) -> dict:
    item.user_response = user_response
    item.confidence_declared = confidence_declared

    variant = item.question_variant
    question = variant.question

    if question.type == QuestionType.multiple_choice:
        outcome = "correct" if str(variant.correct_option_index) == user_response else "incorrect"
        _finalize_item(db, item, outcome)
        return {"outcome": outcome, "correct_option_index": variant.correct_option_index}

    if question.type == QuestionType.true_false:
        outcome = "correct" if str(variant.correct_bool).lower() == user_response.lower() else "incorrect"
        _finalize_item(db, item, outcome)
        return {"outcome": outcome, "correct_bool": variant.correct_bool}

    db.commit()
    return {"evaluation_criteria": question.evaluation_criteria, "expected_answer": question.expected_answer}


def submit_self_rate(db: Session, item: ReviewItem, outcome: str) -> dict:
    _finalize_item(db, item, outcome)
    return {"outcome": outcome}
```

- [ ] **Step 5: Run it to verify it passes**

Run: `pytest tests/reviews/test_grading.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/reviews/__init__.py backend/app/reviews/grading.py backend/tests/reviews/__init__.py backend/tests/reviews/test_grading.py
git commit -m "feat: add answer grading and retention update service"
```

---

### Task 6: `ReviewSelector` (`app/reviews/selector.py`)

**Files:**
- Create: `backend/app/reviews/selector.py`
- Test: `backend/tests/reviews/test_selector.py`

**Interfaces:**
- Consumes: `app.learning.engine.forgetting_risk` (Task 4), `app.models.content.*`, `app.models.mastery.ConceptMastery` (Task 2), `app.models.question.*` (Task 1), `app.models.review.*` (Task 3).
- Produces: `select_concepts(db, user_id, mode, domain_slug=None, topic_slug=None, concept_slugs=None) -> list[Concept]`, `pick_variant(db, user_id, concept_id) -> QuestionVariant | None`, `build_items(db, user_id, mode, ...) -> list[tuple[Concept, QuestionVariant]]` — consumed by Task 7's router.

**Design note (performance):** candidate concepts and their masteries are loaded into Python and filtered/sorted there rather than with complex SQL, since the content volume at this stage (~10 concepts) makes that the simplest correct approach. Revisit with DB-side filtering if the catalog grows to hundreds of concepts.

- [ ] **Step 1: Write the failing test**

`backend/tests/reviews/test_selector.py`:
```python
from datetime import datetime, timezone

from app.models.content import Concept, Domain, Topic
from app.models.mastery import ConceptMastery
from app.models.question import Question, QuestionStatus, QuestionType, QuestionVariant
from app.models.review import ReviewItem, ReviewSession
from app.models.user import User
from app.reviews import selector


def _seed_user(db):
    user = User(username="owner", password_hash="x", totp_secret="x")
    db.add(user)
    db.commit()
    return user


def _seed_domain_topic(db, domain_slug="networking", topic_slug="fundamentals"):
    domain = Domain(slug=domain_slug, name=domain_slug)
    db.add(domain)
    db.flush()
    topic = Topic(domain_id=domain.id, slug=topic_slug, name=topic_slug)
    db.add(topic)
    db.flush()
    return domain, topic


def _seed_concept_with_question(db, topic, slug):
    concept = Concept(topic_id=topic.id, slug=slug, name=slug)
    db.add(concept)
    db.flush()
    question = Question(
        concept_id=concept.id, type=QuestionType.true_false, difficulty=1, status=QuestionStatus.published
    )
    db.add(question)
    db.flush()
    variant = QuestionVariant(question_id=question.id, prompt_markdown="?", correct_bool=True)
    db.add(variant)
    db.commit()
    return concept, variant


def test_general_mode_includes_never_studied_concepts(db_session):
    user = _seed_user(db_session)
    _, topic = _seed_domain_topic(db_session)
    concept, _ = _seed_concept_with_question(db_session, topic, "net-01")

    concepts = selector.select_concepts(db_session, user.id, "general")

    assert concept.id in [c.id for c in concepts]


def test_debilidades_mode_sorts_by_mastery_ascending(db_session):
    user = _seed_user(db_session)
    _, topic = _seed_domain_topic(db_session)
    weak, _ = _seed_concept_with_question(db_session, topic, "net-01")
    strong, _ = _seed_concept_with_question(db_session, topic, "net-02")

    db_session.add(ConceptMastery(user_id=user.id, concept_id=weak.id, mastery_score=20.0))
    db_session.add(ConceptMastery(user_id=user.id, concept_id=strong.id, mastery_score=90.0))
    db_session.commit()

    concepts = selector.select_concepts(db_session, user.id, "debilidades")

    assert [c.id for c in concepts[:2]] == [weak.id, strong.id]


def test_por_tema_filters_by_topic_slug(db_session):
    user = _seed_user(db_session)
    _, topic_a = _seed_domain_topic(db_session, topic_slug="topic-a")
    _, topic_b = _seed_domain_topic(db_session, domain_slug="networking", topic_slug="topic-b")
    concept_a, _ = _seed_concept_with_question(db_session, topic_a, "net-a")
    _seed_concept_with_question(db_session, topic_b, "net-b")

    concepts = selector.select_concepts(db_session, user.id, "por_tema", topic_slug="topic-a")

    assert [c.id for c in concepts] == [concept_a.id]


def test_pre_lab_filters_by_concept_slugs(db_session):
    user = _seed_user(db_session)
    _, topic = _seed_domain_topic(db_session)
    a, _ = _seed_concept_with_question(db_session, topic, "net-a")
    _seed_concept_with_question(db_session, topic, "net-b")

    concepts = selector.select_concepts(db_session, user.id, "pre_lab", concept_slugs=["net-a"])

    assert [c.id for c in concepts] == [a.id]


def test_pick_variant_avoids_recently_shown(db_session):
    user = _seed_user(db_session)
    _, topic = _seed_domain_topic(db_session)
    concept = Concept(topic_id=topic.id, slug="net-01", name="net-01")
    db_session.add(concept)
    db_session.flush()

    question = Question(
        concept_id=concept.id, type=QuestionType.true_false, difficulty=1, status=QuestionStatus.published
    )
    db_session.add(question)
    db_session.flush()
    variant_a = QuestionVariant(question_id=question.id, prompt_markdown="A", correct_bool=True)
    variant_b = QuestionVariant(question_id=question.id, prompt_markdown="B", correct_bool=True)
    db_session.add_all([variant_a, variant_b])
    db_session.commit()

    session = ReviewSession(user_id=user.id, mode="general", started_at=datetime.now(timezone.utc))
    db_session.add(session)
    db_session.flush()
    db_session.add(
        ReviewItem(
            review_session_id=session.id,
            concept_id=concept.id,
            question_variant_id=variant_a.id,
            shown_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    picked = selector.pick_variant(db_session, user.id, concept.id)

    assert picked.id == variant_b.id
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/reviews/test_selector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.reviews.selector'`

- [ ] **Step 3: Write `backend/app/reviews/selector.py`**

```python
import random
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.learning import engine
from app.models.content import Concept, Domain, Topic
from app.models.mastery import ConceptMastery
from app.models.question import Question, QuestionStatus, QuestionVariant
from app.models.review import ReviewItem, ReviewSession

RECENT_VARIANT_EXCLUDE = 3


def _concepts_with_published_questions(
    db: Session, domain_slug: str | None = None, topic_slug: str | None = None, concept_slugs: list[str] | None = None
) -> list[Concept]:
    query = (
        db.query(Concept)
        .join(Question, Question.concept_id == Concept.id)
        .filter(Question.status == QuestionStatus.published)
        .join(Topic, Concept.topic_id == Topic.id)
        .join(Domain, Topic.domain_id == Domain.id)
    )
    if domain_slug:
        query = query.filter(Domain.slug == domain_slug)
    if topic_slug:
        query = query.filter(Topic.slug == topic_slug)
    if concept_slugs:
        query = query.filter(Concept.slug.in_(concept_slugs))
    return query.distinct().all()


def _mastery_map(db: Session, user_id, concept_ids: list) -> dict:
    if not concept_ids:
        return {}
    rows = (
        db.query(ConceptMastery)
        .filter(ConceptMastery.user_id == user_id, ConceptMastery.concept_id.in_(concept_ids))
        .all()
    )
    return {m.concept_id: m for m in rows}


def select_concepts(
    db: Session,
    user_id,
    mode: str,
    domain_slug: str | None = None,
    topic_slug: str | None = None,
    concept_slugs: list[str] | None = None,
) -> list[Concept]:
    now = datetime.now(timezone.utc)
    concepts = _concepts_with_published_questions(
        db,
        domain_slug=domain_slug,
        topic_slug=topic_slug if mode == "por_tema" else None,
        concept_slugs=concept_slugs if mode == "pre_lab" else None,
    )
    masteries = _mastery_map(db, user_id, [c.id for c in concepts])

    def risk(concept: Concept) -> float:
        mastery = masteries.get(concept.id)
        if mastery is None or mastery.schedule is None or mastery.last_tested is None:
            return 1.0
        days = (now - mastery.last_tested).total_seconds() / 86400
        return engine.forgetting_risk(mastery.schedule.stability_days, days)

    def mastery_score(concept: Concept) -> float:
        mastery = masteries.get(concept.id)
        return mastery.mastery_score if mastery else 0.0

    def is_due(concept: Concept) -> bool:
        mastery = masteries.get(concept.id)
        if mastery is None or mastery.schedule is None:
            return True
        return mastery.schedule.next_due_at <= now

    if mode == "general":
        concepts = [c for c in concepts if is_due(c)]
    elif mode == "debilidades":
        concepts = sorted(concepts, key=mastery_score)
    elif mode == "olvidado":
        concepts = sorted(concepts, key=risk, reverse=True)
    elif mode in ("mixto", "sorpresa"):
        random.shuffle(concepts)
    # por_tema / pre_lab ya quedaron filtrados arriba

    return concepts


def pick_variant(db: Session, user_id, concept_id) -> QuestionVariant | None:
    variants = (
        db.query(QuestionVariant)
        .join(Question, QuestionVariant.question_id == Question.id)
        .filter(Question.concept_id == concept_id, Question.status == QuestionStatus.published)
        .all()
    )
    if not variants:
        return None

    recent_variant_ids = {
        row[0]
        for row in (
            db.query(ReviewItem.question_variant_id)
            .join(ReviewSession, ReviewItem.review_session_id == ReviewSession.id)
            .filter(ReviewSession.user_id == user_id, ReviewItem.concept_id == concept_id)
            .order_by(ReviewItem.shown_at.desc())
            .limit(RECENT_VARIANT_EXCLUDE)
        )
    }

    unseen = [v for v in variants if v.id not in recent_variant_ids]
    pool = unseen if unseen else variants
    return random.choice(pool)


def build_items(
    db: Session,
    user_id,
    mode: str,
    domain_slug: str | None = None,
    topic_slug: str | None = None,
    concept_slugs: list[str] | None = None,
    budget_count: int | None = None,
    budget_minutes: int | None = None,
) -> list[tuple[Concept, QuestionVariant]]:
    concepts = select_concepts(db, user_id, mode, domain_slug, topic_slug, concept_slugs)

    if budget_count is None and budget_minutes is not None:
        budget_count = max(1, round(budget_minutes * 60 / 90))
    if budget_count is None:
        budget_count = 10

    concepts = concepts[:budget_count]

    items = []
    for concept in concepts:
        variant = pick_variant(db, user_id, concept.id)
        if variant is not None:
            items.append((concept, variant))
    return items
```

- [ ] **Step 4: Run it to verify it passes**

Run: `pytest tests/reviews/test_selector.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/reviews/selector.py backend/tests/reviews/test_selector.py
git commit -m "feat: add ReviewSelector with 7 review modes and anti-repeat variant picking"
```

---

### Task 7: Reviews router

**Files:**
- Create: `backend/app/reviews/schemas.py`
- Create: `backend/app/reviews/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/reviews/test_router.py`

**Interfaces:**
- Consumes: `app.reviews.grading.*` (Task 5), `app.reviews.selector.build_items` (Task 6), `app.auth.dependencies.get_current_user`.
- Produces: `POST /api/v1/reviews/sessions`, `POST /api/v1/reviews/items/{item_id}/answer`, `POST /api/v1/reviews/items/{item_id}/self-rate`.

- [ ] **Step 1: Write `backend/app/reviews/schemas.py`**

```python
import uuid

from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    mode: str
    domain_slug: str | None = None
    topic_slug: str | None = None
    concept_slugs: list[str] | None = None
    budget_count: int | None = None
    budget_minutes: int | None = None


class ReviewItemPrompt(BaseModel):
    item_id: uuid.UUID
    concept_slug: str
    type: str
    prompt_markdown: str
    options: list[str] | None = None


class CreateSessionResponse(BaseModel):
    session_id: uuid.UUID
    items: list[ReviewItemPrompt]


class AnswerRequest(BaseModel):
    user_response: str
    confidence_declared: str | None = None


class SelfRateRequest(BaseModel):
    outcome: str
```

- [ ] **Step 2: Write `backend/app/reviews/router.py`**

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models.review import ReviewItem, ReviewSession
from app.models.user import User
from app.reviews import grading, selector
from app.reviews.schemas import (
    AnswerRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    ReviewItemPrompt,
    SelfRateRequest,
)

router = APIRouter()


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session(
    payload: CreateSessionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CreateSessionResponse:
    pairs = selector.build_items(
        db,
        user.id,
        payload.mode,
        domain_slug=payload.domain_slug,
        topic_slug=payload.topic_slug,
        concept_slugs=payload.concept_slugs,
        budget_count=payload.budget_count,
        budget_minutes=payload.budget_minutes,
    )

    session = ReviewSession(user_id=user.id, mode=payload.mode, started_at=datetime.now(timezone.utc))
    db.add(session)
    db.flush()

    prompts = []
    for concept, variant in pairs:
        item = ReviewItem(
            review_session_id=session.id,
            concept_id=concept.id,
            question_variant_id=variant.id,
            shown_at=datetime.now(timezone.utc),
        )
        db.add(item)
        db.flush()
        prompts.append(
            ReviewItemPrompt(
                item_id=item.id,
                concept_slug=concept.slug,
                type=variant.question.type.value,
                prompt_markdown=variant.prompt_markdown,
                options=variant.options,
            )
        )
    db.commit()

    return CreateSessionResponse(session_id=session.id, items=prompts)


def _get_item_or_404(db: Session, item_id: str) -> ReviewItem:
    item = db.query(ReviewItem).filter(ReviewItem.id == item_id).first()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review item not found")
    return item


@router.post("/items/{item_id}/answer")
def answer_item(
    item_id: str,
    payload: AnswerRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    item = _get_item_or_404(db, item_id)
    return grading.submit_answer(db, item, payload.user_response, payload.confidence_declared)


@router.post("/items/{item_id}/self-rate")
def self_rate_item(
    item_id: str,
    payload: SelfRateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    item = _get_item_or_404(db, item_id)
    if item.outcome is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Item already rated")
    return grading.submit_self_rate(db, item, payload.outcome)
```

- [ ] **Step 3: Mount it in `backend/app/main.py`**

```python
from app.notes.router import router as notes_router
from app.reviews.router import router as reviews_router
# ...
app.include_router(notes_router, prefix="/api/v1/notes", tags=["notes"])
app.include_router(reviews_router, prefix="/api/v1/reviews", tags=["reviews"])
```

- [ ] **Step 4: Write the failing test**

`backend/tests/reviews/test_router.py`:
```python
import pyotp

from app.auth.security import hash_password
from app.auth.totp import generate_totp_secret
from app.models.content import Concept, Domain, Topic
from app.models.question import Question, QuestionStatus, QuestionType, QuestionVariant
from app.models.user import User


def _login_as_owner(client, db_session):
    secret = generate_totp_secret()
    user = User(username="owner", password_hash=hash_password("s3cret-pass-1"), totp_secret=secret)
    db_session.add(user)
    db_session.commit()

    client.post("/api/v1/auth/login", json={"username": "owner", "password": "s3cret-pass-1"})
    code = pyotp.TOTP(secret).now()
    client.post("/api/v1/auth/mfa/verify", json={"code": code})
    return user


def _seed_mc_concept(db_session):
    domain = Domain(slug="networking", name="Networking")
    db_session.add(domain)
    db_session.flush()
    topic = Topic(domain_id=domain.id, slug="fundamentals", name="Fundamentos")
    db_session.add(topic)
    db_session.flush()
    concept = Concept(topic_id=topic.id, slug="net-01", name="Fundamentos de Redes")
    db_session.add(concept)
    db_session.flush()
    question = Question(
        concept_id=concept.id, type=QuestionType.multiple_choice, difficulty=1, status=QuestionStatus.published
    )
    db_session.add(question)
    db_session.flush()
    variant = QuestionVariant(question_id=question.id, prompt_markdown="?", options=["a", "b"], correct_option_index=1)
    db_session.add(variant)
    db_session.commit()
    return concept


def test_create_session_requires_auth(client):
    resp = client.post("/api/v1/reviews/sessions", json={"mode": "general"})
    assert resp.status_code == 401


def test_create_session_does_not_leak_correct_answer(client, db_session):
    _seed_mc_concept(db_session)
    _login_as_owner(client, db_session)

    resp = client.post("/api/v1/reviews/sessions", json={"mode": "general"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert "correct_option_index" not in body["items"][0]


def test_answer_flow_multiple_choice(client, db_session):
    _seed_mc_concept(db_session)
    _login_as_owner(client, db_session)

    session_resp = client.post("/api/v1/reviews/sessions", json={"mode": "general"})
    item_id = session_resp.json()["items"][0]["item_id"]

    answer_resp = client.post(f"/api/v1/reviews/items/{item_id}/answer", json={"user_response": "1"})
    assert answer_resp.status_code == 200
    assert answer_resp.json()["outcome"] == "correct"
```

- [ ] **Step 5: Run it to verify it passes**

Run: `pytest tests/reviews/test_router.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Run the full backend suite**

Run: `pytest -v`
Expected: all tests pass (all prior plans' tests + these).

- [ ] **Step 7: Commit**

```bash
git add backend/app/reviews/schemas.py backend/app/reviews/router.py backend/app/main.py backend/tests/reviews/test_router.py
git commit -m "feat: add reviews API endpoints"
```

---

### Task 8: `seed_questions.py` — idempotent question loader

**Files:**
- Create: `backend/scripts/seed_questions.py`
- Test: `backend/tests/test_seed_questions.py`

**Interfaces:**
- Consumes: `app.db.SessionLocal`, `app.models.content.Concept`, `app.models.question.*` (Task 1).
- Produces: `scripts.seed_questions.seed_questions(content_dir: str = "content") -> None` — called in Task 11, importable by tests.

**YAML schema** (one file per lesson, sibling to `*.concept.yaml`, glob pattern `*.questions.yaml`):
```yaml
concept_slug: net-02-ethernet-mac-arp
questions:
  - type: multiple_choice          # multiple_choice | true_false | free_explanation
    difficulty: 2                   # 0-7
    variants:
      - prompt_markdown: "..."
        options: ["a", "b", "c", "d"]
        correct_option_index: 1
  - type: true_false
    difficulty: 1
    variants:
      - prompt_markdown: "..."
        correct_bool: true
  - type: free_explanation
    difficulty: 3
    evaluation_criteria: "..."
    expected_answer: "..."
    variants:
      - prompt_markdown: "..."
```

- [ ] **Step 1: Write the failing test**

`backend/tests/test_seed_questions.py`:
```python
import os
import tempfile

import yaml

from app.models.content import Concept, Domain, Topic
from app.models.question import Question, QuestionVariant
from scripts.seed_questions import seed_questions

QUESTIONS_YAML = {
    "concept_slug": "net-01",
    "questions": [
        {
            "type": "multiple_choice",
            "difficulty": 1,
            "variants": [{"prompt_markdown": "¿2+2?", "options": ["3", "4"], "correct_option_index": 1}],
        },
        {
            "type": "true_false",
            "difficulty": 1,
            "variants": [{"prompt_markdown": "El cielo es azul", "correct_bool": True}],
        },
    ],
}


def _seed_concept(db, slug="net-01"):
    domain = Domain(slug="networking", name="Networking")
    db.add(domain)
    db.flush()
    topic = Topic(domain_id=domain.id, slug="fundamentals", name="Fundamentos")
    db.add(topic)
    db.flush()
    concept = Concept(topic_id=topic.id, slug=slug, name=slug)
    db.add(concept)
    db.commit()
    return concept


def _write_content_dir(tmpdir, filename, data):
    content_dir = os.path.join(tmpdir, "content", "networking")
    os.makedirs(content_dir, exist_ok=True)
    with open(os.path.join(content_dir, filename), "w") as f:
        yaml.safe_dump(data, f)
    return os.path.join(tmpdir, "content")


def test_seed_questions_creates_questions_and_variants(db_session):
    _seed_concept(db_session)
    with tempfile.TemporaryDirectory() as tmpdir:
        content_dir = _write_content_dir(tmpdir, "net-01.questions.yaml", QUESTIONS_YAML)
        seed_questions(content_dir)

    assert db_session.query(Question).count() == 2
    assert db_session.query(QuestionVariant).count() == 2


def test_seed_questions_is_idempotent(db_session):
    _seed_concept(db_session)
    with tempfile.TemporaryDirectory() as tmpdir:
        content_dir = _write_content_dir(tmpdir, "net-01.questions.yaml", QUESTIONS_YAML)
        seed_questions(content_dir)
        seed_questions(content_dir)

    assert db_session.query(Question).count() == 2
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_seed_questions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.seed_questions'`

- [ ] **Step 3: Write `backend/scripts/seed_questions.py`**

```python
import glob

import yaml
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.content import Concept
from app.models.question import Question, QuestionStatus, QuestionType, QuestionVariant


def _upsert_question(db: Session, concept: Concept, q_data: dict) -> Question:
    q_type = QuestionType(q_data["type"])
    first_prompt = q_data["variants"][0]["prompt_markdown"]

    existing = (
        db.query(Question)
        .join(QuestionVariant, QuestionVariant.question_id == Question.id)
        .filter(
            Question.concept_id == concept.id,
            Question.type == q_type,
            QuestionVariant.prompt_markdown == first_prompt,
        )
        .first()
    )
    if existing is not None:
        return existing

    question = Question(
        concept_id=concept.id,
        type=q_type,
        difficulty=q_data.get("difficulty", 1),
        evaluation_criteria=q_data.get("evaluation_criteria"),
        expected_answer=q_data.get("expected_answer"),
        status=QuestionStatus.published,
    )
    db.add(question)
    db.flush()

    for v in q_data["variants"]:
        db.add(
            QuestionVariant(
                question_id=question.id,
                prompt_markdown=v["prompt_markdown"],
                options=v.get("options"),
                correct_option_index=v.get("correct_option_index"),
                correct_bool=v.get("correct_bool"),
            )
        )
    return question


def seed_questions(content_dir: str = "content") -> None:
    db = SessionLocal()
    try:
        paths = sorted(glob.glob(f"{content_dir}/**/*.questions.yaml", recursive=True))
        count = 0
        for path in paths:
            with open(path) as f:
                data = yaml.safe_load(f)
            concept = db.query(Concept).filter(Concept.slug == data["concept_slug"]).first()
            if concept is None:
                print(f"WARNING: unknown concept_slug '{data['concept_slug']}' in {path}")
                continue
            for q_data in data["questions"]:
                _upsert_question(db, concept, q_data)
                count += 1
        db.commit()
        print(f"Seeded {count} questions from {content_dir}/")
    finally:
        db.close()


if __name__ == "__main__":
    seed_questions()
```

- [ ] **Step 4: Run it to verify it passes**

Run: `pytest tests/test_seed_questions.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_questions.py backend/tests/test_seed_questions.py
git commit -m "feat: add idempotent YAML question seed loader"
```

---

### Task 9: Frontend `/review` page

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/features/reviews/ReviewPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `api` from `frontend/src/lib/api.ts`.
- Produces: route `/review`.

- [ ] **Step 1: Add review types and API calls to `frontend/src/lib/api.ts`**

Add after the existing `Note` type:

```typescript
export type ReviewItemPrompt = {
  item_id: string;
  concept_slug: string;
  type: "multiple_choice" | "true_false" | "free_explanation";
  prompt_markdown: string;
  options: string[] | null;
};

export type CreateReviewSessionParams = {
  mode: string;
  domain_slug?: string;
  topic_slug?: string;
  concept_slugs?: string[];
  budget_count?: number;
  budget_minutes?: number;
};

export type AnswerResult = {
  outcome?: "correct" | "partial" | "incorrect";
  correct_option_index?: number;
  correct_bool?: boolean;
  evaluation_criteria?: string;
  expected_answer?: string;
};
```

Add to the `api` object:

```typescript
  createReviewSession: (params: CreateReviewSessionParams) =>
    request<{ session_id: string; items: ReviewItemPrompt[] }>("/reviews/sessions", {
      method: "POST",
      body: JSON.stringify(params),
    }),
  answerReviewItem: (itemId: string, user_response: string, confidence_declared?: string) =>
    request<AnswerResult>(`/reviews/items/${itemId}/answer`, {
      method: "POST",
      body: JSON.stringify({ user_response, confidence_declared }),
    }),
  selfRateReviewItem: (itemId: string, outcome: string) =>
    request<{ outcome: string }>(`/reviews/items/${itemId}/self-rate`, {
      method: "POST",
      body: JSON.stringify({ outcome }),
    }),
```

- [ ] **Step 2: Write `frontend/src/features/reviews/ReviewPage.tsx`**

```tsx
import { useState } from "react";
import { api, AnswerResult, ReviewItemPrompt } from "../../lib/api";

type Mode = "general" | "debilidades" | "olvidado" | "por_tema" | "mixto" | "sorpresa" | "pre_lab";
type Outcome = "correct" | "partial" | "incorrect";

const MODES: { value: Mode; label: string }[] = [
  { value: "general", label: "General" },
  { value: "debilidades", label: "Debilidades" },
  { value: "olvidado", label: "Olvidado" },
  { value: "por_tema", label: "Por tema" },
  { value: "mixto", label: "Mixto" },
  { value: "sorpresa", label: "Sorpresa" },
  { value: "pre_lab", label: "Antes de laboratorio" },
];

const CONFIDENCE_OPTIONS = ["nada_seguro", "poco_seguro", "seguro", "muy_seguro"] as const;

export function ReviewPage() {
  const [mode, setMode] = useState<Mode>("general");
  const [budgetCount, setBudgetCount] = useState(5);
  const [items, setItems] = useState<ReviewItemPrompt[] | null>(null);
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<Outcome[]>([]);

  const handleStart = async () => {
    const session = await api.createReviewSession({ mode, budget_count: budgetCount });
    setItems(session.items);
    setIndex(0);
    setResults([]);
  };

  const handleDone = (outcome: Outcome) => {
    setResults((r) => [...r, outcome]);
    setIndex((i) => i + 1);
  };

  if (!items) {
    return (
      <div>
        <h1>Repasar</h1>
        <div>
          {MODES.map((m) => (
            <label key={m.value}>
              <input type="radio" name="mode" checked={mode === m.value} onChange={() => setMode(m.value)} />
              {m.label}
            </label>
          ))}
        </div>
        <label>
          Cantidad de preguntas:
          <input
            type="number"
            value={budgetCount}
            onChange={(e) => setBudgetCount(Number(e.target.value))}
            min={1}
            max={20}
          />
        </label>
        <button onClick={handleStart}>Empezar</button>
      </div>
    );
  }

  if (index >= items.length) {
    const correct = results.filter((r) => r === "correct").length;
    const partial = results.filter((r) => r === "partial").length;
    const incorrect = results.filter((r) => r === "incorrect").length;
    return (
      <div>
        <h1>Resumen</h1>
        <p>
          {correct} de {items.length} correctas ({partial} parciales, {incorrect} incorrectas)
        </p>
        <button onClick={() => setItems(null)}>Repasar de nuevo</button>
      </div>
    );
  }

  return <ReviewItemView key={items[index].item_id} item={items[index]} onDone={handleDone} />;
}

function ReviewItemView({ item, onDone }: { item: ReviewItemPrompt; onDone: (outcome: Outcome) => void }) {
  const [response, setResponse] = useState("");
  const [confidence, setConfidence] = useState<string | undefined>(undefined);
  const [feedback, setFeedback] = useState<AnswerResult | null>(null);

  const handleSubmit = async () => {
    const result = await api.answerReviewItem(item.item_id, response, confidence);
    setFeedback(result);
  };

  const handleSelfRate = async (outcome: Outcome) => {
    await api.selfRateReviewItem(item.item_id, outcome);
    onDone(outcome);
  };

  return (
    <div>
      <p>{item.concept_slug}</p>
      <div>{item.prompt_markdown}</div>

      {!feedback && (
        <>
          <div>
            {CONFIDENCE_OPTIONS.map((c) => (
              <label key={c}>
                <input
                  type="radio"
                  name="confidence"
                  checked={confidence === c}
                  onChange={() => setConfidence(c)}
                />
                {c}
              </label>
            ))}
          </div>

          {item.type === "multiple_choice" && item.options && (
            <div>
              {item.options.map((opt, i) => (
                <label key={i}>
                  <input
                    type="radio"
                    name="response"
                    checked={response === String(i)}
                    onChange={() => setResponse(String(i))}
                  />
                  {opt}
                </label>
              ))}
            </div>
          )}

          {item.type === "true_false" && (
            <div>
              <label>
                <input
                  type="radio"
                  name="response"
                  checked={response === "true"}
                  onChange={() => setResponse("true")}
                />
                Verdadero
              </label>
              <label>
                <input
                  type="radio"
                  name="response"
                  checked={response === "false"}
                  onChange={() => setResponse("false")}
                />
                Falso
              </label>
            </div>
          )}

          {item.type === "free_explanation" && (
            <textarea value={response} onChange={(e) => setResponse(e.target.value)} rows={6} />
          )}

          <button onClick={handleSubmit}>Responder</button>
        </>
      )}

      {feedback && item.type !== "free_explanation" && (
        <div>
          <p>{feedback.outcome === "correct" ? "¡Correcto!" : "Incorrecto"}</p>
          <button onClick={() => onDone(feedback.outcome as Outcome)}>Siguiente</button>
        </div>
      )}

      {feedback && item.type === "free_explanation" && (
        <div>
          <p>Criterios: {feedback.evaluation_criteria}</p>
          <p>Respuesta esperada: {feedback.expected_answer}</p>
          <p>¿Cómo calificas tu respuesta?</p>
          <button onClick={() => handleSelfRate("correct")}>Correcto</button>
          <button onClick={() => handleSelfRate("partial")}>Parcial</button>
          <button onClick={() => handleSelfRate("incorrect")}>Incorrecto</button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Add the route in `frontend/src/App.tsx`**

```tsx
import { ReviewPage } from "./features/reviews/ReviewPage";
// ...
            <Route path="/notes/:id" element={<NoteDetailPage />} />
            <Route path="/review" element={<ReviewPage />} />
```

- [ ] **Step 4: Type-check**

Run: `cd frontend && npx tsc -b --noEmit`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/features/reviews/ReviewPage.tsx frontend/src/App.tsx
git commit -m "feat: add /review page with mode selection and answer flow"
```

---

### Task 10: Dispatch `cybersecurity-instructor` for question content (NET-01–NET-10)

**Files:** none created directly by this task — dispatches a background agent that writes `content/networking/net-XX-*.questions.yaml` (10 files).

- [ ] **Step 1: Dispatch the agent**

Use the `Agent` tool (`subagent_type: general-purpose`, instructed to adopt the persona in `.claude/agents/cybersecurity-instructor.md`, same pattern as when the lessons themselves were written). Prompt must include:
- Read `docs/superpowers/plans/2026-08-13-questions-retention.md` Task 8's YAML schema (reproduced above) — do not invent a different shape.
- Read all 10 existing `content/networking/net-*.yaml` lesson files first, so questions are grounded in what each lesson actually teaches (don't invent facts not covered in the lesson content).
- For each of the 10 concepts, write `content/networking/<same-basename>.questions.yaml` with 3-5 questions, mixing all three types (`multiple_choice`, `true_false`, `free_explanation`) — not all one type.
- `multiple_choice`: 4 options, exactly one correct, distractors must be plausible (not obviously wrong) — a beginner who half-understands the concept should be able to eliminate at most 1-2 options, not 3.
- `true_false`: avoid trivially obvious true/false statements — include at least one per lesson that targets a common misconception documented in that lesson's own `errores_frecuentes` field.
- `free_explanation`: `evaluation_criteria` must be a concrete checklist an autograder-by-eye could use ("menciona X, explica por qué Y, no confunde Z con W"), and `expected_answer` a real model answer, not a one-liner.
- Verify any specific facts via WebSearch as needed (same standard as the lesson-writing task).
- Report back the final list of all 10 files with a one-sentence summary of what each covers.

- [ ] **Step 2: Wait for the agent to complete**

The agent runs in the background — do not fabricate its results. Wait for the completion notification.

No commit in this step — the written files are committed together with validation in Task 11.

---

### Task 11: Load real questions, verify end-to-end, update the checklist

**Files:** none created — this task consumes the 10 `*.questions.yaml` files from Task 10 and Task 8's `seed_questions.py`. Also updates `PROJECT_MASTER_CHECKLIST.md`.

- [ ] **Step 1: Validate the 10 question files**

Run:
```bash
cd backend
.venv/bin/python -c "
import yaml, glob
for path in sorted(glob.glob('../content/networking/*.questions.yaml')):
    with open(path) as f:
        data = yaml.safe_load(f)
    assert 'concept_slug' in data and 'questions' in data, path
    for q in data['questions']:
        assert q['type'] in ('multiple_choice', 'true_false', 'free_explanation'), (path, q['type'])
        assert len(q['variants']) >= 1, path
    print(path, '->', data['concept_slug'], len(data['questions']), 'questions')
"
```
Expected: 10 lines, no assertion errors.

- [ ] **Step 2: Run the seed loader**

Run:
```bash
PYTHONPATH=. .venv/bin/python -c "from scripts.seed_questions import seed_questions; seed_questions('../content')"
```
Expected: `Seeded <N> questions from ../content/`, no `WARNING: unknown concept_slug` lines.

- [ ] **Step 3: Restart the backend and verify via API**

Run (kill by exact PID as established in prior plans — never a broad `pkill -f uvicorn` pattern):
```bash
ss -ltnp | grep 8001   # find the PID
kill <pid>
cd backend && setsid nohup .venv/bin/uvicorn app.main:app --port 8001 > /tmp/uvicorn.log 2>&1 < /dev/null &
disown
sleep 2
curl -s http://localhost:8001/api/v1/health
```

Then, with a fresh authenticated `cookies.txt` (login + MFA, same pattern as prior plans):
```bash
curl -s -b /tmp/cookies.txt -X POST http://localhost:8001/api/v1/reviews/sessions \
  -H "Content-Type: application/json" -d '{"mode":"general","budget_count":5}' | python3 -m json.tool
```
Expected: a session with up to 5 items, each with a `prompt_markdown` and (for multiple_choice) `options`, but no correct-answer fields.

Pick one `multiple_choice` item's `item_id` from the response and answer it:
```bash
curl -s -b /tmp/cookies.txt -X POST http://localhost:8001/api/v1/reviews/items/<item_id>/answer \
  -H "Content-Type: application/json" -d '{"user_response":"0","confidence_declared":"seguro"}' | python3 -m json.tool
```
Expected: `{"outcome": "correct"|"incorrect", "correct_option_index": N}`.

Verify `ConceptMastery`/`ReviewSchedule` were created:
```bash
PGPASSWORD=cyberlearn psql -h localhost -p 55432 -U cyberlearn -d cyberlearn -c \
  "SELECT cm.mastery_score, rs.stability_days, rs.next_due_at FROM concept_masteries cm JOIN review_schedules rs ON rs.concept_mastery_id = cm.id;"
```
Expected: at least one row.

- [ ] **Step 4: Browser walkthrough**

1. Log in, go to `/review`.
2. Pick mode "General", 5 preguntas, click Empezar.
3. Answer a multiple_choice and a true_false item — confirm immediate feedback and that clicking "Siguiente" advances.
4. Answer a free_explanation item — confirm criteria/expected answer appear only after submitting, then self-rate and confirm it advances.
5. Reach the summary screen — confirm the counts match what you answered.

- [ ] **Step 5: Run the full backend test suite one more time**

Run: `cd backend && pytest -v`
Expected: all tests pass.

- [ ] **Step 6: Commit the question content**

```bash
git add content/networking/*.questions.yaml
git commit -m "content: add questions for NET-01 to NET-10"
```

- [ ] **Step 7: Update `PROJECT_MASTER_CHECKLIST.md`**

Mark every completed item under "Banco de preguntas (mínimo) + Motor de retención + Repaso" as `[x]` (all sub-items from Task 1-11 above are now done). Leave the three items under "Pendiente para más adelante" unchecked — they are explicitly deferred, not done. Commit:

```bash
git add PROJECT_MASTER_CHECKLIST.md
git commit -m "docs: update checklist — questions + retention engine complete"
```

Report the resulting checklist section to the user (per their standing instruction to show checklist status after finishing any implementation).
