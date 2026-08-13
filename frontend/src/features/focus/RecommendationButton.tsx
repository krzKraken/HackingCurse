import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Recommendation } from "../../lib/api";

export function RecommendationButton() {
  const [recommendation, setRecommendation] = useState<Recommendation | null | undefined>(undefined);
  const navigate = useNavigate();

  const handleClick = async () => {
    const rec = await api.getRecommendation(15);
    setRecommendation(rec ?? null);
  };

  const handleStart = () => {
    if (!recommendation) return;
    if (recommendation.activity_type === "learn") {
      navigate(`/lessons/${recommendation.concept_slug}`);
    } else {
      navigate("/review");
    }
    setRecommendation(undefined);
  };

  return (
    <div>
      <button onClick={handleClick}>No sé qué estudiar</button>
      {recommendation === null && <p>Todavía no hay contenido con preguntas para recomendar.</p>}
      {recommendation && (
        <div>
          <p>{recommendation.reason}</p>
          <button onClick={handleStart}>Empezar</button>
        </div>
      )}
    </div>
  );
}
