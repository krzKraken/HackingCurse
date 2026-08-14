# Labs Sub-plan B: Terminal Web Integrada — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the user a browser-based terminal (`/bin/sh` inside the running lab container) for any `LabInstance` with `status == running`, without letting the API process touch the Docker socket.

**Architecture:** Browser (xterm.js) opens a WebSocket to a new FastAPI endpoint, which authenticates/authorizes and proxies raw bytes to a second WebSocket server that runs inside the worker process. That worker-side relay does the real `docker exec` (create + start with a raw TTY socket) and pipes bytes between the exec socket and its WebSocket. This keeps "only the worker process imports `docker`" intact, mirroring the `relay.py` TCP relay already built in Sub-plan A.

**Tech Stack:** FastAPI `WebSocket` (API side), `websockets` 17.0.1 (worker-side relay server — already present transitively via `uvicorn[standard]`, now added directly), `docker` SDK `exec_create`/`exec_start(socket=True)`/`exec_resize`, `xterm` + `xterm-addon-fit` (frontend).

## Global Constraints

- Only the worker process (`backend/worker/`) may `import docker`. The API process (`backend/app/`) never touches the Docker SDK — verified in Sub-plan A, must hold here too.
- Terminal access is only ever offered for a `LabInstance` with `status == LabInstanceStatus.running`. Never during `provisioning`, never after `destroyed`/`expired`/`failed`.
- No mocking of Docker in tests — this project's established testing philosophy (see Sub-plan A) is real integration tests against a real Docker daemon.
- Path param naming: never name a FastAPI path parameter `session_id` (collides with the `session_id` cookie parameter used by `get_current_user`) — use `lab_id` / `instance_id`, matching the existing router.

---

### Task 1: Config setting + `websockets` dependency

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_config.py` (new file)

**Interfaces:**
- Produces: `settings.labs_terminal_relay_port: int` (default `8765`), consumed by Task 2 (worker relay server) and Task 3 (API proxy endpoint).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_config.py
from app.config import Settings


def test_labs_terminal_relay_port_default():
    settings = Settings()
    assert settings.labs_terminal_relay_port == 8765
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_config.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'labs_terminal_relay_port'`

- [ ] **Step 3: Add the setting**

In `backend/app/config.py`, add to the `Settings` class (after `login_lockout_seconds`):

```python
    labs_terminal_relay_port: int = 8765
```

- [ ] **Step 4: Pin the `websockets` dependency explicitly**

In `backend/requirements.txt`, add a new line (the package is already present transitively via `uvicorn[standard]==0.32.0`, but the worker now imports it directly, so it must be pinned as a direct dependency):

```
websockets==17.0.1
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/requirements.txt backend/tests/test_config.py
git commit -m "feat: add labs_terminal_relay_port setting"
```

---

### Task 2: Terminal relay core (worker process)

**Files:**
- Create: `backend/worker/terminal_relay.py`
- Test: `backend/tests/worker/test_terminal_relay.py` (new file)

**Interfaces:**
- Consumes: `worker.docker_ops.get_client()` (existing, returns `docker.DockerClient`), `app.db.SessionLocal` (existing), `app.models.lab.LabInstance`/`LabInstanceStatus` (existing).
- Produces:
  - `async def relay_exec_session(websocket, container_id: str) -> None` — bridges bytes between `websocket` and an interactive `/bin/sh` exec session inside `container_id`, until either side closes. Consumed by Task 2's own handler and directly by Task 2's tests.
  - `def instance_container_id(instance_id: str) -> str | None` — returns the container id if the instance exists and `status == running`, else `None`. Consumed by the WebSocket handler in this task and re-used conceptually (re-validated, not imported) by Task 3's API-side check.
  - `async def handler(websocket) -> None` — the `websockets.serve` connection handler; parses `instance_id` from the request path, closes with code `4404` if not running, otherwise runs `relay_exec_session`, closing with `4500` on any Docker error.
  - `def run_relay_server(host: str, port: int) -> None` — blocking entry point (runs its own asyncio event loop forever); consumed by Task 4 (`run_worker.py`).
  - Close codes: `CLOSE_NOT_RUNNING = 4404`, `CLOSE_EXEC_FAILED = 4500` (module-level constants).

