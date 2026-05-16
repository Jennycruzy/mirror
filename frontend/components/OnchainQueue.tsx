import type { OnchainJob } from "../lib/types";

export function OnchainQueue({ jobs }: { jobs: OnchainJob[] }) {
  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-2xl backdrop-blur">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-100">On-Chain Queue</h2>
        <span className="rounded-full bg-slate-900 px-3 py-1 text-xs text-slate-500">Base Sepolia</span>
      </div>
      {jobs.length === 0 ? <p className="mt-4 text-slate-500">No on-chain jobs queued.</p> : null}
      <div className="mt-4 space-y-3">
        {jobs.map((job) => (
          <article key={job.id} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-sm">
            <div className="flex items-center justify-between">
              <span>{job.job_type}</span>
              <span className={statusClass(job.status)}>{job.status}</span>
            </div>
            {job.last_error ? <p className="mt-2 text-rose-300">{job.last_error}</p> : null}
            {job.tx_hash ? <p className="mt-2 text-slate-400">{job.tx_hash}</p> : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function statusClass(status: string) {
  if (status === "confirmed") return "rounded-full bg-teal-500/10 px-2 py-1 text-xs text-teal-200";
  if (status === "failed") return "rounded-full bg-rose-500/10 px-2 py-1 text-xs text-rose-200";
  return "rounded-full bg-amber-500/10 px-2 py-1 text-xs text-amber-200";
}
