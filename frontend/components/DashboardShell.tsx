"use client";

import { useCallback, useEffect, useState } from "react";
import { ActivityFeed } from "./ActivityFeed";
import { BattalionGrid } from "./BattalionGrid";
import { BlueFindingsPanel } from "./BlueFindingsPanel";
import { OnchainQueue } from "./OnchainQueue";
import { PatchQueuePanel } from "./PatchQueuePanel";
import { PositionTable } from "./PositionTable";
import { fetchJson } from "../lib/api";
import { openMirrorStream } from "../lib/sse";
import type { Agent, BlueFinding, Forecast, MirrorEvent, OnchainJob, PaperStatus, PatchRecord, Trade } from "../lib/types";

type DashboardData = {
  agents: Agent[];
  forecasts: Forecast[];
  blueFindings: BlueFinding[];
  onchainJobs: OnchainJob[];
  patches: PatchRecord[];
  trades: Trade[];
  paperStatus: PaperStatus | null;
  events: MirrorEvent[];
};

export function DashboardShell({ initialData, initialError }: { initialData: DashboardData; initialError: string | null }) {
  const [data, setData] = useState(initialData);
  const [events, setEvents] = useState<MirrorEvent[]>(initialData.events);
  const [error, setError] = useState(initialError);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [agents, forecasts, blueFindings, onchainJobs, patches, trades, paperStatus, persistedEvents] = await Promise.all([
        fetchJson<Agent[]>("/agents"),
        fetchJson<Forecast[]>("/forecasts"),
        fetchJson<BlueFinding[]>("/blue-findings"),
        fetchJson<OnchainJob[]>("/onchain-jobs"),
        fetchJson<PatchRecord[]>("/patches"),
        fetchJson<Trade[]>("/trades"),
        fetchJson<PaperStatus>("/trades/paper-status"),
        fetchJson<MirrorEvent[]>("/events?limit=80")
      ]);
      setData({ agents, forecasts, blueFindings, onchainJobs, patches, trades, paperStatus, events: persistedEvents });
      setEvents((current) => mergeEvents(current, persistedEvents));
      setLastUpdated(new Date().toLocaleTimeString());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backend unavailable");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const refreshInterval = window.setInterval(() => void refresh(), 15000);
    const source = openMirrorStream();
    source.onmessage = (event) => {
      const parsed = safeEvent(event.data);
      if (parsed.kind !== "heartbeat") setEvents((current) => [parsed, ...current].slice(0, 40));
      if (parsed.kind !== "heartbeat") void refresh();
    };
    source.addEventListener("heartbeat", () => {
      setLastUpdated(new Date().toLocaleTimeString());
    });
    source.onerror = () => {
      setEvents((current) => [{ kind: "sse_connection_error", severity: "error" }, ...current].slice(0, 40));
    };
    return () => {
      window.clearInterval(refreshInterval);
      source.close();
    };
  }, [refresh]);

  const totalTrades = data.agents.reduce((sum, agent) => sum + (agent.trades_today ?? 0), 0);
  const patchesPassed = data.patches.filter((patch) => patch.gate_passed).length;
  const patchesRejected = data.patches.filter((patch) => patch.status === "rejected").length;
  const crossovers = data.patches.filter((patch) => patch.patch_type === "crossover").length;
  const paperPnl = data.paperStatus?.status?.pnl ?? data.paperStatus?.status?.unrealized_pnl;
  const paperEquity = data.paperStatus?.status?.equity ?? data.paperStatus?.status?.current_value;
  const latestTicker = data.forecasts[0]?.ticker ?? "BTC/USD";
  const openForecasts = data.forecasts.filter((forecast) => forecast.status === "open").length;
  const openTrades = data.trades.filter((trade) => trade.status === "open");
  const closedTrades = data.trades.filter((trade) => trade.status === "closed");
  const longCount = openTrades.filter((trade) => trade.side === "buy").length;
  const shortCount = openTrades.filter((trade) => trade.side === "sell").length;
  const resolvedForecasts = data.forecasts.filter((forecast) => forecast.status === "resolved");
  const avgBrier = average(resolvedForecasts.map((forecast) => forecast.brier_score).filter((value): value is number => typeof value === "number"));
  const latestDirection = data.forecasts[0]?.predicted_direction ?? "flat";
  const mode = data.paperStatus?.status?.mode ?? "unknown";

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_15%_0%,rgba(20,184,166,0.22),transparent_27%),radial-gradient(circle_at_80%_0%,rgba(245,158,11,0.14),transparent_28%),linear-gradient(180deg,#020617_0%,#030712_48%,#020617_100%)] px-4 py-4 text-slate-100 lg:px-6">
      <header className="mirror-panel mirror-scanline mb-4">
        <div className="flex flex-col gap-4 border-b border-cyan-400/10 px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-4">
            <div className="leading-none">
              <p className="bg-gradient-to-r from-amber-200 via-cyan-200 to-teal-300 bg-clip-text font-mono text-5xl font-black uppercase tracking-[0.12em] text-transparent drop-shadow-[0_0_20px_rgba(34,211,238,0.35)] md:text-6xl">
                MIRROR
              </p>
              <p className="mt-1 text-[10px] uppercase tracking-[0.48em] text-cyan-300/80">Adaptive AI Trading Terminal</p>
            </div>
            <span className="hidden h-12 w-px bg-cyan-400/20 md:block" />
            <div className="flex flex-wrap items-center gap-2">
              <span className="border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 font-mono text-xs uppercase tracking-[0.2em] text-cyan-100">{latestTicker}</span>
              <span className={latestDirection === "long" ? "border border-teal-400/30 bg-teal-500/15 px-3 py-1 text-xs uppercase tracking-[0.18em] text-teal-200 shadow-[0_0_18px_rgba(45,212,191,0.16)]" : latestDirection === "short" ? "border border-rose-400/30 bg-rose-500/15 px-3 py-1 text-xs uppercase tracking-[0.18em] text-rose-200 shadow-[0_0_18px_rgba(251,113,133,0.16)]" : "border border-slate-700 bg-slate-800 px-3 py-1 text-xs uppercase tracking-[0.18em] text-slate-300"}>
              signal {latestDirection}
            </span>
              <span className="border border-amber-400/20 bg-amber-400/10 px-3 py-1 text-xs uppercase tracking-[0.18em] text-amber-200">PnL objective</span>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.16em]">
            <span className={error ? "text-rose-300" : "text-teal-300"}>{error ? "degraded" : "connected"}</span>
            <span className="text-slate-700">/</span>
            <span className="text-slate-400">{lastUpdated ? `sync ${lastUpdated}` : "awaiting stream"}</span>
          </div>
        </div>
        <div className="grid gap-px bg-cyan-400/10 md:grid-cols-4 xl:grid-cols-7">
          <TerminalStat label="Portfolio" value={money(paperEquity)} />
          <TerminalStat label="Net PnL" value={money(paperPnl)} tone={(paperPnl ?? 0) >= 0 ? "good" : "bad"} />
          <TerminalStat label="Orders" value={totalTrades} />
          <TerminalStat label="Open Signals" value={openForecasts} />
          <TerminalStat label="Forecasts" value={data.forecasts.length} />
          <TerminalStat label="Patches" value={`${patchesPassed}/${patchesRejected}`} />
          <TerminalStat label="Crossovers" value={crossovers} />
        </div>
        <div className="grid gap-px border-t border-cyan-400/10 bg-cyan-400/10 md:grid-cols-2 xl:grid-cols-6">
          <TerminalStat label="Execution Mode" value={String(mode).toUpperCase()} />
          <TerminalStat label="Open Trades" value={openTrades.length} />
          <TerminalStat label="Long / Short" value={`${longCount}/${shortCount}`} />
          <TerminalStat label="Closed Fills" value={closedTrades.length} />
          <TerminalStat label="Avg Brier" value={avgBrier === null ? "n/a" : avgBrier.toFixed(3)} tone={avgBrier !== null && avgBrier < 0.25 ? "good" : undefined} />
          <TerminalStat label="Blue Findings" value={data.blueFindings.length} />
        </div>
      </header>

      {error ? <div className="mb-4 border border-rose-500/50 bg-rose-950/40 p-3 text-sm text-rose-100 shadow-[0_0_30px_rgba(244,63,94,0.12)]">{error}</div> : null}

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-4">
          <PositionTable paperStatus={data.paperStatus} trades={data.trades} />
          <BattalionGrid agents={data.agents} />
        </div>

        <aside className="space-y-4">
          <ActivityFeed events={events} />
          <BlueFindingsPanel findings={data.blueFindings} />
          <PatchQueuePanel patches={data.patches} />
          <OnchainQueue jobs={data.onchainJobs} />
        </aside>
      </section>
    </main>
  );
}