- [ ] **Step 1: Write the failing test for `relay_exec_session` against a real container**

```python
# backend/tests/worker/test_terminal_relay.py
import asyncio
import time

import pytest
import websockets

pytestmark = pytest.mark.asyncio


@pytest.fixture
def shell_container():
    from worker import docker_ops

    client = docker_ops.get_client()
    import tempfile
    import pathlib

    build_dir = pathlib.Path(tempfile.mkdtemp())
    (build_dir / "Dockerfile").write_text(
        'FROM python:3.12-slim\nCMD ["sleep", "infinity"]\n'
    )
    image, _ = client.images.build(path=str(build_dir), tag="cyberlearn-terminal-test", rm=True)
    container = client.containers.run(image.id, detach=True)
    time.sleep(0.5)
    yield container.id
    container.remove(force=True)


async def test_relay_exec_session_echoes_shell_output(shell_container):
    from worker.terminal_relay import handler
    import websockets.asyncio.server as ws_server

    async def fake_container_lookup(instance_id):
        return shell_container

    import worker.terminal_relay as terminal_relay
    original = terminal_relay.instance_container_id
    terminal_relay.instance_container_id = lambda instance_id: shell_container
    try:
        server = await ws_server.serve(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            async with websockets.connect(f"ws://127.0.0.1:{port}/any-instance-id") as client_ws:
                await client_ws.send("echo hola\n")
                collected = b""
                deadline = asyncio.get_event_loop().time() + 5
                while b"hola" not in collected and asyncio.get_event_loop().time() < deadline:
                    message = await asyncio.wait_for(client_ws.recv(), timeout=5)
                    collected += message if isinstance(message, bytes) else message.encode()
                assert b"hola" in collected
        finally:
            server.close()
            await server.wait_closed()
    finally:
        terminal_relay.instance_container_id = original


async def test_handler_closes_immediately_when_instance_not_running():
    import worker.terminal_relay as terminal_relay
    import websockets.asyncio.server as ws_server

    original = terminal_relay.instance_container_id
    terminal_relay.instance_container_id = lambda instance_id: None
    try:
        server = await ws_server.serve(terminal_relay.handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            async with websockets.connect(f"ws://127.0.0.1:{port}/missing-instance") as client_ws:
                with pytest.raises(websockets.exceptions.ConnectionClosed) as exc_info:
                    await client_ws.recv()
                assert exc_info.value.rcvd.code == terminal_relay.CLOSE_NOT_RUNNING
        finally:
            server.close()
            await server.wait_closed()
    finally:
        terminal_relay.instance_container_id = original
```

Add `pytest-asyncio` marker config if not already present — check `backend/pytest.ini` / `pyproject.toml` first; the project already uses `pytest.mark.asyncio` in `tests/labs/test_flagbox_server.py`, so `asyncio_mode` is already configured. No changes needed there.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/worker/test_terminal_relay.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'worker.terminal_relay'`

- [ ] **Step 3: Write the implementation**

```python
# backend/worker/terminal_relay.py
import asyncio
import json

from app.db import SessionLocal
from app.models.lab import LabInstance, LabInstanceStatus
from worker import docker_ops

CLOSE_NOT_RUNNING = 4404
CLOSE_EXEC_FAILED = 4500


def instance_container_id(instance_id: str) -> str | None:
    db = SessionLocal()
    try:
        instance = db.query(LabInstance).filter(LabInstance.id == instance_id).first()
        if instance is None or instance.status != LabInstanceStatus.running:
            return None
        return instance.container_id
    finally:
        db.close()


