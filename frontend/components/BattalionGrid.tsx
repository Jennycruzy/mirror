import Link from "next/link";
import type { Agent } from "../lib/types";

const styles: Record<string, { border: string; text: string; chip: string }> = {
  "red-a": { border: "border-amber-500/60", text: "text-amber-300", chip: "bg-amber-500/10 text-amber-200" },
  "red-b": { border: "border-teal-400/60", text: "text-teal-300", chip: "bg-teal-400/10 text-teal-100" },
  "red-c": { border: "border-violet-400/60", text: "text-violet-300", chip: "bg-violet-400/10 text-violet-100" },
  "red-d": { border: "border-rose-400/60", text: "text-rose-300", chip: "bg-rose-400/10 text-rose-100" }
};

export function BattalionGrid({ agents }: { agents: Agent[] }) {
  if (agents.length === 0) {
    return <div className="border border-slate-800 bg-slate-950 p-6 text-slate-400">No Red agents found in Postgres.</div>;
  }
  return (
    <section className="grid gap-3 xl:grid-cols-2">
      {agents.map((agent) => (
        <AgentCard key={agent.id} agent={agent} />
      ))}
    </section>
  );
}

function AgentCard({ agent }: { agent: Agent }) {
  const theme = styles[agent.lineage] ?? styles["red-a"];
  const floor = agent.trade_floor ?? 8;
  const tradesToday = agent.trades_today ?? 0;
  const floorPct = Math.min(100, Math.round((tradesToday / Math.max(1, floor)) * 100));
  const latest = agent.latest_forecast;

  return (
    <article className={`border ${theme.border} bg-slate-950/95 shadow-[0_0_26px_rgba(15,23,42,0.55)] transition-colors hover:bg-slate-900/80`}>
      <div className="relative">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 p-4">
          <div>
            <p className={`text-xs uppercase tracking-[0.35em] ${theme.text}`}>{agent.lineage}</p>
            <h2 className="mt-2 font-mono text-xl font-semibold tracking-tight text-slate-50 drop-shadow-[0_0_12px_rgba(248,250,252,0.18)]">MIRROR v{agent.version}</h2>
            <p className="mt-1 text-xs text-slate-500">{agent.name}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`border px-2 py-1 text-xs uppercase tracking-[0.16em] ${theme.chip} ${theme.border}`}>{agent.status}</span>
            <Link className="border border-cyan-400/20 bg-cyan-400/10 px-2 py-1 text-xs uppercase tracking-[0.16em] text-cyan-200 hover:bg-cyan-400/20" href={`/agents/${agent.id}`}>
              Open
            </Link>
          </div>
        </div>

        <div className="grid gap-px bg-slate-800 sm:grid-cols-3">
          <Metric label="24h Brier" value={formatNumber(agent.rolling_24h_brier, 4)} />
          <Metric label="Exposure" value={`${agent.open_positions ?? 0}`} />
          <Metric label="PnL" value={agent.unrealized_pnl_usd === null || agent.unrealized_pnl_usd === undefined ? "n/a" : `$${agent.unrealized_pnl_usd.toFixed(2)}`} />
        </div>

        <div className="border-t border-slate-800 p-4">
          <div className="flex items-center justify-between gap-4">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Signal</p>
            {latest ? <span className="border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-300">{latest.status}</span> : null}
          </div>
          {latest ? (
            <div className="mt-3 grid gap-2 font-mono text-sm text-slate-300 sm:grid-cols-4">
              <span className="text-slate-100">{latest.ticker}</span>
              <span className={latest.predicted_direction === "long" ? "text-teal-300" : latest.predicted_direction === "short" ? "text-rose-300" : "text-slate-400"}>{String(latest.predicted_direction ?? "flat").toUpperCase()}</span>
              <span>{Math.round(latest.confidence * 100)}% confidence</span>
              <span className={latest.will_trade ? "text-amber-200" : "text-slate-500"}>{latest.will_trade ? "EXECUTE" : "HOLD"}</span>
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-500">No forecasts emitted yet.</p>
          )}
        </div>

        <div className="border-t border-slate-800 p-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-500">Session orders</span>
            <span className="text-slate-300">
              {tradesToday}/{floor}
            </span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden bg-slate-900">
            <div className={`h-full shadow-[0_0_14px_currentColor] ${floorPct >= 80 ? "bg-teal-300 text-teal-300" : "bg-amber-300 text-amber-300"}`} style={{ width: `${floorPct}%` }} />
          </div>
        </div>

        <div className="border-t border-slate-800 p-4 text-sm">
          {agent.basescan_url ? (
            <a className="text-slate-300 underline decoration-slate-600 underline-offset-4 hover:text-white" href={agent.basescan_url} target="_blank" rel="noreferrer">
              ERC-8004 token #{agent.on_chain_token_id}
            </a>
          ) : (
            <span className="text-slate-500">Identity: queued/not registered</span>
          )}
        </div>
      </div>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-slate-950/95 p-3">
      <p className="text-[11px] uppercase tracking-[0.2em] text-cyan-200/40">{label}</p>
      <p className="mt-2 font-mono text-lg font-semibold text-slate-100">{value}</p>
    </div>
  );
}

function formatNumber(value: number | null | undefined, digits: number) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "n/a";
}
