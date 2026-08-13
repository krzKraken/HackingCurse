# Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggregate existing `ConceptMastery`/`ReviewSchedule`/`ReviewItem` data into a dashboard summary endpoint, and render it at `/dashboard` alongside static "Próximamente" cards for widgets that depend on modules not built yet (fragmentation, labs, error memory, etc.).

**Architecture:** A new `app/dashboard/` backend module (service + schemas + router, same pattern as `content`/`notes`/`reviews`) with pure read/aggregation queries — no new tables. Frontend adds a `/dashboard` route.

**Tech Stack:** Same as prior plans (FastAPI, SQLAlchemy 2.0.52, Postgres, React+Vite).

## Global Constraints

- No new database tables — this is a read-only aggregation layer over `ConceptMastery`, `ReviewSchedule`, `ReviewItem`, `Domain`/`Topic`/`Concept`, `Question`.
- Must match `docs/superpowers/specs/2026-08-13-dashboard-design.md` exactly, including which widgets are real vs. static "Próximamente" placeholders.
- A domain with zero studied concepts must report `mastery_percent: 0.0`, `studied_count: 0` — never `NaN` or a division-by-zero error.
- `/dashboard` is a separate route from `/` (Home stays as its existing placeholder, per the user's explicit choice during design).
- Route lives under `/api/v1/dashboard/...`, authenticated with `get_current_user`.

---

## File Structure

```
backend/
├── app/
│   ├── dashboard/
│   │   ├── __init__.py
│   │   ├── service.py     # get_global_mastery, get_domains_summary, get_reviews_due_count,
│   │   │                   # get_weak_concepts, get_overdue_concepts, get_recent_activity, get_summary
│   │   ├── schemas.py
│   │   └── router.py
│   └── main.py             # mount dashboard router
└── tests/dashboard/
    ├── __init__.py
    ├── test_service.py
    └── test_router.py

frontend/src/
├── lib/api.ts               # add DashboardSummary type + getDashboardSummary
├── features/dashboard/DashboardPage.tsx
└── App.tsx                  # add /dashboard route
```

---

### Task 1: Dashboard aggregation service

**Files:**
- Create: `backend/app/dashboard/__init__.py`
- Create: `backend/app/dashboard/service.py`
- Test: `backend/tests/dashboard/__init__.py`
- Test: `backend/tests/dashboard/test_service.py`

**Interfaces:**
- Consumes: `app.models.content.*`, `app.models.mastery.*`, `app.models.question.*`, `app.models.review.*`.
- Produces: `get_global_mastery(db, user_id) -> float`, `get_domains_summary(db, user_id) -> list[dict]`, `get_reviews_due_count(db, user_id) -> int`, `get_weak_concepts(db, user_id, limit=5) -> list[dict]`, `get_overdue_concepts(db, user_id, limit=5) -> list[dict]`, `get_recent_activity(db, user_id, limit=10) -> list[dict]`, `get_summary(db, user_id) -> dict` — consumed by Task 2's router.

- [ ] **Step 1: Write the failing test**

`backend/tests/dashboard/__init__.py`: empty file.

`backend/tests/dashboard/test_service.py`:
```python
from datetime import datetime, timedelta, timezone

from app.dashboard import service
from app.models.content import Concept, Domain, Topic
from app.models.mastery import ConceptMastery, ReviewSchedule
from app.models.question import Question, QuestionStatus, QuestionType, QuestionVariant
from app.models.review import ReviewItem, ReviewOutcome, ReviewSession
from app.models.user import User


def _seed_user(db):
    user = User(username="owner", password_hash="x", totp_secret="x")
    db.add(user)
    db.commit()
    return user


def _seed_concept_with_question(db, domain_slug, topic_slug, concept_slug):
    domain = db.query(Domain).filter_by(slug=domain_slug).first()
    if domain is None:
        domain = Domain(slug=domain_slug, name=domain_slug)
        db.add(domain)
        db.flush()
    topic = Topic(domain_id=domain.id, slug=topic_slug, name=topic_slug)
    db.add(topic)
    db.flush()
    concept = Concept(topic_id=topic.id, slug=concept_slug, name=concept_slug)
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
    return concept


def test_global_mastery_is_zero_with_no_history(db_session):
    user = _seed_user(db_session)
    assert service.get_global_mastery(db_session, user.id) == 0.0


def test_global_mastery_averages_all_concept_masteries(db_session):
    user = _seed_user(db_session)
    c1 = _seed_concept_with_question(db_session, "networking", "t1", "c1")
    c2 = _seed_concept_with_question(db_session, "networking", "t1", "c2")
    db_session.add(ConceptMastery(user_id=user.id, concept_id=c1.id, mastery_score=80.0))
    db_session.add(ConceptMastery(user_id=user.id, concept_id=c2.id, mastery_score=40.0))
    db_session.commit()

    assert service.get_global_mastery(db_session, user.id) == 60.0


def test_domains_summary_reports_studied_and_total(db_session):
    user = _seed_user(db_session)
    c1 = _seed_concept_with_question(db_session, "networking", "t1", "c1")
    _seed_concept_with_question(db_session, "networking", "t1", "c2")
    db_session.add(ConceptMastery(user_id=user.id, concept_id=c1.id, mastery_score=100.0))
    db_session.commit()

    domains = service.get_domains_summary(db_session, user.id)

    net = next(d for d in domains if d["slug"] == "networking")
    assert net["studied_count"] == 1
    assert net["total_count"] == 2
    assert net["mastery_percent"] == 100.0


def test_domain_with_no_studied_concepts_has_zero_mastery(db_session):
    user = _seed_user(db_session)
    _seed_concept_with_question(db_session, "networking", "t1", "c1")

    domains = service.get_domains_summary(db_session, user.id)

    net = next(d for d in domains if d["slug"] == "networking")
    assert net["studied_count"] == 0
    assert net["mastery_percent"] == 0.0


def test_reviews_due_count_and_overdue(db_session):
    user = _seed_user(db_session)
    c1 = _seed_concept_with_question(db_session, "networking", "t1", "c1")
    mastery = ConceptMastery(user_id=user.id, concept_id=c1.id, mastery_score=50.0)
    db_session.add(mastery)
    db_session.flush()
    past = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.add(ReviewSchedule(concept_mastery_id=mastery.id, stability_days=5.0, next_due_at=past))
    db_session.commit()

    assert service.get_reviews_due_count(db_session, user.id) == 1
    overdue = service.get_overdue_concepts(db_session, user.id)
    assert overdue[0]["slug"] == "c1"


def test_weak_concepts_sorted_ascending(db_session):
    user = _seed_user(db_session)
    c1 = _seed_concept_with_question(db_session, "networking", "t1", "c1")
    c2 = _seed_concept_with_question(db_session, "networking", "t1", "c2")
    db_session.add(ConceptMastery(user_id=user.id, concept_id=c1.id, mastery_score=90.0))
    db_session.add(ConceptMastery(user_id=user.id, concept_id=c2.id, mastery_score=10.0))
    db_session.commit()

    weak = service.get_weak_concepts(db_session, user.id)

    assert weak[0]["slug"] == "c2"


def test_recent_activity_orders_by_answered_at_desc(db_session):
    user = _seed_user(db_session)
    concept = _seed_concept_with_question(db_session, "networking", "t1", "c1")
    question = db_session.query(Question).filter_by(concept_id=concept.id).first()
    variant = question.variants[0]

    session = ReviewSession(user_id=user.id, mode="general", started_at=datetime.now(timezone.utc))
    db_session.add(session)
    db_session.flush()

    now = datetime.now(timezone.utc)
    db_session.add(
        ReviewItem(
            review_session_id=session.id,
            concept_id=concept.id,
            question_variant_id=variant.id,
            shown_at=now,
            answered_at=now - timedelta(minutes=5),
            outcome=ReviewOutcome.correct,
        )
    )
    db_session.add(
        ReviewItem(
            review_session_id=session.id,
            concept_id=concept.id,
            question_variant_id=variant.id,
            shown_at=now,
            answered_at=now,
            outcome=ReviewOutcome.incorrect,
        )
    )
    db_session.commit()

    activity = service.get_recent_activity(db_session, user.id)

    assert activity[0]["outcome"] == "incorrect"
    assert activity[1]["outcome"] == "correct"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && pytest tests/dashboard/test_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.dashboard'`

- [ ] **Step 3: Write `backend/app/dashboard/__init__.py`** (empty file)

- [ ] **Step 4: Write `backend/app/dashboard/service.py`**

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.content import Concept, Domain, Topic
from app.models.mastery import ConceptMastery, ReviewSchedule
from app.models.question import Question, QuestionStatus
from app.models.review import ReviewItem, ReviewSession


def get_global_mastery(db: Session, user_id) -> float:
    masteries = db.query(ConceptMastery).filter(ConceptMastery.user_id == user_id).all()
    if not masteries:
        return 0.0
    return sum(m.mastery_score for m in masteries) / len(masteries)


def get_domains_summary(db: Session, user_id) -> list[dict]:
    domains = db.query(Domain).order_by(Domain.name).all()
    result = []
    for domain in domains:
        total_count = (
            db.query(Concept)
            .join(Topic, Concept.topic_id == Topic.id)
            .join(Question, Question.concept_id == Concept.id)
            .filter(Topic.domain_id == domain.id, Question.status == QuestionStatus.published)
            .distinct()
            .count()
        )
        masteries = (
            db.query(ConceptMastery)
            .join(Concept, ConceptMastery.concept_id == Concept.id)
            .join(Topic, Concept.topic_id == Topic.id)
            .filter(Topic.domain_id == domain.id, ConceptMastery.user_id == user_id)
            .all()
        )
        studied_count = len(masteries)
        mastery_percent = sum(m.mastery_score for m in masteries) / studied_count if studied_count else 0.0
        result.append(
            {
                "slug": domain.slug,
                "name": domain.name,
                "mastery_percent": mastery_percent,
                "studied_count": studied_count,
                "total_count": total_count,
            }
        )
    return result


def get_reviews_due_count(db: Session, user_id) -> int:
    now = datetime.now(timezone.utc)
    return (
        db.query(ReviewSchedule)
        .join(ConceptMastery, ReviewSchedule.concept_mastery_id == ConceptMastery.id)
        .filter(ConceptMastery.user_id == user_id, ReviewSchedule.next_due_at <= now)
        .count()
    )


def get_weak_concepts(db: Session, user_id, limit: int = 5) -> list[dict]:
    masteries = (
        db.query(ConceptMastery)
        .filter(ConceptMastery.user_id == user_id)
        .order_by(ConceptMastery.mastery_score.asc())
        .limit(limit)
        .all()
    )
    return [{"slug": m.concept.slug, "name": m.concept.name, "mastery_score": m.mastery_score} for m in masteries]


def get_overdue_concepts(db: Session, user_id, limit: int = 5) -> list[dict]:
    now = datetime.now(timezone.utc)
    schedules = (
        db.query(ReviewSchedule)
        .join(ConceptMastery, ReviewSchedule.concept_mastery_id == ConceptMastery.id)
        .filter(ConceptMastery.user_id == user_id, ReviewSchedule.next_due_at <= now)
        .order_by(ReviewSchedule.next_due_at.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "slug": s.concept_mastery.concept.slug,
            "name": s.concept_mastery.concept.name,
            "next_due_at": s.next_due_at,
        }
        for s in schedules
    ]


def get_recent_activity(db: Session, user_id, limit: int = 10) -> list[dict]:
    items = (
        db.query(ReviewItem)
        .join(ReviewSession, ReviewItem.review_session_id == ReviewSession.id)
        .filter(ReviewSession.user_id == user_id, ReviewItem.outcome.isnot(None))
        .order_by(ReviewItem.answered_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "concept_slug": item.concept.slug,
            "concept_name": item.concept.name,
            "outcome": item.outcome.value,
            "answered_at": item.answered_at,
        }
        for item in items
    ]


def get_summary(db: Session, user_id) -> dict:
    return {
        "global_mastery": get_global_mastery(db, user_id),
        "domains": get_domains_summary(db, user_id),
        "reviews_due_count": get_reviews_due_count(db, user_id),
        "weak_concepts": get_weak_concepts(db, user_id),
        "overdue_concepts": get_overdue_concepts(db, user_id),
        "recent_activity": get_recent_activity(db, user_id),
    }
```

- [ ] **Step 5: Run it to verify it passes**

Run: `pytest tests/dashboard/test_service.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/dashboard/__init__.py backend/app/dashboard/service.py backend/tests/dashboard/__init__.py backend/tests/dashboard/test_service.py
git commit -m "feat: add dashboard aggregation service"
```

---

### Task 2: Dashboard schemas + router

**Files:**
- Create: `backend/app/dashboard/schemas.py`
- Create: `backend/app/dashboard/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/dashboard/test_router.py`

**Interfaces:**
- Consumes: `app.dashboard.service.get_summary` (Task 1), `app.auth.dependencies.get_current_user`.
- Produces: `GET /api/v1/dashboard/summary`.

- [ ] **Step 1: Write `backend/app/dashboard/schemas.py`**

```python
from datetime import datetime

from pydantic import BaseModel


class DomainMasterySummary(BaseModel):
    slug: str
    name: str
    mastery_percent: float
    studied_count: int
    total_count: int


class ConceptScoreSummary(BaseModel):
    slug: str
    name: str
    mastery_score: float


class OverdueConceptSummary(BaseModel):
    slug: str
    name: str
    next_due_at: datetime


class RecentActivityItem(BaseModel):
    concept_slug: str
    concept_name: str
    outcome: str
    answered_at: datetime


class DashboardSummary(BaseModel):
    global_mastery: float
    domains: list[DomainMasterySummary]
    reviews_due_count: int
    weak_concepts: list[ConceptScoreSummary]
    overdue_concepts: list[OverdueConceptSummary]
    recent_activity: list[RecentActivityItem]
```

- [ ] **Step 2: Write `backend/app/dashboard/router.py`**

```python
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
```

- [ ] **Step 3: Mount it in `backend/app/main.py`**

```python
from app.dashboard.router import router as dashboard_router
# ...
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])
```

- [ ] **Step 4: Write the failing test**

`backend/tests/dashboard/test_router.py`:
```python
import pyotp

