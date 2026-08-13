# Content + Lessons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the content system (Domain/Topic/Concept/Lesson/ConceptRelationship models, YAML-based seed loader, read API, and a lesson viewer in the frontend), then load the 10 real Networking lessons (NET-01–NET-10) written by the cybersecurity-instructor agent.

**Architecture:** New `content` module in the FastAPI backend (models + service + router), following the same pattern as `auth`. Content is authored as YAML files under `content/networking/` and loaded into Postgres by an idempotent seed script (two-pass: upsert concepts, then resolve relationships). Frontend adds a read-only lesson viewer route.

**Tech Stack:** Same as the scaffolding+auth plan (FastAPI, SQLAlchemy, Alembic, Postgres, React+Vite), plus PyYAML (backend) and `marked` (frontend, Markdown rendering).

## Global Constraints

- Content model and API shape must match `docs/superpowers/specs/2026-08-13-content-lessons-design.md` exactly (10 `Lesson` fields, no more, no less — `error_personal`/`mini_evaluacion`/`laboratorio`/`repaso` are explicitly out of scope here).
- `Concept.slug` is the stable identifier used everywhere (YAML, URLs, relationships) — never expose or depend on internal UUIDs in the API surface beyond what's needed.
- `seed_content.py` must be idempotent — running it twice must not duplicate rows.
- All new routes live under `/api/v1/content/...` and require authentication (reuse `get_current_user` from the scaffolding+auth plan).
- No frontend automated tests in this plan (consistent with the scaffolding+auth plan — verification is manual/backend-test-driven).

---

## File Structure

```
backend/
├── requirements.txt (add pyyaml)
├── app/
│   ├── models/
│   │   └── content.py          # Domain, Topic, Concept, Lesson, ConceptRelationship, RelationshipType
│   ├── content/
│   │   ├── __init__.py
│   │   ├── schemas.py          # ConceptSummary, TopicSummary, DomainSummary, LessonOut, ConceptDetail
│   │   ├── service.py          # get_domains_tree, get_concept_detail
│   │   └── router.py           # GET /domains, GET /concepts/{slug}
│   ├── main.py                 # mount content router
│   └── alembic/env.py          # import app.models.content
├── alembic/versions/0002_create_content_tables.py
├── scripts/
│   └── seed_content.py
└── tests/content/
    ├── __init__.py
    ├── test_service.py
    └── test_router.py

content/networking/            # already exists — written by the cybersecurity-instructor agent
├── net-01-fundamentals.yaml
├── ... (net-02 .. net-10)

frontend/
├── package.json (add marked)
└── src/
    ├── lib/api.ts              # add types + listDomains/getConcept
    ├── features/lessons/
    │   └── LessonPage.tsx
    └── App.tsx                 # add /lessons/:slug route
```

---

### Task 1: Content models + migration

**Files:**
- Create: `backend/app/models/content.py`
- Modify: `backend/alembic/env.py:9` — add `from app.models import content  # noqa: F401`
- Create: `backend/alembic/versions/0002_create_content_tables.py`

**Interfaces:**
- Consumes: `app.db.Base` (from scaffolding+auth plan Task 2).
- Produces: `app.models.content.Domain`, `Topic`, `Concept`, `Lesson`, `ConceptRelationship`, `RelationshipType` (str enum: `prerequisite`, `related`, `continues_with`) — consumed by Tasks 2 and 4.

- [ ] **Step 1: Write `backend/app/models/content.py`**

