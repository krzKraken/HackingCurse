# Focus/Timer + "No sé qué estudiar" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist a single active `LearningSession` per user (timer, active time, last position), let the frontend resume exactly where the user left off, show non-blocking break/hyperfocus reminders, and implement the "No sé qué estudiar" single-recommendation endpoint.

**Architecture:** New `app/focus/` backend module (session lifecycle service + recommendation algorithm + router), one new table. Frontend adds a `FocusSessionProvider` (React context) that pings the backend periodically and drives the timer/reminders, plus a "No sé qué estudiar" button.

**Tech Stack:** Same as prior plans (FastAPI, SQLAlchemy 2.0.52, Alembic, Postgres, React+Vite).

## Global Constraints

- Must match `docs/superpowers/specs/2026-08-13-focus-timer-design.md` exactly, including its 3 documented simplifications (merged `LearningSession`/`FocusSession` table, 3-signal recommendation instead of 5, priority-tier selection instead of weighted sum).
- A user has at most one active (`ended_at IS NULL`) `LearningSession` at a time — starting a new one auto-closes any existing active one.
- The timer must never auto-stop a session, even past the hyperfocus threshold — reminders are informational only.
- Routes live under `/api/v1/focus/...`, authenticated with `get_current_user`.
- No automated frontend tests in this plan (consistent with prior plans — verification is backend-test-driven plus manual browser walkthrough).

---

## File Structure

```
backend/
├── app/
│   ├── models/
│   │   └── focus.py            # LearningSession, TimerMode
│   ├── focus/
│   │   ├── __init__.py
│   │   ├── service.py          # start_session, get_current_session, update_session, end_session
│   │   ├── recommendation.py   # get_recommendation (3-tier priority algorithm)
│   │   ├── schemas.py
│   │   └── router.py
├── alembic/
│   ├── env.py                  # import focus models
│   └── versions/0007_create_focus_tables.py
└── tests/focus/
    ├── __init__.py
    ├── test_service.py
    ├── test_recommendation.py
    └── test_router.py

frontend/src/
├── lib/api.ts                   # add LearningSession/Recommendation types + calls
├── features/focus/
│   ├── useFocusSession.tsx      # FocusSessionProvider + hook (ping, resume, reminders)
│   ├── FocusWidgets.tsx         # timer display, mode selector, resume banner, reminders
│   └── RecommendationButton.tsx # "No sé qué estudiar" button + result card
└── App.tsx                      # wrap routes with FocusSessionProvider, add ProtectedLayout
```

---

### Task 1: `LearningSession` model + migration

**Files:**
- Create: `backend/app/models/focus.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0007_create_focus_tables.py`

**Interfaces:**
- Consumes: `app.db.Base`, `app.models.user.User`.
- Produces: `app.models.focus.LearningSession`, `app.models.focus.TimerMode` (enum: `count_up`, `pomodoro`, `countdown`, `no_timer`).

- [ ] **Step 1: Write `backend/app/models/focus.py`**

```python
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TimerMode(str, enum.Enum):
    count_up = "count_up"
    pomodoro = "pomodoro"
    countdown = "countdown"
    no_timer = "no_timer"


class LearningSession(Base):
    __tablename__ = "learning_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    active_time_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_position: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    timer_mode: Mapped[TimerMode] = mapped_column(
        SAEnum(TimerMode, name="timer_mode"), nullable=False, default=TimerMode.count_up
    )
    pomodoro_preset: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    break_reminder_threshold_min: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    hyperfocus_reminder_min: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
```

- [ ] **Step 2: Register with Alembic**