from app.auth.security import hash_password
from app.auth.totp import generate_totp_secret
from app.models.content import Concept, Domain, Topic
from app.models.mastery import ConceptMastery
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


def test_dashboard_requires_auth(client):
    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 401


def test_dashboard_returns_summary_shape(client, db_session):
    user = _login_as_owner(client, db_session)

    domain = Domain(slug="networking", name="Networking")
    db_session.add(domain)
    db_session.flush()
    topic = Topic(domain_id=domain.id, slug="t1", name="t1")
    db_session.add(topic)
    db_session.flush()
    concept = Concept(topic_id=topic.id, slug="net-01", name="Fundamentos")
    db_session.add(concept)
    db_session.flush()
    question = Question(
        concept_id=concept.id, type=QuestionType.true_false, difficulty=1, status=QuestionStatus.published
    )
    db_session.add(question)
    db_session.flush()
    db_session.add(QuestionVariant(question_id=question.id, prompt_markdown="?", correct_bool=True))
    db_session.add(ConceptMastery(user_id=user.id, concept_id=concept.id, mastery_score=75.0))
    db_session.commit()

    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["global_mastery"] == 75.0
    assert body["domains"][0]["slug"] == "networking"
```

- [ ] **Step 5: Run it to verify it passes**

Run: `pytest tests/dashboard/test_router.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Run the full backend suite**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/dashboard/schemas.py backend/app/dashboard/router.py backend/app/main.py backend/tests/dashboard/test_router.py
git commit -m "feat: add dashboard summary endpoint"
```

---

### Task 3: Frontend `/dashboard` page

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/features/dashboard/DashboardPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `api` from `frontend/src/lib/api.ts`.
- Produces: route `/dashboard`.

- [ ] **Step 1: Add dashboard types and API call to `frontend/src/lib/api.ts`**

Add after the existing `AnswerResult` type:

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
};
```