```python
import enum
import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RelationshipType(str, enum.Enum):
    prerequisite = "prerequisite"
    related = "related"
    continues_with = "continues_with"


class Domain(Base):
    __tablename__ = "domains"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    topics: Mapped[list["Topic"]] = relationship(back_populates="domain", order_by="Topic.name")


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("domain_id", "slug", name="uq_topic_domain_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("domains.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    domain: Mapped["Domain"] = relationship(back_populates="topics")
    concepts: Mapped[list["Concept"]] = relationship(back_populates="topic", order_by="Concept.name")


class Concept(Base):
    __tablename__ = "concepts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    topic: Mapped["Topic"] = relationship(back_populates="concepts")
    lesson: Mapped["Lesson | None"] = relationship(back_populates="concept", uselist=False)


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id"), unique=True, nullable=False
    )

    concepto: Mapped[str | None] = mapped_column(Text, nullable=True)
    como_funciona: Mapped[str | None] = mapped_column(Text, nullable=True)
    por_que_importa: Mapped[str | None] = mapped_column(Text, nullable=True)
    visualizacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    ejemplo: Mapped[str | None] = mapped_column(Text, nullable=True)
    comandos: Mapped[str | None] = mapped_column(Text, nullable=True)
    errores_frecuentes: Mapped[str | None] = mapped_column(Text, nullable=True)
    regla_mental: Mapped[str | None] = mapped_column(Text, nullable=True)
    perspectiva_ofensiva: Mapped[str | None] = mapped_column(Text, nullable=True)
    perspectiva_defensiva: Mapped[str | None] = mapped_column(Text, nullable=True)

    concept: Mapped["Concept"] = relationship(back_populates="lesson")


class ConceptRelationship(Base):
    __tablename__ = "concept_relationships"
    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "type", name="uq_concept_relationship"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=False)
    type: Mapped[RelationshipType] = mapped_column(
        SAEnum(RelationshipType, name="relationship_type"), nullable=False
    )

    source: Mapped["Concept"] = relationship(foreign_keys=[source_id])
    target: Mapped["Concept"] = relationship(foreign_keys=[target_id])
```

- [ ] **Step 2: Register the models with Alembic**

In `backend/alembic/env.py`, change:
```python
from app.models import user  # noqa: F401 — registers User with Base.metadata
```
to:
```python
from app.models import user  # noqa: F401 — registers User with Base.metadata
from app.models import content  # noqa: F401 — registers content models with Base.metadata
```

- [ ] **Step 3: Generate and apply the migration**

Run:
```bash
cd backend
alembic revision --autogenerate -m "create content tables"
mv alembic/versions/<generated_hash>_create_content_tables.py alembic/versions/0002_create_content_tables.py
alembic upgrade head
```

- [ ] **Step 4: Verify the tables**

Run: `PGPASSWORD=cyberlearn psql -h localhost -p 55432 -U cyberlearn -d cyberlearn -c "\dt"`
Expected: `domains`, `topics`, `concepts`, `lessons`, `concept_relationships` all present alongside `users`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/content.py backend/alembic/env.py backend/alembic/versions/0002_create_content_tables.py
git commit -m "feat: add content models (Domain/Topic/Concept/Lesson/ConceptRelationship)"
```

---

### Task 2: Content schemas + service

**Files:**
- Create: `backend/app/content/__init__.py`
- Create: `backend/app/content/schemas.py`
- Create: `backend/app/content/service.py`
- Test: `backend/tests/content/__init__.py`
- Test: `backend/tests/content/test_service.py`

**Interfaces:**
- Consumes: `app.models.content.*` (Task 1).
- Produces: `app.content.service.get_domains_tree(db) -> list[DomainSummary]`, `app.content.service.get_concept_detail(db, slug) -> ConceptDetail | None` — consumed by Task 3's router.

- [ ] **Step 1: Write `backend/app/content/schemas.py`**

```python
from pydantic import BaseModel, ConfigDict


class ConceptSummary(BaseModel):
    slug: str
    name: str


class TopicSummary(BaseModel):
    slug: str
    name: str
    concepts: list[ConceptSummary]


class DomainSummary(BaseModel):
    slug: str
    name: str
    topics: list[TopicSummary]


class LessonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    concepto: str | None = None
    como_funciona: str | None = None
    por_que_importa: str | None = None
    visualizacion: str | None = None
    ejemplo: str | None = None
    comandos: str | None = None
    errores_frecuentes: str | None = None
    regla_mental: str | None = None
    perspectiva_ofensiva: str | None = None
    perspectiva_defensiva: str | None = None


