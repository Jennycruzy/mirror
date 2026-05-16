import type { BlueFinding } from "../lib/types";

export function BlueFindingsPanel({ findings }: { findings: BlueFinding[] }) {
  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6">
      <h2 className="text-lg font-semibold">Blue Findings</h2>
      {findings.length === 0 ? <p className="mt-4 text-slate-400">No Blue findings stored yet.</p> : null}
      <div className="mt-4 space-y-3">
        {findings.map((finding) => (
          <article key={finding.id} className="rounded-2xl border border-slate-800 bg-slate-950/50 p-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">n={finding.sample_size}</span>
              <span className="rounded-full bg-slate-800 px-2 py-1 text-xs">{finding.status}</span>
            </div>
            <p className="mt-2 text-slate-200">{finding.suggested_failure_mode}</p>
            <p className="mt-2 text-sm text-amber-300">Brier gap: {finding.brier_gap.toFixed(3)}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