async def relay_exec_session(websocket, container_id: str) -> None:
    client = docker_ops.get_client()
    exec_id = client.api.exec_create(
        container_id, cmd="/bin/sh", tty=True, stdin=True, stdout=True, stderr=True
    )["Id"]
    sock = client.api.exec_start(exec_id, tty=True, socket=True)
    raw = sock._sock
    raw.setblocking(True)
    loop = asyncio.get_running_loop()

    async def pump_container_to_ws():
        while True:
            try:
                data = await loop.run_in_executor(None, raw.recv, 4096)
            except OSError:
                break
            if not data:
                break
            await websocket.send(data)

    async def pump_ws_to_container():
        async for message in websocket:
            if isinstance(message, str):
                try:
                    payload = json.loads(message)
                except ValueError:
                    payload = None
                if isinstance(payload, dict) and payload.get("type") == "resize":
                    client.api.exec_resize(exec_id, height=payload["rows"], width=payload["cols"])
                    continue
                data = message.encode()
            else:
                data = message
            await loop.run_in_executor(None, raw.sendall, data)

    to_ws = asyncio.ensure_future(pump_container_to_ws())
    to_container = asyncio.ensure_future(pump_ws_to_container())
    try:
        await asyncio.wait({to_ws, to_container}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        to_ws.cancel()
        to_container.cancel()
        raw.close()


async def handler(websocket) -> None:
    path = websocket.request.path
    instance_id = path.strip("/").split("/")[-1]
    container_id = instance_container_id(instance_id)
    if container_id is None:
        await websocket.close(CLOSE_NOT_RUNNING, "lab not running")
        return
    try:
        await relay_exec_session(websocket, container_id)
    except Exception as exc:
        await websocket.close(CLOSE_EXEC_FAILED, str(exc)[:120])


def run_relay_server(host: str, port: int) -> None:
    asyncio.run(_run_forever(host, port))


async def _run_forever(host: str, port: int) -> None:
    import websockets.asyncio.server as ws_server

    async with ws_server.serve(handler, host, port):
        await asyncio.Future()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/worker/test_terminal_relay.py -v`
Expected: PASS (both tests). This talks to a real Docker daemon — make sure Docker is running.

- [ ] **Step 5: Commit**

```bash
git add backend/worker/terminal_relay.py backend/tests/worker/test_terminal_relay.py
git commit -m "feat: add worker-side terminal relay (docker exec over websocket)"
```

---

### Task 3: API WebSocket proxy endpoint

**Files:**
- Modify: `backend/app/labs/router.py`
- Test: `backend/tests/labs/test_terminal_router.py` (new file)

**Interfaces:**
- Consumes: `app.auth.sessions.get_session(session_id: str) -> dict | None` (existing), `app.config.settings.labs_terminal_relay_port` (Task 1), `app.labs.service.get_instance(db, instance_id, user_id) -> LabInstance | None` (existing), `LabInstance.status` (existing enum `LabInstanceStatus`).
- Produces: WebSocket route `GET /api/v1/labs/instances/{instance_id}/terminal` (note: nested under `/instances/{instance_id}/...` to match the existing router's convention for instance-scoped routes — see `get_instance`, `reset_instance`, `destroy_instance`, `get_hint`, `submit_flag` above it in the same file, all under `/instances/{instance_id}/...`). Consumed by Task 5 (frontend).
- Note on ownership errors: `service.get_instance(db, instance_id, user_id)` filters by `user_id` in the query itself (existing behavior, see `app/labs/service.py`), so an instance that exists but belongs to another user returns `None` — same as a nonexistent instance. Both close with `4404`, never `4403`. This matches the existing HTTP routes' `_get_instance_or_404` pattern (info-hiding: a caller can't distinguish "not yours" from "doesn't exist").

- [ ] **Step 1: Write the failing test**

`backend/tests/conftest.py` provides `client` (a `TestClient` whose cookie jar persists across requests within a test) and `db_session`. `backend/tests/labs/test_router.py` already defines the exact login/seed helpers to reuse — `_login_as_owner(client, db_session) -> User` and `_seed_laboratory(db_session) -> Laboratory`. `LabInstance.id` is a `uuid.UUID` column with `default=uuid.uuid4` (not a string), and `requested_at` is non-nullable, so it must be set explicitly when constructing one directly in a test (see `app/models/lab.py`).

```python
# backend/tests/labs/test_terminal_router.py
import uuid
from datetime import datetime, timezone

import pytest

from app.models.lab import LabInstance, LabInstanceStatus
from tests.labs.test_router import _login_as_owner, _seed_laboratory


def test_terminal_rejects_when_instance_not_running(client, db_session):
    laboratory = _seed_laboratory(db_session)
    user = _login_as_owner(client, db_session)

    instance = LabInstance(
        laboratory_id=laboratory.id,
        user_id=user.id,
        status=LabInstanceStatus.requested,
        context_seed={},
        requested_at=datetime.now(timezone.utc),
    )
    db_session.add(instance)
    db_session.commit()

    with client.websocket_connect(f"/api/v1/labs/instances/{instance.id}/terminal") as ws:
        with pytest.raises(Exception):
            ws.receive_text()


def test_terminal_rejects_unknown_instance(client, db_session):
    _login_as_owner(client, db_session)

    with client.websocket_connect(f"/api/v1/labs/instances/{uuid.uuid4()}/terminal") as ws:
        with pytest.raises(Exception):
            ws.receive_text()
```

`tests/labs/test_router.py` has no `__init__.py`-free import concerns — `backend/tests/__init__.py` already exists (added in Sub-plan A specifically to fix a package-shadowing bug), so `from tests.labs.test_router import ...` resolves correctly under pytest's import mode.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/labs/test_terminal_router.py -v`
Expected: FAIL (404 — no such route, or connection rejected because the route doesn't exist)

- [ ] **Step 3: Write the implementation**

In `backend/app/labs/router.py`, add imports and the new endpoint:

```python
import asyncio

import websockets
from fastapi import WebSocket, WebSocketDisconnect

from app.auth.sessions import get_session
from app.models.lab import LabInstanceStatus
```

(merge with existing imports at the top of the file rather than duplicating — `app.config.settings` and `app.db.get_db` are already imported)

```python
@router.websocket("/instances/{instance_id}/terminal")
async def terminal(websocket: WebSocket, instance_id: str) -> None:
    await websocket.accept()

    session_id = websocket.cookies.get(settings.cookie_name)
    session = get_session(session_id) if session_id else None
    if session is None or not session["mfa_verified"]:
        await websocket.close(4401, "not authenticated")
        return

    db = next(get_db())
    try:
        instance = service.get_instance(db, instance_id, session["user_id"])
        if instance is None:
            await websocket.close(4404, "lab instance not found")
            return
        if instance.status != LabInstanceStatus.running:
            await websocket.close(4404, "lab not running")
            return
    finally:
        db.close()

    try:
        relay_url = f"ws://127.0.0.1:{settings.labs_terminal_relay_port}/{instance_id}"
        async with websockets.connect(relay_url) as relay_ws:
            async def browser_to_relay():
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        break
                    data = message.get("bytes") or message.get("text")
                    if data is not None:
                        await relay_ws.send(data)

            async def relay_to_browser():
                async for message in relay_ws:
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            to_relay = asyncio.ensure_future(browser_to_relay())
            to_browser = asyncio.ensure_future(relay_to_browser())
            try:
                await asyncio.wait({to_relay, to_browser}, return_when=asyncio.FIRST_COMPLETED)
            finally:
                to_relay.cancel()
                to_browser.cancel()
    except (OSError, websockets.exceptions.WebSocketException):
        await websocket.close(4503, "terminal service unavailable")
    except WebSocketDisconnect:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/labs/test_terminal_router.py -v`
Expected: PASS

- [ ] **Step 5: Write a second test for the happy path with a real relay running**

```python
def test_terminal_proxies_to_running_instance(client, db_session):
    import pathlib
    import tempfile
    import threading
    import time

    from app.config import settings as app_settings
    from worker import docker_ops, terminal_relay

    laboratory = _seed_laboratory(db_session)
    user = _login_as_owner(client, db_session)

    docker_client = docker_ops.get_client()
    build_dir = pathlib.Path(tempfile.mkdtemp())
    (build_dir / "Dockerfile").write_text('FROM python:3.12-slim\nCMD ["sleep", "infinity"]\n')
    image, _ = docker_client.images.build(path=str(build_dir), tag="cyberlearn-terminal-router-test", rm=True)
    container = docker_client.containers.run(image.id, detach=True)
    time.sleep(0.5)

    instance = LabInstance(
        laboratory_id=laboratory.id,
        user_id=user.id,
        status=LabInstanceStatus.running,
        context_seed={},
        container_id=container.id,
        requested_at=datetime.now(timezone.utc),
    )
    db_session.add(instance)
    db_session.commit()

    relay_thread = threading.Thread(
        target=terminal_relay.run_relay_server, args=("127.0.0.1", 18765), daemon=True
    )
    relay_thread.start()
    time.sleep(0.5)

    original_port = app_settings.labs_terminal_relay_port
    app_settings.labs_terminal_relay_port = 18765
    try:
        with client.websocket_connect(f"/api/v1/labs/instances/{instance.id}/terminal") as ws:
            ws.send_text("echo hola\n")
            collected = ""
            for _ in range(20):
                collected += ws.receive_text()
                if "hola" in collected:
                    break
            assert "hola" in collected
    finally:
        app_settings.labs_terminal_relay_port = original_port
        container.remove(force=True)
```

Run: `cd backend && pytest tests/labs/test_terminal_router.py -v`
Expected: PASS (both tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/labs/router.py backend/tests/labs/test_terminal_router.py
git commit -m "feat: add authenticated WebSocket proxy for lab terminal"
```

---

### Task 4: Wire the relay server into the worker entrypoint

**Files:**
- Modify: `backend/worker/run_worker.py`

**Interfaces:**
- Consumes: `worker.terminal_relay.run_relay_server(host: str, port: int) -> None` (Task 2), `app.config.settings.labs_terminal_relay_port` (Task 1).

- [ ] **Step 1: Modify `run_worker.py` to start the relay server in its own thread**

```python
# backend/worker/run_worker.py
import threading
import time

from redis import Redis
from rq import Queue, Worker

from app.config import settings
from worker.jobs import sweep_expired_labs
from worker.terminal_relay import run_relay_server

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
    threading.Thread(
        target=run_relay_server,
        args=("127.0.0.1", settings.labs_terminal_relay_port),
        daemon=True,
    ).start()

    redis_conn = Redis.from_url(settings.redis_url)
    queue = Queue(QUEUE_NAME, connection=redis_conn)
    worker = Worker([queue], connection=redis_conn)
    worker.work()


if __name__ == "__main__":
    main()
```

There is no isolated unit test for `main()` itself (it blocks forever running the RQ worker loop, same as before this change) — verification happens manually in Task 6's end-to-end step, where the real worker process is started and its relay port checked.

- [ ] **Step 2: Commit**

```bash
git add backend/worker/run_worker.py
git commit -m "feat: start terminal relay server alongside the RQ worker"
```

---

### Task 5: Frontend terminal component

**Files:**
- Modify: `frontend/package.json` (add `xterm`, `xterm-addon-fit`)
- Modify: `frontend/vite.config.ts` (enable WebSocket proxying for `/api`)
- Create: `frontend/src/features/labs/LabTerminal.tsx`
- Modify: `frontend/src/features/labs/LabInstancePage.tsx`

**Interfaces:**
- Consumes: `LabInstance.status` (existing type in `frontend/src/lib/api.ts`), `LabInstance.id` (existing).
- Produces: `LabTerminal` React component with props `{ instanceId: string }`, rendered from `LabInstancePage`.

No backend/pytest tests apply here — this is a frontend UI component. Verification is manual browser testing in Task 6, consistent with the project's established pattern for frontend features (Sub-plan A's `LabsPage`/`LabInstancePage` had no automated frontend tests either — see `docs/superpowers/plans/2026-08-13-labs-orchestrator.md` Task 9).

- [ ] **Step 1: Add frontend dependencies**

```bash
cd frontend && npm install xterm@^5.5.0 xterm-addon-fit@^0.10.0
```

- [ ] **Step 2: Enable WebSocket proxying in Vite dev server**

In `frontend/vite.config.ts`, change the proxy config to the object form with `ws: true`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8001",
        ws: true,
      },
    },
  },
});
```

- [ ] **Step 3: Create the terminal component**

```tsx
// frontend/src/features/labs/LabTerminal.tsx
import { useEffect, useRef } from "react";
import { Terminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import "xterm/css/xterm.css";

type LabTerminalProps = {
  instanceId: string;
};

export function LabTerminal({ instanceId }: LabTerminalProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const term = new Terminal({ convertEol: true });
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(containerRef.current);
    fitAddon.fit();

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(
      `${protocol}//${window.location.host}/api/v1/labs/instances/${instanceId}/terminal`
    );
    ws.binaryType = "arraybuffer";

    ws.onmessage = (event) => {
      if (typeof event.data === "string") {
        term.write(event.data);
      } else {
        term.write(new Uint8Array(event.data));
      }
    };

    ws.onclose = (event) => {
      term.write(`\r\n\r\n[terminal cerrada: ${event.reason || event.code}]\r\n`);
    };

    const dataDisposable = term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data);
      }
    });

    const sendResize = () => {
      fitAddon.fit();
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
      }
    };
    window.addEventListener("resize", sendResize);
    ws.onopen = sendResize;

    return () => {
      window.removeEventListener("resize", sendResize);
      dataDisposable.dispose();
      ws.close();
      term.dispose();
    };
  }, [instanceId]);

  return <div ref={containerRef} style={{ height: "400px", width: "100%" }} />;
}
```

- [ ] **Step 4: Wire the toggle button into `LabInstancePage`**

In `frontend/src/features/labs/LabInstancePage.tsx`, add the import and a toggle:

```tsx
import { LabTerminal } from "./LabTerminal";
```

Add state near the other `useState` calls:

```tsx
const [showTerminal, setShowTerminal] = useState(false);
```

Add the button and conditional render, right after the `<code>nc localhost {instance.host_port}</code>` block:

```tsx
{instance.status === "running" && (
  <div>
    <button onClick={() => setShowTerminal((v) => !v)}>
      {showTerminal ? "Cerrar terminal" : "Abrir terminal"}
    </button>
    {showTerminal && <LabTerminal instanceId={instance.id} />}
  </div>
)}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts frontend/src/features/labs/LabTerminal.tsx frontend/src/features/labs/LabInstancePage.tsx
git commit -m "feat: add integrated web terminal for running lab instances"
```

---

### Task 6: End-to-end verification + update checklist

**Files:**
- Modify: `PROJECT_MASTER_CHECKLIST.md`

- [ ] **Step 1: Run the full backend test suite**

Run: `cd backend && pytest -q`
Expected: all tests pass, including the new `test_terminal_relay.py` and `test_terminal_router.py` (real Docker required and must be running).

- [ ] **Step 2: Start the real worker process (not via pytest)**

```bash
cd backend && setsid nohup python -m worker.run_worker > /tmp/worker.log 2>&1 < /dev/null & disown
sleep 2 && cat /tmp/worker.log
```

Confirm the log shows the RQ worker starting with no traceback (a crash here — e.g. `ImportError` on `worker.terminal_relay`, or a port-already-in-use error on `8765` — must be fixed before continuing; this is exactly the class of bug that surfaced during Sub-plan A's Task 10 and that the test suite alone won't catch, since pytest starts the relay server on a different port in `test_terminal_router.py`).

- [ ] **Step 3: Start the backend API and frontend dev server**

```bash
cd backend && setsid nohup uvicorn app.main:app --port 8001 > /tmp/api.log 2>&1 < /dev/null & disown
cd frontend && setsid nohup npm run dev > /tmp/frontend.log 2>&1 < /dev/null & disown
sleep 2 && cat /tmp/api.log /tmp/frontend.log
```

- [ ] **Step 4: Create a real lab instance via the API and wait for it to run**

```bash
python3 - <<'EOF'
import json, urllib.request, time

