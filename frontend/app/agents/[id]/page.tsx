import { BrierTimeline } from "../../../components/BrierTimeline";
import { CalibrationCurve } from "../../../components/CalibrationCurve";
import { LangGraphView } from "../../../components/LangGraphView";
import { PositionTable } from "../../../components/PositionTable";

export default function AgentPage({ params }: { params: { id: string } }) {
  return (
    <main className="min-h-screen bg-slate-950 px-5 py-8 lg:px-10">
      <header className="mb-8">
        <p className="text-xs uppercase tracking-[0.5em] text-amber-300">Agent Version</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-50">Calibration dossier</h1>
        <p className="mt-2 max-w-2xl text-slate-400">Agent ID: {params.id}</p>
      </header>
      <div className="grid gap-6 xl:grid-cols-2">
        <CalibrationCurve agentId={params.id} />
        <BrierTimeline agentId={params.id} />
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <LangGraphView />
        <PositionTable />
      </div>
    </main>
  );
}
