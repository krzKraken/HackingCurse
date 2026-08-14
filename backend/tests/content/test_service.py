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


from app.content.service import get_knowledge_graph
from app.content.schemas import GraphEdge
from app.models.mastery import ConceptMastery
from app.models.user import User


def _seed_user(db):
    user = User(username="owner", password_hash="x", totp_secret="x")
    db.add(user)
    db.commit()
    return user


def test_get_knowledge_graph_includes_all_concepts_and_relationships(db_session):
    _seed_minimal(db_session)
    user = _seed_user(db_session)

    graph = get_knowledge_graph(db_session, user.id)

    assert {n.slug for n in graph.nodes} == {"net-01", "net-02"}
    assert all(n.studied is False for n in graph.nodes)
    assert all(n.mastery_score == 0.0 for n in graph.nodes)
    assert all(n.next_due_at is None for n in graph.nodes)
    assert graph.edges == [GraphEdge(source_slug="net-02", target_slug="net-01", type="prerequisite")]


def test_get_knowledge_graph_reflects_user_mastery(db_session):
    _, _, _, concept = _seed_minimal(db_session)
    user = _seed_user(db_session)
    db_session.add(ConceptMastery(user_id=user.id, concept_id=concept.id, mastery_score=75.0))
    db_session.commit()

    graph = get_knowledge_graph(db_session, user.id)

    node = next(n for n in graph.nodes if n.slug == "net-02")
    assert node.studied is True
    assert node.mastery_score == 75.0

    other_node = next(n for n in graph.nodes if n.slug == "net-01")
    assert other_node.studied is False


def test_get_knowledge_graph_handles_concept_without_relationships(db_session):
    from app.models.content import Concept, Domain, Topic

    domain = Domain(slug="crypto", name="Criptografía")
    db_session.add(domain)
    db_session.flush()
    topic = Topic(domain_id=domain.id, slug="basics", name="Basics")
    db_session.add(topic)
    db_session.flush()
    db_session.add(Concept(topic_id=topic.id, slug="crypto-01", name="Cifrado simétrico"))
    db_session.commit()
    user = _seed_user(db_session)

    graph = get_knowledge_graph(db_session, user.id)

    assert len(graph.nodes) == 1
    node = graph.nodes[0]
    assert node.slug == "crypto-01"
    assert node.domain_slug == "crypto"
    assert node.topic_slug == "basics"
    assert graph.edges == []
