"use client";

import { useMemo, useState } from "react";
import type { MirrorEvent } from "../lib/types";

export function ActivityFeed({ events }: { events: MirrorEvent[] }) {
  const [severityFilter, setSeverityFilter] = useState<"all" | "info" | "warning" | "error">("all");
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const visibleEvents = useMemo(
    () => events.filter((event) => event.kind !== "heartbeat").filter((event) => severityFilter === "all" || (event.severity ?? "info") === severityFilter),
    [events, severityFilter]
  );
  return (
    <section className="mirror-panel">
      <div className="flex items-center justify-between border-b border-cyan-400/10 p-4">
        <h2 className="font-mono text-lg font-semibold text-slate-100 drop-shadow-[0_0_14px_rgba(34,211,238,0.2)]">Event Tape</h2>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 animate-pulse rounded-full bg-cyan-300 shadow-[0_0_16px_rgba(103,232,249,0.8)]" />
          <span className="border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-cyan-200">stream</span>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 border-b border-cyan-400/10 p-3">
        {(["all", "info", "warning", "error"] as const).map((value) => (
          <button key={value} className={filterButtonClass(severityFilter === value)} type="button" onClick={() => setSeverityFilter(value)}>
            {value}
          </button>
        ))}
      </div>
      <div className="max-h-96 overflow-auto text-sm">
        {visibleEvents.length === 0 ? <p className="p-4 text-slate-500">Awaiting execution, forecast, and calibration events.</p> : null}
        {visibleEvents.map((event, index) => {
          const key = `${event.id ?? event.kind}-${index}`;
          const expanded = expandedKey === key;
          return (
          <article key={key} className={`cursor-pointer border-b border-slate-900 p-3 hover:bg-cyan-950/20 ${expanded ? "bg-cyan-950/20" : ""}`} onClick={() => setExpandedKey(expanded ? null : key)}>
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-slate-200">{labelFor(event.kind)}</span>
              <span className={severityClass(event.severity)}>{event.severity ?? "info"}</span>
            </div>
            {event.payload ? <p className="mt-2 line-clamp-2 text-xs text-slate-500">{summaryFor(event)}</p> : null}
            {event.created_at ? <p className="mt-1 text-xs text-slate-500">{new Date(event.created_at).toLocaleString()}</p> : null}
            {expanded ? (
              <pre className="mt-3 max-h-48 overflow-auto border border-slate-800 bg-slate-950 p-3 text-xs text-cyan-100/80">
                {JSON.stringify(event.payload ?? event, null, 2)}
              </pre>
            ) : null}
          </article>
        );
        })}
      </div>
    </section>
  );
}

function severityClass(severity?: string) {
  if (severity === "error") return "border border-rose-400/20 bg-rose-500/10 px-2 py-1 text-xs text-rose-200";
  if (severity === "warning") return "border border-amber-400/20 bg-amber-500/10 px-2 py-1 text-xs text-amber-200";
  return "border border-teal-400/20 bg-teal-500/10 px-2 py-1 text-xs text-teal-200";
}

function labelFor(kind: string) {
  return String(kind ?? "event").replaceAll("_", " ").toUpperCase();
}

function filterButtonClass(active: boolean) {
  return active
    ? "border border-cyan-300/40 bg-cyan-400/15 px-3 py-1 text-xs uppercase tracking-[0.16em] text-cyan-100"
    : "border border-slate-800 bg-slate-950 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-500 hover:border-cyan-400/20 hover:text-slate-200";
}

function summaryFor(event: MirrorEvent) {
  const payload = event.payload ?? {};
  if (typeof payload.reason === "string") return payload.reason;
  if (typeof payload.ticker === "string") return payload.ticker;
  if (typeof payload.forecast_id === "string") return `forecast ${payload.forecast_id.slice(0, 8)}`;
  return Object.entries(payload)
    .slice(0, 2)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(" / ");
}
