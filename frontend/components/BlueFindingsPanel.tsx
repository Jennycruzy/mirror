import type { BlueFinding } from "../lib/types";

export function BlueFindingsPanel({ findings }: { findings: BlueFinding[] }) {
  return (
    <section className="border border-slate-800 bg-slate-950">
      <div className="flex items-center justify-between border-b border-slate-800 p-4">
        <h2 className="font-mono text-lg font-semibold text-slate-100">Blue Team</h2>
        <span className="bg-blue-500/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-blue-200">calibration attack</span>
      </div>
      {findings.length === 0 ? (
        <div className="p-4 text-sm text-slate-500">
          <p className="text-slate-300">No exploitable calibration gap confirmed yet.</p>
          <p className="mt-2">Blue scans resolved Red forecasts, finds overconfidence regimes, and hands serious failures to the patcher.</p>
        </div>
      ) : null}
      <div className="space-y-3 p-4">
        {findings.map((finding) => (
          <article key={finding.id} className="border border-slate-800 bg-slate-900/60 p-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">n={finding.sample_size}</span>
              <span className="bg-blue-500/10 px-2 py-1 text-xs text-blue-200">{finding.status}</span>
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
