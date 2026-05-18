import { DashboardShell } from "../components/DashboardShell";
import { fetchJson } from "../lib/api";
import type { Agent, BlueFinding, Forecast, MirrorEvent, OnchainJob, PaperStatus, PatchRecord, Trade } from "../lib/types";

export default async function HomePage() {
  let agents: Agent[] = [];
  let forecasts: Forecast[] = [];
  let blueFindings: BlueFinding[] = [];
  let onchainJobs: OnchainJob[] = [];
  let patches: PatchRecord[] = [];
  let trades: Trade[] = [];
  let paperStatus: PaperStatus | null = null;
  let events: MirrorEvent[] = [];
  let error: string | null = null;
  try {
    [agents, forecasts, blueFindings, onchainJobs, patches, trades, paperStatus, events] = await Promise.all([
      fetchJson<Agent[]>("/agents"),
      fetchJson<Forecast[]>("/forecasts"),
      fetchJson<BlueFinding[]>("/blue-findings"),
      fetchJson<OnchainJob[]>("/onchain-jobs"),
      fetchJson<PatchRecord[]>("/patches"),
      fetchJson<Trade[]>("/trades"),
      fetchJson<PaperStatus>("/trades/paper-status"),
      fetchJson<MirrorEvent[]>("/events?limit=80")
    ]);
  } catch (err) {
    error = err instanceof Error ? err.message : "Backend unavailable";
  }

  return <DashboardShell initialData={{ agents, forecasts, blueFindings, onchainJobs, patches, trades, paperStatus, events }} initialError={error} />;
}