class ConceptRelationships(BaseModel):
    prerequisites: list[ConceptSummary]
    related: list[ConceptSummary]
    continues_with: list[ConceptSummary]


class ConceptDetail(BaseModel):
    slug: str
    name: str
    lesson: LessonOut | None
    relationships: ConceptRelationships
```

- [ ] **Step 2: Write the failing test**

`backend/tests/content/__init__.py`: empty file.

`backend/tests/content/test_service.py`:
```python
from app.content.service import get_concept_detail, get_domains_tree
from app.models.content import Concept, ConceptRelationship, Domain, Lesson, RelationshipType, Topic


def _seed_minimal(db):
    domain = Domain(slug="networking", name="Networking")
    db.add(domain)
    db.flush()

    topic = Topic(domain_id=domain.id, slug="fundamentals", name="Fundamentos")
    db.add(topic)
    db.flush()

    prereq = Concept(topic_id=topic.id, slug="net-01", name="Fundamentos de Redes")
    concept = Concept(topic_id=topic.id, slug="net-02", name="Ethernet, MAC y ARP")
    db.add_all([prereq, concept])
    db.flush()

    lesson = Lesson(concept_id=concept.id, concepto="Un protocolo...", regla_mental="MAC = a quien se lo entrego.")
    db.add(lesson)

    db.add(ConceptRelationship(source_id=concept.id, target_id=prereq.id, type=RelationshipType.prerequisite))
    db.commit()
    return domain, topic, prereq, concept


def test_get_domains_tree_returns_nested_structure(db_session):
    _seed_minimal(db_session)

    domains = get_domains_tree(db_session)

    assert len(domains) == 1
    assert domains[0].slug == "networking"
    assert len(domains[0].topics) == 1
    assert domains[0].topics[0].slug == "fundamentals"
    slugs = {c.slug for c in domains[0].topics[0].concepts}
    assert slugs == {"net-01", "net-02"}


def test_get_concept_detail_includes_lesson_and_relationships(db_session):
    _seed_minimal(db_session)

    detail = get_concept_detail(db_session, "net-02")

    assert detail is not None
    assert detail.name == "Ethernet, MAC y ARP"
    assert detail.lesson.concepto == "Un protocolo..."
    assert detail.lesson.regla_mental == "MAC = a quien se lo entrego."
    assert [p.slug for p in detail.relationships.prerequisites] == ["net-01"]
    assert detail.relationships.related == []
    assert detail.relationships.continues_with == []


def test_get_concept_detail_returns_none_for_unknown_slug(db_session):
    assert get_concept_detail(db_session, "does-not-exist") is None
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd backend && pytest tests/content/test_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.content'`

- [ ] **Step 4: Write `backend/app/content/__init__.py`** (empty file)

- [ ] **Step 5: Write `backend/app/content/service.py`**

```python
from sqlalchemy.orm import Session, selectinload

from app.content.schemas import (
    ConceptDetail,
    ConceptRelationships,
    ConceptSummary,
    DomainSummary,
    LessonOut,
    TopicSummary,
)
from app.models.content import Concept, ConceptRelationship, Domain, RelationshipType, Topic


def get_domains_tree(db: Session) -> list[DomainSummary]:
    domains = (
        db.query(Domain)
        .options(selectinload(Domain.topics).selectinload(Topic.concepts))
        .order_by(Domain.name)
        .all()
    )
    return [
        DomainSummary(
            slug=d.slug,
            name=d.name,
            topics=[
                TopicSummary(
                    slug=t.slug,
                    name=t.name,
                    concepts=[ConceptSummary(slug=c.slug, name=c.name) for c in t.concepts],
                )
                for t in d.topics
            ],
        )
        for d in domains
    ]


def get_concept_detail(db: Session, slug: str) -> ConceptDetail | None:
    concept = db.query(Concept).filter(Concept.slug == slug).first()
    if concept is None:
        return None

    lesson_out = LessonOut.model_validate(concept.lesson) if concept.lesson is not None else None

    rels = db.query(ConceptRelationship).filter(ConceptRelationship.source_id == concept.id).all()
    by_type: dict[RelationshipType, list[ConceptSummary]] = {t: [] for t in RelationshipType}
    for rel in rels:
        by_type[rel.type].append(ConceptSummary(slug=rel.target.slug, name=rel.target.name))

    return ConceptDetail(
        slug=concept.slug,
        name=concept.name,
        lesson=lesson_out,
        relationships=ConceptRelationships(
            prerequisites=by_type[RelationshipType.prerequisite],
            related=by_type[RelationshipType.related],
            continues_with=by_type[RelationshipType.continues_with],
        ),
    )
```

