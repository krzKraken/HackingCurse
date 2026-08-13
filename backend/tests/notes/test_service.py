import pytest

from app.models.content import Concept, Domain, Topic
from app.models.note import Note, NoteLink
from app.notes import service


def _seed_concept(db, slug="net-01", name="Fundamentos de Redes"):
    domain = Domain(slug="networking", name="Networking")
    db.add(domain)
    db.flush()
    topic = Topic(domain_id=domain.id, slug="fundamentals", name="Fundamentos")
    db.add(topic)
    db.flush()
    concept = Concept(topic_id=topic.id, slug=slug, name=name)
    db.add(concept)
    db.commit()
    return concept


def test_upsert_note_by_concept_creates_then_updates(db_session):
    concept = _seed_concept(db_session)

    note = service.upsert_note_by_concept(db_session, concept.slug, "Mis notas", "primer contenido")
    assert note.linked_concept_id == concept.id
    assert db_session.query(Note).filter_by(linked_concept_id=concept.id).count() == 1

    note2 = service.upsert_note_by_concept(db_session, concept.slug, "Mis notas", "contenido actualizado")
    assert note2.id == note.id
    assert note2.body_markdown == "contenido actualizado"
    assert db_session.query(Note).filter_by(linked_concept_id=concept.id).count() == 1


def test_upsert_note_by_concept_raises_for_unknown_slug(db_session):
    with pytest.raises(ValueError):
        service.upsert_note_by_concept(db_session, "does-not-exist", "t", "b")


def test_wikilink_resolves_to_concept(db_session):
    concept = _seed_concept(db_session)

    note = service.create_global_note(db_session, "Nota libre", f"Repasar [[{concept.slug}]] pronto")

    links = db_session.query(NoteLink).filter_by(source_note_id=note.id).all()
    assert len(links) == 1
    assert links[0].target_concept_id == concept.id
    assert links[0].target_note_id is None


def test_wikilink_resolves_to_another_note(db_session):
    target = service.create_global_note(db_session, "Objetivo", "cuerpo")
    source = service.create_global_note(db_session, "Origen", "Ver [[Objetivo]] para más detalle")

    links = db_session.query(NoteLink).filter_by(source_note_id=source.id).all()
    assert len(links) == 1
    assert links[0].target_note_id == target.id
    assert links[0].target_concept_id is None


def test_wikilink_unresolved_is_stored_without_target(db_session):
    note = service.create_global_note(db_session, "Nota", "Ver [[algo-que-no-existe]]")

    links = db_session.query(NoteLink).filter_by(source_note_id=note.id).all()
    assert len(links) == 1
    assert links[0].target_concept_id is None
    assert links[0].target_note_id is None


def test_update_note_recalculates_links(db_session):
    concept = _seed_concept(db_session)
    note = service.create_global_note(db_session, "Nota", "sin links")
    assert db_session.query(NoteLink).filter_by(source_note_id=note.id).count() == 0

    service.update_note(db_session, note, "Nota", f"ahora sí [[{concept.slug}]]")

    links = db_session.query(NoteLink).filter_by(source_note_id=note.id).all()
    assert len(links) == 1
    assert links[0].target_concept_id == concept.id


def test_delete_note(db_session):
    note = service.create_global_note(db_session, "Nota", "cuerpo")
    service.delete_note(db_session, note)
    assert service.get_note(db_session, note.id) is None
