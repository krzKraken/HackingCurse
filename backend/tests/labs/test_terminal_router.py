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
            collected = b""
            for _ in range(20):
                message = ws.receive()
                chunk = message.get("bytes") or message.get("text")
                if chunk is not None:
                    collected += chunk if isinstance(chunk, bytes) else chunk.encode()
                if b"hola" in collected:
                    break
            assert b"hola" in collected
    finally:
        app_settings.labs_terminal_relay_port = original_port
        container.remove(force=True)
