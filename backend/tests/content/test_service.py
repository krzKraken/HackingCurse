from app.content.service import get_concept_detail, get_domains_tree
from app.models.content import Concept, ConceptRelationship, Domain, Lesson, RelationshipType, Topic


def _seed_minimal(db):
    domain = Domain(slug="networking", name="Networking")
    db.add(domain)
    db.flush()

    topic = Topic(domain_id=domain.id, slug="fundamentals", name="Fundamentos")
    db.add(topic)
    db.flush()

    prereq = Concept(topic_id=topic.id, slug="net-01", name="Fundamentos de Redes")
    concept = Concept(topic_id=topic.id, slug="net-02", name="Ethernet, MAC y ARP")
    db.add_all([prereq, concept])
    db.flush()

    lesson = Lesson(concept_id=concept.id, concepto="Un protocolo...", regla_mental="MAC = a quien se lo entrego.")
    db.add(lesson)

    db.add(ConceptRelationship(source_id=concept.id, target_id=prereq.id, type=RelationshipType.prerequisite))
    db.commit()
    return domain, topic, prereq, concept


def test_get_domains_tree_returns_nested_structure(db_session):
    _seed_minimal(db_session)

    domains = get_domains_tree(db_session)

    assert len(domains) == 1
    assert domains[0].slug == "networking"
    assert len(domains[0].topics) == 1
    assert domains[0].topics[0].slug == "fundamentals"
    slugs = {c.slug for c in domains[0].topics[0].concepts}
    assert slugs == {"net-01", "net-02"}


def test_get_concept_detail_includes_lesson_and_relationships(db_session):
    _seed_minimal(db_session)

    detail = get_concept_detail(db_session, "net-02")

    assert detail is not None
    assert detail.name == "Ethernet, MAC y ARP"
    assert detail.lesson.concepto == "Un protocolo..."
    assert detail.lesson.regla_mental == "MAC = a quien se lo entrego."
    assert [p.slug for p in detail.relationships.prerequisites] == ["net-01"]
    assert detail.relationships.related == []
    assert detail.relationships.continues_with == []


def test_get_concept_detail_returns_none_for_unknown_slug(db_session):
    assert get_concept_detail(db_session, "does-not-exist") is None