# Reuse whatever login flow the previous Sub-plan A verification used
# (see the session transcript / CLAUDE.md for the owner credentials) to
# obtain a valid session cookie, then:
req = urllib.request.Request(
    "http://localhost:8001/api/v1/labs/<laboratory_id>/instances",
    method="POST",
    headers={"Cookie": "<cl_session cookie from login>"},
)
resp = urllib.request.urlopen(req)
instance = json.loads(resp.read())
print(instance)
EOF
```

Poll `GET /api/v1/labs/instances/{id}` until `status == "running"`.

- [ ] **Step 5: Connect to the terminal via a raw WebSocket client and verify shell access**

```bash
pip install websocket-client --quiet 2>/dev/null || true
python3 - <<'EOF'
import websocket

ws = websocket.create_connection(
    "ws://localhost:8001/api/v1/labs/instances/<instance_id>/terminal",
    cookie="cl_session=<session value>",
)
ws.send("whoami\n")
print(ws.recv())
ws.send("ls /app\n")
print(ws.recv())
ws.close()
EOF
```

Expected: the first `recv()` echoes shell output containing `root` (or the container's default user), the second lists `server.py` (FlagBox's build context).

- [ ] **Step 6: Manual browser check**

Navigate to `/labs/<instance_id>` in a browser, click "Abrir terminal", confirm a live shell prompt renders and responds to typed commands (e.g. `ls`, `whoami`). Resize the browser window and confirm the terminal reflows without breaking.

- [ ] **Step 7: Destroy the instance and confirm the terminal connection drops cleanly**

```bash
curl -X POST -H "Cookie: cl_session=<session value>" \
  http://localhost:8001/api/v1/labs/instances/<instance_id>/destroy
