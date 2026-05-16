import type { Agent } from "../lib/types";

const colors: Record<string, string> = {
  "red-a": "border-amber-500/70",
  "red-b": "border-teal-400/70",
  "red-c": "border-violet-400/70",
  "red-d": "border-rose-400/70"
};

export function BattalionGrid({ agents }: { agents: Agent[] }) {
  if (agents.length === 0) {
    return <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-8 text-slate-400">No Red agents found in Postgres.</div>;
  }
  return (
    <div className="grid gap-5 md:grid-cols-2">
      {agents.map((agent) => (
        <article key={agent.id} className={`rounded-3xl border ${colors[agent.lineage] ?? "border-slate-700"} bg-slate-900/80 p-6 shadow-2xl`}>
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold tracking-tight">{agent.lineage.toUpperCase()}</h2>
            <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300">{agent.status}</span>
          </div>
          <p className="mt-3 text-slate-300">Version {agent.version}</p>
          <p className="mt-2 text-sm text-slate-500">ERC-8004 token: {agent.on_chain_token_id ?? "not registered"}</p>
        </article>
      ))}
    </div>
  );
}

