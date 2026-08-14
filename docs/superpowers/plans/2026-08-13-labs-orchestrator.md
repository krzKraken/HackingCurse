# Labs Orchestrator Implementation Plan (Sub-plan A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working lab orchestrator — `Laboratory`/`LabInstance` models, a Docker-isolated per-instance network + container lifecycle driven by RQ jobs run by a separate worker process, a real vulnerable TCP service ("FlagBox") to prove it end-to-end, the API layer, and a minimal frontend — with network isolation verified by real integration tests, not just documented.

**Architecture:** The FastAPI API process never imports the `docker` SDK — it only enqueues RQ jobs (by string reference) onto a `labs` queue backed by the existing Redis. A separate `worker` process (own package `backend/worker/`, run via `rq worker labs`) is the only code that talks to the Docker daemon. Each `LabInstance` gets its own isolated (`internal=True`) Docker network and a container with a Docker-assigned ephemeral host port.

**Tech Stack:** Same as prior plans (FastAPI, SQLAlchemy 2.0.52, Alembic, Postgres, Redis, React+Vite) plus `docker` (Docker SDK for Python) and `rq` (Redis Queue) in the backend, and Docker itself as an integration-test dependency — these tests talk to a real Docker daemon, same philosophy as using real Postgres/Redis elsewhere in this project.

## Global Constraints