```

Confirm any open browser terminal shows the `[terminal cerrada: ...]` message and the WS closes without the API or worker process crashing (check `/tmp/api.log` and `/tmp/worker.log` for tracebacks).

- [ ] **Step 8: Stop the manually-started processes**

```bash
ss -ltnp | grep -E ':8001|:5173' 
# kill the exact PIDs found, never a name/pattern-based pkill
kill <api_pid> <frontend_pid> <worker_pid>
```

- [ ] **Step 9: Update `PROJECT_MASTER_CHECKLIST.md`**

Change the "Labs + orquestador Docker" section header (drop the "sin terminal web" caveat) and add a line:

```markdown
### Labs + orquestador Docker
- [x] Modelo Laboratory/LabInstance + definición declarativa YAML (sin LabAttempt separado — simplificación documentada)
- [x] Worker orquestador (RQ) con acceso exclusivo al socket Docker
- [x] Aislamiento de red verificado (test de integración real: no alcanza Internet ni Postgres del host)
- [x] 1 lab Docker real (FlagBox, IDOR sobre TCP custom) con cleanup automático — más labs quedan pendientes de contenido, no de infraestructura
- [x] Terminal web integrada para labs (xterm.js + docker exec vía WebSockets, proxy autenticado a través del worker)
```

Remove the now-obsolete pending line about Sub-plan B from wherever it was added at the end of Sub-plan A.

- [ ] **Step 10: Commit**

```bash
git add PROJECT_MASTER_CHECKLIST.md
git commit -m "docs: update checklist — labs terminal (Sub-plan B) complete"
```
