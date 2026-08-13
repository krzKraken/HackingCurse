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
    (`-p`/`ports=`) on a container whose only network is `internal=True` —
    "there is no meaningful action" from Docker's point of view, since an
    internal network has no external connectivity by definition. See
    `start_port_relay` for how the host actually becomes reachable without
    weakening that isolation.
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
    network is still reachable from outside. The Docker HOST can always
    reach into a bridge network it created (it owns the bridge interface)
    even when that network is internal — `internal=True` only removes the
    *container's* outbound route, not the host's inbound one. Returns
    (host_port, relay_pid).
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