Add to the `api` object:

```typescript
  getDashboardSummary: () => request<DashboardSummary>("/dashboard/summary"),
```

- [ ] **Step 2: Write `frontend/src/features/dashboard/DashboardPage.tsx`**

```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, DashboardSummary } from "../../lib/api";

const COMING_SOON = [
  "Fragmentación",
  "Knowledge Connectivity",
  "Error Memory",
  "Labs recomendados",
  "Tiempo de práctica",
  "Pistas usadas",
  "Logros",
  "Independence / Transfer / Methodology Score",
];

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);

  useEffect(() => {
    api.getDashboardSummary().then(setSummary);
  }, []);

  if (!summary) return <p>Cargando…</p>;

  return (
    <div>
      <h1>Dashboard</h1>

      <section>
        <h2>Nivel global</h2>
        <p>{summary.global_mastery.toFixed(0)}%</p>
      </section>

      <section>
        <h2>Nivel por dominio</h2>
        <ul>
          {summary.domains.map((d) => (
            <li key={d.slug}>
              {d.name}: {d.mastery_percent.toFixed(0)}% ({d.studied_count}/{d.total_count} conceptos estudiados)
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Repasos vencidos</h2>
        <p>
          {summary.reviews_due_count} <Link to="/review">Repasar ahora</Link>
        </p>
        <ul>
          {summary.overdue_concepts.map((c) => (
            <li key={c.slug}>
              <Link to={`/lessons/${c.slug}`}>{c.name}</Link>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Conceptos débiles</h2>
        <ul>
          {summary.weak_concepts.map((c) => (
            <li key={c.slug}>
              <Link to={`/lessons/${c.slug}`}>{c.name}</Link> — {c.mastery_score.toFixed(0)}%
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Últimos repasos</h2>
        <ul>
          {summary.recent_activity.map((a, i) => (
            <li key={i}>
              {a.concept_name} — {a.outcome} ({new Date(a.answered_at).toLocaleString()})
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Próximamente</h2>
        <ul>
          {COMING_SOON.map((label) => (
            <li key={label} style={{ opacity: 0.5 }}>
              {label}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Add the route in `frontend/src/App.tsx`**

```tsx
import { DashboardPage } from "./features/dashboard/DashboardPage";
// ...
            <Route path="/review" element={<ReviewPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
```

- [ ] **Step 4: Type-check**

Run: `cd frontend && npx tsc -b --noEmit`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/features/dashboard/DashboardPage.tsx frontend/src/App.tsx
git commit -m "feat: add /dashboard page with real widgets and coming-soon cards"
```

---

### Task 4: End-to-end verification + update checklist

**Files:** none created. Also updates `PROJECT_MASTER_CHECKLIST.md`.

- [ ] **Step 1: Restart the backend (kill by exact PID, never a broad pattern) and verify**

Run:
```bash
ss -ltnp | grep 8001   # find the PID
kill <pid>
cd backend && setsid nohup .venv/bin/uvicorn app.main:app --port 8001 > /tmp/uvicorn.log 2>&1 < /dev/null &
disown
sleep 2
curl -s http://localhost:8001/api/v1/health
```

- [ ] **Step 2: Verify via API with a fresh authenticated session**

```bash
curl -s -b /tmp/cookies.txt http://localhost:8001/api/v1/dashboard/summary | python3 -m json.tool
```
Expected: a summary reflecting the review activity already in the dev database from the questions-retention plan's Task 11 verification (non-zero `global_mastery`, at least one domain, some `recent_activity`).

- [ ] **Step 3: Browser walkthrough**

1. Log in, go to `/dashboard`.
2. Confirm the "Nivel global" and "Nivel por dominio" numbers look sane (not `NaN`, not empty).
3. Confirm "Repasos vencidos" links to `/review` and works.
4. Confirm "Conceptos débiles" links go to the right `/lessons/:slug` pages.
5. Confirm the "Próximamente" section renders and is visually distinct (dimmed) from the real widgets.
6. Answer a couple more questions in `/review`, return to `/dashboard`, confirm the numbers changed.

- [ ] **Step 4: Run the full backend test suite one more time**

Run: `cd backend && pytest -v`
Expected: all tests pass.

- [ ] **Step 5: Update `PROJECT_MASTER_CHECKLIST.md`**

Mark "Agregación de métricas ya calculadas (nivel por dominio, retención, repasos pendientes)" under "Dashboard" as `[x]`. Commit:

```bash
git add PROJECT_MASTER_CHECKLIST.md
git commit -m "docs: update checklist — dashboard complete"
```

Report the resulting checklist section to the user.
