import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { marked } from "marked";
import { api, ApiError, ConceptDetail, ConceptSummary, LessonContent } from "../../lib/api";
import { NoteEditor } from "../notes/NoteEditor";

const SECTIONS: { key: keyof LessonContent; title: string }[] = [
  { key: "concepto", title: "Concepto" },
  { key: "como_funciona", title: "Cómo funciona internamente" },
  { key: "por_que_importa", title: "Por qué importa en seguridad" },
  { key: "visualizacion", title: "Visualización" },
  { key: "ejemplo", title: "Ejemplo" },
  { key: "comandos", title: "Comandos" },
  { key: "errores_frecuentes", title: "Errores frecuentes" },
  { key: "regla_mental", title: "🧠 Regla mental" },
  { key: "perspectiva_ofensiva", title: "Perspectiva ofensiva" },
  { key: "perspectiva_defensiva", title: "Perspectiva defensiva" },
];

export function LessonPage() {
  const { slug } = useParams<{ slug: string }>();
  const [concept, setConcept] = useState<ConceptDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    setConcept(null);
    setError(null);
    api
      .getConcept(slug)
      .then(setConcept)
      .catch((err) => {
        setError(err instanceof ApiError && err.status === 404 ? "Lección no encontrada" : "Error al cargar");
      });
  }, [slug]);

  if (error) return <p role="alert">{error}</p>;
  if (!concept) return <p>Cargando…</p>;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "2rem" }}>
      <article>
        <h1>{concept.name}</h1>
        {SECTIONS.map(({ key, title }) => {
          const content = concept.lesson?.[key];
          if (!content) return null;
          return (
            <section key={key}>
              <h2>{title}</h2>
              <div dangerouslySetInnerHTML={{ __html: marked.parse(content) as string }} />
            </section>
          );
        })}
        <section>
          <h2>Relaciones</h2>
          <RelationList title="Prerequisitos" items={concept.relationships.prerequisites} />
          <RelationList title="Relacionado" items={concept.relationships.related} />
          <RelationList title="Continúa con" items={concept.relationships.continues_with} />
        </section>
      </article>
      <ConceptNotePanel slug={slug!} />
    </div>
  );
}

function ConceptNotePanel({ slug }: { slug: string }) {
  const [note, setNote] = useState<{ title: string; body_markdown: string } | null>(null);

  useEffect(() => {
    setNote(null);
    api
      .getNoteByConcept(slug)
      .then((n) => setNote({ title: n.title, body_markdown: n.body_markdown }))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setNote({ title: "Mis notas", body_markdown: "" });
        }
      });
  }, [slug]);

  if (!note) return null;

  return (
    <aside>
      <h2>Notas</h2>
      <NoteEditor
        initialTitle={note.title}
        initialBody={note.body_markdown}
        onSave={(title, body) => api.putNoteByConcept(slug, title, body)}
      />
    </aside>
  );
}

function RelationList({ title, items }: { title: string; items: ConceptSummary[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3>{title}</h3>
      <ul>
        {items.map((c) => (
          <li key={c.slug}>
            <Link to={`/lessons/${c.slug}`}>{c.name}</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