In `backend/alembic/env.py`, add after the `question` import (order among the new modules doesn't matter, just keep it alongside the others):
```python
from app.models import focus  # noqa: F401 — registers focus models with Base.metadata
```

- [ ] **Step 3: Generate and apply the migration**

Run:
```bash
cd backend
alembic revision --autogenerate -m "create focus tables"
mv alembic/versions/<generated_hash>_create_focus_tables.py alembic/versions/0007_create_focus_tables.py
alembic upgrade head
```

- [ ] **Step 4: Verify**

Run: `PGPASSWORD=cyberlearn psql -h localhost -p 55432 -U cyberlearn -d cyberlearn -c "\d learning_sessions"`
Expected: table present with all the columns above.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/focus.py backend/alembic/env.py backend/alembic/versions/0007_create_focus_tables.py
git commit -m "feat: add LearningSession model"
```

---

### Task 2: Focus session lifecycle service

**Files:**
- Create: `backend/app/focus/__init__.py`
- Create: `backend/app/focus/service.py`
- Test: `backend/tests/focus/__init__.py`
- Test: `backend/tests/focus/test_service.py`

**Interfaces:**
- Consumes: `app.models.focus.*` (Task 1).
- Produces: `start_session(db, user_id) -> LearningSession`, `get_current_session(db, user_id) -> LearningSession | None`, `update_session(db, session, active_time_sec=None, last_position=None, timer_mode=None, pomodoro_preset=None) -> LearningSession`, `end_session(db, session) -> LearningSession` — consumed by Task 4's router.

- [ ] **Step 1: Write the failing test**

`backend/tests/focus/__init__.py`: empty file.

`backend/tests/focus/test_service.py`:
```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && pytest tests/focus/test_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.focus'`

- [ ] **Step 3: Write `backend/app/focus/__init__.py`** (empty file)

- [ ] **Step 4: Write `backend/app/focus/service.py`**

```python
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
```

- [ ] **Step 5: Run it to verify it passes**

Run: `pytest tests/focus/test_service.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/focus/__init__.py backend/app/focus/service.py backend/tests/focus/__init__.py backend/tests/focus/test_service.py
git commit -m "feat: add focus session lifecycle service"
```

---

### Task 3: "No sé qué estudiar" recommendation algorithm

**Files:**
- Create: `backend/app/focus/recommendation.py`
- Test: `backend/tests/focus/test_recommendation.py`

**Interfaces:**
- Consumes: `app.learning.engine.forgetting_risk` (questions-retention plan), `app.models.content.*`, `app.models.mastery.*`, `app.models.question.*`.
- Produces: `get_recommendation(db, user_id, minutes: int = 15) -> dict | None` — consumed by Task 4's router.

- [ ] **Step 1: Write the failing test**

`backend/tests/focus/test_recommendation.py`:
```python
from datetime import datetime, timedelta, timezone

from app.focus import recommendation
from app.models.content import Concept, ConceptRelationship, Domain, RelationshipType, Topic
from app.models.mastery import ConceptMastery, ReviewSchedule
from app.models.question import Question, QuestionStatus, QuestionType, QuestionVariant
from app.models.user import User


def _seed_user(db):
    user = User(username="owner", password_hash="x", totp_secret="x")
    db.add(user)
    db.commit()
    return user


def _seed_concept(db, slug, prereq=None):
    domain = db.query(Domain).filter_by(slug="networking").first()
    if domain is None:
        domain = Domain(slug="networking", name="Networking")
        db.add(domain)
        db.flush()
    topic = db.query(Topic).filter_by(domain_id=domain.id, slug="t1").first()
    if topic is None:
        topic = Topic(domain_id=domain.id, slug="t1", name="t1")
        db.add(topic)
        db.flush()
    concept = Concept(topic_id=topic.id, slug=slug, name=slug)
    db.add(concept)
    db.flush()
    question = Question(
        concept_id=concept.id, type=QuestionType.true_false, difficulty=1, status=QuestionStatus.published
    )
    db.add(question)
    db.flush()
    db.add(QuestionVariant(question_id=question.id, prompt_markdown="?", correct_bool=True))
    if prereq is not None:
        db.add(ConceptRelationship(source_id=concept.id, target_id=prereq.id, type=RelationshipType.prerequisite))
    db.commit()
    return concept


def test_recommends_next_concept_for_fresh_user(db_session):
    user = _seed_user(db_session)
    _seed_concept(db_session, "net-01")

    rec = recommendation.get_recommendation(db_session, user.id)

    assert rec["activity_type"] == "learn"
    assert rec["concept_slug"] == "net-01"


def test_does_not_recommend_concept_with_unmet_prerequisite(db_session):
    user = _seed_user(db_session)
    c1 = _seed_concept(db_session, "net-01")
    _seed_concept(db_session, "net-02", prereq=c1)

    rec = recommendation.get_recommendation(db_session, user.id)

    assert rec["concept_slug"] == "net-01"


def test_recommends_next_concept_once_prerequisite_satisfied(db_session):
    user = _seed_user(db_session)
    c1 = _seed_concept(db_session, "net-01")
    _seed_concept(db_session, "net-02", prereq=c1)
    db_session.add(ConceptMastery(user_id=user.id, concept_id=c1.id, mastery_score=100.0))
    db_session.commit()

    rec = recommendation.get_recommendation(db_session, user.id)

    assert rec["concept_slug"] == "net-02"


def test_prioritizes_overdue_review_over_new_concept(db_session):
    user = _seed_user(db_session)
    c1 = _seed_concept(db_session, "net-01")
    _seed_concept(db_session, "net-02")
    mastery = ConceptMastery(
        user_id=user.id,
        concept_id=c1.id,
        mastery_score=80.0,
        last_tested=datetime.now(timezone.utc) - timedelta(days=10),
    )
    db_session.add(mastery)
    db_session.flush()
    db_session.add(
        ReviewSchedule(
            concept_mastery_id=mastery.id,
            stability_days=1.0,
            next_due_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    db_session.commit()

    rec = recommendation.get_recommendation(db_session, user.id)

    assert rec["activity_type"] == "review"
    assert rec["concept_slug"] == "net-01"


def test_returns_none_when_no_content_exists(db_session):
    user = _seed_user(db_session)
    assert recommendation.get_recommendation(db_session, user.id) is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/focus/test_recommendation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.focus.recommendation'`

- [ ] **Step 3: Write `backend/app/focus/recommendation.py`**

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.learning import engine
from app.models.content import Concept, ConceptRelationship, RelationshipType
from app.models.mastery import ConceptMastery
from app.models.question import Question, QuestionStatus


def _concepts_with_questions(db: Session) -> list[Concept]:
    return (
        db.query(Concept)
        .join(Question, Question.concept_id == Concept.id)
        .filter(Question.status == QuestionStatus.published)
        .distinct()
        .all()
    )


def _mastery_map(db: Session, user_id, concept_ids: list) -> dict:
    if not concept_ids:
        return {}
    rows = (
        db.query(ConceptMastery)
        .filter(ConceptMastery.user_id == user_id, ConceptMastery.concept_id.in_(concept_ids))
        .all()
    )
    return {m.concept_id: m for m in rows}


def _prerequisites_satisfied(db: Session, concept_id, mastery_map: dict) -> bool:
    prereqs = (
        db.query(ConceptRelationship)
        .filter(
            ConceptRelationship.source_id == concept_id,
            ConceptRelationship.type == RelationshipType.prerequisite,
        )
        .all()
    )
    return all(rel.target_id in mastery_map for rel in prereqs)


def get_recommendation(db: Session, user_id, minutes: int = 15) -> dict | None:
    now = datetime.now(timezone.utc)
    concepts = _concepts_with_questions(db)
    if not concepts:
        return None
    mastery_map = _mastery_map(db, user_id, [c.id for c in concepts])

    due = []
    for c in concepts:
        mastery = mastery_map.get(c.id)
        if mastery is None or mastery.schedule is None:
            continue
        if mastery.schedule.next_due_at <= now:
            days = (now - mastery.last_tested).total_seconds() / 86400 if mastery.last_tested else 0
            risk = engine.forgetting_risk(mastery.schedule.stability_days, days)
            due.append((risk, c))
    if due:
        due.sort(key=lambda pair: pair[0], reverse=True)
        concept = due[0][1]
        return {
            "activity_type": "review",
            "concept_slug": concept.slug,
            "concept_name": concept.name,
            "reason": f"{concept.name} tiene retención baja y está vencido para repaso.",
        }

    if minutes >= 10:
        for c in concepts:
            if c.id in mastery_map:
                continue
            if _prerequisites_satisfied(db, c.id, mastery_map):
                return {
                    "activity_type": "learn",
                    "concept_slug": c.slug,
                    "concept_name": c.name,
                    "reason": f"{c.name} es el siguiente concepto en tu ruta — ya tienes los prerequisitos.",
                }

    studied = [(m.mastery_score, c) for c in concepts if (m := mastery_map.get(c.id)) is not None]
    if studied:
        studied.sort(key=lambda pair: pair[0])
        concept = studied[0][1]
        return {
            "activity_type": "review",
            "concept_slug": concept.slug,
            "concept_name": concept.name,
            "reason": f"{concept.name} es tu concepto más débil actualmente.",
        }

    return None
```

- [ ] **Step 4: Run it to verify it passes**

Run: `pytest tests/focus/test_recommendation.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/focus/recommendation.py backend/tests/focus/test_recommendation.py
git commit -m "feat: add 'No sé qué estudiar' recommendation algorithm"
```

---

### Task 4: Focus router

**Files:**
- Create: `backend/app/focus/schemas.py`
- Create: `backend/app/focus/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/focus/test_router.py`

**Interfaces:**
- Consumes: `app.focus.service.*` (Task 2), `app.focus.recommendation.get_recommendation` (Task 3), `app.auth.dependencies.get_current_user`.
- Produces: `POST /api/v1/focus/sessions`, `GET /api/v1/focus/sessions/current`, `PATCH /api/v1/focus/sessions/{id}`, `POST /api/v1/focus/sessions/{id}/end`, `GET /api/v1/focus/recommendation`.

- [ ] **Step 1: Write `backend/app/focus/schemas.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel


class SessionOut(BaseModel):
    id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    active_time_sec: int
    last_position: str | None
    timer_mode: str
    pomodoro_preset: str | None
    break_reminder_threshold_min: int
    hyperfocus_reminder_min: int


class SessionUpdate(BaseModel):
    active_time_sec: int | None = None
    last_position: str | None = None
    timer_mode: str | None = None
    pomodoro_preset: str | None = None


class RecommendationOut(BaseModel):
    activity_type: str
    concept_slug: str
    concept_name: str
    reason: str
```

- [ ] **Step 2: Write `backend/app/focus/router.py`**

```python
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


def _get_session_or_404(db: Session, user: User, session_id: str) -> LearningSession:
    session = (
        db.query(LearningSession)
        .filter(LearningSession.id == session_id, LearningSession.user_id == user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return session


@router.patch("/sessions/{session_id}", response_model=SessionOut)
def update_session_endpoint(
    session_id: str,
    payload: SessionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionOut:
    session = _get_session_or_404(db, user, session_id)
    session = service.update_session(
        db,
        session,
        active_time_sec=payload.active_time_sec,
        last_position=payload.last_position,
        timer_mode=payload.timer_mode,
        pomodoro_preset=payload.pomodoro_preset,
    )
    return _to_session_out(session)


@router.post("/sessions/{session_id}/end", response_model=SessionOut)
def end_session_endpoint(
    session_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SessionOut:
    session = _get_session_or_404(db, user, session_id)
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
```

- [ ] **Step 3: Mount it in `backend/app/main.py`**

```python
from app.focus.router import router as focus_router
# ...
app.include_router(focus_router, prefix="/api/v1/focus", tags=["focus"])
```

- [ ] **Step 4: Write the failing test**

`backend/tests/focus/test_router.py`:
```python
import pyotp

from app.auth.security import hash_password
from app.auth.totp import generate_totp_secret
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


def test_sessions_require_auth(client):
    assert client.post("/api/v1/focus/sessions").status_code == 401


def test_start_get_update_end_session_flow(client, db_session):
    _login_as_owner(client, db_session)

    start_resp = client.post("/api/v1/focus/sessions")
    assert start_resp.status_code == 200
    session_id = start_resp.json()["id"]

    current_resp = client.get("/api/v1/focus/sessions/current")
    assert current_resp.status_code == 200
    assert current_resp.json()["id"] == session_id

    update_resp = client.patch(
        f"/api/v1/focus/sessions/{session_id}",
        json={"active_time_sec": 90, "last_position": "/lessons/net-01"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["active_time_sec"] == 90

    end_resp = client.post(f"/api/v1/focus/sessions/{session_id}/end")
    assert end_resp.status_code == 200
    assert end_resp.json()["ended_at"] is not None

    assert client.get("/api/v1/focus/sessions/current").status_code == 404


def test_recommendation_returns_204_with_no_content(client, db_session):
    _login_as_owner(client, db_session)
    resp = client.get("/api/v1/focus/recommendation")
    assert resp.status_code == 204
```

- [ ] **Step 5: Run it to verify it passes**

Run: `pytest tests/focus/test_router.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Run the full backend suite**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/focus/schemas.py backend/app/focus/router.py backend/app/main.py backend/tests/focus/test_router.py
git commit -m "feat: add focus session and recommendation API endpoints"
```

---

### Task 5: Frontend focus session hook (ping, resume, reminders)

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/features/focus/useFocusSession.tsx`

**Interfaces:**
- Consumes: `api`, `useAuth` from `frontend/src/features/auth/useAuth.tsx`.
- Produces: `<FocusSessionProvider>`, `useFocusSession()` hook — consumed by Task 6's widgets and Task 7's App.tsx wiring.

- [ ] **Step 1: Add focus types and API calls to `frontend/src/lib/api.ts`**

Add after the existing `DashboardSummary` type:

```typescript
export type LearningSession = {
  id: string;
  started_at: string;
  ended_at: string | null;
  active_time_sec: number;
  last_position: string | null;
  timer_mode: "count_up" | "pomodoro" | "countdown" | "no_timer";
  pomodoro_preset: string | null;
  break_reminder_threshold_min: number;
  hyperfocus_reminder_min: number;
};

export type Recommendation = {
  activity_type: "review" | "learn";
  concept_slug: string;
  concept_name: string;
  reason: string;
};
```

Add to the `api` object:

```typescript
  startFocusSession: () => request<LearningSession>("/focus/sessions", { method: "POST" }),
  getCurrentFocusSession: () => request<LearningSession>("/focus/sessions/current"),
  updateFocusSession: (
    id: string,
    patch: Partial<{
      active_time_sec: number;
      last_position: string;
      timer_mode: string;
      pomodoro_preset: string;
    }>
  ) => request<LearningSession>(`/focus/sessions/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  endFocusSession: (id: string) => request<LearningSession>(`/focus/sessions/${id}/end`, { method: "POST" }),
  getRecommendation: (minutes?: number) =>
    request<Recommendation | undefined>(`/focus/recommendation${minutes ? `?minutes=${minutes}` : ""}`),
```

- [ ] **Step 2: Write `frontend/src/features/focus/useFocusSession.tsx`**

```tsx
import { createContext, useContext, useEffect, useRef, useState, ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { api, LearningSession } from "../../lib/api";
import { useAuth } from "../auth/useAuth";

const PING_INTERVAL_MS = 30000;

type FocusState = {
  session: LearningSession | null;
  activeSeconds: number;
  resumePath: string | null;
  dismissResume: () => void;
  breakReminderVisible: boolean;
  dismissBreakReminder: (skipToday: boolean) => void;
  hyperfocusReminderVisible: boolean;
  dismissHyperfocusReminder: () => void;
  focusModeEnabled: boolean;
  toggleFocusMode: () => void;
  setTimerMode: (mode: string) => void;
};

const FocusContext = createContext<FocusState | null>(null);

function todayKey(): string {
  return `focus-break-dismissed-${new Date().toDateString()}`;
}

export function FocusSessionProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  const [session, setSession] = useState<LearningSession | null>(null);
  const [activeSeconds, setActiveSeconds] = useState(0);
  const [resumePath, setResumePath] = useState<string | null>(null);
  const [breakReminderVisible, setBreakReminderVisible] = useState(false);
  const [hyperfocusReminderVisible, setHyperfocusReminderVisible] = useState(false);
  const [focusModeEnabled, setFocusModeEnabled] = useState(
    () => localStorage.getItem("focus-mode") === "true"
  );
  const sessionRef = useRef<LearningSession | null>(null);
  const activeSecondsRef = useRef(0);
  const initialized = useRef(false);

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);
  useEffect(() => {
    activeSecondsRef.current = activeSeconds;
  }, [activeSeconds]);

  useEffect(() => {
    if (!user || initialized.current) return;
    initialized.current = true;

    api
      .getCurrentFocusSession()
      .then((s) => {
        setSession(s);
        setActiveSeconds(s.active_time_sec);
        if (s.last_position) setResumePath(s.last_position);
      })
      .catch(() => {
        api.startFocusSession().then(setSession);
      });
  }, [user]);

  useEffect(() => {
    if (!session) return;
    const id = setInterval(() => setActiveSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [session]);

  useEffect(() => {
    if (!session) return;
    const id = setInterval(() => {
      if (sessionRef.current) {
        api.updateFocusSession(sessionRef.current.id, {
          active_time_sec: activeSecondsRef.current,
          last_position: location.pathname,
        });
      }
    }, PING_INTERVAL_MS);
    return () => clearInterval(id);
  }, [session, location.pathname]);

  useEffect(() => {
    if (!session) return;
    const minutes = activeSeconds / 60;
    if (minutes >= session.break_reminder_threshold_min && localStorage.getItem(todayKey()) !== "true") {
      setBreakReminderVisible(true);
    }
    if (minutes >= session.hyperfocus_reminder_min) {
      setHyperfocusReminderVisible(true);
    }
  }, [activeSeconds, session]);

  const dismissResume = () => setResumePath(null);

  const dismissBreakReminder = (skipToday: boolean) => {
    setBreakReminderVisible(false);
    if (skipToday) localStorage.setItem(todayKey(), "true");
  };

  const dismissHyperfocusReminder = () => setHyperfocusReminderVisible(false);

  const toggleFocusMode = () => {
    setFocusModeEnabled((prev) => {
      const next = !prev;
      localStorage.setItem("focus-mode", String(next));
      return next;
    });
  };

  const setTimerMode = (mode: string) => {
    if (!session) return;
    api.updateFocusSession(session.id, { timer_mode: mode }).then(setSession);
  };

  return (
    <FocusContext.Provider
      value={{
        session,
        activeSeconds,
        resumePath,
        dismissResume,
        breakReminderVisible,
        dismissBreakReminder,
        hyperfocusReminderVisible,
        dismissHyperfocusReminder,
        focusModeEnabled,
        toggleFocusMode,
        setTimerMode,
      }}
    >
      {children}
    </FocusContext.Provider>
  );
}

export function useFocusSession(): FocusState {
  const ctx = useContext(FocusContext);
  if (!ctx) throw new Error("useFocusSession must be used inside FocusSessionProvider");
  return ctx;
}
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc -b --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/features/focus/useFocusSession.tsx
git commit -m "feat: add FocusSessionProvider with session ping/resume/reminders"
```

---

### Task 6: Frontend widgets — timer, reminders, resume banner, "No sé qué estudiar"

**Files:**
- Create: `frontend/src/features/focus/FocusWidgets.tsx`
- Create: `frontend/src/features/focus/RecommendationButton.tsx`

**Interfaces:**
- Consumes: `useFocusSession` (Task 5), `api.getRecommendation` (Task 5).
- Produces: `<FocusWidgets />`, `<RecommendationButton />` — consumed by Task 7's App.tsx wiring.

- [ ] **Step 1: Write `frontend/src/features/focus/FocusWidgets.tsx`**

```tsx
import { useFocusSession } from "./useFocusSession";

function formatSeconds(total: number): string {
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function FocusWidgets() {
  const {
    session,
    activeSeconds,
    resumePath,
    dismissResume,
    breakReminderVisible,
    dismissBreakReminder,
    hyperfocusReminderVisible,
    dismissHyperfocusReminder,
    focusModeEnabled,
    toggleFocusMode,
    setTimerMode,
  } = useFocusSession();

  return (
    <div>
      {resumePath && (
        <div>
          <a href={resumePath}>Continuar donde estabas</a>
          <button onClick={dismissResume}>Cerrar</button>
        </div>
      )}

      {session && (
        <div>
          {session.timer_mode !== "no_timer" && <span>{formatSeconds(activeSeconds)}</span>}
          <select value={session.timer_mode} onChange={(e) => setTimerMode(e.target.value)}>
            <option value="count_up">Count Up</option>
            <option value="pomodoro">Pomodoro</option>
            <option value="countdown">Countdown</option>
            <option value="no_timer">Sin timer</option>
          </select>
          <button onClick={toggleFocusMode}>{focusModeEnabled ? "Salir de Focus Mode" : "Focus Mode"}</button>
        </div>
      )}

      {breakReminderVisible && (
        <div role="alert">
          <p>Llevas un buen rato concentrado. ¿Pausa de 5 minutos?</p>
          <button onClick={() => dismissBreakReminder(false)}>Pausa</button>
          <button onClick={() => dismissBreakReminder(false)}>Seguir</button>
          <button onClick={() => dismissBreakReminder(true)}>No volver a preguntar hoy</button>
        </div>
      )}

      {hyperfocusReminderVisible && (
        <div role="alert">
          <p>Has trabajado mucho tiempo seguido. Guarda tus notas y considera una pausa.</p>
          <button onClick={dismissHyperfocusReminder}>Entendido</button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Write `frontend/src/features/focus/RecommendationButton.tsx`**

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Recommendation } from "../../lib/api";

export function RecommendationButton() {
  const [recommendation, setRecommendation] = useState<Recommendation | null | undefined>(undefined);
  const navigate = useNavigate();

  const handleClick = async () => {
    const rec = await api.getRecommendation(15);
    setRecommendation(rec ?? null);
  };

  const handleStart = () => {
    if (!recommendation) return;
    if (recommendation.activity_type === "learn") {
      navigate(`/lessons/${recommendation.concept_slug}`);
    } else {
      navigate("/review");
    }
    setRecommendation(undefined);
  };

  return (
    <div>
      <button onClick={handleClick}>No sé qué estudiar</button>
      {recommendation === null && <p>Todavía no hay contenido con preguntas para recomendar.</p>}
      {recommendation && (
        <div>
          <p>{recommendation.reason}</p>
          <button onClick={handleStart}>Empezar</button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc -b --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/focus/FocusWidgets.tsx frontend/src/features/focus/RecommendationButton.tsx
git commit -m "feat: add focus timer widgets and 'No sé qué estudiar' button"
```

---

### Task 7: Wire into `App.tsx` and verify end-to-end

**Files:**
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `<FocusSessionProvider>` (Task 5), `<FocusWidgets>`/`<RecommendationButton>` (Task 6).

- [ ] **Step 1: Update `frontend/src/App.tsx`**

```tsx
import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
import { AuthProvider } from "./features/auth/useAuth";
import { LoginPage } from "./features/auth/LoginPage";
import { MfaPage } from "./features/auth/MfaPage";
import { ProtectedRoute } from "./features/auth/ProtectedRoute";
import { LessonPage } from "./features/lessons/LessonPage";
import { NotesPage } from "./features/notes/NotesPage";
import { NoteDetailPage } from "./features/notes/NoteDetailPage";
import { ReviewPage } from "./features/reviews/ReviewPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { FocusSessionProvider } from "./features/focus/useFocusSession";
import { FocusWidgets } from "./features/focus/FocusWidgets";
import { RecommendationButton } from "./features/focus/RecommendationButton";

function Home() {
  return <h1>Dashboard (placeholder)</h1>;
}

function ProtectedLayout() {
  return (
    <>
      <FocusWidgets />
      <RecommendationButton />
      <Outlet />
    </>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <FocusSessionProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/mfa" element={<MfaPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<ProtectedLayout />}>
                <Route path="/" element={<Home />} />
                <Route path="/lessons/:slug" element={<LessonPage />} />
                <Route path="/notes" element={<NotesPage />} />
                <Route path="/notes/:id" element={<NoteDetailPage />} />
                <Route path="/review" element={<ReviewPage />} />
                <Route path="/dashboard" element={<DashboardPage />} />
              </Route>
            </Route>
          </Routes>
        </FocusSessionProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc -b --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: wire focus session provider and widgets into the app layout"
```

- [ ] **Step 4: Restart the backend (kill by exact PID) and verify via API**

```bash
ss -ltnp | grep 8001   # find the PID
kill <pid>
cd backend && setsid nohup .venv/bin/uvicorn app.main:app --port 8001 > /tmp/uvicorn.log 2>&1 < /dev/null &
disown
sleep 2
curl -s http://localhost:8001/api/v1/health
```

With a fresh authenticated `cookies.txt`:
```bash
curl -s -b /tmp/cookies.txt -X POST http://localhost:8001/api/v1/focus/sessions | python3 -m json.tool
curl -s -b /tmp/cookies.txt http://localhost:8001/api/v1/focus/sessions/current | python3 -m json.tool
curl -s -b /tmp/cookies.txt "http://localhost:8001/api/v1/focus/recommendation?minutes=15" | python3 -m json.tool
```
Expected: a session created, then returned by `/current`; a recommendation reflecting the dev database's existing review history (should recommend an overdue review if any exist from prior plans' verification).

- [ ] **Step 5: Browser walkthrough**

1. Log in. Confirm the timer widget appears and starts counting up.
2. Navigate between `/dashboard`, a lesson, and `/notes` — confirm no errors, and that the session's `last_position` updates (check via `GET /focus/sessions/current` in another terminal).
3. Click "No sé qué estudiar" — confirm it shows a single recommendation with a reason, and "Empezar" navigates to the right place (a lesson for `learn`, `/review` for `review`).
4. Toggle Focus Mode — confirm the toggle button label flips (visual polish is out of scope; just confirm the state toggles).
5. Reload the page — confirm the timer resumes from roughly where it left off (via the persisted `active_time_sec`), not from zero.

- [ ] **Step 6: Run the full backend test suite one more time**

Run: `cd backend && pytest -v`
Expected: all tests pass.

- [ ] **Step 7: Update `PROJECT_MASTER_CHECKLIST.md`**

Mark under "Focus/Timer + 'No sé qué estudiar'". Note: this plan implements position resume (`last_position` + banner) but NOT "context recap" (the 3-quick-questions check after a multi-day gap, master prompt §52) — split the existing checklist line so that part stays honestly unchecked:
```markdown
- [x] LearningSession, timer (4 modos), Focus Mode
- [x] Session resume (última posición)
- [ ] Context recap (3 preguntas rápidas tras un hueco de varios días — no implementado en este sub-plan)
- [x] Algoritmo de recomendación única ("No sé qué estudiar")
```
Commit:
```bash
git add PROJECT_MASTER_CHECKLIST.md
git commit -m "docs: update checklist — focus/timer complete"
```

Report the resulting checklist section to the user.
