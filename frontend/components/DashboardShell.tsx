"use client";

import { useCallback, useEffect, useState } from "react";
import { ActivityFeed } from "./ActivityFeed";
import { BattalionGrid } from "./BattalionGrid";
import { BlueFindingsPanel } from "./BlueFindingsPanel";
import { OnchainQueue } from "./OnchainQueue";
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
};

export function DashboardShell({ initialData, initialError }: { initialData: DashboardData; initialError: string | null }) {
  const [data, setData] = useState(initialData);
  const [events, setEvents] = useState<MirrorEvent[]>([]);
  const [error, setError] = useState(initialError);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [agents, forecasts, blueFindings, onchainJobs, patches, trades, paperStatus] = await Promise.all([
        fetchJson<Agent[]>("/agents"),
        fetchJson<Forecast[]>("/forecasts"),
        fetchJson<BlueFinding[]>("/blue-findings"),
        fetchJson<OnchainJob[]>("/onchain-jobs"),
        fetchJson<PatchRecord[]>("/patches"),
        fetchJson<Trade[]>("/trades"),
        fetchJson<PaperStatus>("/trades/paper-status")
      ]);
      setData({ agents, forecasts, blueFindings, onchainJobs, patches, trades, paperStatus });
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
      setEvents((current) => [parsed, ...current].slice(0, 40));
      if (parsed.kind !== "heartbeat") void refresh();
    };
    source.addEventListener("heartbeat", (event) => {
      setEvents((current) => [safeEvent((event as MessageEvent).data), ...current].slice(0, 40));
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
  const paperPnl = data.paperStatus?.status?.pnl;
  const paperEquity = data.paperStatus?.status?.equity;

  return (
    <main className="relative min-h-screen overflow-hidden px-5 py-6 lg:px-10">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_18%_12%,rgba(245,158,11,0.18),transparent_28%),radial-gradient(circle_at_80%_4%,rgba(45,212,191,0.14),transparent_24%),linear-gradient(135deg,rgba(15,23,42,0.95),rgba(2,6,23,1))]" />
      <header className="mb-8 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.62em] text-amber-300">MIRROR</p>
          <h1 className="mt-4 max-w-5xl text-5xl font-semibold tracking-[-0.05em] text-slate-50 md:text-7xl">Calibration warfare for autonomous markets.</h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-400">Red trades, Blue attacks confidence, Gemini patches, holdout gates decide survival. Every number here comes from the backend.</p>
        </div>
        <div className="rounded-3xl border border-slate-700/70 bg-slate-950/70 p-4 text-sm text-slate-400 shadow-2xl backdrop-blur">
          <p className="text-slate-500">System Link</p>
          <p className="mt-1 text-slate-100">{error ? "degraded" : "connected"}</p>
          <p className="mt-1 text-xs">{lastUpdated ? `updated ${lastUpdated}` : "waiting for SSE"}</p>
        </div>
      </header>

      {error ? <div className="mb-6 rounded-3xl border border-rose-400/50 bg-rose-950/40 p-4 text-rose-100 shadow-xl">{error}</div> : null}

      <section className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <Stat label="Forecasts" value={data.forecasts.length} note="total returned" />
        <Stat label="Paper PnL" value={money(paperPnl)} note="realized + unrealized" tone={(paperPnl ?? 0) >= 0 ? "good" : "bad"} />
        <Stat label="Equity" value={money(paperEquity)} note="Kraken paper" />
        <Stat label="Trades Today" value={totalTrades} note="paper only" />
        <Stat label="Patches Passed" value={patchesPassed} note="holdout gate" />
        <Stat label="Patches Rejected" value={patchesRejected} note="with reasons" />
        <Stat label="Crossovers" value={crossovers} note="horizontal lineage" />
      </section>

      <BattalionGrid agents={data.agents} />

      <div className="mt-6">
        <PositionTable paperStatus={data.paperStatus} trades={data.trades} />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <BlueFindingsPanel findings={data.blueFindings} />
        <OnchainQueue jobs={data.onchainJobs} />
      </div>

      <div className="mt-6">
        <ActivityFeed events={events} />
      </div>
    </main>
  );
}

function Stat({ label, value, note, tone }: { label: string; value: string | number; note: string; tone?: "good" | "bad" }) {
  const valueClass = tone === "good" ? "text-teal-300" : tone === "bad" ? "text-rose-300" : "text-slate-50";
  return (
    <div className="group rounded-3xl border border-slate-800/90 bg-slate-950/60 p-5 shadow-xl backdrop-blur transition duration-300 hover:-translate-y-1 hover:border-amber-300/50">
      <p className="text-xs uppercase tracking-[0.25em] text-slate-500">{label}</p>
      <p className={`mt-3 text-3xl font-semibold tracking-tight ${valueClass}`}>{value}</p>
      <p className="mt-2 text-xs text-slate-500">{note}</p>
    </div>
  );
}

function money(value: number | null | undefined) {
  return value === null || value === undefined ? "n/a" : `$${value.toFixed(2)}`;
}

function safeEvent(data: string): MirrorEvent {
  try {
    return JSON.parse(data) as MirrorEvent;
  } catch {
    return { kind: data };
  }
}
