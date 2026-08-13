import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, Note } from "../../lib/api";
import { NoteEditor } from "./NoteEditor";

export function NoteDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [note, setNote] = useState<Note | null>(null);

  useEffect(() => {
    if (!id) return;
    api.getNote(id).then(setNote);
  }, [id]);

  if (!note) return <p>Cargando…</p>;

  return (
    <NoteEditor
      initialTitle={note.title}
      initialBody={note.body_markdown}
      onSave={(title, body) => api.updateNote(note.id, title, body)}
    />
  );
}
