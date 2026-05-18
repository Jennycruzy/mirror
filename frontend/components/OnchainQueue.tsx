import type { OnchainJob } from "../lib/types";

export function OnchainQueue({ jobs }: { jobs: OnchainJob[] }) {
  return (
    <section className="border border-amber-500/20 bg-slate-950/95">
      <div className="flex items-center justify-between border-b border-slate-800 p-4">
        <h2 className="font-mono text-lg font-semibold text-slate-100">Patch & Identity Queue</h2>
        <span className="bg-slate-900 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-500">ERC-8004</span>
      </div>
      {jobs.length === 0 ? (
        <div className="p-4 text-sm text-slate-500">
          <p className="text-slate-300">No promoted strategy versions queued.</p>
          <p className="mt-2">Accepted patches mint new agent identities and post calibration reputation when on-chain mode is enabled.</p>
        </div>
      ) : null}
      <div className="space-y-3 p-4">
        {jobs.map((job) => (
          <article key={job.id} className="border border-amber-500/10 bg-slate-900/70 p-4 text-sm">
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
  if (status === "confirmed") return "bg-teal-500/10 px-2 py-1 text-xs text-teal-200";
  if (status === "failed") return "bg-rose-500/10 px-2 py-1 text-xs text-rose-200";
  return "bg-amber-500/10 px-2 py-1 text-xs text-amber-200";
}
