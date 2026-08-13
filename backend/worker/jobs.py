from datetime import datetime, timezone

from app.db import SessionLocal
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
