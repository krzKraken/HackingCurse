import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, LabInstance } from "../../lib/api";
import { LabTerminal } from "./LabTerminal";

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATUSES = new Set(["running", "destroyed", "expired", "failed"]);

export function LabInstancePage() {
  const { labId } = useParams<{ labId: string }>();
  const [instance, setInstance] = useState<LabInstance | null>(null);
  const [hintText, setHintText] = useState<string | null>(null);
  const [flag, setFlag] = useState("");
  const [submitResult, setSubmitResult] = useState<string | null>(null);
  const [showTerminal, setShowTerminal] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!labId) return;
    api.createLabInstance(labId).then(setInstance);
  }, [labId]);

  useEffect(() => {
    if (!instance || TERMINAL_STATUSES.has(instance.status)) return;
    pollRef.current = setInterval(() => {
      api.getLabInstance(instance.id).then(setInstance);
    }, POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [instance]);

  const handleHint = async (level: number) => {
    const hint = await api.getLabHint(instance!.id, level);
    setHintText(hint.text);
  };

  const handleSubmit = async () => {
    const result = await api.submitLabFlag(instance!.id, flag);
    setSubmitResult(result.correct ? "¡Correcto!" : "Incorrecto, sigue intentando.");
    if (result.solved) {
      setInstance(await api.getLabInstance(instance!.id));
    }
  };

  const handleReset = async () => {
    const refreshed = await api.resetLabInstance(instance!.id);
    setInstance(refreshed);
    setSubmitResult(null);
    setHintText(null);
  };

  if (!instance) return <p>Creando instancia…</p>;

  return (
    <div>
      <h1>Laboratorio</h1>
      <p>Estado: {instance.status}</p>

      {instance.status === "running" && instance.host_port && (
        <p>
          Conéctate con: <code>nc localhost {instance.host_port}</code>
        </p>
      )}

      {instance.status === "running" && (
        <div>
          <button onClick={() => setShowTerminal((v) => !v)}>
            {showTerminal ? "Cerrar terminal" : "Abrir terminal"}
          </button>
          {showTerminal && <LabTerminal instanceId={instance.id} />}
        </div>
      )}

      <div>
        <button onClick={() => handleHint(1)}>Hint 1</button>
        <button onClick={() => handleHint(2)}>Hint 2</button>
        <button onClick={() => handleHint(3)}>Hint 3</button>
        <button onClick={() => handleHint(4)}>Hint 4</button>
      </div>
      {hintText && <p>{hintText}</p>}

      <div>
        <input value={flag} onChange={(e) => setFlag(e.target.value)} placeholder="FLAG{...}" />
        <button onClick={handleSubmit}>Enviar flag</button>
      </div>
      {submitResult && <p>{submitResult}</p>}
      {instance.solved && <p>¡Laboratorio resuelto!</p>}

      <button onClick={handleReset}>Reset</button>
    </div>
  );
}
