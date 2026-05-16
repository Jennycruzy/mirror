import { DashboardShell } from "../components/DashboardShell";
import { fetchJson } from "../lib/api";
import type { Agent, BlueFinding, Forecast, OnchainJob, PatchRecord } from "../lib/types";

export default async function HomePage() {
  let agents: Agent[] = [];
  let forecasts: Forecast[] = [];
  let blueFindings: BlueFinding[] = [];
  let onchainJobs: OnchainJob[] = [];
  let patches: PatchRecord[] = [];
  let error: string | null = null;
  try {
    [agents, forecasts, blueFindings, onchainJobs, patches] = await Promise.all([
      fetchJson<Agent[]>("/agents"),
      fetchJson<Forecast[]>("/forecasts"),
      fetchJson<BlueFinding[]>("/blue-findings"),
      fetchJson<OnchainJob[]>("/onchain-jobs"),
      fetchJson<PatchRecord[]>("/patches")
    ]);
  } catch (err) {
    error = err instanceof Error ? err.message : "Backend unavailable";
  }

  return <DashboardShell initialData={{ agents, forecasts, blueFindings, onchainJobs, patches }} initialError={error} />;
}
