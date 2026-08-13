import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, Note } from "../../lib/api";

export function NotesPage() {
  const [notes, setNotes] = useState<Note[] | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.listNotes().then(setNotes);
  }, []);

  const handleCreate = async () => {
    const note = await api.createNote("Nueva nota", "");
    navigate(`/notes/${note.id}`);
  };

  if (!notes) return <p>Cargando…</p>;

  return (
    <div>
      <h1>Notas</h1>
      <button onClick={handleCreate}>Nueva nota</button>
      <ul>
        {notes.map((n) => (
          <li key={n.id}>
            {n.is_global ? (
              <Link to={`/notes/${n.id}`}>{n.title}</Link>
            ) : (
              <span>
                {n.title} — <Link to={`/lessons/${n.linked_concept_slug}`}>ver lección</Link>
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