- [ ] **Step 6: Run it to verify it passes**

Run: `pytest tests/content/test_service.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/content/__init__.py backend/app/content/schemas.py backend/app/content/service.py backend/tests/content
git commit -m "feat: add content schemas and query service"
```

---

### Task 3: Content router

**Files:**
- Create: `backend/app/content/router.py`
- Modify: `backend/app/main.py` — mount the content router
- Test: `backend/tests/content/test_router.py`

**Interfaces:**
- Consumes: `app.content.service.get_domains_tree`/`get_concept_detail` (Task 2), `app.auth.dependencies.get_current_user` (scaffolding+auth plan Task 8).
- Produces: `GET /api/v1/content/domains`, `GET /api/v1/content/concepts/{slug}`.

- [ ] **Step 1: Write `backend/app/content/router.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.content import service
from app.content.schemas import ConceptDetail, DomainSummary
from app.db import get_db
from app.models.user import User

router = APIRouter()


@router.get("/domains", response_model=list[DomainSummary])
def list_domains(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[DomainSummary]:
    return service.get_domains_tree(db)


@router.get("/concepts/{slug}", response_model=ConceptDetail)
def get_concept(
    slug: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> ConceptDetail:
    detail = service.get_concept_detail(db, slug)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Concept not found")
    return detail
```

- [ ] **Step 2: Mount it in `backend/app/main.py`**

```python
from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.content.router import router as content_router

app = FastAPI(title="CyberLearn API")
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(content_router, prefix="/api/v1/content", tags=["content"])


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 3: Write the failing test**

`backend/tests/content/test_router.py`:
```python
from tests.content.test_service import _seed_minimal


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


def test_list_domains_requires_auth(client):
    resp = client.get("/api/v1/content/domains")
    assert resp.status_code == 401


def test_list_domains_returns_seeded_tree(client, db_session):
    _seed_minimal(db_session)
    _login_as_owner(client, db_session)

    resp = client.get("/api/v1/content/domains")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["slug"] == "networking"


def test_get_concept_returns_404_for_unknown_slug(client, db_session):
    _login_as_owner(client, db_session)

    resp = client.get("/api/v1/content/concepts/does-not-exist")
    assert resp.status_code == 404


def test_get_concept_returns_lesson_for_known_slug(client, db_session):
    _seed_minimal(db_session)
    _login_as_owner(client, db_session)

    resp = client.get("/api/v1/content/concepts/net-02")
    assert resp.status_code == 200
    body = resp.json()
    assert body["lesson"]["regla_mental"] == "MAC = a quien se lo entrego."
    assert body["relationships"]["prerequisites"][0]["slug"] == "net-01"
```

- [ ] **Step 4: Run it to verify it fails**

Run: `pytest tests/content/test_router.py -v`
Expected: FAIL (`app.content.router` doesn't exist yet if Step 1-2 not yet applied; if already applied, this step is a no-op check — proceed to Step 5's run)

- [ ] **Step 5: Run it to verify it passes**

Run: `pytest tests/content/test_router.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/content/router.py backend/app/main.py backend/tests/content/test_router.py
git commit -m "feat: add content API endpoints (domains tree, concept detail)"
```

---

### Task 4: `seed_content.py` — idempotent YAML loader

**Files:**
- Modify: `backend/requirements.txt` — add `pyyaml==6.0.3`
- Create: `backend/scripts/seed_content.py`
- Test: `backend/tests/test_seed_content.py`

**Interfaces:**
- Consumes: `app.db.SessionLocal` (scaffolding+auth plan Task 2), `app.models.content.*` (Task 1).
- Produces: `scripts.seed_content.seed_content(content_dir: str = "content") -> None` — called manually in Task 6, and importable by tests.

- [ ] **Step 1: Add PyYAML to requirements**

In `backend/requirements.txt`, add a line: `pyyaml==6.0.3`

Run: `cd backend && .venv/bin/pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

