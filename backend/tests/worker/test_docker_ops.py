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
