import { forwardRef, useImperativeHandle, useMemo, useRef } from "react";
import ForceGraph2D, { ForceGraphMethods } from "react-force-graph-2d";
import { GraphResponse } from "../../lib/api";

type GraphNodeDatum = {
  id: string;
  slug: string;
  name: string;
  domain_slug: string;
  topic_slug: string;
  mastery_score: number;
  studied: boolean;
  next_due_at: string | null;
  x?: number;
  y?: number;
};

type GraphLinkDatum = {
  source: string;
  target: string;
  type: "prerequisite" | "related" | "continues_with";
};

const EDGE_COLOR: Record<GraphLinkDatum["type"], string> = {
  prerequisite: "#3b82f6",
  continues_with: "#a855f7",
  related: "#9ca3af",
};

function masteryColor(score: number): string {
  const clamped = Math.max(0, Math.min(100, score));
  const hue = (clamped / 100) * 120;
  return `hsl(${hue}, 70%, 45%)`;
}

function nodeFillColor(node: GraphNodeDatum, highlightSlug?: string): string {
  if (node.slug === highlightSlug) return "#facc15";
  return node.studied ? masteryColor(node.mastery_score) : "#888888";
}

export type KnowledgeGraphHandle = {
  centerOnNode: (slug: string) => void;
};

type KnowledgeGraphProps = {
  data: GraphResponse;
  height: number;
  interactive: boolean;
  highlightSlug?: string;
  onNodeClick: (slug: string) => void;
};

export const KnowledgeGraph = forwardRef<KnowledgeGraphHandle, KnowledgeGraphProps>(
  function KnowledgeGraph({ data, height, interactive, highlightSlug, onNodeClick }, ref) {
    const graphRef = useRef<ForceGraphMethods>();

    const graphData = useMemo(
      () => ({
        nodes: data.nodes.map((n) => ({ ...n, id: n.slug })) as GraphNodeDatum[],
        links: data.edges.map((e) => ({
          source: e.source_slug,
          target: e.target_slug,
          type: e.type,
        })) as GraphLinkDatum[],
      }),
      [data]
    );

    useImperativeHandle(ref, () => ({
      centerOnNode: (slug: string) => {
        const node = graphData.nodes.find((n) => n.id === slug);
        if (node && graphRef.current && node.x !== undefined && node.y !== undefined) {
          graphRef.current.centerAt(node.x, node.y, 600);
          graphRef.current.zoom(4, 600);
        }
      },
    }));

    return (
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        height={height}
        nodeId="id"
        nodeLabel={(node) => {
          const n = node as GraphNodeDatum;
          const masteryLine = n.studied ? `Mastery: ${n.mastery_score.toFixed(0)}%` : "No estudiado";
          const dueLine = n.next_due_at
            ? `<br/>Próximo repaso: ${new Date(n.next_due_at).toLocaleDateString()}`
            : "";
          return `<div><strong>${n.name}</strong><br/>${masteryLine}${dueLine}</div>`;
        }}
        nodeColor={(node) => nodeFillColor(node as GraphNodeDatum, highlightSlug)}
        enableNodeDrag={interactive}
        linkColor={(link) => EDGE_COLOR[(link as GraphLinkDatum).type]}
        linkDirectionalArrowLength={(link) => ((link as GraphLinkDatum).type === "related" ? 0 : 6)}
        linkDirectionalArrowRelPos={1}
        linkLineDash={(link) => ((link as GraphLinkDatum).type === "continues_with" ? [2, 2] : null)}
        onNodeClick={(node) => onNodeClick((node as GraphNodeDatum).slug)}
      />
    );
  }
);
