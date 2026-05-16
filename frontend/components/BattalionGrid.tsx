import type { Agent } from "../lib/types";

const styles: Record<string, { border: string; glow: string; text: string; chip: string }> = {
  "red-a": { border: "border-amber-400/70", glow: "from-amber-500/20", text: "text-amber-300", chip: "bg-amber-500/10 text-amber-200" },
  "red-b": { border: "border-teal-300/70", glow: "from-teal-400/20", text: "text-teal-200", chip: "bg-teal-400/10 text-teal-100" },
  "red-c": { border: "border-violet-300/70", glow: "from-violet-400/20", text: "text-violet-200", chip: "bg-violet-400/10 text-violet-100" },
  "red-d": { border: "border-rose-300/70", glow: "from-rose-400/20", text: "text-rose-200", chip: "bg-rose-400/10 text-rose-100" }
};

export function BattalionGrid({ agents }: { agents: Agent[] }) {
  if (agents.length === 0) {
    return <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-8 text-slate-400">No Red agents found in Postgres.</div>;
  }
  return (
    <section className="grid gap-5 xl:grid-cols-2">
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
    <article className={`relative overflow-hidden rounded-[2rem] border ${theme.border} bg-slate-950/75 p-6 shadow-2xl backdrop-blur`}>
      <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${theme.glow} via-transparent to-transparent`} />
      <div className="relative">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className={`text-xs uppercase tracking-[0.42em] ${theme.text}`}>{agent.lineage}</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-50">Version {agent.version}</h2>
            <p className="mt-1 text-sm text-slate-500">{agent.name}</p>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs ${theme.chip}`}>{agent.status}</span>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          <Metric label="24h Brier" value={formatNumber(agent.rolling_24h_brier, 4)} />
          <Metric label="Open Positions" value={`${agent.open_positions ?? 0}`} />
          <Metric label="PnL" value={agent.unrealized_pnl_usd === null || agent.unrealized_pnl_usd === undefined ? "n/a" : `$${agent.unrealized_pnl_usd.toFixed(2)}`} />
        </div>

        <div className="mt-5 rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
          <div className="flex items-center justify-between gap-4">
            <p className="text-sm text-slate-500">Latest forecast</p>
            {latest ? <span className="rounded-full bg-slate-800 px-2 py-1 text-xs text-slate-300">{latest.status}</span> : null}
          </div>
          {latest ? (
            <div className="mt-3 grid gap-2 text-sm text-slate-300 sm:grid-cols-4">
              <span>{latest.ticker}</span>
              <span className="capitalize">{latest.predicted_direction}</span>
              <span>{Math.round(latest.confidence * 100)}% confidence</span>
              <span>{latest.will_trade ? "trade" : "abstain"}</span>
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-500">No forecasts emitted yet.</p>
          )}
        </div>

        <div className="mt-5">
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-500">Trade floor</span>
            <span className="text-slate-300">
              {tradesToday}/{floor}
            </span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800">
            <div className={`h-full rounded-full ${floorPct >= 80 ? "bg-teal-300" : "bg-amber-300"}`} style={{ width: `${floorPct}%` }} />
          </div>
        </div>

        <div className="mt-5 text-sm">
          {agent.basescan_url ? (
            <a className="text-slate-300 underline decoration-slate-600 underline-offset-4 hover:text-white" href={agent.basescan_url} target="_blank" rel="noreferrer">
              ERC-8004 token #{agent.on_chain_token_id}
            </a>
          ) : (
            <span className="text-slate-500">ERC-8004 token: queued/not registered</span>
          )}
        </div>
      </div>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-3">
      <p className="text-[11px] uppercase tracking-[0.2em] text-slate-600">{label}</p>
      <p className="mt-2 text-lg font-semibold text-slate-100">{value}</p>
    </div>
  );
}

function formatNumber(value: number | null | undefined, digits: number) {
  return value === null || value === undefined ? "n/a" : value.toFixed(digits);
}
