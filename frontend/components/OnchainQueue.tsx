import type { OnchainJob } from "../lib/types";

export function OnchainQueue({ jobs }: { jobs: OnchainJob[] }) {
  return (
    <section className="mirror-panel border-amber-500/20">
      <div className="flex items-center justify-between border-b border-amber-400/10 p-4">
        <h2 className="font-mono text-lg font-semibold text-slate-100 drop-shadow-[0_0_14px_rgba(251,191,36,0.2)]">Patch & Identity Queue</h2>
        <span className="border border-amber-400/20 bg-amber-500/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-amber-200">ERC-8004</span>
      </div>
      {jobs.length === 0 ? (
        <div className="p-4 text-sm text-slate-500">
          <p className="text-slate-300">No promoted strategy versions queued.</p>
          <p className="mt-2">Accepted patches mint new agent identities and post calibration reputation when on-chain mode is enabled.</p>
        </div>
      ) : null}
      <div className="space-y-3 p-4">
        {jobs.map((job) => (
          <article key={job.id} className="border border-amber-500/20 bg-amber-950/10 p-4 text-sm shadow-[inset_0_0_24px_rgba(146,64,14,0.1)]">
            <div className="flex items-center justify-between">
              <span>{job.job_type}</span>
              <span className={statusClass(job.status)}>{job.status}</span>
            </div>
            {job.last_error && job.status !== "confirmed" ? <p className="mt-2 text-rose-300">{job.last_error}</p> : null}
            {job.tx_hash ? <p className="mt-2 text-slate-400">{job.tx_hash}</p> : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function statusClass(status: string) {
  if (status === "confirmed") return "border border-teal-400/20 bg-teal-500/10 px-2 py-1 text-xs text-teal-200";
  if (status === "failed") return "border border-rose-400/20 bg-rose-500/10 px-2 py-1 text-xs text-rose-200";
  return "border border-amber-400/20 bg-amber-500/10 px-2 py-1 text-xs text-amber-200";
}
