from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models.note import Note
from app.models.user import User
from app.notes import service
from app.notes.schemas import NoteOut, NoteWrite

router = APIRouter()


def _to_note_out(note: Note) -> NoteOut:
    return NoteOut(
        id=note.id,
        title=note.title,
        body_markdown=note.body_markdown,
        is_global=note.is_global,
        linked_concept_slug=note.concept.slug if note.concept is not None else None,
        updated_at=note.updated_at,
    )


@router.get("", response_model=list[NoteOut])
def list_notes(db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> list[NoteOut]:
    return [_to_note_out(n) for n in service.list_notes(db)]


@router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NoteWrite, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> NoteOut:
    return _to_note_out(service.create_global_note(db, payload.title, payload.body_markdown))


@router.get("/by-concept/{slug}", response_model=NoteOut)
def get_note_by_concept(
    slug: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> NoteOut:
    note = service.get_note_by_concept_slug(db, slug)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    return _to_note_out(note)


@router.put("/by-concept/{slug}", response_model=NoteOut)
def put_note_by_concept(
    slug: str, payload: NoteWrite, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> NoteOut:
    try:
        note = service.upsert_note_by_concept(db, slug, payload.title, payload.body_markdown)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Concept not found")
    return _to_note_out(note)


@router.get("/{note_id}", response_model=NoteOut)
def get_note(
    note_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> NoteOut:
    note = service.get_note(db, note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    return _to_note_out(note)


@router.put("/{note_id}", response_model=NoteOut)
def put_note(
    note_id: str,
    payload: NoteWrite,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> NoteOut:
    note = service.get_note(db, note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    return _to_note_out(service.update_note(db, note, payload.title, payload.body_markdown))


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> None:
    note = service.get_note(db, note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    service.delete_note(db, note)
