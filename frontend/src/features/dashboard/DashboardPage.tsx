import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, DashboardSummary, GraphResponse } from "../../lib/api";
import { KnowledgeGraph } from "../graph/KnowledgeGraph";

const COMING_SOON = [
  "Fragmentación",
  "Error Memory",
  "Labs recomendados",
  "Tiempo de práctica",
  "Transfer / Methodology Score",
];

export function DashboardPage() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);

  useEffect(() => {
    api.getDashboardSummary().then(setSummary);
    api.getKnowledgeGraph().then(setGraph);
  }, []);

  if (!summary) return <p>Cargando…</p>;

  return (
    <div>
      <h1>Dashboard</h1>

      <section>
        <h2>Nivel global</h2>
        <p>{summary.global_mastery.toFixed(0)}%</p>
      </section>

      <section>
        <h2>Nivel por dominio</h2>
        <ul>
          {summary.domains.map((d) => (
            <li key={d.slug}>
              {d.name}: {d.mastery_percent.toFixed(0)}% ({d.studied_count}/{d.total_count} conceptos estudiados)
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Repasos vencidos</h2>
        <p>
          {summary.reviews_due_count} <Link to="/review">Repasar ahora</Link>
        </p>
        <ul>
          {summary.overdue_concepts.map((c) => (
            <li key={c.slug}>
              <Link to={`/lessons/${c.slug}`}>{c.name}</Link>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Conceptos débiles</h2>
        <ul>
          {summary.weak_concepts.map((c) => (
            <li key={c.slug}>
              <Link to={`/lessons/${c.slug}`}>{c.name}</Link> — {c.mastery_score.toFixed(0)}%
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Últimos repasos</h2>
        <ul>
          {summary.recent_activity.map((a, i) => (
            <li key={i}>
              {a.concept_name} — {a.outcome} ({new Date(a.answered_at).toLocaleString()})
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Uso de pistas en labs</h2>
        {summary.independence_score === null ? (
          <p>Todavía no resolviste ningún lab.</p>
        ) : (
          <>
            <p>Independence Score: {summary.independence_score.toFixed(0)}%</p>
            <ul>
              {Object.entries(summary.hint_dependency)
                .sort(([a], [b]) => Number(a) - Number(b))
                .map(([level, count]) => (
                  <li key={level}>
                    {level === "0" ? "Sin pistas" : `Pista ${level}`}: {count}
                  </li>
                ))}
            </ul>
          </>
        )}
      </section>

      <section>
        <h2>Logros</h2>
        <p>
          Nivel {summary.level} — {summary.xp_total} XP
        </p>
        {summary.achievements.length === 0 ? (
          <p>Todavía no desbloqueaste ningún logro.</p>
        ) : (
          <ul>
            {summary.achievements.map((a) => (
              <li key={a.key}>
                <strong>{a.title}</strong> — {a.description} ({new Date(a.unlocked_at).toLocaleDateString()})
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2>Knowledge Graph</h2>
        {graph === null ? (
          <p>Cargando…</p>
        ) : graph.nodes.length === 0 ? (
          <p>Todavía no hay contenido para mostrar.</p>
        ) : (
          <>
            <KnowledgeGraph
              data={graph}
              height={300}
              interactive={false}
              onNodeClick={(slug) => navigate(`/lessons/${slug}`)}
            />
            <p>
              <Link to="/graph">Ver grafo completo</Link>
            </p>
          </>
        )}
      </section>

      <section>
        <h2>Próximamente</h2>
        <ul>
          {COMING_SOON.map((label) => (
            <li key={label} style={{ opacity: 0.5 }}>
              {label}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
