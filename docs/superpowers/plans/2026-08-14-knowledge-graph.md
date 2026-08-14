# Knowledge Graph Navegable Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a navigable, interactive visualization of all concepts and their relationships (`prerequisite`/`related`/`continues_with`), colored by the current user's mastery, reachable both as a full page (`/graph`) and as a small preview embedded in the Dashboard.

**Architecture:** A new read-only endpoint (`GET /content/graph`) joins `Concept`/`Topic`/`Domain` with the current user's `ConceptMastery`/`ReviewSchedule` (left join, so unstudied concepts still appear) and all `ConceptRelationship` rows, returning one flat `GraphResponse {nodes, edges}`. The frontend renders it with `react-force-graph-2d` (force-directed layout) through one shared `KnowledgeGraph` component reused at full size on `/graph` (with domain filter, search, click-to-navigate) and at reduced size (read-only) on the Dashboard.

**Tech Stack:** FastAPI, SQLAlchemy (existing `Concept`/`Topic`/`Domain`/`ConceptRelationship`/`ConceptMastery`/`ReviewSchedule` models, no new tables), React/TypeScript, `react-force-graph-2d` (new frontend dependency).

**Spec:** `docs/superpowers/specs/2026-08-14-knowledge-graph-design.md`

## Global Constraints

- No new database tables or migrations — this feature only reads existing `Concept`, `Topic`, `Domain`, `ConceptRelationship`, `ConceptMastery`, `ReviewSchedule` tables.
- The graph endpoint is a single query for nodes (one join, no N+1) and a single separate query for relationships (per spec's Backend section) — never a per-relationship lookup query.
- Nodes are `Concept` only. `Domain`/`Topic` are attributes on the node (`domain_slug`, `topic_slug`) for filtering/coloring, never graph nodes themselves (spec decision 4).
- Layout is force-directed (auto-layout), never a fixed hierarchical/dagre layout (spec decision 3).
- A concept with no `ConceptMastery` row for the current user must still appear in the graph, with `studied=False, mastery_score=0.0, next_due_at=None` — never omitted (spec: "Manejo de errores / casos vacíos").
- This project has no automated frontend test framework (confirmed: no `vitest`/`jest` in `frontend/package.json`, no `*.test.tsx` files anywhere). Frontend tasks are verified via `npx tsc -b` (typecheck) plus manual browser verification, matching every prior frontend sub-plan (e.g. gamification Task 4) — do not introduce a test framework as part of this plan.
- Backend tasks follow strict TDD against the real test Postgres (`tests/conftest.py` — no mocks), matching every existing test in `backend/tests/content/`.

---

### Task 1: Backend — graph schemas + `get_knowledge_graph` service

**Files:**
- Modify: `backend/app/content/schemas.py`
- Modify: `backend/app/content/service.py`
- Test: `backend/tests/content/test_service.py`

**Interfaces:**
- Consumes: `app.models.content.Concept/Topic/Domain/ConceptRelationship/RelationshipType` (existing), `app.models.mastery.ConceptMastery/ReviewSchedule` (existing, read-only).
- Produces: `GraphNode(slug, name, domain_slug, topic_slug, mastery_score: float, studied: bool, next_due_at: datetime | None)`, `GraphEdge(source_slug, target_slug, type: RelationshipType)`, `GraphResponse(nodes: list[GraphNode], edges: list[GraphEdge])` in `app.content.schemas`. `get_knowledge_graph(db: Session, user_id) -> GraphResponse` in `app.content.service`. Consumed by Task 2's router.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/content/test_service.py` (it already has `_seed_minimal` — reuse it):

```python
from app.content.service import get_knowledge_graph
from app.content.schemas import GraphEdge
from app.models.mastery import ConceptMastery
from app.models.user import User


def _seed_user(db):
    user = User(username="owner", password_hash="x", totp_secret="x")
    db.add(user)
    db.commit()
    return user


def test_get_knowledge_graph_includes_all_concepts_and_relationships(db_session):
    _seed_minimal(db_session)
    user = _seed_user(db_session)

    graph = get_knowledge_graph(db_session, user.id)

    assert {n.slug for n in graph.nodes} == {"net-01", "net-02"}
    assert all(n.studied is False for n in graph.nodes)
    assert all(n.mastery_score == 0.0 for n in graph.nodes)
    assert all(n.next_due_at is None for n in graph.nodes)
    assert graph.edges == [GraphEdge(source_slug="net-02", target_slug="net-01", type="prerequisite")]


def test_get_knowledge_graph_reflects_user_mastery(db_session):
    _, _, _, concept = _seed_minimal(db_session)
    user = _seed_user(db_session)
    db_session.add(ConceptMastery(user_id=user.id, concept_id=concept.id, mastery_score=75.0))
    db_session.commit()

    graph = get_knowledge_graph(db_session, user.id)

    node = next(n for n in graph.nodes if n.slug == "net-02")
    assert node.studied is True
    assert node.mastery_score == 75.0

    other_node = next(n for n in graph.nodes if n.slug == "net-01")
    assert other_node.studied is False


def test_get_knowledge_graph_handles_concept_without_relationships(db_session):
    from app.models.content import Concept, Domain, Topic

    domain = Domain(slug="crypto", name="Criptografía")
    db_session.add(domain)
    db_session.flush()
    topic = Topic(domain_id=domain.id, slug="basics", name="Basics")
    db_session.add(topic)
    db_session.flush()
    db_session.add(Concept(topic_id=topic.id, slug="crypto-01", name="Cifrado simétrico"))
    db_session.commit()
    user = _seed_user(db_session)

    graph = get_knowledge_graph(db_session, user.id)

    assert len(graph.nodes) == 1
    node = graph.nodes[0]
    assert node.slug == "crypto-01"
    assert node.domain_slug == "crypto"
    assert node.topic_slug == "basics"
    assert graph.edges == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/content/test_service.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_knowledge_graph'` (or `GraphEdge`)

- [ ] **Step 3: Add the schemas**

In `backend/app/content/schemas.py`, add `from datetime import datetime` to the imports and `RelationshipType` from the content models, then append:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.content import RelationshipType

# ... existing ConceptSummary / TopicSummary / DomainSummary / LessonOut /
# ConceptRelationships / ConceptDetail stay unchanged, append below them:


class GraphNode(BaseModel):
    slug: str
    name: str
    domain_slug: str
    topic_slug: str
    mastery_score: float
    studied: bool
    next_due_at: datetime | None


class GraphEdge(BaseModel):
    source_slug: str
    target_slug: str
    type: RelationshipType


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
```

- [ ] **Step 4: Add the service function**

In `backend/app/content/service.py`, extend the existing import line and add the function at the end of the file:

```python
from app.content.schemas import (
    ConceptDetail,
    ConceptRelationships,
    ConceptSummary,
    DomainSummary,
    GraphEdge,
    GraphNode,
    GraphResponse,
    LessonOut,
    TopicSummary,
)
from app.models.content import Concept, ConceptRelationship, Domain, RelationshipType, Topic
from app.models.mastery import ConceptMastery, ReviewSchedule


def get_knowledge_graph(db: Session, user_id) -> GraphResponse:
    rows = (
        db.query(Concept, Topic, Domain, ConceptMastery, ReviewSchedule)
        .join(Topic, Concept.topic_id == Topic.id)
        .join(Domain, Topic.domain_id == Domain.id)
        .outerjoin(
            ConceptMastery,
            (ConceptMastery.concept_id == Concept.id) & (ConceptMastery.user_id == user_id),
        )
        .outerjoin(ReviewSchedule, ReviewSchedule.concept_mastery_id == ConceptMastery.id)
        .all()
    )

    nodes = [
        GraphNode(
            slug=concept.slug,
            name=concept.name,
            domain_slug=domain.slug,
            topic_slug=topic.slug,
            mastery_score=mastery.mastery_score if mastery is not None else 0.0,
            studied=mastery is not None,
            next_due_at=schedule.next_due_at if schedule is not None else None,
        )
        for concept, topic, domain, mastery, schedule in rows
    ]
    slug_by_concept_id = {concept.id: concept.slug for concept, *_ in rows}

    relationships = db.query(ConceptRelationship).all()
    edges = [
        GraphEdge(
            source_slug=slug_by_concept_id[rel.source_id],
            target_slug=slug_by_concept_id[rel.target_id],
            type=rel.type,
        )
        for rel in relationships
        if rel.source_id in slug_by_concept_id and rel.target_id in slug_by_concept_id
    ]

    return GraphResponse(nodes=nodes, edges=edges)
```

Note the `Session` import already exists at the top of `service.py` (`from sqlalchemy.orm import Session, selectinload`) — no change needed there.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/content/test_service.py -v`
Expected: PASS (all tests in the file, including the 3 new ones)

- [ ] **Step 6: Run the full backend test suite**

Run: `cd backend && pytest -q`
Expected: all pass, no regressions.

- [ ] **Step 7: Commit**

```bash
git add backend/app/content/schemas.py backend/app/content/service.py backend/tests/content/test_service.py
git commit -m "feat: add knowledge graph schema and service"
```

---

### Task 2: Backend — `GET /content/graph` endpoint

**Files:**
- Modify: `backend/app/content/router.py`
- Modify: `backend/tests/content/test_router.py`

**Interfaces:**
- Consumes: `app.content.service.get_knowledge_graph(db, user_id) -> GraphResponse` (Task 1).
- Produces: `GET /api/v1/content/graph` → `GraphResponse` JSON, 401 without a session. Consumed by Task 3's `api.getKnowledgeGraph()`.

- [ ] **Step 1: Make `_login_as_owner` return the user and write the failing tests**

`backend/tests/content/test_router.py`'s `_login_as_owner` currently doesn't return the created user. Change its last line from nothing to `return user` (safe — no existing caller uses the return value):

```python
def _login_as_owner(client, db_session):
    import pyotp

    from app.auth.security import hash_password
    from app.auth.totp import generate_totp_secret
    from app.models.user import User

    secret = generate_totp_secret()
    user = User(username="owner", password_hash=hash_password("s3cret-pass-1"), totp_secret=secret)
    db_session.add(user)
    db_session.commit()

    client.post("/api/v1/auth/login", json={"username": "owner", "password": "s3cret-pass-1"})
    code = pyotp.TOTP(secret).now()
    client.post("/api/v1/auth/mfa/verify", json={"code": code})
    return user
```

Then append these tests to the same file:

```python
def test_get_knowledge_graph_requires_auth(client):
    resp = client.get("/api/v1/content/graph")
    assert resp.status_code == 401


def test_get_knowledge_graph_returns_nodes_and_edges(client, db_session):
    _seed_minimal(db_session)
    _login_as_owner(client, db_session)

    resp = client.get("/api/v1/content/graph")

    assert resp.status_code == 200
    body = resp.json()
    slugs = {n["slug"] for n in body["nodes"]}
    assert slugs == {"net-01", "net-02"}
    assert body["edges"] == [{"source_slug": "net-02", "target_slug": "net-01", "type": "prerequisite"}]


def test_get_knowledge_graph_reflects_user_mastery(client, db_session):
    from app.models.mastery import ConceptMastery

    _, _, _, concept = _seed_minimal(db_session)
    user = _login_as_owner(client, db_session)
    db_session.add(ConceptMastery(user_id=user.id, concept_id=concept.id, mastery_score=42.0))
    db_session.commit()

    resp = client.get("/api/v1/content/graph")

    assert resp.status_code == 200
    body = resp.json()
    node = next(n for n in body["nodes"] if n["slug"] == "net-02")
    assert node["studied"] is True
    assert node["mastery_score"] == 42.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/content/test_router.py -v`
Expected: the 3 new tests FAIL with 404 (route doesn't exist yet); the rest of the file still passes.

- [ ] **Step 3: Add the endpoint**

In `backend/app/content/router.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.content import service
from app.content.schemas import ConceptDetail, DomainSummary, GraphResponse
from app.db import get_db
from app.models.user import User

router = APIRouter()


@router.get("/domains", response_model=list[DomainSummary])
def list_domains(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[DomainSummary]:
    return service.get_domains_tree(db)


@router.get("/graph", response_model=GraphResponse)
def get_knowledge_graph(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> GraphResponse:
    return service.get_knowledge_graph(db, user.id)


@router.get("/concepts/{slug}", response_model=ConceptDetail)
def get_concept(
    slug: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> ConceptDetail:
    detail = service.get_concept_detail(db, slug)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Concept not found")
    return detail
```

(The `/graph` route is added before `/concepts/{slug}` so it can't ever be shadowed by a path parameter — it isn't in this case since `/graph` and `/concepts/{slug}` are disjoint prefixes, but keeping fixed-path routes grouped together above parameterized ones is the existing convention in this file.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/content/test_router.py -v`
Expected: PASS (all tests, including the 3 new ones)

- [ ] **Step 5: Run the full backend test suite**

Run: `cd backend && pytest -q`
Expected: all pass, no regressions.

- [ ] **Step 6: Commit**

```bash
git add backend/app/content/router.py backend/tests/content/test_router.py
git commit -m "feat: add GET /content/graph endpoint"
```

---

### Task 3: Frontend — `KnowledgeGraph` component + `/graph` page

**Files:**
- Modify: `frontend/package.json` (via `npm install`)
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/features/graph/KnowledgeGraph.tsx`
- Create: `frontend/src/features/graph/GraphPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `GET /api/v1/content/graph` → `GraphResponse` (Task 2, JSON field names verbatim: `slug, name, domain_slug, topic_slug, mastery_score, studied, next_due_at` for nodes; `source_slug, target_slug, type` for edges).
- Produces: `KnowledgeGraph` component `{ data: GraphResponse, height: number, interactive: boolean, highlightSlug?: string, onNodeClick: (slug: string) => void }` with an imperative handle `{ centerOnNode(slug: string): void }` via `ref`. Consumed by Task 4's Dashboard integration.

No backend tests apply to this task — pure frontend UI, verified via typecheck + manual browser check per this project's established pattern (no automated frontend test suite exists — see Global Constraints).

- [ ] **Step 1: Install the graph library**

```bash
cd frontend && npm install react-force-graph-2d
```

- [ ] **Step 2: Add the graph types and API call**

In `frontend/src/lib/api.ts`, add these types near `ConceptDetail`/`DomainSummary`:

```typescript
export type GraphNode = {
  slug: string;
  name: string;
  domain_slug: string;
  topic_slug: string;
  mastery_score: number;
  studied: boolean;
  next_due_at: string | null;
};

export type GraphEdge = {
  source_slug: string;
  target_slug: string;
  type: "prerequisite" | "related" | "continues_with";
};

export type GraphResponse = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};
```

And add this entry to the `api` object, next to `listDomains`/`getConcept`:

```typescript
  getKnowledgeGraph: () => request<GraphResponse>("/content/graph"),
```

- [ ] **Step 3: Create the shared `KnowledgeGraph` component**

```tsx
// frontend/src/features/graph/KnowledgeGraph.tsx
import { forwardRef, useImperativeHandle, useMemo, useRef } from "react";
import ForceGraph2D, { ForceGraphMethods } from "react-force-graph-2d";
import { GraphResponse } from "../../lib/api";

type GraphNodeDatum = {
  id: string;
  slug: string;
  name: string;
  domain_slug: string;
  topic_slug: string;
  mastery_score: number;
  studied: boolean;
  next_due_at: string | null;
  x?: number;
  y?: number;
};

type GraphLinkDatum = {
  source: string;
  target: string;
  type: "prerequisite" | "related" | "continues_with";
};

const EDGE_COLOR: Record<GraphLinkDatum["type"], string> = {
  prerequisite: "#3b82f6",
  continues_with: "#a855f7",
  related: "#9ca3af",
};

function masteryColor(score: number): string {
  const clamped = Math.max(0, Math.min(100, score));
  const hue = (clamped / 100) * 120;
  return `hsl(${hue}, 70%, 45%)`;
}

function nodeFillColor(node: GraphNodeDatum, highlightSlug?: string): string {
  if (node.slug === highlightSlug) return "#facc15";
  return node.studied ? masteryColor(node.mastery_score) : "#888888";
}

export type KnowledgeGraphHandle = {
  centerOnNode: (slug: string) => void;
};

type KnowledgeGraphProps = {
  data: GraphResponse;
  height: number;
  interactive: boolean;
  highlightSlug?: string;
  onNodeClick: (slug: string) => void;
};

export const KnowledgeGraph = forwardRef<KnowledgeGraphHandle, KnowledgeGraphProps>(
  function KnowledgeGraph({ data, height, interactive, highlightSlug, onNodeClick }, ref) {
    const graphRef = useRef<ForceGraphMethods>();

    const graphData = useMemo(
      () => ({
        nodes: data.nodes.map((n) => ({ ...n, id: n.slug })) as GraphNodeDatum[],
        links: data.edges.map((e) => ({
          source: e.source_slug,
          target: e.target_slug,
          type: e.type,
        })) as GraphLinkDatum[],
      }),
      [data]
    );

    useImperativeHandle(ref, () => ({
      centerOnNode: (slug: string) => {
        const node = graphData.nodes.find((n) => n.id === slug);
        if (node && graphRef.current && node.x !== undefined && node.y !== undefined) {
          graphRef.current.centerAt(node.x, node.y, 600);
          graphRef.current.zoom(4, 600);
        }
      },
    }));

    return (
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        height={height}
        nodeId="id"
        nodeLabel={(node) => {
          const n = node as GraphNodeDatum;
          const masteryLine = n.studied ? `Mastery: ${n.mastery_score.toFixed(0)}%` : "No estudiado";
          const dueLine = n.next_due_at
            ? `<br/>Próximo repaso: ${new Date(n.next_due_at).toLocaleDateString()}`
            : "";
          return `<div><strong>${n.name}</strong><br/>${masteryLine}${dueLine}</div>`;
        }}
        nodeColor={(node) => nodeFillColor(node as GraphNodeDatum, highlightSlug)}
        enableNodeDrag={interactive}
        linkColor={(link) => EDGE_COLOR[(link as GraphLinkDatum).type]}
        linkDirectionalArrowLength={(link) => ((link as GraphLinkDatum).type === "related" ? 0 : 6)}
        linkDirectionalArrowRelPos={1}
        linkLineDash={(link) => ((link as GraphLinkDatum).type === "continues_with" ? [2, 2] : null)}
        onNodeClick={(node) => onNodeClick((node as GraphNodeDatum).slug)}
      />
    );
  }
);
```

If `npx tsc -b` (Step 6 below) reports that `linkLineDash` or another prop doesn't exist on `ForceGraph2D`'s props type, open `frontend/node_modules/react-force-graph-2d/dist/react-force-graph-2d.d.ts` to find the exact prop name/signature the installed version ships and adjust the corresponding line — the surrounding structure (node coloring, click handling, arrow length) does not depend on that one prop.

- [ ] **Step 4: Create the full graph page**

```tsx
// frontend/src/features/graph/GraphPage.tsx
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, GraphResponse } from "../../lib/api";
import { KnowledgeGraph, KnowledgeGraphHandle } from "./KnowledgeGraph";

function filterGraphByDomains(data: GraphResponse, selectedDomains: Set<string>): GraphResponse {
  const nodes = data.nodes.filter((n) => selectedDomains.has(n.domain_slug));
  const nodeSlugs = new Set(nodes.map((n) => n.slug));
  const edges = data.edges.filter((e) => nodeSlugs.has(e.source_slug) && nodeSlugs.has(e.target_slug));
  return { nodes, edges };
}

export function GraphPage() {
  const navigate = useNavigate();
  const graphRef = useRef<KnowledgeGraphHandle>(null);
  const [data, setData] = useState<GraphResponse | null>(null);
  const [selectedDomains, setSelectedDomains] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [highlightSlug, setHighlightSlug] = useState<string | undefined>(undefined);

  useEffect(() => {
    api.getKnowledgeGraph().then((graph) => {
      setData(graph);
      setSelectedDomains(new Set(graph.nodes.map((n) => n.domain_slug)));
    });
  }, []);

  const domains = useMemo(
    () => Array.from(new Set((data?.nodes ?? []).map((n) => n.domain_slug))).sort(),
    [data]
  );

  const filtered = useMemo(
    () => (data ? filterGraphByDomains(data, selectedDomains) : null),
    [data, selectedDomains]
  );

  function toggleDomain(domain: string) {
    setSelectedDomains((prev) => {
      const next = new Set(prev);
      if (next.has(domain)) next.delete(domain);
      else next.add(domain);
      return next;
    });
  }

  function handleSearch(e: FormEvent) {
    e.preventDefault();
    const match = data?.nodes.find((n) => n.name.toLowerCase().includes(search.toLowerCase()));
    if (match) {
      setHighlightSlug(match.slug);
      graphRef.current?.centerOnNode(match.slug);
    }
  }

  if (!data || !filtered) return <p>Cargando…</p>;

  if (data.nodes.length === 0) {
    return <p>Todavía no hay contenido para mostrar.</p>;
  }

  return (
    <div style={{ display: "flex", height: "calc(100vh - 40px)" }}>
      <aside style={{ width: 220, padding: 16, overflowY: "auto", flexShrink: 0 }}>
        <h2>Dominios</h2>
        {domains.map((domain) => (
          <label key={domain} style={{ display: "block" }}>
            <input type="checkbox" checked={selectedDomains.has(domain)} onChange={() => toggleDomain(domain)} />
            {" "}
            {domain}
          </label>
        ))}
        <form onSubmit={handleSearch} style={{ marginTop: 16 }}>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar concepto…"
          />
          <button type="submit">Buscar</button>
        </form>
      </aside>
      <div style={{ flex: 1 }}>
        {filtered.nodes.length === 0 ? (
          <p>Ningún concepto coincide con el filtro.</p>
        ) : (
          <KnowledgeGraph
            ref={graphRef}
            data={filtered}
            height={window.innerHeight - 40}
            interactive={true}
            highlightSlug={highlightSlug}
            onNodeClick={(slug) => navigate(`/lessons/${slug}`)}
          />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Wire the route**

In `frontend/src/App.tsx`, add the import and route:

```tsx
import { GraphPage } from "./features/graph/GraphPage";
```

```tsx
                <Route path="/labs" element={<LabsPage />} />
                <Route path="/labs/:labId" element={<LabInstancePage />} />
                <Route path="/graph" element={<GraphPage />} />
```

- [ ] **Step 6: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: no errors. If stray `.js` files appear next to `.tsx` sources (known `tsc -b` side effect in this project, no `outDir` configured), delete them: `find src -name "*.js" -delete` from `frontend/`.

- [ ] **Step 7: Manual verification**

Check what's already running before starting anything: `ss -ltnp | grep -E ':8001|:517[0-9]|:8765'`. Port 5173 on this machine may belong to an unrelated project (SimuCenter-OS) — never assume it's CyberLearn's without checking `cat /proc/<pid>/cwd`.

If the backend isn't running: `cd backend && source .venv/bin/activate && setsid nohup uvicorn app.main:app --port 8001 > /tmp/api.log 2>&1 < /dev/null & disown`

If the frontend isn't running: `cd frontend && setsid nohup npm run dev > /tmp/frontend.log 2>&1 < /dev/null & disown` (check `/tmp/frontend.log` for the port it actually bound to).

Mint an authenticated session for the existing `owner` user directly (avoids needing the password):

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

Set that value as a `cl_session` cookie in the browser, navigate to `/graph`, and confirm:
- Nodes render for the seeded Networking concepts (NET-01–10), spread out by the force layout.
- Zoom (scroll) and pan (drag background) both work.
- Dragging a node (drag interaction, since `interactive=true`) moves it.
- Hovering a node shows a tooltip with its name and mastery/"No estudiado".
- Unchecking a domain in the sidebar removes its nodes (and any edges touching them) from the canvas.
- Typing a concept name into the search box and submitting centers/zooms on that node and colors it yellow.
- Clicking a node navigates to `/lessons/:slug` for that concept.

Clean up afterward: stop any process you started by exact PID (`ss -ltnp | grep <port>` → `kill <pid>`, never `pkill` by name/pattern).

- [ ] **Step 8: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/api.ts frontend/src/features/graph/ frontend/src/App.tsx
git commit -m "feat: add navigable knowledge graph page"
```

---

### Task 4: Frontend — Dashboard preview + link

**Files:**
- Modify: `frontend/src/features/dashboard/DashboardPage.tsx`

**Interfaces:**
- Consumes: `api.getKnowledgeGraph()` and `KnowledgeGraph` component (Task 3).

No backend tests apply to this task — pure frontend UI, verified via typecheck + manual browser check.

- [ ] **Step 1: Add the graph fetch and remove the placeholder**

In `frontend/src/features/dashboard/DashboardPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, DashboardSummary, GraphResponse } from "../../lib/api";
import { KnowledgeGraph } from "../graph/KnowledgeGraph";

const COMING_SOON = [
  "Fragmentación",
  "Error Memory",
  "Labs recomendados",
  "Tiempo de práctica",
  "Transfer / Methodology Score",
];

export function DashboardPage() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);

  useEffect(() => {
    api.getDashboardSummary().then(setSummary);
    api.getKnowledgeGraph().then(setGraph);
  }, []);

  if (!summary) return <p>Cargando…</p>;
```

("Knowledge Connectivity" is removed from `COMING_SOON` since this task replaces it with a real section.)

- [ ] **Step 2: Add the Knowledge Graph section**

Insert this new `<section>` immediately after the "Logros" section and before "Próximamente":

```tsx
      <section>
        <h2>Knowledge Graph</h2>
        {graph === null ? (
          <p>Cargando…</p>
        ) : graph.nodes.length === 0 ? (
          <p>Todavía no hay contenido para mostrar.</p>
        ) : (
          <>
            <KnowledgeGraph
              data={graph}
              height={300}
              interactive={false}
              onNodeClick={(slug) => navigate(`/lessons/${slug}`)}
            />
            <p>
              <Link to="/graph">Ver grafo completo</Link>
            </p>
          </>
        )}
      </section>
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: no errors. Clean up any stray `.js` files as in Task 3 Step 6 if they appear.

- [ ] **Step 4: Manual verification**

Using the same running backend/frontend and minted session cookie from Task 3 Step 7 (mint a fresh one if the prior session expired), navigate to `/dashboard` and confirm:
- The "Knowledge Graph" section renders a small (300px tall), read-only graph (no drag) with the same nodes as `/graph`.
- Clicking a node in the preview navigates to `/lessons/:slug`.
- "Ver grafo completo" navigates to `/graph`.
- "Knowledge Connectivity" no longer appears under "Próximamente".

Clean up afterward: stop any process you started by exact PID, same as Task 3 Step 7.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/dashboard/DashboardPage.tsx
git commit -m "feat: show knowledge graph preview on the dashboard"
```

---

### Task 5: Update checklist

**Files:**
- Modify: `PROJECT_MASTER_CHECKLIST.md`

- [ ] **Step 1: Update the Fase 2 section**

The current `### Pendientes de Fase 2` block looks like:

```markdown
### Pendientes de Fase 2
- [ ] Knowledge graph navegable — vista visual interactiva (hoy solo lista jerárquica vía relaciones)
- [ ] Base de datos de vulnerabilidades
- [ ] Error Memory completo (`ErrorPattern`)
- [ ] Fragmentation score + ejercicios integradores
- [ ] Export/Import Obsidian (notas y lecciones)
- [ ] Búsqueda global / Command Palette (Ctrl+K)
```

Replace it with:

```markdown
### Knowledge graph navegable
- [x] Endpoint `GET /content/graph` (nodos = concepts con mastery del usuario, aristas = `ConceptRelationship`)
- [x] Página `/graph` con auto-layout por fuerza, filtro por dominio, búsqueda y click-to-navigate
- [x] Preview embebido en el Dashboard (reemplaza el placeholder "Knowledge Connectivity")

### Pendientes de Fase 2
- [ ] Base de datos de vulnerabilidades
- [ ] Error Memory completo (`ErrorPattern`)
- [ ] Fragmentation score + ejercicios integradores
- [ ] Export/Import Obsidian (notas y lecciones)
- [ ] Búsqueda global / Command Palette (Ctrl+K)
```

- [ ] **Step 2: Commit**

```bash
git add PROJECT_MASTER_CHECKLIST.md
git commit -m "docs: update checklist — Fase 2 Knowledge graph navegable complete"
```