`backend/tests/test_seed_content.py`:
```python
import os
import tempfile

import yaml

from app.models.content import Concept, ConceptRelationship, Domain, Lesson, Topic
from scripts.seed_content import seed_content

NET_01 = {
    "domain": {"slug": "networking", "name": "Networking"},
    "topic": {"slug": "fundamentals", "name": "Fundamentos"},
    "concept": {"slug": "net-01", "name": "Fundamentos de Redes"},
    "lesson": {"concepto": "Una red es...", "regla_mental": "Regla 1"},
    "relationships": [],
}

NET_02 = {
    "domain": {"slug": "networking", "name": "Networking"},
    "topic": {"slug": "fundamentals", "name": "Fundamentos"},
    "concept": {"slug": "net-02", "name": "Ethernet, MAC y ARP"},
    "lesson": {"concepto": "ARP es...", "regla_mental": "Regla 2"},
    "relationships": [{"type": "prerequisite", "target_slug": "net-01"}],
}


def _write_content_dir(tmpdir, files: dict[str, dict]) -> str:
    content_dir = os.path.join(tmpdir, "content", "networking")
    os.makedirs(content_dir, exist_ok=True)
    for filename, data in files.items():
        with open(os.path.join(content_dir, filename), "w") as f:
            yaml.safe_dump(data, f)
    return os.path.join(tmpdir, "content")


def test_seed_content_creates_concepts_lessons_and_relationships(db_session):
    with tempfile.TemporaryDirectory() as tmpdir:
        content_dir = _write_content_dir(tmpdir, {"net-01.yaml": NET_01, "net-02.yaml": NET_02})
        seed_content(content_dir)

    assert db_session.query(Domain).filter_by(slug="networking").count() == 1
    assert db_session.query(Topic).filter_by(slug="fundamentals").count() == 1
    net01 = db_session.query(Concept).filter_by(slug="net-01").one()
    net02 = db_session.query(Concept).filter_by(slug="net-02").one()
    assert db_session.query(Lesson).filter_by(concept_id=net02.id).one().regla_mental == "Regla 2"

    rel = db_session.query(ConceptRelationship).filter_by(source_id=net02.id, target_id=net01.id).one()
    assert rel.type.value == "prerequisite"


def test_seed_content_is_idempotent(db_session):
    with tempfile.TemporaryDirectory() as tmpdir:
        content_dir = _write_content_dir(tmpdir, {"net-01.yaml": NET_01, "net-02.yaml": NET_02})
        seed_content(content_dir)
        seed_content(content_dir)

    assert db_session.query(Concept).filter_by(slug="net-01").count() == 1
    assert db_session.query(Concept).filter_by(slug="net-02").count() == 1
    assert db_session.query(ConceptRelationship).count() == 1
```

