import os
import tempfile

import yaml

from app.models.content import Concept, ConceptRelationship, Domain, Lesson, Topic
from scripts.seed_content import seed_content

NET_01 = {
    "domain": {"slug": "networking", "name": "Networking"},
    "topic": {"slug": "fundamentals", "name": "Fundamentos"},
    "concept": {"slug": "net-01", "name": "Fundamentos de Redes"},
    "lesson": {"concepto": "Una red es...", "regla_mental": "Regla 1"},
    "relationships": [],
}

NET_02 = {
    "domain": {"slug": "networking", "name": "Networking"},
    "topic": {"slug": "fundamentals", "name": "Fundamentos"},
    "concept": {"slug": "net-02", "name": "Ethernet, MAC y ARP"},
    "lesson": {"concepto": "ARP es...", "regla_mental": "Regla 2"},
    "relationships": [{"type": "prerequisite", "target_slug": "net-01"}],
}


def _write_content_dir(tmpdir, files: dict[str, dict]) -> str:
    content_dir = os.path.join(tmpdir, "content", "networking")
    os.makedirs(content_dir, exist_ok=True)
    for filename, data in files.items():
        with open(os.path.join(content_dir, filename), "w") as f:
            yaml.safe_dump(data, f)
    return os.path.join(tmpdir, "content")


def test_seed_content_creates_concepts_lessons_and_relationships(db_session):
    with tempfile.TemporaryDirectory() as tmpdir:
        content_dir = _write_content_dir(tmpdir, {"net-01.yaml": NET_01, "net-02.yaml": NET_02})
        seed_content(content_dir)

    assert db_session.query(Domain).filter_by(slug="networking").count() == 1
    assert db_session.query(Topic).filter_by(slug="fundamentals").count() == 1
    net01 = db_session.query(Concept).filter_by(slug="net-01").one()
    net02 = db_session.query(Concept).filter_by(slug="net-02").one()
    assert db_session.query(Lesson).filter_by(concept_id=net02.id).one().regla_mental == "Regla 2"

    rel = db_session.query(ConceptRelationship).filter_by(source_id=net02.id, target_id=net01.id).one()
    assert rel.type.value == "prerequisite"


def test_seed_content_is_idempotent(db_session):
    with tempfile.TemporaryDirectory() as tmpdir:
        content_dir = _write_content_dir(tmpdir, {"net-01.yaml": NET_01, "net-02.yaml": NET_02})
        seed_content(content_dir)
        seed_content(content_dir)

    assert db_session.query(Concept).filter_by(slug="net-01").count() == 1
    assert db_session.query(Concept).filter_by(slug="net-02").count() == 1
    assert db_session.query(ConceptRelationship).count() == 1
