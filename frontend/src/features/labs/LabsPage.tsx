import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Laboratory } from "../../lib/api";

export function LabsPage() {
  const [labs, setLabs] = useState<Laboratory[] | null>(null);

  useEffect(() => {
    api.listLabs().then(setLabs);
  }, []);

  if (!labs) return <p>Cargando…</p>;

  return (
    <div>
      <h1>Laboratorios</h1>
      <ul>
        {labs.map((lab) => (
          <li key={lab.id}>
            <Link to={`/labs/${lab.id}`}>{lab.title}</Link> — {lab.difficulty}, ~{lab.duration_estimate_min} min
          </li>
        ))}
      </ul>
    </div>
  );
}
