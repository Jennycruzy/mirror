import type { OnchainJob } from "../lib/types";

export function OnchainQueue({ jobs }: { jobs: OnchainJob[] }) {
  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6">
      <h2 className="text-lg font-semibold">On-Chain Queue</h2>
      {jobs.length === 0 ? <p className="mt-4 text-slate-400">No on-chain jobs queued.</p> : null}
      <div className="mt-4 space-y-3">
        {jobs.map((job) => (
          <article key={job.id} className="rounded-2xl border border-slate-800 bg-slate-950/50 p-4 text-sm">
            <div className="flex items-center justify-between">
              <span>{job.job_type}</span>
              <span className="rounded-full bg-slate-800 px-2 py-1 text-xs">{job.status}</span>
            </div>
            {job.last_error ? <p className="mt-2 text-rose-300">{job.last_error}</p> : null}
            {job.tx_hash ? <p className="mt-2 text-slate-400">{job.tx_hash}</p> : null}
          </article>
        ))}
      </div>
    </section>
  );
}