- Must match `docs/superpowers/specs/2026-08-13-labs-orchestrator-design.md` exactly, including its security controls table (§5) — every control listed there must be backed by a real test, not just present in code.
- The API process's own source code must never `import docker`. Jobs are enqueued by string path (`queue.enqueue("worker.jobs.provision_lab", instance_id)`), which RQ supports without the enqueuing process needing the target function importable.
  - **Caveat, stated explicitly and not hidden:** in this dev environment, API and worker run from the same virtualenv, so the `docker` package is technically installed either way, and the OS user running both processes has the same Docker socket permissions. The code-level separation enforced here is real and meaningful (it's what makes a future split into separate deployable services/users straightforward), but the OS-level privilege separation described in the Fase 0 threat model (§4) is a deployment-topology concern, not something this dev setup enforces today. Note this as a known gap, not something to silently pretend is solved.
- Every `docker_build_context` must resolve inside the repo-root `labs/` directory — verified with a rejection test, not just assumed.
- `destroy_lab` and the security-isolation tests must verify against the real Docker API (`client.containers.list(...)`, `client.networks.list(...)`) that no resources with the instance's label remain — never assume cleanup succeeded.
- No automated frontend tests in this plan (consistent with prior plans).

---

## File Structure

```
backend/
├── requirements.txt              # add docker, rq
├── app/
│   ├── models/
│   │   └── lab.py                 # Laboratory, LaboratoryConcept, LabInstance, LabInstanceStatus
│   └── labs/
│       ├── __init__.py
│       ├── schemas.py
│       ├── service.py
│       └── router.py
├── worker/
│   ├── __init__.py
│   ├── docker_ops.py               # create_isolated_network, run_lab_container, destroy_lab_resources, verify_no_orphans
│   ├── flag.py                     # generate_flag_token
│   ├── jobs.py                     # provision_lab, destroy_lab, reset_lab, sweep_expired_labs
│   └── run_worker.py                # entrypoint: rq worker + sweep loop thread
├── scripts/
│   └── seed_labs.py
├── alembic/
│   ├── env.py                       # import lab models
│   └── versions/0008_create_lab_tables.py
└── tests/
    ├── labs/{__init__.py, test_flagbox_server.py, test_router.py}
    ├── worker/{__init__.py, test_docker_ops.py, test_jobs.py, test_network_isolation.py}
    └── test_seed_labs.py

labs/flagbox/
├── Dockerfile
├── server.py
└── lab.yaml

frontend/src/
├── lib/api.ts                       # add Laboratory/LabInstance types + calls
├── features/labs/{LabsPage.tsx, LabInstancePage.tsx}
└── App.tsx                          # add /labs and /labs/:labId routes
```

---

### Task 1: `Laboratory`/`LabInstance` models + migration

**Files:**
- Create: `backend/app/models/lab.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0008_create_lab_tables.py`

**Interfaces:**
- Consumes: `app.db.Base`, `app.models.content.Concept`, `app.models.user.User`.
- Produces: `Laboratory`, `LaboratoryConcept`, `LabInstance`, `LabInstanceStatus` (enum: `requested`, `provisioning`, `running`, `stopped`, `destroyed`, `expired`, `failed`).

- [ ] **Step 1: Write `backend/app/models/lab.py`**

```python
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class LabInstanceStatus(str, enum.Enum):
    requested = "requested"
    provisioning = "provisioning"
    running = "running"
    stopped = "stopped"
    destroyed = "destroyed"
    expired = "expired"
    failed = "failed"


class Laboratory(Base):
    __tablename__ = "laboratories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_estimate_min: Mapped[int] = mapped_column(Integer, nullable=False)
    docker_build_context: Mapped[str] = mapped_column(String(255), nullable=False)
    hints: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cpu_limit: Mapped[str] = mapped_column(String(16), nullable=False)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    max_lifetime_min: Mapped[int] = mapped_column(Integer, nullable=False)
    cleanup_remove_volumes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LaboratoryConcept(Base):
    __tablename__ = "laboratory_concepts"

    laboratory_id: Mapped[str] = mapped_column(String(64), ForeignKey("laboratories.id"), primary_key=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("concepts.id"), primary_key=True)


class LabInstance(Base):
    __tablename__ = "lab_instances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    laboratory_id: Mapped[str] = mapped_column(String(64), ForeignKey("laboratories.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[LabInstanceStatus] = mapped_column(
        SAEnum(LabInstanceStatus, name="lab_instance_status"),
        nullable=False,
        default=LabInstanceStatus.requested,
    )
    container_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    network_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    host_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    relay_pid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    context_seed: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    solved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    solved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    destroyed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    laboratory: Mapped["Laboratory"] = relationship()
```

- [ ] **Step 2: Register with Alembic**

In `backend/alembic/env.py`, add after the `focus` import:
```python
from app.models import lab  # noqa: F401 — registers lab models with Base.metadata
```

- [ ] **Step 3: Generate and apply the migration**

Run:
```bash
cd backend
alembic revision --autogenerate -m "create lab tables"
mv alembic/versions/<generated_hash>_create_lab_tables.py alembic/versions/0008_create_lab_tables.py
alembic upgrade head
```

- [ ] **Step 4: Verify**

Run: `PGPASSWORD=cyberlearn psql -h localhost -p 55432 -U cyberlearn -d cyberlearn -c "\dt"`
Expected: `laboratories`, `laboratory_concepts`, `lab_instances` present.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/lab.py backend/alembic/env.py backend/alembic/versions/0008_create_lab_tables.py
git commit -m "feat: add Laboratory and LabInstance models"
```

---

### Task 2: FlagBox — the vulnerable lab service

**Files:**
- Create: `labs/flagbox/server.py`
- Create: `labs/flagbox/Dockerfile`
- Create: `labs/flagbox/lab.yaml`
- Test: `backend/tests/labs/__init__.py`
- Test: `backend/tests/labs/test_flagbox_server.py`

**Interfaces:**
- Produces: a standalone TCP service (no dependency on the rest of the backend) — consumed by Task 4/5's Docker orchestration tests and Task 10's manual verification.

This task is TDD against the **protocol logic directly** (via `asyncio`, no Docker needed) — proves the IDOR bug is real before we ever containerize it.

- [ ] **Step 1: Write `labs/flagbox/server.py`**

```python
import asyncio
import os

FLAG_TOKEN = os.environ.get("FLAG_TOKEN", "FLAG{dev_placeholder}")

USERS: dict[str, int] = {}
NOTES: dict[int, dict[str, str]] = {
    0: {"owner": "admin", "content": FLAG_TOKEN},
    1: {"owner": "alice", "content": "Reunion movida a las 3pm."},
    2: {"owner": "bob", "content": "Recordar renovar el certificado TLS."},
}

_next_user_id = 1


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    global _next_user_id
    session: dict[str, str | int | None] = {"username": None, "user_id": None}

    writer.write(b"FLAGBOX v1\r\n")
    await writer.drain()

    while True:
        line = await reader.readline()
        if not line:
            break
        command = line.decode("utf-8", errors="replace").strip()
        if not command:
            continue

        parts = command.split(" ", 1)
        verb = parts[0].upper()
        arg = parts[1] if len(parts) > 1 else ""

        if verb == "LOGIN":
            username = arg.strip() or "anonymous"
            if username not in USERS:
                USERS[username] = _next_user_id
                _next_user_id += 1
            session["username"] = username
            session["user_id"] = USERS[username]
            writer.write(f"OK session={session['user_id']}\r\n".encode())

        elif verb == "WHOAMI":
            if session["username"] is None:
                writer.write(b"ERR not logged in\r\n")
            else:
                writer.write(f"USER {session['username']} id={session['user_id']}\r\n".encode())

        elif verb == "GET":
            if session["username"] is None:
                writer.write(b"ERR not logged in\r\n")
            else:
                try:
                    note_id = int(arg.strip())
                except ValueError:
                    writer.write(b"ERR invalid id\r\n")
                else:
                    # VULNERABILITY: no check that note_id belongs to the
                    # logged-in session — classic IDOR at the protocol level.
                    note = NOTES.get(note_id)
                    if note is None:
                        writer.write(b"ERR not found\r\n")
                    else:
                        writer.write(f"NOTE {note['content']}\r\n".encode())

        else:
            writer.write(b"ERR unknown command\r\n")

        await writer.drain()

    writer.close()


async def main() -> None:
    server = await asyncio.start_server(handle_client, "0.0.0.0", 9000)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Write `labs/flagbox/Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY server.py .
EXPOSE 9000
CMD ["python", "server.py"]
```

- [ ] **Step 3: Write `labs/flagbox/lab.yaml`**

```yaml
id: net-tcp-flagbox-001
title: "FlagBox"
type: black_box
difficulty: beginner
duration_estimate_min: 30
concept_slugs: [net-05-tcp-udp, net-09-packet-analysis]
docker_build_context: labs/flagbox
cpu_limit: "0.5"
memory_limit_mb: 128
max_lifetime_min: 120
cleanup_remove_volumes: true
hints:
  - level: 1
    text: "Conéctate al servicio con netcat y observa el banner. ¿Qué comandos acepta?"
  - level: 2
    text: "Captura el tráfico con Wireshark mientras interactúas — es texto plano por línea."
  - level: 3
    text: "Prueba el comando GET con distintos IDs. ¿El servicio valida que el ID te pertenece?"
  - level: 4
    text: "GET 0 es el registro más antiguo del sistema — ¿de quién podría ser?"
```

- [ ] **Step 4: Write the test (protocol-level, no Docker)**

`backend/tests/labs/__init__.py`: empty file.

`backend/tests/labs/test_flagbox_server.py`:
```python
import importlib.util
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio

FLAGBOX_DIR = Path(__file__).resolve().parents[3] / "labs" / "flagbox"
_spec = importlib.util.spec_from_file_location("flagbox_server", FLAGBOX_DIR / "server.py")
flagbox_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(flagbox_server)


@pytest_asyncio.fixture
async def flagbox_client():
    flagbox_server.FLAG_TOKEN = "FLAG{test_token_123}"
    flagbox_server.NOTES[0]["content"] = flagbox_server.FLAG_TOKEN
    flagbox_server.USERS.clear()
    flagbox_server._next_user_id = 1

    import asyncio

    server = await asyncio.start_server(flagbox_server.handle_client, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    serve_task = asyncio.ensure_future(server.serve_forever())
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        yield reader, writer
    finally:
        writer.close()
        serve_task.cancel()
        server.close()


@pytest.mark.asyncio
async def test_banner_on_connect(flagbox_client):
    reader, _writer = flagbox_client
    banner = await reader.readline()
    assert banner == b"FLAGBOX v1\r\n"


@pytest.mark.asyncio
async def test_login_and_whoami(flagbox_client):
    reader, writer = flagbox_client
    await reader.readline()
    writer.write(b"LOGIN alice\r\n")
    await writer.drain()
    resp = await reader.readline()
    assert resp.startswith(b"OK session=")

    writer.write(b"WHOAMI\r\n")
    await writer.drain()
    resp = await reader.readline()
    assert resp == b"USER alice id=1\r\n"


@pytest.mark.asyncio
async def test_get_without_login_fails(flagbox_client):
    reader, writer = flagbox_client
    await reader.readline()
    writer.write(b"GET 0\r\n")
    await writer.drain()
    resp = await reader.readline()
    assert resp == b"ERR not logged in\r\n"


@pytest.mark.asyncio
async def test_idor_get_0_leaks_flag_regardless_of_owner(flagbox_client):
    reader, writer = flagbox_client
    await reader.readline()
    writer.write(b"LOGIN mallory\r\n")
    await writer.drain()
    await reader.readline()

    writer.write(b"GET 0\r\n")
    await writer.drain()
    resp = await reader.readline()
    assert resp == b"NOTE FLAG{test_token_123}\r\n"


@pytest.mark.asyncio
async def test_get_unknown_id_returns_not_found(flagbox_client):
    reader, writer = flagbox_client
    await reader.readline()
    writer.write(b"LOGIN alice\r\n")
    await writer.drain()
    await reader.readline()

    writer.write(b"GET 999\r\n")
    await writer.drain()
    resp = await reader.readline()
    assert resp == b"ERR not found\r\n"
```

- [ ] **Step 5: Run it to verify it passes**

Run: `cd backend && pytest tests/labs/test_flagbox_server.py -v`
Expected: PASS (5 tests) — this proves the IDOR bug (`GET 0` leaks the flag for any logged-in user) is real, before any Docker involvement.

- [ ] **Step 6: Manual smoke test with real netcat**

Run:
```bash
cd labs/flagbox
FLAG_TOKEN="FLAG{manual_test}" python3 server.py &
sleep 1
printf 'LOGIN test\r\nGET 0\r\n' | nc -q1 localhost 9000
kill %1
```
Expected output includes `NOTE FLAG{manual_test}`.

- [ ] **Step 7: Commit**

```bash
git add labs/flagbox backend/tests/labs
git commit -m "feat: add FlagBox vulnerable TCP lab service"
```

---

### Task 3: `seed_labs.py` — idempotent lab catalog loader

**Files:**
- Create: `backend/scripts/seed_labs.py`
- Test: `backend/tests/test_seed_labs.py`

**Interfaces:**
- Consumes: `app.db.SessionLocal`, `app.models.content.Concept`, `app.models.lab.Laboratory`/`LaboratoryConcept`.
- Produces: `scripts.seed_labs.seed_labs(labs_dir: str = "labs") -> None` — used in Task 10.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_seed_labs.py`:
```python
import os
import tempfile

import yaml

from app.models.content import Concept, Domain, Topic
from app.models.lab import Laboratory, LaboratoryConcept
from scripts.seed_labs import seed_labs

LAB_YAML = {
    "id": "test-lab-001",
    "title": "Test Lab",
    "type": "black_box",
    "difficulty": "beginner",
    "duration_estimate_min": 15,
    "concept_slugs": ["net-01"],
    "docker_build_context": "labs/test-lab",
    "cpu_limit": "0.5",
    "memory_limit_mb": 128,
    "max_lifetime_min": 60,
    "cleanup_remove_volumes": True,
    "hints": [{"level": 1, "text": "hint uno"}],
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


def _write_labs_dir(tmpdir, data):
    lab_dir = os.path.join(tmpdir, "labs", "test-lab")
    os.makedirs(lab_dir, exist_ok=True)
    with open(os.path.join(lab_dir, "lab.yaml"), "w") as f:
        yaml.safe_dump(data, f)
    return os.path.join(tmpdir, "labs")


def test_seed_labs_creates_laboratory_and_concept_links(db_session):
    _seed_concept(db_session)
    with tempfile.TemporaryDirectory() as tmpdir:
        labs_dir = _write_labs_dir(tmpdir, LAB_YAML)
        seed_labs(labs_dir)

    lab = db_session.query(Laboratory).filter_by(id="test-lab-001").one()
    assert lab.title == "Test Lab"
    assert lab.hints == [{"level": 1, "text": "hint uno"}]
    assert db_session.query(LaboratoryConcept).filter_by(laboratory_id=lab.id).count() == 1


def test_seed_labs_is_idempotent(db_session):
    _seed_concept(db_session)
    with tempfile.TemporaryDirectory() as tmpdir:
        labs_dir = _write_labs_dir(tmpdir, LAB_YAML)
        seed_labs(labs_dir)
        seed_labs(labs_dir)

    assert db_session.query(Laboratory).filter_by(id="test-lab-001").count() == 1
    assert db_session.query(LaboratoryConcept).filter_by(laboratory_id="test-lab-001").count() == 1
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && pytest tests/test_seed_labs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.seed_labs'`

- [ ] **Step 3: Write `backend/scripts/seed_labs.py`**

```python
import glob

import yaml
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.content import Concept
from app.models.lab import Laboratory, LaboratoryConcept


def _upsert_laboratory(db: Session, data: dict) -> Laboratory:
    lab = db.query(Laboratory).filter(Laboratory.id == data["id"]).first()
    if lab is None:
        lab = Laboratory(id=data["id"])
        db.add(lab)

    lab.title = data["title"]
    lab.type = data["type"]
    lab.difficulty = data["difficulty"]
    lab.duration_estimate_min = data["duration_estimate_min"]
    lab.docker_build_context = data["docker_build_context"]
    lab.hints = data.get("hints", [])
    lab.cpu_limit = data["cpu_limit"]
    lab.memory_limit_mb = data["memory_limit_mb"]
    lab.max_lifetime_min = data["max_lifetime_min"]
    lab.cleanup_remove_volumes = data.get("cleanup_remove_volumes", True)
    db.flush()
    return lab


def seed_labs(labs_dir: str = "labs") -> None:
    db = SessionLocal()
    try:
        paths = sorted(glob.glob(f"{labs_dir}/**/lab.yaml", recursive=True))
        for path in paths:
            with open(path) as f:
                data = yaml.safe_load(f)
            lab = _upsert_laboratory(db, data)

            db.query(LaboratoryConcept).filter(LaboratoryConcept.laboratory_id == lab.id).delete()
            for slug in data.get("concept_slugs", []):
                concept = db.query(Concept).filter(Concept.slug == slug).first()
                if concept is None:
                    print(f"WARNING: unknown concept_slug '{slug}' in {path}")
                    continue
                db.add(LaboratoryConcept(laboratory_id=lab.id, concept_id=concept.id))
        db.commit()
        print(f"Seeded {len(paths)} laboratories from {labs_dir}/")
    finally:
        db.close()


if __name__ == "__main__":
    seed_labs()
```

- [ ] **Step 4: Run it to verify it passes**

Run: `pytest tests/test_seed_labs.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_labs.py backend/tests/test_seed_labs.py
git commit -m "feat: add idempotent lab catalog seed loader"
```

---

### Task 4: Docker orchestration primitives (`worker/docker_ops.py`)

**Files:**
- Modify: `backend/requirements.txt` — add `docker==7.1.0`
- Create: `backend/worker/__init__.py`
- Create: `backend/worker/docker_ops.py`
- Test: `backend/tests/worker/__init__.py`
- Test: `backend/tests/worker/test_docker_ops.py`

**Interfaces:**
- Produces: `get_client() -> docker.DockerClient`, `resolve_build_context(docker_build_context: str) -> Path`, `create_isolated_network(instance_id: str) -> str`, `run_lab_container(instance_id, docker_build_context, network_id, target_port, env, cpu_limit, memory_limit_mb) -> tuple[str, str]` (returns `container_id, container_ip` — see correction below), `start_port_relay(instance_id, container_ip, target_port) -> tuple[int, int]` (returns `host_port, relay_pid`), `stop_port_relay(relay_pid) -> None`, `destroy_lab_resources(container_id, network_id, relay_pid=None) -> None`, `verify_no_orphans(instance_id: str) -> bool`, and `LABEL_KEY` — consumed by Task 5's jobs and Task 8's security tests.

**These are real integration tests against the Docker daemon** — no mocking, same philosophy as the rest of this project's tests against real Postgres/Redis.

**Design correction, discovered by these very tests:** the original plan (and design spec's first draft) called for publishing the container's port directly via Docker (`ports={f"{target_port}/tcp": None}`). Running that against a real Docker daemon fails with `403 Forbidden` — **Docker refuses to publish ports on a container whose only network is `internal=True`**, since an internal network has no external connectivity by definition. The fix: the Docker **host** can always reach into a bridge network it created (it owns the bridge interface), even when that network is `internal=True` — only the *container's* outbound route is blocked, not the host's inbound one. So instead of Docker-native port publishing, `run_lab_container` returns the container's IP on the isolated network, and a separate `start_port_relay` launches a tiny host-side `asyncio` TCP relay (`worker/relay.py`, its own file, no dependencies) as an independent subprocess that forwards `host_port → container_ip:target_port`. Its PID is tracked (`LabInstance.relay_pid`, added via a follow-up migration `0009_add_relay_pid_to_lab_instances.py` after Task 1) so `destroy_lab` can terminate it. This is exactly the kind of thing real-Docker integration tests are for — a mocked test would never have caught it.

- [ ] **Step 1: Add `docker` to requirements and install**

In `backend/requirements.txt`, add: `docker==7.1.0`

Run:
```bash
cd backend
.venv/bin/pip install -r requirements.txt
```
If this fails due to a Python 3.14 compatibility issue (same class of problem hit with SQLAlchemy in the scaffolding+auth plan), bump to the latest available version with `.venv/bin/pip index versions docker` and use that instead — document the change in the commit message like the SQLAlchemy bump was documented.

- [ ] **Step 2: Write the failing test**

`backend/tests/worker/__init__.py`: empty file.

`backend/tests/worker/test_docker_ops.py`:
```python
import socket
import time

import pytest


@pytest.fixture
def temp_build_context(tmp_path, monkeypatch):
    from worker import docker_ops

    lab_dir = tmp_path / "labs" / "echo-test"
    lab_dir.mkdir(parents=True)
    (lab_dir / "server.py").write_text(
        "import socket\n"
        "s = socket.socket()\n"
        "s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
        "s.bind(('0.0.0.0', 9000))\n"
        "s.listen(1)\n"
        "while True:\n"
        "    conn, _ = s.accept()\n"
        "    conn.sendall(b'hello\\n')\n"
        "    conn.close()\n"
    )
    (lab_dir / "Dockerfile").write_text(
        'FROM python:3.12-slim\nWORKDIR /app\nCOPY server.py .\nCMD ["python3", "server.py"]\n'
    )
    monkeypatch.setattr(docker_ops, "LABS_ROOT", tmp_path / "labs")
    return "labs/echo-test"


def test_resolve_build_context_rejects_outside_allowlist(temp_build_context):
    from worker import docker_ops

    with pytest.raises(ValueError):
        docker_ops.resolve_build_context("../../etc")


def test_create_and_destroy_isolated_network():
    from worker import docker_ops

    network_id = docker_ops.create_isolated_network("test-instance-1")
    try:
        client = docker_ops.get_client()
        network = client.networks.get(network_id)
        assert network.attrs["Internal"] is True
    finally:
        docker_ops.destroy_lab_resources(None, network_id)
    assert docker_ops.verify_no_orphans("test-instance-1")


def test_run_lab_container_and_relay_makes_it_reachable_from_host(temp_build_context):
    from worker import docker_ops

    instance_id = "test-instance-2"
    network_id = docker_ops.create_isolated_network(instance_id)
    container_id = None
    relay_pid = None
    try:
        container_id, container_ip = docker_ops.run_lab_container(
            instance_id, temp_build_context, network_id, 9000, {}, "0.5", 128
        )
        time.sleep(1)
        host_port, relay_pid = docker_ops.start_port_relay(instance_id, container_ip, 9000)
        time.sleep(1)
        with socket.create_connection(("127.0.0.1", host_port), timeout=5) as sock:
            data = sock.recv(1024)
        assert data == b"hello\n"
    finally:
        docker_ops.destroy_lab_resources(container_id, network_id, relay_pid)
    assert docker_ops.verify_no_orphans(instance_id)
```

- [ ] **Step 3: Run it to verify it fails**

Run: `pytest tests/worker/test_docker_ops.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'worker.docker_ops'`

- [ ] **Step 4: Write `backend/worker/__init__.py`** (empty file)

- [ ] **Step 5: Write `backend/worker/relay.py`**

```python
import asyncio
import sys


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        writer.close()


async def _handle(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    target_host: str,
    target_port: int,
) -> None:
    try:
        remote_reader, remote_writer = await asyncio.open_connection(target_host, target_port)
    except OSError:
        client_writer.close()
        return
    await asyncio.gather(
        _pipe(client_reader, remote_writer),
        _pipe(remote_reader, client_writer),
    )


async def main(listen_port: int, target_host: str, target_port: int) -> None:
    server = await asyncio.start_server(
        lambda r, w: _handle(r, w, target_host, target_port), "0.0.0.0", listen_port
    )
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    # argv: listen_port target_host target_port instance_id
    # instance_id is accepted only so the process is identifiable in `ps`
    # output for manual debugging — it plays no role in the relay logic.
    listen_port_arg = int(sys.argv[1])
    target_host_arg = sys.argv[2]
    target_port_arg = int(sys.argv[3])
    asyncio.run(main(listen_port_arg, target_host_arg, target_port_arg))
```

- [ ] **Step 6: Write `backend/worker/docker_ops.py`**

```python
import os
import pathlib
import signal
import socket
import subprocess
import sys

import docker
from docker.errors import NotFound

LABEL_KEY = "cyberlearn_instance_id"
LABS_ROOT = pathlib.Path(__file__).resolve().parents[2] / "labs"

_client = None


def get_client() -> docker.DockerClient:
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def resolve_build_context(docker_build_context: str) -> pathlib.Path:
    resolved = (LABS_ROOT.parent / docker_build_context).resolve()
    labs_root_resolved = LABS_ROOT.resolve()
    if resolved != labs_root_resolved and labs_root_resolved not in resolved.parents:
        raise ValueError(f"docker_build_context '{docker_build_context}' is outside the labs/ allowlist")
    if not resolved.is_dir():
        raise ValueError(f"docker_build_context '{docker_build_context}' does not exist")
    return resolved


def create_isolated_network(instance_id: str) -> str:
    client = get_client()
    network = client.networks.create(
        name=f"cyberlearn-lab-{instance_id}",
        driver="bridge",
        internal=True,
        labels={LABEL_KEY: instance_id},
    )
    return network.id


def run_lab_container(
    instance_id: str,
    docker_build_context: str,
    network_id: str,
    target_port: int,
    env: dict,
    cpu_limit: str,
    memory_limit_mb: int,
) -> tuple[str, str]:
    """Builds and runs the lab container on the isolated network.

    Returns (container_id, container_ip). Docker forbids publishing ports
    on a container whose only network is `internal=True` — see the
    correction note above this task. Use `start_port_relay` to make it
    reachable from the host.
    """
    client = get_client()
    build_path = resolve_build_context(docker_build_context)
    image, _logs = client.images.build(path=str(build_path), tag=f"cyberlearn-lab-{instance_id}", rm=True)

    container = client.containers.run(
        image.id,
        detach=True,
        network=network_id,
        environment=env,
        labels={LABEL_KEY: instance_id},
        mem_limit=f"{memory_limit_mb}m",
        nano_cpus=int(float(cpu_limit) * 1_000_000_000),
    )
    container.reload()
    networks = container.attrs["NetworkSettings"]["Networks"]
    container_ip = next(iter(networks.values()))["IPAddress"]
    return container.id, container_ip


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 0))
        return s.getsockname()[1]


def start_port_relay(instance_id: str, container_ip: str, target_port: int) -> tuple[int, int]:
    """Starts a host-side TCP relay so a container on an `internal=True`
    network is still reachable from outside. Returns (host_port, relay_pid).
    """
    host_port = _pick_free_port()
    relay_module = pathlib.Path(__file__).resolve().parent / "relay.py"
    process = subprocess.Popen(
        [sys.executable, str(relay_module), str(host_port), container_ip, str(target_port), instance_id],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return host_port, process.pid


def stop_port_relay(relay_pid: int | None) -> None:
    if relay_pid is None:
        return
    try:
        os.kill(relay_pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def destroy_lab_resources(
    container_id: str | None, network_id: str | None, relay_pid: int | None = None
) -> None:
    stop_port_relay(relay_pid)
    client = get_client()
    if container_id:
        try:
            container = client.containers.get(container_id)
            container.remove(force=True)
        except NotFound:
            pass
    if network_id:
        try:
            network = client.networks.get(network_id)
            network.remove()
        except NotFound:
            pass


def verify_no_orphans(instance_id: str) -> bool:
    client = get_client()
    containers = client.containers.list(all=True, filters={"label": f"{LABEL_KEY}={instance_id}"})
    networks = client.networks.list(filters={"label": f"{LABEL_KEY}={instance_id}"})
    return not containers and not networks
```

- [ ] **Step 7: Run it to verify it passes**

Run: `pytest tests/worker/test_docker_ops.py -v`
Expected: PASS (3 tests). This will take longer than other test files (~10-30s) because it builds a real Docker image — that's expected.

- [ ] **Step 8: Add `relay_pid` to `LabInstance` and commit**

`internal=True` networks blocking port publishing (discovered above) wasn't known when Task 1's model was written, so `relay_pid` needs a follow-up migration:

```bash
cd backend
# add `relay_pid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)` to LabInstance in app/models/lab.py
alembic revision --autogenerate -m "add relay_pid to lab_instances"
mv alembic/versions/<generated_hash>_add_relay_pid_to_lab_instances.py alembic/versions/0009_add_relay_pid_to_lab_instances.py
alembic upgrade head
```

```bash
git add backend/requirements.txt backend/worker/__init__.py backend/worker/relay.py backend/worker/docker_ops.py backend/tests/worker/__init__.py backend/tests/worker/test_docker_ops.py backend/app/models/lab.py backend/alembic/versions/0009_add_relay_pid_to_lab_instances.py
git commit -m "feat: add Docker orchestration primitives (isolated network, container lifecycle, host-side relay)"
```

---

### Task 5: RQ jobs (`worker/jobs.py`)

**Files:**
- Modify: `backend/requirements.txt` — add `rq==2.1.0`
- Create: `backend/worker/flag.py`
- Create: `backend/worker/jobs.py`
- Test: `backend/tests/worker/test_jobs.py`

**Interfaces:**
- Consumes: `worker.docker_ops.*` (Task 4), `app.models.lab.*` (Task 1), `app.db.SessionLocal`.
- Produces: `provision_lab(instance_id: str) -> None`, `destroy_lab(instance_id: str) -> None`, `reset_lab(instance_id: str) -> None`, `sweep_expired_labs() -> None` — consumed by Task 7's router (enqueued by string reference) and Task 6's worker entrypoint.

- [ ] **Step 1: Add `rq` to requirements and install**

In `backend/requirements.txt`, add: `rq==2.1.0`

Run: `cd backend && .venv/bin/pip install -r requirements.txt` (adjust version on a Python 3.14 compat failure, same as Task 4 Step 1).

- [ ] **Step 2: Write `backend/worker/flag.py`**

```python
import secrets


def generate_flag_token() -> str:
    return f"FLAG{{{secrets.token_hex(8)}}}"
```

- [ ] **Step 3: Write the failing test**

`backend/tests/worker/test_jobs.py`:
```python
import socket
import time
from datetime import datetime, timezone

from app.models.lab import Laboratory, LabInstance, LabInstanceStatus
from app.models.user import User
from worker import docker_ops, jobs


def _seed_user(db):
    user = User(username="owner", password_hash="x", totp_secret="x")
    db.add(user)
    db.commit()
    return user


def _seed_flagbox_laboratory(db):
    lab = Laboratory(
        id="net-tcp-flagbox-001",
        title="FlagBox",
        type="black_box",
        difficulty="beginner",
        duration_estimate_min=30,
        docker_build_context="labs/flagbox",
        hints=[],
        cpu_limit="0.5",
        memory_limit_mb=128,
        max_lifetime_min=120,
        cleanup_remove_volumes=True,
    )
    db.add(lab)
    db.commit()
    return lab


def _seed_instance(db, lab, user):
    instance = LabInstance(
        laboratory_id=lab.id,
        user_id=user.id,
        status=LabInstanceStatus.requested,
        context_seed={},
        requested_at=datetime.now(timezone.utc),
    )
    db.add(instance)
    db.commit()
    return instance


def test_provision_lab_creates_running_instance_reachable_over_tcp(db_session):
    user = _seed_user(db_session)
    lab = _seed_flagbox_laboratory(db_session)
    instance = _seed_instance(db_session, lab, user)

    try:
        jobs.provision_lab(str(instance.id))
        db_session.refresh(instance)

        assert instance.status == LabInstanceStatus.running
        assert instance.host_port is not None
        assert instance.relay_pid is not None
        assert "flag_token" in instance.context_seed

        time.sleep(1)
        with socket.create_connection(("127.0.0.1", instance.host_port), timeout=5) as sock:
            banner = sock.recv(1024)
        assert banner == b"FLAGBOX v1\r\n"
    finally:
        jobs.destroy_lab(str(instance.id))

    db_session.refresh(instance)
    assert instance.status == LabInstanceStatus.destroyed
    assert docker_ops.verify_no_orphans(str(instance.id))


def test_reset_lab_generates_new_flag_token(db_session):
    user = _seed_user(db_session)
    lab = _seed_flagbox_laboratory(db_session)
    instance = _seed_instance(db_session, lab, user)

    jobs.provision_lab(str(instance.id))
    db_session.refresh(instance)
    first_token = instance.context_seed["flag_token"]

    try:
        jobs.reset_lab(str(instance.id))
        db_session.refresh(instance)
        assert instance.context_seed["flag_token"] != first_token
        assert instance.status == LabInstanceStatus.running
    finally:
        jobs.destroy_lab(str(instance.id))


def test_sweep_expired_labs_destroys_instances_past_max_lifetime(db_session):
    user = _seed_user(db_session)
    lab = _seed_flagbox_laboratory(db_session)
    lab.max_lifetime_min = 0
    db_session.commit()
    instance = _seed_instance(db_session, lab, user)

    jobs.provision_lab(str(instance.id))
    db_session.refresh(instance)
    assert instance.status == LabInstanceStatus.running

    time.sleep(1)
    jobs.sweep_expired_labs()
    db_session.refresh(instance)

    assert instance.status == LabInstanceStatus.expired
    assert docker_ops.verify_no_orphans(str(instance.id))
```

- [ ] **Step 4: Run it to verify it fails**

Run: `pytest tests/worker/test_jobs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'worker.jobs'`

- [ ] **Step 5: Write `backend/worker/jobs.py`**

```python
from datetime import datetime, timezone

from app.db import SessionLocal

# LabInstance/LaboratoryConcept reference users.id/concepts.id by string FK.
# SQLAlchemy configures mappers lazily and needs every referenced model
# module imported somewhere in this process before the first flush/commit,
# or it raises NoReferencedTableError. The API process gets these for free
# via app.main's router imports; the worker process does not (it never
# imports app.main), so they must be imported explicitly here. This was
# only caught by actually running the worker as its own process in Task 10
# — the test suite never hit it because pytest's conftest imports the full
# app (and therefore every model) into the same process regardless.
from app.models import content, user  # noqa: F401
from app.models.lab import Laboratory, LabInstance, LabInstanceStatus
from worker import docker_ops
from worker.flag import generate_flag_token

TARGET_PORT = 9000


def provision_lab(instance_id: str) -> None:
    db = SessionLocal()
    try:
        instance = db.query(LabInstance).filter(LabInstance.id == instance_id).first()
        if instance is None:
            return
        laboratory = db.query(Laboratory).filter(Laboratory.id == instance.laboratory_id).first()

        instance.status = LabInstanceStatus.provisioning
        db.commit()

        flag_token = generate_flag_token()
        instance.context_seed = {"flag_token": flag_token}

        network_id = docker_ops.create_isolated_network(str(instance.id))
        container_id, container_ip = docker_ops.run_lab_container(
            str(instance.id),
            laboratory.docker_build_context,
            network_id,
            TARGET_PORT,
            {"FLAG_TOKEN": flag_token},
            laboratory.cpu_limit,
            laboratory.memory_limit_mb,
        )
        host_port, relay_pid = docker_ops.start_port_relay(str(instance.id), container_ip, TARGET_PORT)

        instance.network_id = network_id
        instance.container_id = container_id
        instance.host_port = host_port
        instance.relay_pid = relay_pid
        instance.status = LabInstanceStatus.running
        instance.started_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        failed = db.query(LabInstance).filter(LabInstance.id == instance_id).first()
        if failed is not None:
            failed.status = LabInstanceStatus.failed
            db.commit()
        raise
    finally:
        db.close()


def destroy_lab(instance_id: str) -> None:
    db = SessionLocal()
    try:
        instance = db.query(LabInstance).filter(LabInstance.id == instance_id).first()
        if instance is None:
            return
        docker_ops.destroy_lab_resources(instance.container_id, instance.network_id, instance.relay_pid)
        instance.status = LabInstanceStatus.destroyed
        instance.destroyed_at = datetime.now(timezone.utc)
        instance.container_id = None
        instance.network_id = None
        instance.relay_pid = None
        db.commit()
    finally:
        db.close()


def reset_lab(instance_id: str) -> None:
    destroy_lab(instance_id)
    db = SessionLocal()
    try:
        instance = db.query(LabInstance).filter(LabInstance.id == instance_id).first()
        if instance is not None:
            instance.status = LabInstanceStatus.requested
            instance.solved = False
            instance.solved_at = None
            instance.hints_used = 0
            db.commit()
    finally:
        db.close()
    provision_lab(instance_id)


def sweep_expired_labs() -> None:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        running = db.query(LabInstance).filter(LabInstance.status == LabInstanceStatus.running).all()
        for instance in running:
            if instance.started_at is None:
                continue
            laboratory = db.query(Laboratory).filter(Laboratory.id == instance.laboratory_id).first()
            elapsed_min = (now - instance.started_at).total_seconds() / 60
            if elapsed_min > laboratory.max_lifetime_min:
                docker_ops.destroy_lab_resources(instance.container_id, instance.network_id, instance.relay_pid)
                instance.status = LabInstanceStatus.expired
                instance.destroyed_at = now
                instance.container_id = None
                instance.network_id = None
                instance.relay_pid = None
        db.commit()
    finally:
        db.close()
```

- [ ] **Step 6: Run it to verify it passes**

Run: `pytest tests/worker/test_jobs.py -v`

**If you hit `psycopg.errors.FeatureNotSupported: cached plan must not change result type`:** this is a pre-existing test-infrastructure issue, not a bug in the code above — psycopg3 auto-prepares statements after a few executions on a pooled connection, and this test file is the first one to run enough sequential queries (via `worker`'s own `SessionLocal()` calls across provision/destroy/reset/sweep) to trigger it against a connection whose pooled peer had a table dropped/recreated by the `tests/conftest.py` fixture in between. Fix `backend/app/db.py` by disabling server-side prepare:

```python
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"prepare_threshold": None},
)
```

Then re-run. Expected: PASS (3 tests). These build and run the real FlagBox image — slower than typical tests, that's expected.

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/worker/flag.py backend/worker/jobs.py backend/tests/worker/test_jobs.py backend/app/db.py
git commit -m "feat: add lab provisioning/destroy/reset/expiry-sweep jobs"
```

---

### Task 6: Worker entrypoint

**Files:**
- Create: `backend/worker/run_worker.py`

**Interfaces:**
- Consumes: `worker.jobs.sweep_expired_labs` (Task 5), `app.config.settings.redis_url`.
- Produces: a runnable entrypoint (`python -m worker.run_worker`), verified manually in Task 10 — no automated test (thin glue script, same category as `scripts/create_owner.py`).

- [ ] **Step 1: Write `backend/worker/run_worker.py`**

```python
import threading
import time

from redis import Redis
from rq import Queue, Worker

from app.config import settings
from worker.jobs import sweep_expired_labs

QUEUE_NAME = "labs"
SWEEP_INTERVAL_SECONDS = 60


def run_sweep_loop() -> None:
    while True:
        try:
            sweep_expired_labs()
        except Exception as exc:  # noqa: BLE001 — defensive: never let the sweep loop die silently
            print(f"sweep_expired_labs failed: {exc}")
        time.sleep(SWEEP_INTERVAL_SECONDS)


def main() -> None:
    threading.Thread(target=run_sweep_loop, daemon=True).start()

    redis_conn = Redis.from_url(settings.redis_url)
    queue = Queue(QUEUE_NAME, connection=redis_conn)
    worker = Worker([queue], connection=redis_conn)
    worker.work()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it starts cleanly**

Run (from `backend/`, with Redis already up):
```bash
timeout 5 .venv/bin/python -m worker.run_worker || true
```
Expected: log lines showing the RQ worker started and listening on the `labs` queue, no import errors. (`timeout 5` just stops it after 5s since `worker.work()` runs forever — this step only confirms it boots.)

- [ ] **Step 3: Commit**

```bash
git add backend/worker/run_worker.py
git commit -m "feat: add worker entrypoint with periodic expiry sweep"
```

---

### Task 7: Labs API

**Files:**
- Create: `backend/app/labs/__init__.py`
- Create: `backend/app/labs/schemas.py`
- Create: `backend/app/labs/service.py`
- Create: `backend/app/labs/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/labs/test_router.py`

**Interfaces:**
- Consumes: `app.models.lab.*` (Task 1), `app.auth.dependencies.get_current_user`. Enqueues `worker.jobs.provision_lab`/`reset_lab`/`destroy_lab` **by string reference** — does not import `worker.jobs` or `worker.docker_ops` directly (see Global Constraints).
- Produces: `GET /api/v1/labs`, `POST /api/v1/labs/{laboratory_id}/instances`, `GET /api/v1/labs/instances/{instance_id}`, `POST /api/v1/labs/instances/{instance_id}/reset`, `POST /api/v1/labs/instances/{instance_id}/destroy`, `GET /api/v1/labs/instances/{instance_id}/hints/{level}`, `POST /api/v1/labs/instances/{instance_id}/submit`.

- [ ] **Step 1: Write `backend/app/labs/schemas.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel


class LaboratoryOut(BaseModel):
    id: str
    title: str
    type: str
    difficulty: str
    duration_estimate_min: int
    concept_slugs: list[str]


class LabInstanceOut(BaseModel):
    id: uuid.UUID
    laboratory_id: str
    status: str
    host_port: int | None
    hints_used: int
    solved: bool
    requested_at: datetime
    started_at: datetime | None


class SubmitFlagRequest(BaseModel):
    flag: str


class SubmitFlagResponse(BaseModel):
    correct: bool
    solved: bool


class HintOut(BaseModel):
    level: int
    text: str
```

- [ ] **Step 2: Write `backend/app/labs/service.py`**

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.content import Concept
from app.models.lab import Laboratory, LabInstance, LabInstanceStatus, LaboratoryConcept


def list_laboratories(db: Session) -> list[dict]:
    labs = db.query(Laboratory).all()
    result = []
    for lab in labs:
        slugs = (
            db.query(Concept.slug)
            .join(LaboratoryConcept, LaboratoryConcept.concept_id == Concept.id)
            .filter(LaboratoryConcept.laboratory_id == lab.id)
            .all()
        )
        result.append({"laboratory": lab, "concept_slugs": [s[0] for s in slugs]})
    return result


def create_instance(db: Session, laboratory_id: str, user_id) -> LabInstance:
    instance = LabInstance(
        laboratory_id=laboratory_id,
        user_id=user_id,
        status=LabInstanceStatus.requested,
        context_seed={},
        requested_at=datetime.now(timezone.utc),
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)
    return instance


def get_instance(db: Session, instance_id: str, user_id) -> LabInstance | None:
    return (
        db.query(LabInstance)
        .filter(LabInstance.id == instance_id, LabInstance.user_id == user_id)
        .first()
    )


def reveal_hint(db: Session, instance: LabInstance, laboratory: Laboratory, level: int) -> dict | None:
    matching = next((h for h in laboratory.hints if h["level"] == level), None)
    if matching is None:
        return None
    if level > instance.hints_used:
        instance.hints_used = level
        db.commit()
    return matching


def submit_flag(db: Session, instance: LabInstance, flag: str) -> bool:
    correct = instance.context_seed.get("flag_token") == flag
    if correct and not instance.solved:
        instance.solved = True
        instance.solved_at = datetime.now(timezone.utc)
        db.commit()
    return correct
```

- [ ] **Step 3: Write `backend/app/labs/router.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from redis import Redis
from rq import Queue
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.config import settings
from app.db import get_db
from app.labs import service
from app.labs.schemas import HintOut, LabInstanceOut, LaboratoryOut, SubmitFlagRequest, SubmitFlagResponse
from app.models.lab import Laboratory, LabInstance
from app.models.user import User

router = APIRouter()

_redis_conn = Redis.from_url(settings.redis_url)
_queue = Queue("labs", connection=_redis_conn)


def _to_laboratory_out(entry: dict) -> LaboratoryOut:
    lab: Laboratory = entry["laboratory"]
    return LaboratoryOut(
        id=lab.id,
        title=lab.title,
        type=lab.type,
        difficulty=lab.difficulty,
        duration_estimate_min=lab.duration_estimate_min,
        concept_slugs=entry["concept_slugs"],
    )


def _to_instance_out(instance: LabInstance) -> LabInstanceOut:
    return LabInstanceOut(
        id=instance.id,
        laboratory_id=instance.laboratory_id,
        status=instance.status.value,
        host_port=instance.host_port,
        hints_used=instance.hints_used,
        solved=instance.solved,
        requested_at=instance.requested_at,
        started_at=instance.started_at,
    )


@router.get("", response_model=list[LaboratoryOut])
def list_labs(db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> list[LaboratoryOut]:
    return [_to_laboratory_out(e) for e in service.list_laboratories(db)]


@router.post("/{laboratory_id}/instances", response_model=LabInstanceOut)
def create_instance(
    laboratory_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LabInstanceOut:
    laboratory = db.query(Laboratory).filter(Laboratory.id == laboratory_id).first()
    if laboratory is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Laboratory not found")
    instance = service.create_instance(db, laboratory_id, user.id)
    _queue.enqueue("worker.jobs.provision_lab", str(instance.id))
    return _to_instance_out(instance)


def _get_instance_or_404(db: Session, user: User, instance_id: str) -> LabInstance:
    instance = service.get_instance(db, instance_id, user.id)
    if instance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab instance not found")
    return instance


@router.get("/instances/{instance_id}", response_model=LabInstanceOut)
def get_instance(
    instance_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LabInstanceOut:
    return _to_instance_out(_get_instance_or_404(db, user, instance_id))


@router.post("/instances/{instance_id}/reset", response_model=LabInstanceOut)
def reset_instance(
    instance_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LabInstanceOut:
    instance = _get_instance_or_404(db, user, instance_id)
    _queue.enqueue("worker.jobs.reset_lab", str(instance.id))
    return _to_instance_out(instance)


@router.post("/instances/{instance_id}/destroy", response_model=LabInstanceOut)
def destroy_instance(
    instance_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LabInstanceOut:
    instance = _get_instance_or_404(db, user, instance_id)
    _queue.enqueue("worker.jobs.destroy_lab", str(instance.id))
    return _to_instance_out(instance)


@router.get("/instances/{instance_id}/hints/{level}", response_model=HintOut)
def get_hint(
    instance_id: str,
    level: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HintOut:
    instance = _get_instance_or_404(db, user, instance_id)
    laboratory = db.query(Laboratory).filter(Laboratory.id == instance.laboratory_id).first()
    hint = service.reveal_hint(db, instance, laboratory, level)
    if hint is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hint not found")
    return HintOut(**hint)


@router.post("/instances/{instance_id}/submit", response_model=SubmitFlagResponse)
def submit_flag(
    instance_id: str,
    payload: SubmitFlagRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubmitFlagResponse:
    instance = _get_instance_or_404(db, user, instance_id)
    correct = service.submit_flag(db, instance, payload.flag)
    return SubmitFlagResponse(correct=correct, solved=instance.solved)
```

Note: jobs are enqueued via `_queue.enqueue("worker.jobs.provision_lab", ...)` — a **string** reference, not `from worker.jobs import provision_lab`. This is the concrete mechanism behind the "API never imports `docker`" constraint: RQ resolves the string to a callable only inside the worker process when it dequeues the job.

- [ ] **Step 4: Write `backend/app/labs/__init__.py`** (empty file)

- [ ] **Step 5: Mount it in `backend/app/main.py`**

```python
from app.labs.router import router as labs_router
# ...
app.include_router(labs_router, prefix="/api/v1/labs", tags=["labs"])
```

- [ ] **Step 6: Write the failing test**

`backend/tests/labs/test_router.py`:
```python
import pyotp

from app.auth.security import hash_password
from app.auth.totp import generate_totp_secret
from app.models.lab import Laboratory, LabInstance
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


def _seed_laboratory(db_session):
    lab = Laboratory(
        id="net-tcp-flagbox-001",
        title="FlagBox",
        type="black_box",
        difficulty="beginner",
        duration_estimate_min=30,
        docker_build_context="labs/flagbox",
        hints=[{"level": 1, "text": "Conéctate con netcat"}],
        cpu_limit="0.5",
        memory_limit_mb=128,
        max_lifetime_min=120,
        cleanup_remove_volumes=True,
    )
    db_session.add(lab)
    db_session.commit()
    return lab


def test_labs_require_auth(client):
    assert client.get("/api/v1/labs").status_code == 401


def test_list_labs(client, db_session):
    _seed_laboratory(db_session)
    _login_as_owner(client, db_session)

    resp = client.get("/api/v1/labs")
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == "net-tcp-flagbox-001"


def test_create_instance_and_get_it(client, db_session):
    _seed_laboratory(db_session)
    _login_as_owner(client, db_session)

    create_resp = client.post("/api/v1/labs/net-tcp-flagbox-001/instances")
    assert create_resp.status_code == 200
    instance_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "requested"

    get_resp = client.get(f"/api/v1/labs/instances/{instance_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == instance_id


def test_get_hint_increments_hints_used(client, db_session):
    _seed_laboratory(db_session)
    _login_as_owner(client, db_session)

    instance_id = client.post("/api/v1/labs/net-tcp-flagbox-001/instances").json()["id"]

    hint_resp = client.get(f"/api/v1/labs/instances/{instance_id}/hints/1")
    assert hint_resp.status_code == 200
    assert hint_resp.json()["text"] == "Conéctate con netcat"

    get_resp = client.get(f"/api/v1/labs/instances/{instance_id}")
    assert get_resp.json()["hints_used"] == 1


def test_submit_flag_correct_and_incorrect(client, db_session):
    _seed_laboratory(db_session)
    _login_as_owner(client, db_session)

    instance_id = client.post("/api/v1/labs/net-tcp-flagbox-001/instances").json()["id"]

    instance = db_session.query(LabInstance).filter(LabInstance.id == instance_id).first()
    instance.context_seed = {"flag_token": "FLAG{test}"}
    db_session.commit()

    wrong_resp = client.post(f"/api/v1/labs/instances/{instance_id}/submit", json={"flag": "FLAG{wrong}"})
    assert wrong_resp.json() == {"correct": False, "solved": False}

    correct_resp = client.post(f"/api/v1/labs/instances/{instance_id}/submit", json={"flag": "FLAG{test}"})
    assert correct_resp.json() == {"correct": True, "solved": True}
```

Note: these tests create instances via the API, which enqueues a real RQ job onto Redis — but since no worker is running during the test suite, the job just sits queued and is never processed, so `status` stays `requested`/`host_port` stays null throughout these tests. That's fine — this file tests the API contract, not job execution (Tasks 4-5 already cover job execution against real Docker).

- [ ] **Step 7: Run it to verify it passes**

Run: `pytest tests/labs/test_router.py -v`
Expected: PASS (5 tests)

- [ ] **Step 8: Run the full backend suite**

Run: `pytest -v`
Expected: all tests pass (will take noticeably longer than before due to the Docker-building tests in Tasks 4-5).

- [ ] **Step 9: Commit**

```bash
git add backend/app/labs backend/app/main.py backend/tests/labs/test_router.py
git commit -m "feat: add labs API endpoints"
```

---

### Task 8: Network isolation — real security verification

**Files:**
- Test: `backend/tests/worker/test_network_isolation.py`

**Interfaces:**
- Consumes: `worker.docker_ops.*` (Task 4).
- Produces: no new production code — this task exists purely to give the security claims in the design spec (§5) a real, automated check instead of only documentation.

- [ ] **Step 1: Write `backend/tests/worker/test_network_isolation.py`**

```python
import pytest

from worker import docker_ops


@pytest.fixture
def isolated_network():
    network_id = docker_ops.create_isolated_network("net-isolation-test")
    yield network_id
    docker_ops.destroy_lab_resources(None, network_id)


def test_isolated_network_cannot_reach_internet(isolated_network):
    client = docker_ops.get_client()
    container = client.containers.run(
        "python:3.12-slim",
        command=["python3", "-c", "import socket; socket.create_connection(('8.8.8.8', 53), timeout=3)"],
        network=isolated_network,
        detach=True,
        labels={docker_ops.LABEL_KEY: "net-isolation-test"},
    )
    try:
        result = container.wait(timeout=15)
        assert result["StatusCode"] != 0
    finally:
        container.remove(force=True)


def test_isolated_network_cannot_reach_host_postgres(isolated_network):
    client = docker_ops.get_client()
    container = client.containers.run(
        "python:3.12-slim",
        command=[
            "python3",
            "-c",
            "import socket; socket.create_connection(('host.docker.internal', 55432), timeout=3)",
        ],
        network=isolated_network,
        detach=True,
        extra_hosts={"host.docker.internal": "host-gateway"},
        labels={docker_ops.LABEL_KEY: "net-isolation-test"},
    )
    try:
        result = container.wait(timeout=15)
        assert result["StatusCode"] != 0
    finally:
        container.remove(force=True)
```

- [ ] **Step 2: Run it to verify it passes**

Run: `cd backend && pytest tests/worker/test_network_isolation.py -v`
Expected: PASS (2 tests). Both prove — against real Docker networking, not documentation — that a container on an isolated lab network cannot reach the internet or the host's Postgres.

**If either test fails:** stop and investigate before continuing to Task 9 — this is the load-bearing security property of the whole sub-plan.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/worker/test_network_isolation.py
git commit -m "test: verify isolated lab network cannot reach internet or host services"
```

---

### Task 9: Frontend — labs catalog and instance page

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/features/labs/LabsPage.tsx`
- Create: `frontend/src/features/labs/LabInstancePage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `api` from `frontend/src/lib/api.ts`.
- Produces: routes `/labs` and `/labs/:labId`.

- [ ] **Step 1: Add lab types and API calls to `frontend/src/lib/api.ts`**

Add after the existing `Recommendation` type:

```typescript
export type Laboratory = {
  id: string;
  title: string;
  type: string;
  difficulty: string;
  duration_estimate_min: number;
  concept_slugs: string[];
};

export type LabInstance = {
  id: string;
  laboratory_id: string;
  status: "requested" | "provisioning" | "running" | "stopped" | "destroyed" | "expired" | "failed";
  host_port: number | null;
  hints_used: number;
  solved: boolean;
  requested_at: string;
  started_at: string | null;
};
```

Add to the `api` object:

```typescript
  listLabs: () => request<Laboratory[]>("/labs"),
  createLabInstance: (laboratoryId: string) =>
    request<LabInstance>(`/labs/${laboratoryId}/instances`, { method: "POST" }),
  getLabInstance: (instanceId: string) => request<LabInstance>(`/labs/instances/${instanceId}`),
  resetLabInstance: (instanceId: string) =>
    request<LabInstance>(`/labs/instances/${instanceId}/reset`, { method: "POST" }),
  destroyLabInstance: (instanceId: string) =>
    request<LabInstance>(`/labs/instances/${instanceId}/destroy`, { method: "POST" }),
  getLabHint: (instanceId: string, level: number) =>
    request<{ level: number; text: string }>(`/labs/instances/${instanceId}/hints/${level}`),
  submitLabFlag: (instanceId: string, flag: string) =>
    request<{ correct: boolean; solved: boolean }>(`/labs/instances/${instanceId}/submit`, {
      method: "POST",
      body: JSON.stringify({ flag }),
    }),
```

- [ ] **Step 2: Write `frontend/src/features/labs/LabsPage.tsx`**

```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Laboratory } from "../../lib/api";

export function LabsPage() {
  const [labs, setLabs] = useState<Laboratory[] | null>(null);

  useEffect(() => {
    api.listLabs().then(setLabs);
  }, []);

  if (!labs) return <p>Cargando…</p>;

  return (
    <div>
      <h1>Laboratorios</h1>
      <ul>
        {labs.map((lab) => (
          <li key={lab.id}>
            <Link to={`/labs/${lab.id}`}>{lab.title}</Link> — {lab.difficulty}, ~{lab.duration_estimate_min} min
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 3: Write `frontend/src/features/labs/LabInstancePage.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, LabInstance } from "../../lib/api";

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATUSES = new Set(["running", "destroyed", "expired", "failed"]);

export function LabInstancePage() {
  const { labId } = useParams<{ labId: string }>();
  const [instance, setInstance] = useState<LabInstance | null>(null);
  const [hintText, setHintText] = useState<string | null>(null);
  const [flag, setFlag] = useState("");
  const [submitResult, setSubmitResult] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!labId) return;
    api.createLabInstance(labId).then(setInstance);
  }, [labId]);

  useEffect(() => {
    if (!instance || TERMINAL_STATUSES.has(instance.status)) return;
    pollRef.current = setInterval(() => {
      api.getLabInstance(instance.id).then(setInstance);
    }, POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [instance]);

  const handleHint = async (level: number) => {
    const hint = await api.getLabHint(instance!.id, level);
    setHintText(hint.text);
  };

  const handleSubmit = async () => {
    const result = await api.submitLabFlag(instance!.id, flag);
    setSubmitResult(result.correct ? "¡Correcto!" : "Incorrecto, sigue intentando.");
    if (result.solved) {
      setInstance(await api.getLabInstance(instance!.id));
    }
  };

  const handleReset = async () => {
    const refreshed = await api.resetLabInstance(instance!.id);
    setInstance(refreshed);
    setSubmitResult(null);
    setHintText(null);
  };

  if (!instance) return <p>Creando instancia…</p>;

  return (
    <div>
      <h1>Laboratorio</h1>
      <p>Estado: {instance.status}</p>

      {instance.status === "running" && instance.host_port && (
        <p>
          Conéctate con: <code>nc localhost {instance.host_port}</code>
        </p>
      )}

      <div>
        <button onClick={() => handleHint(1)}>Hint 1</button>
        <button onClick={() => handleHint(2)}>Hint 2</button>
        <button onClick={() => handleHint(3)}>Hint 3</button>
        <button onClick={() => handleHint(4)}>Hint 4</button>
      </div>
      {hintText && <p>{hintText}</p>}

      <div>
        <input value={flag} onChange={(e) => setFlag(e.target.value)} placeholder="FLAG{...}" />
        <button onClick={handleSubmit}>Enviar flag</button>
      </div>
      {submitResult && <p>{submitResult}</p>}
      {instance.solved && <p>¡Laboratorio resuelto!</p>}

      <button onClick={handleReset}>Reset</button>
    </div>
  );
}
```

- [ ] **Step 4: Add routes in `frontend/src/App.tsx`**

```tsx
import { LabsPage } from "./features/labs/LabsPage";
import { LabInstancePage } from "./features/labs/LabInstancePage";
// ...
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/labs" element={<LabsPage />} />
                <Route path="/labs/:labId" element={<LabInstancePage />} />
```

- [ ] **Step 5: Type-check**

Run: `cd frontend && npx tsc -b --noEmit`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/features/labs frontend/src/App.tsx
git commit -m "feat: add labs catalog and instance pages"
```

---

### Task 10: End-to-end verification, worker running for real, update checklist

**Files:** none created. Also updates `PROJECT_MASTER_CHECKLIST.md`.

- [ ] **Step 1: Seed the lab catalog into the dev database**

Run:
```bash
cd backend
PYTHONPATH=. .venv/bin/python -c "from scripts.seed_labs import seed_labs; seed_labs('../labs')"
```
Expected: `Seeded 1 laboratories from ../labs/`.

- [ ] **Step 2: Start the worker (real, long-running) alongside the API**

Run:
```bash
cd backend
setsid nohup .venv/bin/python -m worker.run_worker > /tmp/worker.log 2>&1 < /dev/null &
disown
sleep 2
cat /tmp/worker.log
```
Expected: log shows the RQ worker listening on the `labs` queue with no errors.

- [ ] **Step 3: Restart the backend API (kill by exact PID, never a broad `pkill` pattern) and verify**

```bash
ss -ltnp | grep 8001   # find the PID
kill <pid>
cd backend && setsid nohup .venv/bin/uvicorn app.main:app --port 8001 > /tmp/uvicorn.log 2>&1 < /dev/null &
disown
sleep 2
curl -s http://localhost:8001/api/v1/health
```

- [ ] **Step 4: Solve FlagBox end-to-end via the real API + real netcat**

With a fresh authenticated `cookies.txt`:
```bash
curl -s -b /tmp/cookies.txt http://localhost:8001/api/v1/labs | python3 -m json.tool

INSTANCE_ID=$(curl -s -b /tmp/cookies.txt -X POST http://localhost:8001/api/v1/labs/net-tcp-flagbox-001/instances | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
echo "instance: $INSTANCE_ID"

# poll until running (worker needs a few seconds to build+run the image the first time)
for i in $(seq 1 20); do
  STATUS=$(curl -s -b /tmp/cookies.txt http://localhost:8001/api/v1/labs/instances/$INSTANCE_ID | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])")
  echo "status: $STATUS"
  [ "$STATUS" = "running" ] && break
  sleep 3
done

HOST_PORT=$(curl -s -b /tmp/cookies.txt http://localhost:8001/api/v1/labs/instances/$INSTANCE_ID | python3 -c "import json,sys; print(json.load(sys.stdin)['host_port'])")
echo "host_port: $HOST_PORT"

FLAG=$(printf 'LOGIN attacker\r\nGET 0\r\n' | timeout 5 nc localhost $HOST_PORT | grep NOTE | cut -d' ' -f2)
echo "captured flag: $FLAG"

curl -s -b /tmp/cookies.txt -X POST http://localhost:8001/api/v1/labs/instances/$INSTANCE_ID/submit \
  -H "Content-Type: application/json" -d "{\"flag\":\"$FLAG\"}" | python3 -m json.tool
```
Expected final response: `{"correct": true, "solved": true}`.

- [ ] **Step 5: Clean up the instance and verify no orphaned Docker resources**

```bash
curl -s -b /tmp/cookies.txt -X POST http://localhost:8001/api/v1/labs/instances/$INSTANCE_ID/destroy > /dev/null
sleep 2
docker ps -a --filter "label=cyberlearn_instance_id=$INSTANCE_ID"
docker network ls --filter "label=cyberlearn_instance_id=$INSTANCE_ID"
```
Expected: both commands return empty (header row only) — no leftover containers or networks.

- [ ] **Step 6: Browser walkthrough**

1. Log in, go to `/labs`.
2. Click into FlagBox — confirm the page shows "Creando instancia…" then transitions to `running` with connection instructions.
3. Reveal hints 1-4 in order, confirm `hints_used` increments (visible by refreshing `/labs/:labId` or checking the API).
4. Using a terminal, `nc localhost <port>` with the shown port, run `LOGIN test` then `GET 0`, copy the flag.
5. Paste the flag into the input and submit — confirm "¡Correcto!" and "¡Laboratorio resuelto!" appear.
6. Click Reset — confirm the page returns to "Creando instancia…" and a new instance/port appears.

- [ ] **Step 7: Run the full backend test suite one final time**

Run: `cd backend && pytest -v`
Expected: all tests pass (this run will be the slowest yet, due to the several real-Docker-build tests across Tasks 2, 4, 5, 8 — that's expected and correct, not a regression to fix).

- [ ] **Step 8: Update `PROJECT_MASTER_CHECKLIST.md`**

Mark under "Labs + orquestador Docker":
```markdown
- [x] Modelo Laboratory/LabInstance/LabAttempt + definición declarativa YAML
- [x] Worker orquestador (Celery/RQ) con acceso exclusivo al socket Docker
- [x] Aislamiento de red verificado (test de integración de seguridad)
- [x] 2-3 labs Docker reales con cleanup automático
```
Note: only 1 lab (FlagBox) was built in this sub-plan, not 2-3 — adjust the line to be honest about that:
```markdown
- [x] 1 lab Docker real (FlagBox) con cleanup automático — más labs quedan pendientes de contenido, no de infraestructura
```
Also add a new pending line under "Pendiente para más adelante" noting Sub-plan B:
```markdown
- [ ] Terminal web integrada para labs (Sub-plan B: xterm.js + docker exec vía WebSockets)
```

Commit:
```bash
git add PROJECT_MASTER_CHECKLIST.md
git commit -m "docs: update checklist — labs orchestrator (Sub-plan A) complete"
```

Report the resulting checklist section to the user.