function TerminalStat({ label, value, tone }: { label: string; value: string | number; tone?: "good" | "bad" }) {
  const valueClass =
    tone === "good"
      ? "text-teal-300 drop-shadow-[0_0_12px_rgba(45,212,191,0.35)]"
      : tone === "bad"
        ? "text-rose-300 drop-shadow-[0_0_12px_rgba(251,113,133,0.28)]"
        : "text-slate-50";
  return (
    <div className="bg-slate-950/95 px-4 py-3 transition-colors hover:bg-slate-900/90">
      <p className="text-[10px] uppercase tracking-[0.22em] text-cyan-200/45">{label}</p>
      <p className={`mt-1 font-mono text-xl font-semibold ${valueClass}`}>{value}</p>
    </div>
  );
}

function money(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? `$${value.toFixed(2)}` : "n/a";
}

function average(values: number[]) {
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function safeEvent(data: string): MirrorEvent {
  try {
    return JSON.parse(data) as MirrorEvent;
  } catch {
    return { kind: data };
  }
}

function mergeEvents(current: MirrorEvent[], incoming: MirrorEvent[]) {
  const merged = [...current, ...incoming];
  const seen = new Set<string>();
  return merged
    .filter((event) => {
      const key = event.id ?? `${event.kind}-${event.created_at ?? ""}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((a, b) => Date.parse(b.created_at ?? "0") - Date.parse(a.created_at ?? "0"))
    .slice(0, 80);
}
