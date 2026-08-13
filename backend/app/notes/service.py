import re
import uuid

from sqlalchemy.orm import Session

from app.models.content import Concept
from app.models.note import Note, NoteLink

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _resolve_links(db: Session, note: Note) -> None:
    db.query(NoteLink).filter(NoteLink.source_note_id == note.id).delete()

    for match in WIKILINK_RE.finditer(note.body_markdown):
        link_text = match.group(1).strip()

        concept = (
            db.query(Concept)
            .filter((Concept.slug == link_text) | (Concept.name.ilike(link_text)))
            .first()
        )

        target_note = None
        if concept is None:
            target_note = (
                db.query(Note)
                .filter(Note.title.ilike(link_text), Note.id != note.id)
                .first()
            )

        db.add(
            NoteLink(
                source_note_id=note.id,
                target_concept_id=concept.id if concept else None,
                target_note_id=target_note.id if target_note else None,
                link_text=link_text,
            )
        )


def list_notes(db: Session) -> list[Note]:
    return db.query(Note).order_by(Note.updated_at.desc()).all()


def get_note(db: Session, note_id: uuid.UUID | str) -> Note | None:
    return db.query(Note).filter(Note.id == note_id).first()


def get_note_by_concept_slug(db: Session, slug: str) -> Note | None:
    return (
        db.query(Note)
        .join(Concept, Note.linked_concept_id == Concept.id)
        .filter(Concept.slug == slug)
        .first()
    )


def create_global_note(db: Session, title: str, body_markdown: str) -> Note:
    note = Note(title=title, body_markdown=body_markdown, is_global=True)
    db.add(note)
    db.flush()
    _resolve_links(db, note)
    db.commit()
    db.refresh(note)
    return note


def update_note(db: Session, note: Note, title: str, body_markdown: str) -> Note:
    note.title = title
    note.body_markdown = body_markdown
    db.flush()
    _resolve_links(db, note)
    db.commit()
    db.refresh(note)
    return note


def delete_note(db: Session, note: Note) -> None:
    db.delete(note)
    db.commit()


def upsert_note_by_concept(db: Session, slug: str, title: str, body_markdown: str) -> Note:
    concept = db.query(Concept).filter(Concept.slug == slug).first()
    if concept is None:
        raise ValueError(f"unknown concept slug: {slug}")

    note = db.query(Note).filter(Note.linked_concept_id == concept.id).first()
    if note is None:
        note = Note(
            title=title, body_markdown=body_markdown, is_global=False, linked_concept_id=concept.id
        )
        db.add(note)
    else:
        note.title = title
        note.body_markdown = body_markdown

    db.flush()
    _resolve_links(db, note)
    db.commit()
    db.refresh(note)
    return note
