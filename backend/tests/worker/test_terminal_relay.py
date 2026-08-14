import asyncio
import pathlib
import tempfile
import time

import pytest
import websockets

pytestmark = pytest.mark.asyncio


@pytest.fixture
def shell_container():
    from worker import docker_ops

    client = docker_ops.get_client()
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
    import websockets.asyncio.server as ws_server

    import worker.terminal_relay as terminal_relay

    original = terminal_relay.instance_container_id
    terminal_relay.instance_container_id = lambda instance_id: shell_container
    try:
        server = await ws_server.serve(terminal_relay.handler, "127.0.0.1", 0)
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
    import websockets.asyncio.server as ws_server

    import worker.terminal_relay as terminal_relay

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
