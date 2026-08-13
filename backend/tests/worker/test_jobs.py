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
