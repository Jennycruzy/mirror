import { ActivityFeed } from "../components/ActivityFeed";
import { BattalionGrid } from "../components/BattalionGrid";
import { BlueFindingsPanel } from "../components/BlueFindingsPanel";
import { OnchainQueue } from "../components/OnchainQueue";
import { fetchJson } from "../lib/api";
import type { Agent, BlueFinding, Forecast, OnchainJob } from "../lib/types";

export default async function HomePage() {
  let agents: Agent[] = [];
  let forecasts: Forecast[] = [];
  let blueFindings: BlueFinding[] = [];
  let onchainJobs: OnchainJob[] = [];
  let error: string | null = null;
  try {
    [agents, forecasts, blueFindings, onchainJobs] = await Promise.all([
      fetchJson<Agent[]>("/agents"),
      fetchJson<Forecast[]>("/forecasts"),
      fetchJson<BlueFinding[]>("/blue-findings"),
      fetchJson<OnchainJob[]>("/onchain-jobs")
    ]);
  } catch (err) {
    error = err instanceof Error ? err.message : "Backend unavailable";
  }

  return (
    <main className="min-h-screen px-6 py-8 lg:px-12">
      <div className="mb-10 max-w-5xl">
        <p className="text-sm uppercase tracking-[0.5em] text-amber-400">MIRROR</p>
        <h1 className="mt-4 text-5xl font-semibold tracking-tight text-slate-100">Calibration is the fitness function.</h1>
        <p className="mt-4 max-w-2xl text-slate-400">Real backend state only. Missing integrations and failed calls are displayed instead of masked.</p>
      </div>
      {error ? <div className="mb-6 rounded-2xl border border-rose-500/50 bg-rose-950/40 p-4 text-rose-200">{error}</div> : null}
      <section className="mb-6 grid gap-4 md:grid-cols-3">
        <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6">
          <p className="text-slate-500">Total Forecasts</p>
          <p className="mt-2 text-4xl font-semibold">{forecasts.length}</p>
        </div>
        <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6">
          <p className="text-slate-500">Active Reds</p>
          <p className="mt-2 text-4xl font-semibold">{agents.length}</p>
        </div>
        <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6">
          <p className="text-slate-500">Latest Status</p>
          <p className="mt-2 text-lg text-slate-300">{error ? "backend error" : "connected"}</p>
        </div>
      </section>
      <BattalionGrid agents={agents} />
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <BlueFindingsPanel findings={blueFindings} />
        <OnchainQueue jobs={onchainJobs} />
      </div>
      <div className="mt-6">
        <ActivityFeed />
      </div>
    </main>
  );
}
