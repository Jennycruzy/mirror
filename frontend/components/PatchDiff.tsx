import type { PatchRecord } from "../lib/types";

export function PatchDiff({ patch }: { patch?: PatchRecord }) {
  if (!patch) {
    return <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 text-slate-400">Patch not found.</div>;
  }
  return (
    <section className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Patch Diff</h2>
        <span className="rounded-full bg-slate-800 px-3 py-1 text-xs">{patch.status}</span>
      </div>
      <pre className="overflow-auto rounded-xl bg-slate-950 p-4 text-sm text-slate-300">{JSON.stringify(patch.proposed_patch_json, null, 2)}</pre>
      <div className="grid gap-3 text-sm md:grid-cols-2">
        <Metric label="Pre Brier" value={patch.holdout_pre_brier} />
        <Metric label="Post Brier" value={patch.holdout_post_brier} />
        <Metric label="Brier Improvement" value={patch.brier_improvement_pct} suffix="%" />
        <Metric label="Trade Preservation" value={patch.trade_rate_preservation_pct} suffix="%" />
      </div>
      {patch.rejection_reason ? <p className="rounded-xl border border-rose-500/40 bg-rose-950/30 p-3 text-rose-200">{patch.rejection_reason}</p> : null}
      {patch.applied_agent_id ? <p className="text-teal-300">Applied agent: {patch.applied_agent_id}</p> : null}
    </section>
  );
}

function Metric({ label, value, suffix = "" }: { label: string; value?: number | null; suffix?: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
      <p className="text-slate-500">{label}</p>
      <p className="mt-1 text-lg text-slate-100">{value === null || value === undefined ? "n/a" : `${value.toFixed(3)}${suffix}`}</p>
    </div>
  );
}
