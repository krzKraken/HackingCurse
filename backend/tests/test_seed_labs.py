import os
import tempfile

import yaml

from app.models.content import Concept, Domain, Topic
from app.models.lab import Laboratory, LaboratoryConcept
from scripts.seed_labs import seed_labs

LAB_YAML = {
    "id": "test-lab-001",
    "title": "Test Lab",
    "type": "black_box",
    "difficulty": "beginner",
    "duration_estimate_min": 15,
    "concept_slugs": ["net-01"],
    "docker_build_context": "labs/test-lab",
    "cpu_limit": "0.5",
    "memory_limit_mb": 128,
    "max_lifetime_min": 60,
    "cleanup_remove_volumes": True,
    "hints": [{"level": 1, "text": "hint uno"}],
}


def _seed_concept(db, slug="net-01"):
    domain = Domain(slug="networking", name="Networking")
    db.add(domain)
    db.flush()
    topic = Topic(domain_id=domain.id, slug="fundamentals", name="Fundamentos")
    db.add(topic)
    db.flush()
    concept = Concept(topic_id=topic.id, slug=slug, name=slug)
    db.add(concept)
    db.commit()
    return concept


def _write_labs_dir(tmpdir, data):
    lab_dir = os.path.join(tmpdir, "labs", "test-lab")
    os.makedirs(lab_dir, exist_ok=True)
    with open(os.path.join(lab_dir, "lab.yaml"), "w") as f:
        yaml.safe_dump(data, f)
    return os.path.join(tmpdir, "labs")


def test_seed_labs_creates_laboratory_and_concept_links(db_session):
    _seed_concept(db_session)
    with tempfile.TemporaryDirectory() as tmpdir:
        labs_dir = _write_labs_dir(tmpdir, LAB_YAML)
        seed_labs(labs_dir)

    lab = db_session.query(Laboratory).filter_by(id="test-lab-001").one()
    assert lab.title == "Test Lab"
    assert lab.hints == [{"level": 1, "text": "hint uno"}]
    assert db_session.query(LaboratoryConcept).filter_by(laboratory_id=lab.id).count() == 1


def test_seed_labs_is_idempotent(db_session):
    _seed_concept(db_session)
    with tempfile.TemporaryDirectory() as tmpdir:
        labs_dir = _write_labs_dir(tmpdir, LAB_YAML)
        seed_labs(labs_dir)
        seed_labs(labs_dir)

    assert db_session.query(Laboratory).filter_by(id="test-lab-001").count() == 1
    assert db_session.query(LaboratoryConcept).filter_by(laboratory_id="test-lab-001").count() == 1
