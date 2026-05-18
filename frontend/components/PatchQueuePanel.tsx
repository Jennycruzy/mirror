import type { PatchRecord } from "../lib/types";

export function PatchQueuePanel({ patches }: { patches: PatchRecord[] }) {
  const recent = patches.slice(0, 5);
  return (
    <section className="border border-violet-500/20 bg-slate-950/95">
      <div className="flex items-center justify-between border-b border-slate-800 p-4">
        <h2 className="font-mono text-lg font-semibold text-slate-100">Strategy Patches</h2>
        <span className="bg-violet-500/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-violet-200">holdout gate</span>
      </div>
      {recent.length === 0 ? (
        <div className="p-4 text-sm text-slate-500">
          <p className="text-slate-300">No patch proposals stored yet.</p>
          <p className="mt-2">A patch appears here after Blue finds a real calibration weakness and Gemini proposes a strategy change.</p>
        </div>
      ) : null}
      <div className="divide-y divide-slate-900">
        {recent.map((patch) => (
          <article key={patch.id} className="p-4 text-sm hover:bg-slate-900/60">
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-slate-200">{patch.patch_type.toUpperCase()}</span>
              <span className={statusClass(patch.status)}>{patch.status}</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500">
              <span>Pre Brier {number(patch.holdout_pre_brier)}</span>
              <span>Post Brier {number(patch.holdout_post_brier)}</span>
              <span>Trade Preserve {number(patch.trade_rate_preservation_pct)}%</span>
              <span>{patch.gate_passed ? "Gate passed" : "Gate not passed"}</span>
            </div>
            {patch.rejection_reason ? <p className="mt-2 text-xs text-rose-300">{patch.rejection_reason}</p> : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function statusClass(status: string) {
  if (status === "accepted") return "bg-teal-500/10 px-2 py-1 text-xs text-teal-200";
  if (status === "rejected") return "bg-rose-500/10 px-2 py-1 text-xs text-rose-200";
  return "bg-amber-500/10 px-2 py-1 text-xs text-amber-200";
}

function number(value: number | null | undefined) {
  return value === null || value === undefined ? "n/a" : value.toFixed(3);
}
