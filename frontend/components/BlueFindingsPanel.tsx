import type { BlueFinding } from "../lib/types";

export function BlueFindingsPanel({ findings }: { findings: BlueFinding[] }) {
  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-2xl backdrop-blur">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-100">Blue Findings</h2>
        <span className="rounded-full bg-slate-900 px-3 py-1 text-xs text-slate-500">miscalibration</span>
      </div>
      {findings.length === 0 ? <p className="mt-4 text-slate-500">No Blue findings stored yet.</p> : null}
      <div className="mt-4 space-y-3">
        {findings.map((finding) => (
          <article key={finding.id} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">n={finding.sample_size}</span>
              <span className="rounded-full bg-blue-500/10 px-2 py-1 text-xs text-blue-200">{finding.status}</span>
            </div>
            <p className="mt-2 text-slate-200">{finding.suggested_failure_mode}</p>
            <div className="mt-3 grid gap-2 text-xs text-slate-400 sm:grid-cols-3">
              <span>Brier gap {finding.brier_gap.toFixed(3)}</span>
              <span>Pred {finding.predicted_confidence_avg.toFixed(2)}</span>
              <span>Actual {finding.realized_accuracy.toFixed(2)}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
