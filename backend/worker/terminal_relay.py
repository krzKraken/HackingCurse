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
