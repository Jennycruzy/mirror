"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchJson } from "../lib/api";
import type { LineageGraph, LineageNode } from "../lib/types";

const colors: Record<string, string> = {
  "red-a": "#f59e0b",
  "red-b": "#2dd4bf",
  "red-c": "#a78bfa",
  "red-d": "#fb7185"
};

export function PhylogeneticTree() {
  const [graph, setGraph] = useState<LineageGraph>({ nodes: [], edges: [] });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<LineageGraph>("/lineage").then(setGraph).catch((err) => setError(err.message));
  }, []);

  const positions = useMemo(() => layoutNodes(graph.nodes), [graph.nodes]);

  if (error) {
    return <div className="rounded-2xl border border-rose-500/40 bg-rose-950/30 p-6 text-rose-200">{error}</div>;
  }
  if (graph.nodes.length === 0) {
    return <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 text-slate-400">No lineage nodes stored yet.</div>;
  }

  return (
    <section className="overflow-auto rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
      <svg width="960" height="520" role="img" aria-label="MIRROR lineage graph">
        {graph.edges.map((edge) => {
          const source = positions.get(edge.source);
          const target = positions.get(edge.target);
          if (!source || !target) return null;
          return (
            <line
              key={`${edge.source}-${edge.target}-${edge.type}`}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              stroke={edge.type === "crossover" ? "#94a3b8" : "#475569"}
              strokeWidth={2}
              strokeDasharray={edge.type === "crossover" ? "7 7" : undefined}
            />
          );
        })}
        {graph.nodes.map((node) => {
          const position = positions.get(node.id);
          if (!position) return null;
          return (
            <g key={node.id} transform={`translate(${position.x}, ${position.y})`}>
              <circle r="26" fill={colors[node.lineage] ?? "#64748b"} fillOpacity="0.2" stroke={colors[node.lineage] ?? "#64748b"} strokeWidth="2" />
              <text y="-4" textAnchor="middle" fill="#e2e8f0" fontSize="12" fontWeight="700">
                {node.lineage.toUpperCase()}
              </text>
              <text y="12" textAnchor="middle" fill="#cbd5e1" fontSize="11">
                v{node.version}
              </text>
              <text y="44" textAnchor="middle" fill="#94a3b8" fontSize="10">
                {node.token_id ? `#${node.token_id}` : "unminted"}
              </text>
            </g>
          );
        })}
      </svg>
    </section>
  );
}

function layoutNodes(nodes: LineageNode[]) {
  const order = ["red-a", "red-b", "red-c", "red-d"];
  const grouped = new Map<string, LineageNode[]>();
  for (const node of nodes) {
    grouped.set(node.lineage, [...(grouped.get(node.lineage) ?? []), node]);
  }
  const positions = new Map<string, { x: number; y: number }>();
  for (const [row, lineage] of order.entries()) {
    const lineageNodes = (grouped.get(lineage) ?? []).sort((a, b) => a.version - b.version);
    lineageNodes.forEach((node, col) => {
      positions.set(node.id, { x: 100 + col * 190, y: 80 + row * 110 });
    });
  }
  return positions;
}
