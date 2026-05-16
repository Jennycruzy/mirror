import { BrierTimeline } from "../../../components/BrierTimeline";
import { CalibrationCurve } from "../../../components/CalibrationCurve";
import { LangGraphView } from "../../../components/LangGraphView";

export default function AgentPage({ params }: { params: { id: string } }) {
  return (
    <main className="min-h-screen space-y-6 p-8">
      <h1 className="text-3xl font-semibold">Agent Detail</h1>
      <CalibrationCurve agentId={params.id} />
      <BrierTimeline agentId={params.id} />
      <LangGraphView />
    </main>
  );
}
