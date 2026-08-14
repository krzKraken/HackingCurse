# Fase 2: Challenges + Hints Progresivos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Dashboard's "Pistas usadas" / "Independence Score" placeholders with real metrics computed from existing `LabInstance` data.

**Architecture:** A new `get_hint_dependency(db, user_id)` function in `app/dashboard/service.py` groups the user's solved `LabInstance` rows by `hints_used` and computes an Independence Score. `get_summary()` folds its result into the existing `DashboardSummary` dict. The frontend renders it in a new Dashboard section.

**Tech Stack:** FastAPI, SQLAlchemy, existing `LabInstance`/`LabInstanceStatus` models (no new tables/migrations), React/TypeScript.

## Global Constraints

- No new database tables or migrations — `LabInstance.hints_used` and `LabInstance.solved` already carry everything needed (per spec decision 3).
- "Challenge" content is **not** a new model — a future `Laboratory` with `type="challenge"` is handled identically to today's `type="black_box"` FlagBox by all existing code. Nothing to build for that half of the spec (per spec decision 1) — this plan implements only the metrics half.
- `independence_score` must be `None`, never `0.0`, when the user has solved zero labs (per spec: avoids implying "0% independent" when there's simply no data).

---

### Task 1: Hint dependency metrics (backend)

**Files:**
- Modify: `backend/app/dashboard/service.py`
- Modify: `backend/app/dashboard/schemas.py`
- Test: `backend/tests/dashboard/test_service.py`
- Test: `backend/tests/dashboard/test_router.py`

**Interfaces:**
- Consumes: `app.models.lab.LabInstance` (existing — has `user_id`, `solved: bool`, `hints_used: int`).
- Produces:
  - `get_hint_dependency(db: Session, user_id) -> dict` returning `{"breakdown": dict[int, int], "independence_score": float | None}`. Consumed by `get_summary()` in this same task, and by Task 2's frontend indirectly via the `/dashboard/summary` response.
  - `DashboardSummary.hint_dependency: dict[int, int]` and `DashboardSummary.independence_score: float | None` — consumed by Task 2's frontend types.

- [ ] **Step 1: Write the failing service-level tests**

Add to `backend/tests/dashboard/test_service.py` (append at the end of the file; the existing `_seed_user` helper is reused):

```python
from app.models.lab import Laboratory, LabInstance, LabInstanceStatus


def _seed_laboratory(db, lab_id="test-lab"):
    lab = db.query(Laboratory).filter_by(id=lab_id).first()
    if lab is not None:
        return lab
    lab = Laboratory(
        id=lab_id,
        title="Test Lab",
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
    from datetime import datetime, timezone

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


def test_hint_dependency_with_no_solved_labs_has_no_independence_score(db_session):
    user = _seed_user(db_session)
    result = service.get_hint_dependency(db_session, user.id)
    assert result == {"breakdown": {}, "independence_score": None}


def test_hint_dependency_breakdown_and_independence_score(db_session):
    user = _seed_user(db_session)
    _seed_solved_instance(db_session, user, hints_used=0)
    _seed_solved_instance(db_session, user, hints_used=0)
    _seed_solved_instance(db_session, user, hints_used=1)
    _seed_solved_instance(db_session, user, hints_used=2)

    result = service.get_hint_dependency(db_session, user.id)

    assert result["breakdown"] == {0: 2, 1: 1, 2: 1}
    assert result["independence_score"] == 50.0


def test_hint_dependency_only_counts_solved_instances(db_session):
    from datetime import datetime, timezone

    user = _seed_user(db_session)
    lab = _seed_laboratory(db_session)
    unsolved = LabInstance(
        laboratory_id=lab.id,
        user_id=user.id,
        status=LabInstanceStatus.running,
        context_seed={},
        requested_at=datetime.now(timezone.utc),
        solved=False,
        hints_used=3,
    )
    db_session.add(unsolved)
    db_session.commit()

    result = service.get_hint_dependency(db_session, user.id)

    assert result == {"breakdown": {}, "independence_score": None}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/dashboard/test_service.py -k hint_dependency -v`
Expected: FAIL with `AttributeError: module 'app.dashboard.service' has no attribute 'get_hint_dependency'`

- [ ] **Step 3: Implement `get_hint_dependency`**

In `backend/app/dashboard/service.py`, add the import and function:

```python
from app.models.lab import LabInstance
```

(merge into the existing import block at the top of the file, which already imports from `app.models.content`, `app.models.mastery`, `app.models.question`, `app.models.review`)

```python
def get_hint_dependency(db: Session, user_id) -> dict:
    solved = db.query(LabInstance).filter(LabInstance.user_id == user_id, LabInstance.solved == True).all()
    if not solved:
        return {"breakdown": {}, "independence_score": None}
    breakdown: dict[int, int] = {}
    for instance in solved:
        breakdown[instance.hints_used] = breakdown.get(instance.hints_used, 0) + 1
    no_hints_count = breakdown.get(0, 0)
    independence_score = no_hints_count / len(solved) * 100
    return {"breakdown": breakdown, "independence_score": independence_score}
```

- [ ] **Step 4: Wire it into `get_summary`**

In `backend/app/dashboard/service.py`, modify `get_summary`:

```python
def get_summary(db: Session, user_id) -> dict:
    hint_dependency = get_hint_dependency(db, user_id)
    return {
        "global_mastery": get_global_mastery(db, user_id),
        "domains": get_domains_summary(db, user_id),
        "reviews_due_count": get_reviews_due_count(db, user_id),
        "weak_concepts": get_weak_concepts(db, user_id),
        "overdue_concepts": get_overdue_concepts(db, user_id),
        "recent_activity": get_recent_activity(db, user_id),
        "hint_dependency": hint_dependency["breakdown"],
        "independence_score": hint_dependency["independence_score"],
    }
```

- [ ] **Step 5: Add the fields to `DashboardSummary`**

In `backend/app/dashboard/schemas.py`, modify the `DashboardSummary` class:

```python
class DashboardSummary(BaseModel):
    global_mastery: float
    domains: list[DomainMasterySummary]
    reviews_due_count: int
    weak_concepts: list[ConceptScoreSummary]
    overdue_concepts: list[OverdueConceptSummary]
    recent_activity: list[RecentActivityItem]
    hint_dependency: dict[int, int]
    independence_score: float | None
```

- [ ] **Step 6: Run the service tests to verify they pass**

Run: `cd backend && pytest tests/dashboard/test_service.py -v`
Expected: all pass, including the 3 new tests and all pre-existing ones.

- [ ] **Step 7: Write the failing router-level test**

Append to `backend/tests/dashboard/test_router.py`:

```python
def test_dashboard_includes_hint_dependency_with_no_solved_labs(client, db_session):
    _login_as_owner(client, db_session)

    resp = client.get("/api/v1/dashboard/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["hint_dependency"] == {}
    assert body["independence_score"] is None
```

- [ ] **Step 8: Run to verify it fails, then passes**

Run: `cd backend && pytest tests/dashboard/test_router.py -v`
Expected first: FAIL with a `KeyError` or `assert` failure (the field doesn't exist in the response yet) — actually, since Step 3-5 are already implemented by this point, this should already PASS. Run it to confirm; if it fails, re-check Step 5's schema field names match exactly (`hint_dependency`, `independence_score`).

- [ ] **Step 9: Run the full backend test suite**

Run: `cd backend && pytest -q`
Expected: all tests pass (108 existing + 4 new = 112).

- [ ] **Step 10: Commit**

```bash
git add backend/app/dashboard/service.py backend/app/dashboard/schemas.py backend/tests/dashboard/test_service.py backend/tests/dashboard/test_router.py
git commit -m "feat: add hint dependency and independence score metrics to dashboard"
```

---

### Task 2: Dashboard UI for hint dependency

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/features/dashboard/DashboardPage.tsx`

**Interfaces:**
- Consumes: `DashboardSummary.hint_dependency` and `DashboardSummary.independence_score` (Task 1, JSON keys `hint_dependency`/`independence_score`; note that JSON object keys are always strings, so on the TypeScript side `hint_dependency` deserializes as `Record<string, number>`, not `Record<number, number>` — object keys in JS/TS are always strings regardless of the Python `dict[int, int]` on the wire).

No backend tests apply to this task — pure frontend UI, verified manually per the project's established pattern for Dashboard/Labs UI work (no automated frontend test suite exists in this codebase; see Sub-plan A/B).

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
};
```

- [ ] **Step 2: Render the new section and trim `COMING_SOON`**

In `frontend/src/features/dashboard/DashboardPage.tsx`, change the `COMING_SOON` array:

```tsx
const COMING_SOON = [
  "Fragmentación",
  "Knowledge Connectivity",
  "Error Memory",
  "Labs recomendados",
  "Tiempo de práctica",
  "Logros",
  "Transfer / Methodology Score",
];
```

(removed `"Pistas usadas"` and replaced `"Independence / Transfer / Methodology Score"` with `"Transfer / Methodology Score"`)

Add a new `<section>` immediately before the `<section><h2>Próximamente</h2>...` block:

```tsx
<section>
  <h2>Uso de pistas en labs</h2>
  {summary.independence_score === null ? (
    <p>Todavía no resolviste ningún lab.</p>
  ) : (
    <>
      <p>Independence Score: {summary.independence_score.toFixed(0)}%</p>
      <ul>
        {Object.entries(summary.hint_dependency)
          .sort(([a], [b]) => Number(a) - Number(b))
          .map(([level, count]) => (
            <li key={level}>
              {level === "0" ? "Sin pistas" : `Pista ${level}`}: {count}
            </li>
          ))}
      </ul>
    </>
  )}
</section>
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: no errors. If stray `.js` files appear alongside `.tsx` sources afterward (a known side effect of this project's `tsc -b` without a configured `outDir`), delete them — they are build byproducts, not source (`find src -name "*.js" -delete` from `frontend/`).

- [ ] **Step 4: Manual verification**

Start the backend (`cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8001`, or reuse an already-running instance — check `ss -ltnp | grep 8001` first) and the frontend (`cd frontend && npm run dev`; note port 5173 may be occupied by an unrelated project on this machine — check `ss -ltnp | grep -E ':517[0-9]'` before assuming which port is CyberLearn's). Log in, solve at least one lab instance with a known `hints_used` value (or mint a session directly via `app.auth.sessions.create_session` for the existing `owner` user and drive the flow via `POST /api/v1/labs/{id}/instances` + `POST /api/v1/labs/instances/{id}/submit`, same approach used for Sub-plan B's E2E verification), then load `/dashboard` and confirm "Uso de pistas en labs" shows the correct breakdown and Independence Score instead of "Todavía no resolviste ningún lab."

Stop any manually-started processes by exact PID afterward (`ss -ltnp | grep <port>` → `kill <pid>`) — never a name/pattern-based `pkill`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/features/dashboard/DashboardPage.tsx
git commit -m "feat: show hint dependency and independence score on the dashboard"
```

---

### Task 3: Update checklist

**Files:**
- Modify: `PROJECT_MASTER_CHECKLIST.md`

- [ ] **Step 1: Add the Fase 2 entry**

Add a new subsection under `## Fase 2` (before the existing flat item list, following the pattern used for other completed sub-plans elsewhere in the file):

```markdown
## Fase 2

### Challenges + hints progresivos
- [x] Challenges: cubierto por `Laboratory.type` (campo ya existente, sin modelo nuevo — ver `docs/superpowers/specs/2026-08-14-challenges-hints-design.md` decisión 1)
- [x] Hint Dependency + Independence Score en el Dashboard

- [ ] Gamificación (sobria)
- [ ] Knowledge graph navegable — vista visual interactiva (hoy solo lista jerárquica vía relaciones)
- [ ] Base de datos de vulnerabilidades
- [ ] Error Memory completo (`ErrorPattern`)
- [ ] Fragmentation score + ejercicios integradores
- [ ] Export/Import Obsidian (notas y lecciones)
- [ ] Búsqueda global / Command Palette (Ctrl+K)
```

(this replaces the current flat `- [ ] Challenges + hints progresivos` line and the line directly below it, keeping the rest of the Fase 2 list as-is)

- [ ] **Step 2: Commit**

```bash
git add PROJECT_MASTER_CHECKLIST.md
git commit -m "docs: update checklist — Fase 2 challenges + hints progresivos complete"
```
