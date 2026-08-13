import { useState } from "react";
import { api, AnswerResult, ReviewItemPrompt } from "../../lib/api";

type Mode = "general" | "debilidades" | "olvidado" | "por_tema" | "mixto" | "sorpresa" | "pre_lab";
type Outcome = "correct" | "partial" | "incorrect";

const MODES: { value: Mode; label: string }[] = [
  { value: "general", label: "General" },
  { value: "debilidades", label: "Debilidades" },
  { value: "olvidado", label: "Olvidado" },
  { value: "por_tema", label: "Por tema" },
  { value: "mixto", label: "Mixto" },
  { value: "sorpresa", label: "Sorpresa" },
  { value: "pre_lab", label: "Antes de laboratorio" },
];

const CONFIDENCE_OPTIONS = ["nada_seguro", "poco_seguro", "seguro", "muy_seguro"] as const;

export function ReviewPage() {
  const [mode, setMode] = useState<Mode>("general");
  const [budgetCount, setBudgetCount] = useState(5);
  const [items, setItems] = useState<ReviewItemPrompt[] | null>(null);
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<Outcome[]>([]);

  const handleStart = async () => {
    const session = await api.createReviewSession({ mode, budget_count: budgetCount });
    setItems(session.items);
    setIndex(0);
    setResults([]);
  };

  const handleDone = (outcome: Outcome) => {
    setResults((r) => [...r, outcome]);
    setIndex((i) => i + 1);
  };

  if (!items) {
    return (
      <div>
        <h1>Repasar</h1>
        <div>
          {MODES.map((m) => (
            <label key={m.value}>
              <input type="radio" name="mode" checked={mode === m.value} onChange={() => setMode(m.value)} />
              {m.label}
            </label>
          ))}
        </div>
        <label>
          Cantidad de preguntas:
          <input
            type="number"
            value={budgetCount}
            onChange={(e) => setBudgetCount(Number(e.target.value))}
            min={1}
            max={20}
          />
        </label>
        <button onClick={handleStart}>Empezar</button>
      </div>
    );
  }

  if (index >= items.length) {
    const correct = results.filter((r) => r === "correct").length;
    const partial = results.filter((r) => r === "partial").length;
    const incorrect = results.filter((r) => r === "incorrect").length;
    return (
      <div>
        <h1>Resumen</h1>
        <p>
          {correct} de {items.length} correctas ({partial} parciales, {incorrect} incorrectas)
        </p>
        <button onClick={() => setItems(null)}>Repasar de nuevo</button>
      </div>
    );
  }

  return <ReviewItemView key={items[index].item_id} item={items[index]} onDone={handleDone} />;
}

function ReviewItemView({ item, onDone }: { item: ReviewItemPrompt; onDone: (outcome: Outcome) => void }) {
  const [response, setResponse] = useState("");
  const [confidence, setConfidence] = useState<string | undefined>(undefined);
  const [feedback, setFeedback] = useState<AnswerResult | null>(null);

  const handleSubmit = async () => {
    const result = await api.answerReviewItem(item.item_id, response, confidence);
    setFeedback(result);
  };

  const handleSelfRate = async (outcome: Outcome) => {
    await api.selfRateReviewItem(item.item_id, outcome);
    onDone(outcome);
  };

  return (
    <div>
      <p>{item.concept_slug}</p>
      <div>{item.prompt_markdown}</div>

      {!feedback && (
        <>
          <div>
            {CONFIDENCE_OPTIONS.map((c) => (
              <label key={c}>
                <input
                  type="radio"
                  name="confidence"
                  checked={confidence === c}
                  onChange={() => setConfidence(c)}
                />
                {c}
              </label>
            ))}
          </div>

          {item.type === "multiple_choice" && item.options && (
            <div>
              {item.options.map((opt, i) => (
                <label key={i}>
                  <input
                    type="radio"
                    name="response"
                    checked={response === String(i)}
                    onChange={() => setResponse(String(i))}
                  />
                  {opt}
                </label>
              ))}
            </div>
          )}

          {item.type === "true_false" && (
            <div>
              <label>
                <input
                  type="radio"
                  name="response"
                  checked={response === "true"}
                  onChange={() => setResponse("true")}
                />
                Verdadero
              </label>
              <label>
                <input
                  type="radio"
                  name="response"
                  checked={response === "false"}
                  onChange={() => setResponse("false")}
                />
                Falso
              </label>
            </div>
          )}

          {item.type === "free_explanation" && (
            <textarea value={response} onChange={(e) => setResponse(e.target.value)} rows={6} />
          )}

          <button onClick={handleSubmit}>Responder</button>
        </>
      )}

      {feedback && item.type !== "free_explanation" && (
        <div>
          <p>{feedback.outcome === "correct" ? "¡Correcto!" : "Incorrecto"}</p>
          <button onClick={() => onDone(feedback.outcome as Outcome)}>Siguiente</button>
        </div>
      )}

      {feedback && item.type === "free_explanation" && (
        <div>
          <p>Criterios: {feedback.evaluation_criteria}</p>
          <p>Respuesta esperada: {feedback.expected_answer}</p>
          <p>¿Cómo calificas tu respuesta?</p>
          <button onClick={() => handleSelfRate("correct")}>Correcto</button>
          <button onClick={() => handleSelfRate("partial")}>Parcial</button>
          <button onClick={() => handleSelfRate("incorrect")}>Incorrecto</button>
        </div>
      )}
    </div>
  );
}
