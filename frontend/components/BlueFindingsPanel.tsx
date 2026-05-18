import type { BlueFinding } from "../lib/types";

export function BlueFindingsPanel({ findings }: { findings: BlueFinding[] }) {
  return (
    <section className="mirror-panel border-blue-500/20">
      <div className="flex items-center justify-between border-b border-blue-400/10 p-4">
        <h2 className="font-mono text-lg font-semibold text-slate-100 drop-shadow-[0_0_14px_rgba(96,165,250,0.2)]">Blue Team</h2>
        <span className="border border-blue-400/20 bg-blue-500/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-blue-200">calibration attack</span>
      </div>
      {findings.length === 0 ? (
        <div className="p-4 text-sm text-slate-500">
          <p className="text-slate-300">No exploitable calibration gap confirmed yet.</p>
          <p className="mt-2">Blue scans resolved Red forecasts, finds overconfidence regimes, and hands serious failures to the patcher.</p>
        </div>
      ) : null}
      <div className="space-y-3 p-4">
        {findings.map((finding) => (
          <article key={finding.id} className="border border-blue-500/20 bg-blue-950/15 p-4 shadow-[inset_0_0_24px_rgba(30,64,175,0.12)]">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">n={finding.sample_size}</span>
              <span className="border border-blue-400/20 bg-blue-500/10 px-2 py-1 text-xs text-blue-200">{finding.status}</span>
            </div>
            <p className="mt-2 text-slate-200">{finding.suggested_failure_mode}</p>
            <p className="mt-2 text-xs text-blue-200/80">{finding.suggested_fix_direction}</p>
            <div className="mt-3 grid gap-2 text-xs text-slate-400 sm:grid-cols-3">
              <span>Brier gap {number(finding.brier_gap, 3)}</span>
              <span>Pred {number(finding.predicted_confidence_avg, 2)}</span>
              <span>Actual {number(finding.realized_accuracy, 2)}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function number(value: number | null | undefined, digits: number) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "n/a";
}