Note: `seed_content` uses its own `SessionLocal` internally (not the test's `db_session` fixture), so this test relies on `conftest.py`'s `_clean_state` fixture pointing at the same test database — it does, since both use `app.db.engine`/`app.config.settings.database_url`.

- [ ] **Step 3: Run it to verify it fails**

Run: `pytest tests/test_seed_content.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.seed_content'`

- [ ] **Step 4: Write `backend/scripts/seed_content.py`**

```python
import glob
import sys

import yaml
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.content import Concept, ConceptRelationship, Domain, Lesson, RelationshipType, Topic

LESSON_FIELDS = {
    "concepto",
    "como_funciona",
    "por_que_importa",
    "visualizacion",
    "ejemplo",
    "comandos",
    "errores_frecuentes",
    "regla_mental",
    "perspectiva_ofensiva",
    "perspectiva_defensiva",
}


def _upsert_domain(db: Session, data: dict) -> Domain:
    domain = db.query(Domain).filter(Domain.slug == data["slug"]).first()
    if domain is None:
        domain = Domain(slug=data["slug"], name=data["name"])
        db.add(domain)
        db.flush()
    else:
        domain.name = data["name"]
    return domain


def _upsert_topic(db: Session, domain: Domain, data: dict) -> Topic:
    topic = (
        db.query(Topic)
        .filter(Topic.domain_id == domain.id, Topic.slug == data["slug"])
        .first()
    )
    if topic is None:
        topic = Topic(domain_id=domain.id, slug=data["slug"], name=data["name"])
        db.add(topic)
        db.flush()
    else:
        topic.name = data["name"]
    return topic


def _upsert_concept(db: Session, topic: Topic, data: dict) -> Concept:
    concept = db.query(Concept).filter(Concept.slug == data["slug"]).first()
    if concept is None:
        concept = Concept(topic_id=topic.id, slug=data["slug"], name=data["name"])
        db.add(concept)
        db.flush()
    else:
        concept.topic_id = topic.id
        concept.name = data["name"]
    return concept


def _upsert_lesson(db: Session, concept: Concept, data: dict) -> None:
    values = {field: data.get(field) for field in LESSON_FIELDS}
    lesson = db.query(Lesson).filter(Lesson.concept_id == concept.id).first()
    if lesson is None:
        db.add(Lesson(concept_id=concept.id, **values))
    else:
        for field, value in values.items():
            setattr(lesson, field, value)


def seed_content(content_dir: str = "content") -> None:
    db = SessionLocal()
    try:
        paths = sorted(glob.glob(f"{content_dir}/**/*.yaml", recursive=True))
        parsed: list[tuple[Concept, list[dict]]] = []

        for path in paths:
            with open(path) as f:
                data = yaml.safe_load(f)
            domain = _upsert_domain(db, data["domain"])
            topic = _upsert_topic(db, domain, data["topic"])
            concept = _upsert_concept(db, topic, data["concept"])
            _upsert_lesson(db, concept, data["lesson"])
            parsed.append((concept, data.get("relationships", [])))
        db.commit()

        for concept, relationships in parsed:
            for rel in relationships:
                target = db.query(Concept).filter(Concept.slug == rel["target_slug"]).first()
                if target is None:
                    print(
                        f"WARNING: unknown target_slug '{rel['target_slug']}' referenced by '{concept.slug}'",
                        file=sys.stderr,
                    )
                    continue
                rel_type = RelationshipType(rel["type"])
                existing = (
                    db.query(ConceptRelationship)
                    .filter_by(source_id=concept.id, target_id=target.id, type=rel_type)
                    .first()
                )
                if existing is None:
                    db.add(ConceptRelationship(source_id=concept.id, target_id=target.id, type=rel_type))
        db.commit()
        print(f"Seeded {len(parsed)} concepts from {content_dir}/")
    finally:
        db.close()


if __name__ == "__main__":
    seed_content()
```

- [ ] **Step 5: Run it to verify it passes**

Run: `pytest tests/test_seed_content.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/scripts/seed_content.py backend/tests/test_seed_content.py
git commit -m "feat: add idempotent YAML content seed loader"
```

---

### Task 5: Frontend lesson viewer

**Files:**
- Modify: `frontend/package.json` — add `marked` dependency
- Modify: `frontend/src/lib/api.ts` — add content types and API calls
- Create: `frontend/src/features/lessons/LessonPage.tsx`
- Modify: `frontend/src/App.tsx` — add `/lessons/:slug` route

**Interfaces:**
- Consumes: `api` from `frontend/src/lib/api.ts` (scaffolding+auth plan Task 10), `<ProtectedRoute>` (scaffolding+auth plan Task 11).
- Produces: route `/lessons/:slug` rendering a `ConceptDetail`.

- [ ] **Step 1: Add `marked` and install**

Run:
```bash
cd frontend
npm install marked
```

- [ ] **Step 2: Add content types and API calls to `frontend/src/lib/api.ts`**

Add these exports (after the existing `ApiError` class, before the `api` object):

```typescript
export type ConceptSummary = { slug: string; name: string };

export type LessonContent = {
  concepto: string | null;
  como_funciona: string | null;
  por_que_importa: string | null;
  visualizacion: string | null;
  ejemplo: string | null;
  comandos: string | null;
  errores_frecuentes: string | null;
  regla_mental: string | null;
  perspectiva_ofensiva: string | null;
  perspectiva_defensiva: string | null;
};

export type ConceptDetail = {
  slug: string;
  name: string;
  lesson: LessonContent | null;
  relationships: {
    prerequisites: ConceptSummary[];
    related: ConceptSummary[];
    continues_with: ConceptSummary[];
  };
};

export type DomainSummary = {
  slug: string;
  name: string;
  topics: { slug: string; name: string; concepts: ConceptSummary[] }[];
};
```

Add these methods to the existing `api` object (alongside `login`, `verifyMfa`, etc.):

```typescript
  listDomains: () => request<DomainSummary[]>("/content/domains"),
  getConcept: (slug: string) => request<ConceptDetail>(`/content/concepts/${slug}`),
```

- [ ] **Step 3: Write `frontend/src/features/lessons/LessonPage.tsx`**

```tsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { marked } from "marked";
import { api, ApiError, ConceptDetail, ConceptSummary, LessonContent } from "../../lib/api";

const SECTIONS: { key: keyof LessonContent; title: string }[] = [
  { key: "concepto", title: "Concepto" },
  { key: "como_funciona", title: "Cómo funciona internamente" },
  { key: "por_que_importa", title: "Por qué importa en seguridad" },
  { key: "visualizacion", title: "Visualización" },
  { key: "ejemplo", title: "Ejemplo" },
  { key: "comandos", title: "Comandos" },
  { key: "errores_frecuentes", title: "Errores frecuentes" },
  { key: "regla_mental", title: "🧠 Regla mental" },
  { key: "perspectiva_ofensiva", title: "Perspectiva ofensiva" },
  { key: "perspectiva_defensiva", title: "Perspectiva defensiva" },
];

export function LessonPage() {
  const { slug } = useParams<{ slug: string }>();
  const [concept, setConcept] = useState<ConceptDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    setConcept(null);
    setError(null);
    api
      .getConcept(slug)
      .then(setConcept)
      .catch((err) => {
        setError(err instanceof ApiError && err.status === 404 ? "Lección no encontrada" : "Error al cargar");
      });
  }, [slug]);

  if (error) return <p role="alert">{error}</p>;
  if (!concept) return <p>Cargando…</p>;

  return (
    <article>
      <h1>{concept.name}</h1>
      {SECTIONS.map(({ key, title }) => {
        const content = concept.lesson?.[key];
        if (!content) return null;
        return (
          <section key={key}>
            <h2>{title}</h2>
            <div dangerouslySetInnerHTML={{ __html: marked.parse(content) as string }} />
          </section>
        );
      })}
      <section>
        <h2>Relaciones</h2>
        <RelationList title="Prerequisitos" items={concept.relationships.prerequisites} />
        <RelationList title="Relacionado" items={concept.relationships.related} />
        <RelationList title="Continúa con" items={concept.relationships.continues_with} />
      </section>
    </article>
  );
}

function RelationList({ title, items }: { title: string; items: ConceptSummary[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3>{title}</h3>
      <ul>
        {items.map((c) => (
          <li key={c.slug}>
            <Link to={`/lessons/${c.slug}`}>{c.name}</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Add the route in `frontend/src/App.tsx`**

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./features/auth/useAuth";
import { LoginPage } from "./features/auth/LoginPage";
import { MfaPage } from "./features/auth/MfaPage";
import { ProtectedRoute } from "./features/auth/ProtectedRoute";
import { LessonPage } from "./features/lessons/LessonPage";

function Home() {
  return <h1>Dashboard (placeholder)</h1>;
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/mfa" element={<MfaPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Home />} />
            <Route path="/lessons/:slug" element={<LessonPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

- [ ] **Step 5: Type-check**

Run: `cd frontend && npx tsc -b --noEmit`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/api.ts frontend/src/features/lessons frontend/src/App.tsx
git commit -m "feat: add lesson viewer route with Markdown rendering"
```

---

### Task 6: Load real NET-01–NET-10 content and verify end-to-end

**Files:** none created — this task consumes the `content/networking/*.yaml` files written by the cybersecurity-instructor agent (already on disk) and Task 4's `seed_content.py`.

**Precondition:** the cybersecurity-instructor agent's background task has completed and 10 files exist under `content/networking/`. If not yet done, wait for it before starting this task.

- [ ] **Step 1: Validate the 10 YAML files parse and match the schema**

Run:
```bash
cd backend
.venv/bin/python -c "
import yaml, glob
for path in sorted(glob.glob('../content/networking/*.yaml')):
    with open(path) as f:
        data = yaml.safe_load(f)
    assert 'domain' in data and 'topic' in data and 'concept' in data and 'lesson' in data, path
    assert set(data['concept'].keys()) == {'slug', 'name'}, f'{path} has unexpected concept keys: {data[\"concept\"].keys()}'
    print(path, '->', data['concept']['slug'])
"
```
Expected: 10 lines printed, no assertion errors. If any file has an unexpected `concept` key (e.g. a stray `level` field), fix the YAML file before continuing.

- [ ] **Step 2: Run the seed loader against the dev database**

Run:
```bash
cd backend
PYTHONPATH=. .venv/bin/python -m scripts.seed_content
```
(Or `.venv/bin/python -c "from scripts.seed_content import seed_content; seed_content('../content')"` if the default `content_dir="content"` doesn't resolve from `backend/` — adjust the relative path to point at the repo-root `content/` directory.)

Expected output: `Seeded 10 concepts from .../content/`, no `WARNING: unknown target_slug` lines (if any appear, a `relationships.target_slug` in one YAML file doesn't match another file's `concept.slug` — fix the mismatched slug).

- [ ] **Step 3: Verify via the API**

Restart the backend if it was running with stale code (`pkill -f "uvicorn app.main:app"` then relaunch per the scaffolding+auth plan's Task 12 instructions), then:

```bash
# reuse the cookies.txt from a fresh login+MFA (see scaffolding+auth plan Task 12)
curl -s -b /tmp/cookies.txt http://localhost:8001/api/v1/content/domains | python3 -m json.tool
curl -s -b /tmp/cookies.txt http://localhost:8001/api/v1/content/concepts/net-02-ethernet-mac-arp | python3 -m json.tool
```

Expected: the domains tree shows `networking` with its topics/concepts; the ARP concept response includes a non-null `lesson` and `relationships.prerequisites` containing `net-01-fundamentals`.

- [ ] **Step 4: Verify in the browser**

With the frontend dev server running, open `http://localhost:5174/lessons/net-01-fundamentals` (log in first if the session expired). Confirm the lesson renders with headed sections, then click through a "Continúa con" link to `net-02-ethernet-mac-arp` and confirm its "Prerequisitos" list links back to `net-01-fundamentals`.

- [ ] **Step 5: Run the full backend test suite one more time**

Run: `cd backend && pytest -v`
Expected: all tests from Tasks 1-4 (plus the scaffolding+auth plan's tests) pass.

No commit for this task — it's a content-loading and verification checkpoint. The `content/networking/*.yaml` files themselves should already be committed by (or alongside) the agent that wrote them; if not, commit them here:

```bash
git add content/networking
git commit -m "content: add NET-01 to NET-10 Networking lessons"
```
