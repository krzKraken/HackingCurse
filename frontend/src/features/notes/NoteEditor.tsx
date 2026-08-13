import { useEffect, useRef, useState } from "react";
import { marked } from "marked";

type NoteEditorProps = {
  initialTitle: string;
  initialBody: string;
  onSave: (title: string, body: string) => Promise<unknown>;
};

export function NoteEditor({ initialTitle, initialBody, onSave }: NoteEditorProps) {
  const [title, setTitle] = useState(initialTitle);
  const [body, setBody] = useState(initialBody);
  const [status, setStatus] = useState<"idle" | "saving" | "saved">("idle");
  const isFirstRun = useRef(true);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setTitle(initialTitle);
    setBody(initialBody);
    isFirstRun.current = true;
  }, [initialTitle, initialBody]);

  useEffect(() => {
    if (isFirstRun.current) {
      isFirstRun.current = false;
      return;
    }
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      setStatus("saving");
      onSave(title, body).then(() => setStatus("saved"));
    }, 1500);
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, body]);

  return (
    <div>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Título"
        aria-label="Título de la nota"
      />
      <span aria-live="polite">{status === "saving" ? "Guardando…" : status === "saved" ? "Guardado" : ""}</span>
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={12}
        placeholder="Escribe en Markdown… usa [[concepto]] para enlazar"
      />
      <div dangerouslySetInnerHTML={{ __html: marked.parse(body) as string }} />
    </div>
  );
}
