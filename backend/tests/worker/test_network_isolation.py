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
