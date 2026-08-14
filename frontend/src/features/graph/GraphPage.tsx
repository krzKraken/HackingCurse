import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, GraphResponse } from "../../lib/api";
import { KnowledgeGraph, KnowledgeGraphHandle } from "./KnowledgeGraph";

function filterGraphByDomains(data: GraphResponse, selectedDomains: Set<string>): GraphResponse {
  const nodes = data.nodes.filter((n) => selectedDomains.has(n.domain_slug));
  const nodeSlugs = new Set(nodes.map((n) => n.slug));
  const edges = data.edges.filter((e) => nodeSlugs.has(e.source_slug) && nodeSlugs.has(e.target_slug));
  return { nodes, edges };
}

export function GraphPage() {
  const navigate = useNavigate();
  const graphRef = useRef<KnowledgeGraphHandle>(null);
  const [data, setData] = useState<GraphResponse | null>(null);
  const [selectedDomains, setSelectedDomains] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [highlightSlug, setHighlightSlug] = useState<string | undefined>(undefined);
  const [searchNotFound, setSearchNotFound] = useState(false);
  const [viewportHeight, setViewportHeight] = useState(window.innerHeight);

  useEffect(() => {
    api.getKnowledgeGraph().then((graph) => {
      setData(graph);
      setSelectedDomains(new Set(graph.nodes.map((n) => n.domain_slug)));
    });
  }, []);

  useEffect(() => {
    function handleResize() {
      setViewportHeight(window.innerHeight);
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const domains = useMemo(
    () => Array.from(new Set((data?.nodes ?? []).map((n) => n.domain_slug))).sort(),
    [data]
  );

  const filtered = useMemo(
    () => (data ? filterGraphByDomains(data, selectedDomains) : null),
    [data, selectedDomains]
  );

  function toggleDomain(domain: string) {
    setSelectedDomains((prev) => {
      const next = new Set(prev);
      if (next.has(domain)) next.delete(domain);
      else next.add(domain);
      return next;
    });
  }

  function handleSearch(e: FormEvent) {
    e.preventDefault();
    const match = filtered?.nodes.find((n) => n.name.toLowerCase().includes(search.toLowerCase()));
    if (match) {
      setHighlightSlug(match.slug);
      setSearchNotFound(false);
      graphRef.current?.centerOnNode(match.slug);
    } else {
      setSearchNotFound(true);
    }
  }

  if (!data || !filtered) return <p>Cargando…</p>;

  if (data.nodes.length === 0) {
    return <p>Todavía no hay contenido para mostrar.</p>;
  }

  return (
    <div style={{ display: "flex", height: "calc(100vh - 40px)" }}>
      <aside style={{ width: 220, padding: 16, overflowY: "auto", flexShrink: 0 }}>
        <h2>Dominios</h2>
        {domains.map((domain) => (
          <label key={domain} style={{ display: "block" }}>
            <input type="checkbox" checked={selectedDomains.has(domain)} onChange={() => toggleDomain(domain)} />
            {" "}
            {domain}
          </label>
        ))}
        <form onSubmit={handleSearch} style={{ marginTop: 16 }}>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar concepto…"
          />
          <button type="submit">Buscar</button>
        </form>
        {searchNotFound && <p>No se encontró ningún concepto.</p>}
      </aside>
      <div style={{ flex: 1, minWidth: 0 }}>
        {filtered.nodes.length === 0 ? (
          <p>Ningún concepto coincide con el filtro.</p>
        ) : (
          <KnowledgeGraph
            ref={graphRef}
            data={filtered}
            height={viewportHeight - 40}
            interactive={true}
            highlightSlug={highlightSlug}
            onNodeClick={(slug) => navigate(`/lessons/${slug}`)}
          />
        )}
      </div>
    </div>
  );
}
