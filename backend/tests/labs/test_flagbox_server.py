import asyncio
import importlib.util
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
